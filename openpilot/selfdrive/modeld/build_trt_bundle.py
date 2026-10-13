"""Compile a big-model ONNX into a local TensorRT bundle.

Produces, inside <bundle>:
    big_driving_supercombo_metadata.pkl   input/output shapes + output slices
    driving_supercombo_fp16.plan          fp16 TensorRT engine

Two families are supported, told apart by the graph inputs:

  * stateless fused - img/big_img/desire_pulse/traffic_convention/action_t/
    features_buffer in, one flat `outputs` out. modeld_bigcombo loads these.
  * stateful generic (cinque) - new_img/desire/traffic_convention/action_t plus
    state_* in, `outputs` + next_state_* out. stateful_model_state loads these.

The ONNX is patched before parsing because TensorRT rejects UINT8 graph I/O:
  * fused: image inputs redeclared FP16 with the head Cast removed (jetlink patch);
  * stateful: the uint8 tensors (new_img / state_img_q / next_state_img_q) are
    retyped FP16 (0..255 is exact; the graph's own Casts stay).
The original file is never modified.

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

FUSED_REQUIRED_INPUTS = ("img", "big_img", "desire_pulse", "traffic_convention", "action_t", "features_buffer")
STATEFUL_MARKER_INPUT = "new_img"  # present only in the stateful generic export
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


def _import_onnx():
  """The `onnx` package, from wherever it exists on this box (see _FALLBACK)."""
  candidates = (os.environ.get("OPENPILOT_ONNX_PATH"), *_FALLBACK_ONNX_PATHS, *_SYSTEM_DIST_PACKAGES)
  for path in candidates:
    if path and path not in sys.path and Path(path).is_dir():
      sys.path.append(path)
  import onnx
  return onnx


def patch_onnx_stateful(onnx_path: Path, out_path: Path, *, progress=None) -> int:
  """Retype the model's UINT8 tensors to FP16 so TensorRT accepts the graph.

  The stateful cinque export carries a uint8 image input and a uint8 image state
  (new_img / state_img_q / next_state_img_q); TensorRT rejects uint8 graph I/O.
  0..255 is exact in fp16, so a plain retype suffices - the graph's own Casts
  keep working.
  """
  onnx = _import_onnx()
  from onnx import TensorProto
  model = onnx.load(str(onnx_path), load_external_data=False)
  changed = 0
  for vi in list(model.graph.input) + list(model.graph.output) + list(model.graph.value_info):
    if vi.type.tensor_type.elem_type == TensorProto.UINT8:
      vi.type.tensor_type.elem_type = TensorProto.FLOAT16
      changed += 1
  onnx.save(model, str(out_path))
  if progress:
    progress(f"retyped {changed} uint8 tensors to fp16")
  return changed


def patch_onnx(onnx_path: Path, out_path: Path, *, stateful: bool = False,
               progress=None, force: bool = False) -> Path:
  """Write a TensorRT-parseable copy of an ONNX next to the original.

  Reuses an existing copy that is at least as new as the source: patching a
  ~766 MB file is minutes of I/O, and rerunning the build should not redo it.
  """
  if not force and out_path.is_file() and out_path.stat().st_mtime >= onnx_path.stat().st_mtime:
    if progress:
      progress(f"reusing patched copy: {out_path.name} ({out_path.stat().st_size / 1e6:.1f} MB)")
    return out_path
  if stateful:
    if progress:
      progress(f"patching {onnx_path.name} for TensorRT (stateful: uint8 tensors -> fp16)")
    patch_onnx_stateful(onnx_path, out_path, progress=progress)
  else:
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
  names = set(meta["input_shapes"])
  if not (set(FUSED_REQUIRED_INPUTS) <= names or STATEFUL_MARKER_INPUT in names):
    raise ValueError(
      f"unsupported model inputs {sorted(names)}; expected fused {FUSED_REQUIRED_INPUTS} or a "
      f"stateful export with {STATEFUL_MARKER_INPUT!r}")
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
  # Highest kernel-autotuning level (what `trtexec --best` uses) plus a persistent
  # timing cache: the first build autotunes harder and is slower, but the winning
  # kernels are cached next to the plan and reused on the next build.
  # Kernel-autotuning effort. Measured on cinque-v3 (2026-10-13): level 3 and 4
  # build identical-speed engines (~21 ms) and level 5 OOMs this 29 GB box, so 3
  # stays the default; raise TRT_OPT_LEVEL to experiment.
  try:
    config.builder_optimization_level = int(os.environ.get("TRT_OPT_LEVEL", "3"))
  except Exception:
    pass
  cache_path = plan_path.parent / "timing_cache.bin"
  try:
    cache = config.create_timing_cache(cache_path.read_bytes()) if cache_path.is_file() else None
    if cache is None:
      cache = config.create_timing_cache(b"")
    config.set_timing_cache(cache, ignore_mismatch=False)
  except Exception as e:
    if progress:
      progress(f"timing cache unavailable: {e}")

  t0 = time.monotonic()
  if progress:
    progress(f"building engine (fp16={fp16}); this takes minutes")
  serialized = builder.build_serialized_network(network, config)
  if serialized is None:
    raise RuntimeError("TensorRT build returned no engine")
  data = bytes(serialized)
  plan_path.parent.mkdir(parents=True, exist_ok=True)
  plan_path.write_bytes(data)
  try:
    cache_path.write_bytes(config.get_timing_cache().serialize())
  except Exception:
    pass
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
  stateful = STATEFUL_MARKER_INPUT in pickle.loads(metadata.read_bytes())["input_shapes"]
  if progress:
    progress(f"metadata written: {metadata.name} ({'stateful' if stateful else 'fused'})")

  # The metadata comes from the original file; only the engine build needs the
  # TensorRT-friendly copy.
  patched = patch_onnx(onnx, bundle / PATCHED_ONNX_NAME, stateful=stateful, progress=progress)
  try:
    plan = build_engine(patched, bundle / PLAN_NAME, fp16=fp16, progress=progress)
  finally:
    if not keep_patched:
      patched.unlink(missing_ok=True)
  return {"bundle": str(bundle), "metadata": str(metadata), "plan": str(plan),
          "plan_bytes": plan.stat().st_size, "stateful": stateful}


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
