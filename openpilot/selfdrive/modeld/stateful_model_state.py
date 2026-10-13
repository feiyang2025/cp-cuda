"""ModelState-compatible driver for the STATEFUL (cinque-family) big model on the local GPU.

Mirrors precompiled_runner.PrecompiledModelState, but runs the TensorRT engine
in-process (stateful_trt_runner.StatefulTensorRTPolicyRunner) instead of spawning
the AMD tinygrad worker. Same `run(bufs, transforms, inputs, prepare_only)`
contract so modeld can select it interchangeably.

Input mapping (validated 2026-10-13 against live TGC ground truth, see
docs/cinque_stateful_trt_plan.md):
  new_img (2,6,128,256) = [ warp(road).current, warp(wide).current ]
    cuda_transform outputs 2 temporal frames per camera; index 1 is the current
    one (cuda_transform.cu step 7).
  desire (8,), traffic_convention (1,2), action_t (1,2) from the frame inputs.
  state_img_q (2,5,6,128,256) / state_desire_q (132,1,8) / state_feat_q (128,1,16384)
    are rolled every frame from the engine's next_state_* outputs.
  outputs (1,18452) share TGC's layout, so the existing Parser and output_slices
    are reused unchanged.
"""
from __future__ import annotations

import ctypes
import pickle
from pathlib import Path

import numpy as np

from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.modeld.constants import ModelConstants
from openpilot.selfdrive.modeld.parse_model_outputs import Parser
from openpilot.selfdrive.modeld.stateful_trt_runner import StatefulTensorRTPolicyRunner

METADATA_NAME = "big_driving_supercombo_metadata.pkl"
PLAN_NAME = "driving_supercombo_fp16.plan"
MODEL_H, MODEL_W = 128, 256
CAMERAS = ("img", "big_img")          # (road, wide)
# Matches modeld_bigcombo: cuda_transform_init(width*2, height*2, temporal_skip).
TRANSFORM_W, TRANSFORM_H, TEMPORAL_SKIP = MODEL_W * 2, MODEL_H * 2, 4


class StatefulModelState:
  def __init__(self, cam_w: int = 0, cam_h: int = 0, bundle_dir: str | Path = ""):
    bundle = Path(bundle_dir)
    with (bundle / METADATA_NAME).open("rb") as f:
      metadata = pickle.load(f)
    self.input_shapes = metadata["input_shapes"]
    self.output_slices = metadata["output_slices"]
    self.checkpoint = metadata.get("model_checkpoint")
    self.vision_input_names = list(CAMERAS)
    self.usbgpu = True  # runs the big model; HUD/selfdrived treat it like the eGPU tier

    self.runner = StatefulTensorRTPolicyRunner(bundle / PLAN_NAME, self.input_shapes)
    self.cuda = self.runner.cuda
    self.parser = Parser()
    self.prev_desire = np.zeros(ModelConstants.DESIRE_LEN, dtype=np.float32)
    self.desire_len = int(self.input_shapes["desire"][0])
    # The recurrent state is owned by the runner (device-resident); no host buffers here.

    # cuda_transform outputs (2,6,128,256) per camera; index 1 is the current frame.
    self._dev_out = {k: np.zeros((2, 6, MODEL_H, MODEL_W), dtype=np.uint8) for k in CAMERAS}
    self._setup_transform()

  # ── warp ────────────────────────────────────────────────────────────────────
  def _setup_transform(self) -> None:
    lib = Path(__file__).parent / "transforms" / "libcuda_transform.so"
    self._tr = ctypes.CDLL(str(lib))
    self._tr.cuda_transform_init.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    self._tr.cuda_transform_init.restype = None
    self._tr.cuda_transform_execute.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    self._tr.cuda_transform_execute.restype = ctypes.c_void_p
    self._states = {}
    for key in CAMERAS:
      state = ctypes.create_string_buffer(128)
      self._tr.cuda_transform_init(ctypes.byref(state), TRANSFORM_W, TRANSFORM_H, TEMPORAL_SKIP)
      self._states[key] = state

  def _warp_current(self, key: str, buf, transform: np.ndarray) -> np.ndarray:
    """Warp one camera and return its current-frame 6ch image (6,128,256)."""
    data = np.frombuffer(buf.data, dtype=np.uint8)
    out_ptr = self._tr.cuda_transform_execute(
      ctypes.byref(self._states[key]), ctypes.c_void_p(data.ctypes.data),
      buf.width, buf.height, buf.stride, buf.uv_offset, data.nbytes,
      transform.astype(np.float32).ctypes.data_as(ctypes.POINTER(ctypes.c_float)), 0)
    if not out_ptr:
      raise RuntimeError(f"cuda_transform_execute returned null for {key}")
    host = self._dev_out[key]
    self.cuda.download(ctypes.c_void_p(out_ptr), host)
    return host[1]  # index 1 = current frame (see cuda_transform.cu step 7)

  # ── per-frame ───────────────────────────────────────────────────────────────
  def run(self, buf, wbuf, transform: np.ndarray, transform_wide: np.ndarray,
          inputs: dict, prepare_only: bool) -> dict[str, np.ndarray] | None:
    """Same signature as modeld_bigcombo.ModelState.run so modeld can swap it in."""
    if prepare_only:
      return None

    new_img = np.stack([self._warp_current("img", buf, transform),
                        self._warp_current("big_img", wbuf, transform_wide)]).astype(np.float16)

    inputs["desire"][0] = 0
    desire = np.where(inputs["desire"] - self.prev_desire > .99, inputs["desire"], 0)
    self.prev_desire[:] = inputs["desire"]

    out = self.runner.run(new_img, desire.astype(np.float32),
                          inputs["traffic_convention"].astype(np.float32), inputs["action_t"].astype(np.float32))

    if not np.isfinite(out).all():
      cloudlog.error("[Stateful] non-finite model output")
      return None
    return self.parser.parse_outputs({k: out[v][np.newaxis] for k, v in self.output_slices.items()})

  def warmup(self) -> None:
    """Prime the engine (state starts zeroed inside the runner)."""
    z = np.zeros((2, 6, MODEL_H, MODEL_W), dtype=np.float16)
    self.runner.run(z, np.zeros(ModelConstants.DESIRE_LEN, dtype=np.float32),
                    np.zeros((1, 2), dtype=np.float32), np.zeros((1, 2), dtype=np.float32))

  def __del__(self):
    runner = getattr(self, "runner", None)
    del runner
