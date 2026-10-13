"""Compile a stateless fused big-model ONNX into a local TensorRT bundle.

Produces, inside <bundle>:
    big_driving_supercombo_metadata.pkl   input/output shapes + output slices
    driving_supercombo_fp16.plan          fp16 TensorRT engine

That is the layout modeld_bigcombo loads. Only the stateless fused family is
supported - the fused ONNX takes img/big_img/desire_pulse/traffic_convention/
action_t/features_buffer and returns one flat `outputs` tensor. The newer
"stateful generic" exports (state_* in, next_state_* out) are AMD-runtime only
and are rejected by generic_model_runtime on this branch.

The ONNX is patched before parsing (jetlink's onnx_patch): TensorRT rejects the
UINT8 image inputs, so they are redeclared FP16 with the head Cast removed.
Feeding 0..255 as fp16 is exact; the original file is never modified.

TensorRT ships with JetPack in the system dist-packages, which is not on the
venv path, so it is imported explicitly here. onnx is not on the venv path
either and is taken from a child venv or the system when present.
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
import time
from pathlib import Path

# Stateful generic exports are not usable here; see the module docstring.
FUSED_REQUIRED_INPUTS = ("img", "big_img", "desire_pulse", "traffic_convention", "action_t", "features_buffer")
METADATA_NAME = "big_driving_supercombo_metadata.pkl"
PLAN_NAME = "driving_supercombo_fp16.plan"
PATCHED_ONNX_NAME = "big_driving_supercombo.patched.onnx"

_SYSTEM_DIST_PACKAGES = ("/usr/lib/python3.12/dist-packages",)
# onnx is not a runtime dependency of openpilot, so a sibling venv may be the
# only place it exists on this box. Override with OPENPILOT_ONNX_PATH.
_FALLBACK_ONNX_PATHS = ("/home/nvidia/公共/sunnypilot-cuda/.venv/lib/python3.12/site-packages",)
_THIRD_PARTY = Path(__file__).resolve().parents[3] / "third_party"


def _import_tensorrt():
  for path in _SYSTEM_DIST_PACKAGES:
    if path not in sys.path:
      sys.path.insert(0, path)
  import tensorrt as trt
  return trt


def _import_patch_file():
  """jetlink's onnx_patch.patch_file, which needs the `onnx` package."""
  candidates = (os.environ.get("OPENPILOT_ONNX_PATH"), *_FALLBACK_ONNX_PATHS, *_SYSTEM_DIST_PACKAGES)
  for path in candidates:
    if path and path not in sys.path and Path(path).is_dir():
      sys.path.append(path)
  jetlink = _THIRD_PARTY / "jetlink"
  if jetlink.is_dir() and str(jetlink) not in sys.path:
    sys.path.insert(0, str(jetlink))
  from jetlink.onnx_patch import patch_file
  return patch_file


def patch_onnx(onnx_path: Path, out_path: Path, *, progress=None, force: bool = False) -> Path:
  """Write a TensorRT-parseable copy of a fused ONNX next to the original.

  Reuses an existing copy that is at least as new as the source: patching a
  ~766 MB file is minutes of I/O, and rerunning the build should not redo it.
  """
  if not force and out_path.is_file() and out_path.stat().st_mtime >= onnx_path.stat().st_mtime:
    if progress:
      progress(f"reusing patched copy: {out_path.name} ({out_path.stat().st_size / 1e6:.1f} MB)")
    return out_path
  if progress:
    progress(f"patching {onnx_path.name} for TensorRT (uint8 image inputs -> fp16)")
  patch_file = _import_patch_file()
  patch_file(str(onnx_path), str(out_path), check=False)
  if progress:
    progress(f"patched copy: {out_path.name} ({out_path.stat().st_size / 1e6:.1f} MB)")
  return out_path


def write_metadata(onnx_path: Path, bundle: Path) -> Path:
  """Derive <bundle>/big_driving_supercombo_metadata.pkl from the ONNX."""
  from openpilot.selfdrive.modeld.get_model_metadata import make_metadata_dict

  meta = make_metadata_dict(str(onnx_path))
  missing = [k for k in FUSED_REQUIRED_INPUTS if k not in meta["input_shapes"]]
  if missing:
    raise ValueError(f"not a stateless fused model: missing inputs {missing} (got {sorted(meta['input_shapes'])})")
  out = bundle / METADATA_NAME
  out.parent.mkdir(parents=True, exist_ok=True)
  with out.open("wb") as f:
    pickle.dump(meta, f)
  return out


def build_engine(onnx_path: Path, plan_path: Path, *, fp16: bool = True, progress=None) -> Path:
  """Build an fp16 TensorRT engine from a fused ONNX."""
  trt = _import_tensorrt()
  logger = trt.Logger(trt.Logger.WARNING)
  builder = trt.Builder(logger)
  network = builder.create_network(0)
  parser = trt.OnnxParser(network, logger)

  if progress:
    progress(f"parsing {onnx_path.name}")
  if not parser.parse_from_file(str(onnx_path)):
    errors = [str(parser.get_error(i)) for i in range(parser.num_errors)]
    raise RuntimeError(f"ONNX parse failed: {errors}")

  config = builder.create_builder_config()
  if fp16:
    config.set_flag(trt.BuilderFlag.FP16)

  t0 = time.monotonic()
  if progress:
    progress(f"building engine (fp16={fp16}); this takes minutes")
  serialized = builder.build_serialized_network(network, config)
  if serialized is None:
    raise RuntimeError("TensorRT build returned no engine")
  data = bytes(serialized)
  plan_path.parent.mkdir(parents=True, exist_ok=True)
  plan_path.write_bytes(data)
  if progress:
    progress(f"built {plan_path.name}: {len(data) / 1e6:.1f} MB in {time.monotonic() - t0:.0f}s")
  return plan_path


def compile_bundle(bundle_dir: str | Path, onnx_path: str | Path | None = None,
                   *, fp16: bool = True, progress=None, keep_patched: bool = False) -> dict:
  """Metadata + engine for a bundle. onnx_path defaults to <bundle>/big_driving_supercombo.onnx."""
  bundle = Path(bundle_dir)
  onnx = Path(onnx_path) if onnx_path else bundle / "big_driving_supercombo.onnx"
  if not onnx.is_file():
    raise FileNotFoundError(onnx)

  metadata = write_metadata(onnx, bundle)
  if progress:
    progress(f"metadata written: {metadata.name}")

  # The metadata comes from the original file; only the engine build needs the
  # TensorRT-friendly copy.
  patched = patch_onnx(onnx, bundle / PATCHED_ONNX_NAME, progress=progress)
  try:
    plan = build_engine(patched, bundle / PLAN_NAME, fp16=fp16, progress=progress)
  finally:
    if not keep_patched:
      patched.unlink(missing_ok=True)
  return {"bundle": str(bundle), "metadata": str(metadata), "plan": str(plan),
          "plan_bytes": plan.stat().st_size}


def main() -> int:
  parser = argparse.ArgumentParser(description="Compile a fused big-model ONNX into a TRT bundle")
  parser.add_argument("--bundle", required=True, help="bundle directory (created if missing)")
  parser.add_argument("--onnx", default=None, help="ONNX path (default <bundle>/big_driving_supercombo.onnx)")
  parser.add_argument("--fp32", action="store_true", help="build fp32 instead of fp16")
  parser.add_argument("--keep-patched", action="store_true", help="keep the patched ONNX next to the original")
  args = parser.parse_args()

  print(f"[build_trt] bundle={args.bundle}")
  result = compile_bundle(args.bundle, args.onnx, fp16=not args.fp32,
                          keep_patched=args.keep_patched,
                          progress=lambda m: print(f"[build_trt] {m}", flush=True))
  print(f"[build_trt] done: {result['plan']} ({result['plan_bytes'] / 1e6:.1f} MB)")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
