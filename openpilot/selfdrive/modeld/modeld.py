#!/usr/bin/env python3
import os
os.environ['LRU'] = '0'  # Disable LRU GPU alloc cache early (tinygrad import reads it)
import ctypes
try:
  from openpilot.system.hardware import TICI
except ImportError:
  # master-c3 系硬件抽象无 TICI 常量: 非 TICI 平台 → 走 CUDA 路径
  TICI = False
from tinygrad.tensor import Tensor
from tinygrad.dtype import dtypes
from tinygrad.device import Device
if TICI:
  from openpilot.selfdrive.modeld.runners.tinygrad_helpers import qcom_tensor_from_opencl_address
  os.environ['QCOM'] = '1'
else:
  os.environ['CUDA'] = '1'
import time
import pickle
import numpy as np
try:
  import openpilot.cereal.messaging as messaging
  from openpilot.cereal import log
  from opendbc.car.structs import car
except ImportError:
  import cereal.messaging as messaging
  from cereal import car, log
from pathlib import Path
from setproctitle import setproctitle
try:
  from openpilot.cereal.messaging import PubMaster, SubMaster
except ImportError:
  from cereal.messaging import PubMaster, SubMaster
from msgq.visionipc import VisionIpcClient, VisionBuf
try:
  from msgq.visionipc import VisionStreamType
  _VST_ROAD = VisionStreamType.VISION_STREAM_ROAD
  _VST_DRIVER = VisionStreamType.VISION_STREAM_DRIVER
  _VST_WIDE_ROAD = VisionStreamType.VISION_STREAM_WIDE_ROAD
except ImportError:
  # 无类型 msgq (新代, master-c3 系): 数值与 sp 枚举一致, kit 内部自洽
  _VST_ROAD, _VST_DRIVER, _VST_WIDE_ROAD = 0, 1, 2
try:
  from openpilot.cereal import log as _cereal_log
except ImportError:
  from cereal import log as _cereal_log
# cereal schema 自适应 (master-c3: roadCameraState→narrowRoadCameraState, 无 liveCalibration)
_EV_FIELDS = set(_cereal_log.Event.schema.fields.keys())
_MSG_ROAD = 'roadCameraState' if 'roadCameraState' in _EV_FIELDS else 'narrowRoadCameraState'
_MSG_LIVECAL = 'liveCalibration' if 'liveCalibration' in _EV_FIELDS else None
from opendbc.car.car_helpers import get_demo_car_params
from openpilot.common.swaglog import cloudlog
from openpilot.common.params import Params
from openpilot.common.filter_simple import FirstOrderFilter
from openpilot.common.realtime import config_realtime_process
from openpilot.common.transformations.camera import DEVICE_CAMERAS
from openpilot.common.transformations.model import get_warp_matrix
from openpilot.system import sentry
from openpilot.selfdrive.controls.lib.desire_helper import DesireHelper
from openpilot.selfdrive.modeld.parse_model_outputs import Parser
from openpilot.selfdrive.modeld.fill_model_msg import (fill_model_msg, fill_pose_msg, fill_driving_model_data,
                                                       get_action_from_plan, PublishState)
from openpilot.selfdrive.modeld import model_bundle
from openpilot.selfdrive.modeld.camera_sync import MAX_FRAME_SKEW, TOLERANCE_NS, receive_camera_pair
from openpilot.selfdrive.modeld.constants import ModelConstants, Plan
from openpilot.selfdrive.modeld.gpu_state import (SOURCE_SMALL, mark_inference_active,
                                                  publish_gpu_state, republish_gpu_state)

# TRT 加载兜底闭环参数(可用环境变量覆盖)
TRT_LOAD_ATTEMPTS = int(os.getenv("TRT_LOAD_ATTEMPTS", "3"))
TRT_LOAD_RETRY_INTERVAL = float(os.getenv("TRT_LOAD_RETRY_INTERVAL", "2.0"))

# 所有小模型 bundle 都起不来时的重试间隔: 不用 raise 让 manager 疯转, 而是原地等,
# 给"模型还在下载"这种情况一个自愈机会。
MODEL_RETRY_INTERVAL = float(os.getenv("MODEL_RETRY_INTERVAL", "10.0"))

PROCESS_NAME = "selfdrive.modeld.modeld"
SEND_RAW_PRED = os.getenv('SEND_RAW_PRED')

# 兼容 master-c3 系: 原生 modeld.py 导出此常量, controlsd.py import 它
LAT_SMOOTH_SECONDS = 0.0

DEFAULT_MODEL_DIR = Path(__file__).parent / 'models'


def _read_model_param(params=None):
  """Active model bundle name.

  Tolerates this tree's Params API (no `encoding` kwarg) and a missing 'Model' key
  (both differ from the API this file was written against). Because the registry has
  no 'Model' key at all, the fallbacks are: MODEL_NAME env -> the selection file the
  web model picker writes -> DEFAULT_NAME. See model_bundle for the file layout.

  The parser handles both bundle generations: lane_lines/road_edges/lead are read
  from whichever output carries them (vision on CD210, policy on FiletOFish) and the
  plan is decoded as MHP or a single MDN depending on its encoded length.
  """
  p = params if params is not None else Params()
  try:
    v = p.get("Model")
  except Exception:
    v = None
  if isinstance(v, (bytes, bytearray)):
    v = bytes(v).decode("utf-8", "replace")
  return v or model_bundle.active_name()


def get_model_name():
  return _read_model_param()


def get_model_dir():
  return DEFAULT_MODEL_DIR / get_model_name()


def _missing_bundle_files(model_dir: Path) -> list[str]:
  """Files ModelState.__init__ needs that are not present in the bundle.

  The two metadata pickles are always read. The tinygrad pickles are only read
  when no TensorRT engine is present, so a TRT bundle does not need them.
  """
  needed = ['driving_vision_metadata.pkl', 'driving_policy_metadata.pkl']
  has_trt = ((model_dir / 'driving_vision_fp16.plan').is_file()
             and (model_dir / 'driving_policy_fp16.plan').is_file())
  if not has_trt:
    needed += ['driving_vision_tinygrad.pkl', 'driving_policy_tinygrad.pkl']
  return [f for f in needed if not (model_dir / f).is_file()]


class FrameMeta:
  frame_id: int = 0
  timestamp_sof: int = 0
  timestamp_eof: int = 0

  def __init__(self, vipc=None):
    if vipc is not None:
      self.frame_id, self.timestamp_sof, self.timestamp_eof = vipc.frame_id, vipc.timestamp_sof, vipc.timestamp_eof

class ModelState:
  frames: dict
  inputs: dict[str, np.ndarray]
  output: np.ndarray
  prev_desire: np.ndarray  # for tracking the rising edge of the pulse

  def __init__(self, context=None, model_dir=None):
    model_dir = Path(model_dir) if model_dir is not None else get_model_dir()
    missing = _missing_bundle_files(model_dir)
    if missing:
      raise model_bundle.ModelBundleIncomplete(model_dir.name, missing)
    # Record what actually loaded: when the first-choice bundle is skipped the
    # selected name and the running name differ, and every log line that mentions
    # the model has to name the one that is really executing.
    self.model_dir = model_dir

    vision_metadata_path = model_dir / 'driving_vision_metadata.pkl'
    policy_metadata_path = model_dir / 'driving_policy_metadata.pkl'
    vision_pkl_path = model_dir / 'driving_vision_tinygrad.pkl'
    policy_pkl_path = model_dir / 'driving_policy_tinygrad.pkl'

    with open(vision_metadata_path, 'rb') as f:
      vision_metadata = pickle.load(f)
      self.vision_input_shapes = vision_metadata['input_shapes']
      self.vision_output_slices = vision_metadata['output_slices']
      vision_output_size = vision_metadata['output_shapes']['outputs'][1]
    self.vision_input_names = list(self.vision_input_shapes.keys())

    with open(policy_metadata_path, 'rb') as f:
      policy_metadata = pickle.load(f)
      self.policy_input_shapes = policy_metadata['input_shapes']
      self.policy_output_slices = policy_metadata['output_slices']
      policy_output_size = policy_metadata['output_shapes']['outputs'][1]

    # Derive all dimensions dynamically from metadata shapes
    # (different models use different key names, so search by pattern)
    self.temporal_skip = ModelConstants.MODEL_RUN_FREQ // ModelConstants.MODEL_CONTEXT_FREQ  # == 4
    _temporal_key = next((k for k in ['desire', 'desire_pulse', 'features_buffer'] if k in self.policy_input_shapes), None)
    _temporal_shape = self.policy_input_shapes[_temporal_key]
    self.input_history_buffer_len = _temporal_shape[1]
    _desire_key = next((k for k in ['desire', 'desire_pulse'] if k in self.policy_input_shapes), None)
    self.desire_len = self.policy_input_shapes[_desire_key][2] if _desire_key is not None else ModelConstants.DESIRE_LEN
    self.feature_len = self.policy_input_shapes['features_buffer'][2]
    self.full_history_buffer_len = self.input_history_buffer_len * self.temporal_skip

    # Derive model dimensions from vision input shape: (1, channels, h, w)
    # Each sub-plane in transform output is (w, h) → model input channel is (h, w)
    # MODEL_W = w * 2, MODEL_H = h * 2
    _model_input_shape = self.vision_input_shapes[self.vision_input_names[0]]
    _model_h, _model_w = _model_input_shape[2], _model_input_shape[3]
    self._model_w = _model_w * 2
    self._model_h = _model_h * 2

    # CUDA-only build: OpenCL frames are created lazily further down, and only
    # when the CUDA transform is unavailable (see the guard after the CUDA init).
    self.frames = {}
    self.prev_desire = np.zeros(self.desire_len, dtype=np.float32)

    self.full_features_buffer = np.zeros((1, self.full_history_buffer_len, self.feature_len), dtype=np.float32)
    self.full_desire = np.zeros((1, self.full_history_buffer_len, self.desire_len), dtype=np.float32)
    self.full_prev_desired_curv = None
    self.temporal_idxs = slice(-1 - (self.temporal_skip * (self.input_history_buffer_len - 1)), None, self.temporal_skip)

    # Create policy inputs dynamically from model metadata
    self.numpy_inputs = {name: np.zeros(shape, dtype=np.float32) for name, shape in self.policy_input_shapes.items()}

    # Initialize prev_desired_curv buffer using actual model shape
    prev_curv_shape = self.numpy_inputs.get('prev_desired_curv', np.zeros((1,), dtype=np.float32)).shape
    self.full_prev_desired_curv = np.zeros((1, self.full_history_buffer_len, prev_curv_shape[-1]), dtype=np.float32)

    # img buffers are managed in openCL transform code
    self.vision_inputs: dict[str, Tensor] = {}
    self.vision_input_ptrs: dict[str, int] = {}  # CUDA device ptrs for TRT zero-copy
    self.vision_output = np.zeros(vision_output_size, dtype=np.float32)
    self.policy_inputs = {k: Tensor(v, device='NPY').realize() for k,v in self.numpy_inputs.items()}
    self.policy_output = np.zeros(policy_output_size, dtype=np.float32)
    self.parser = Parser()

    # Initialize CUDA transform pipeline (bypass OpenCL on non-TICI)
    self._cuda_transform = None
    if not TICI:
      try:
        transform_dir = Path(__file__).parent / 'transforms'
        lib_path = transform_dir / 'libcuda_transform.so'
        if lib_path.exists():
          self._cu_transform = ctypes.CDLL(str(lib_path))
          self._cu_transform.cuda_transform_init.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
          self._cu_transform.cuda_transform_init.restype = None
          self._cu_transform.cuda_transform_execute.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
          self._cu_transform.cuda_transform_execute.restype = ctypes.c_void_p
          self._cu_transform.cuda_transform_destroy.argtypes = [ctypes.c_void_p]
          self._cu_transform.cuda_transform_destroy.restype = None

          self._cuda_states = {}
          for key in ('input_imgs', 'big_input_imgs'):
            state = ctypes.create_string_buffer(128)
            self._cu_transform.cuda_transform_init(
              ctypes.byref(state), self._model_w, self._model_h, self.temporal_skip
            )
            self._cuda_states[key] = state
          self._cuda_transform = True
          cloudlog.warning("CUDA transform initialized (OpenCL bypassed)")
          # 零拷贝: VisionIPC buffer 是 cudaHostRegister 映射的, 用设备指针喂 transform 省掉 H2D
          self._vipc_devptr = {}
          self._cudart_zc = None
          try:
            self._cudart_zc = ctypes.CDLL('libcudart.so')
            self._cudart_zc.cudaHostGetDevicePointer.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_uint]
            self._cudart_zc.cudaHostGetDevicePointer.restype = ctypes.c_int
          except Exception as e:
            cloudlog.warning(f"zerocopy device ptr unavailable: {e}")
      except Exception as e:
        cloudlog.warning(f"CUDA transform not available: {e}")
        self._cuda_transform = False

    # OpenCL frame fallback. This tree ships no OpenCL model stack, so it is only
    # usable where a CL context exists (TICI); elsewhere fail loudly rather than
    # importing a module that no longer exists.
    if TICI or not self._cuda_transform:
      if context is None:
        raise RuntimeError("modeld is CUDA-only in this tree: OpenCL frames need a CL context")
      from openpilot.selfdrive.modeld.models.commonmodel_pyx import DrivingModelFrame
      self.frames = {k: DrivingModelFrame(context, self.temporal_skip) for k in ('input_imgs', 'big_input_imgs')}

    # ── Force tinygrad CUDA device init BEFORE TRT ──
    # TRT will piggyback on tinygrad's context so they share the same CUDA context.
    # Without this, TRT creates its own context and tinygrad creates a different one,
    # causing 'invalid resource handle' on TRT inference.
    _ = Device['CUDA']

    # Try TensorRT engine first (much faster, ~2ms vs ~50ms)
    # 兜底闭环: plan 存在但加载失败 → 按 TRT_LOAD_ATTEMPTS 重试(间隔 TRT_LOAD_RETRY_INTERVAL) →
    # 仍失败才降级 tinygrad, 并记录失败原因供 cloudlog 汇总排查(不再静默只打一行 warning)。
    trt_engine_path = model_dir / 'driving_vision_fp16.plan'
    self.use_trt = trt_engine_path.exists()
    self.trt_vision_fail_reason = ""
    if self.use_trt:
      for attempt in range(1, TRT_LOAD_ATTEMPTS + 1):
        try:
          from openpilot.selfdrive.modeld.runners.tensorrt_runner import TensorRTModel
          self.vision_run = TensorRTModel(str(trt_engine_path))
          cloudlog.warning("Using TensorRT for vision model (FP16)")
          print("[INFO] Using TensorRT for vision model")
          break
        except Exception as e:
          self.trt_vision_fail_reason = f"{e}"
          if attempt < TRT_LOAD_ATTEMPTS:
            cloudlog.warning(f"TRT vision load failed ({e}), retry {attempt}/{TRT_LOAD_ATTEMPTS} in {TRT_LOAD_RETRY_INTERVAL}s")
            print(f"[WARN] TRT vision load failed: {e}, retry {attempt}/{TRT_LOAD_ATTEMPTS}")
            time.sleep(TRT_LOAD_RETRY_INTERVAL)
          else:
            cloudlog.warning(f"TRT vision load failed after {TRT_LOAD_ATTEMPTS} attempts ({e}), falling back to tinygrad")
            print(f"[WARN] TRT vision load failed after {TRT_LOAD_ATTEMPTS} attempts: {e}, falling back to tinygrad")
            self.use_trt = False
    if not self.use_trt:
      with open(vision_pkl_path, "rb") as f:
        self.vision_run = pickle.load(f)

    # Try TensorRT for policy model too (same pattern as vision)
    policy_trt_path = model_dir / 'driving_policy_fp16.plan'
    self.use_trt_policy = policy_trt_path.exists()
    self.trt_policy_fail_reason = ""
    if self.use_trt_policy:
      for attempt in range(1, TRT_LOAD_ATTEMPTS + 1):
        try:
          from openpilot.selfdrive.modeld.runners.tensorrt_runner import TensorRTModel
          self.policy_run = TensorRTModel(str(policy_trt_path))
          cloudlog.warning("Using TensorRT for policy model (FP16)")
          print("[INFO] Using TensorRT for policy model")
          break
        except Exception as e:
          self.trt_policy_fail_reason = f"{e}"
          if attempt < TRT_LOAD_ATTEMPTS:
            cloudlog.warning(f"Policy TRT load failed ({e}), retry {attempt}/{TRT_LOAD_ATTEMPTS} in {TRT_LOAD_RETRY_INTERVAL}s")
            print(f"[WARN] Policy TRT load failed: {e}, retry {attempt}/{TRT_LOAD_ATTEMPTS}")
            time.sleep(TRT_LOAD_RETRY_INTERVAL)
          else:
            cloudlog.warning(f"Policy TRT load failed after {TRT_LOAD_ATTEMPTS} attempts ({e}), falling back to tinygrad")
            print(f"[WARN] Policy TRT load failed after {TRT_LOAD_ATTEMPTS} attempts: {e}, falling back to tinygrad")
            self.use_trt_policy = False
    if not self.use_trt_policy:
      with open(policy_pkl_path, "rb") as f:
        self.policy_run = pickle.load(f)

  def slice_outputs(self, model_outputs: np.ndarray, output_slices: dict[str, slice]) -> dict[str, np.ndarray]:
    parsed_model_outputs = {k: model_outputs[np.newaxis, v] for k,v in output_slices.items()}
    return parsed_model_outputs

  def run(self, buf: VisionBuf, wbuf: VisionBuf, transform: np.ndarray, transform_wide: np.ndarray,
                inputs: dict[str, np.ndarray], prepare_only: bool) -> dict[str, np.ndarray] | None:
    # Model decides when action is completed, so desire input is just a pulse triggered on rising edge
    inputs['desire'][0] = 0
    new_desire = np.where(inputs['desire'] - self.prev_desire > .99, inputs['desire'], 0)
    self.prev_desire[:] = inputs['desire']

    self.full_desire[0,:-1] = self.full_desire[0,1:]
    self.full_desire[0,-1] = new_desire

    # Populate policy inputs dynamically by name
    desire_hist = self.full_desire.reshape((1, self.input_history_buffer_len, self.temporal_skip, -1)).max(axis=2)
    if 'desire' in self.numpy_inputs:
      self.numpy_inputs['desire'][:] = desire_hist
    if 'desire_pulse' in self.numpy_inputs:
      self.numpy_inputs['desire_pulse'][:] = desire_hist
    if 'traffic_convention' in self.numpy_inputs:
      self.numpy_inputs['traffic_convention'][:] = inputs['traffic_convention']
    if 'lateral_control_params' in self.numpy_inputs:
      self.numpy_inputs['lateral_control_params'][:] = inputs['lateral_control_params']

    if TICI:
      imgs_cl = {'input_imgs': self.frames['input_imgs'].prepare(buf, transform.flatten()),
                 'big_input_imgs': self.frames['big_input_imgs'].prepare(wbuf, transform_wide.flatten())}
      for i, cl_key in enumerate(['input_imgs', 'big_input_imgs']):
        model_key = self.vision_input_names[i]
        if model_key not in self.vision_inputs:
          self.vision_inputs[model_key] = qcom_tensor_from_opencl_address(imgs_cl[cl_key].mem_address, self.vision_input_shapes[model_key], dtype=dtypes.uint8)
    elif self._cuda_transform:
      for i, (key, fbuf) in enumerate([('input_imgs', buf), ('big_input_imgs', wbuf)]):
        model_key = self.vision_input_names[i]
        state = self._cuda_states[key]
        proj = transform if key == 'input_imgs' else transform_wide
        # 零拷贝: buffer 若是映射内存, 用设备指针, transform 内部跳过 H2D
        # 注意: msgq 的 VisionBuf.data 是 memoryview(不是 numpy 数组), 必须先 frombuffer
        # 才能取 .ctypes / .nbytes (否则 AttributeError: 'memoryview' object has no attribute 'ctypes')
        data_np = np.frombuffer(fbuf.data, dtype=np.uint8)
        c_ptr = data_np.ctypes.data
        input_is_device = 0
        if self._cudart_zc is not None:
          dptr = self._vipc_devptr.get(c_ptr)
          if dptr is None:
            d = ctypes.c_void_p()
            if self._cudart_zc.cudaHostGetDevicePointer(ctypes.byref(d), ctypes.c_void_p(c_ptr), 0) == 0 and d.value:
              dptr = d.value
              self._vipc_devptr[c_ptr] = dptr
          if dptr is not None:
            c_ptr = dptr
            input_is_device = 1
        buf_len = data_np.nbytes
        output_ptr = self._cu_transform.cuda_transform_execute(
          ctypes.byref(state), ctypes.c_void_p(c_ptr),
          fbuf.width, fbuf.height, fbuf.stride, fbuf.uv_offset,
          buf_len,
          proj.astype(np.float32).ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
          input_is_device
        )
        self.vision_inputs[model_key] = Tensor.from_blob(output_ptr, self.vision_input_shapes[model_key], dtype=dtypes.uint8, device='CUDA')
        self.vision_input_ptrs[model_key] = output_ptr  # save for TRT zero-copy
    else:
      imgs_cl = {'input_imgs': self.frames['input_imgs'].prepare(buf, transform.flatten()),
                 'big_input_imgs': self.frames['big_input_imgs'].prepare(wbuf, transform_wide.flatten())}
      for i, cl_key in enumerate(['input_imgs', 'big_input_imgs']):
        model_key = self.vision_input_names[i]
        frame_input = self.frames[cl_key].buffer_from_cl(imgs_cl[cl_key]).reshape(self.vision_input_shapes[model_key])
        self.vision_inputs[model_key] = Tensor(frame_input, dtype=dtypes.uint8).realize()

    if prepare_only:
      return None

    if self.use_trt:
      # ── Zero-copy: pass saved CUDA device pointers directly ──
      # These are saved at transform time: no tinygrad internal API needed.
      if self.vision_input_ptrs:
        # Have CUDA pointers saved from CUDA transform path
        input_ptrs = {k: self.vision_input_ptrs[k] for k in self.vision_input_names}
        self.vision_output = self.vision_run(**input_ptrs)
      else:
        # Fallback: pass numpy arrays (TRT runner does H2D copy internally)
        np_inputs = {k: self.vision_inputs[k].numpy() for k in self.vision_input_names}
        self.vision_output = self.vision_run(**np_inputs)
    else:
      self.vision_output = self.vision_run(**self.vision_inputs).numpy().flatten()
    vision_outputs_dict = self.parser.parse_vision_outputs(self.slice_outputs(self.vision_output, self.vision_output_slices))

    self.full_features_buffer[0,:-1] = self.full_features_buffer[0,1:]
    self.full_features_buffer[0,-1] = vision_outputs_dict['hidden_state'][0, :]
    if 'features_buffer' in self.numpy_inputs:
      self.numpy_inputs['features_buffer'][:] = self.full_features_buffer[0, self.temporal_idxs]

    if self.use_trt_policy:
      self.policy_output = self.policy_run(**self.numpy_inputs)
      # 模型健康报警: 平时静默, 仅在输出发散/NaN/顶 fp16 上限时打印 (velocity 乱跳的预兆)
      fb = self.numpy_inputs.get('features_buffer')
      po = np.asarray(self.policy_output).ravel().astype(np.float32)
      po_finite = np.isfinite(po)
      po_finite_pct = po_finite.mean() * 100.0
      po_absmax = np.abs(po[po_finite]).max() if po_finite.any() else -1.0
      if fb is not None and (po_finite_pct < 100.0 or po_absmax > 60000.0):
        print(f'[MODELD-ALERT] fb_std={fb.std():.5f} fb_absmax={np.abs(fb).max():.4f} '
              f'po_finite={po_finite_pct:.0f}% po_absmax={po_absmax:.1f}', flush=True)
    else:
      self.policy_output = self.policy_run(**self.policy_inputs).numpy().flatten()
    policy_outputs_dict = self.parser.parse_policy_outputs(self.slice_outputs(self.policy_output, self.policy_output_slices))

    if 'prev_desired_curv' in self.numpy_inputs:
      self.full_prev_desired_curv[0,:-1] = self.full_prev_desired_curv[0,1:]
      if 'desired_curvature' in policy_outputs_dict:
        self.full_prev_desired_curv[0,-1,0] = policy_outputs_dict['desired_curvature'][0, 0]
      else:
        plan_last = policy_outputs_dict['plan'][0, -1] if policy_outputs_dict['plan'].ndim == 3 else policy_outputs_dict['plan'][0, 0, -1]
        vx = float(plan_last[Plan.VELOCITY][0])
        yaw_rate = float(plan_last[Plan.ORIENTATION_RATE][2])
        self.full_prev_desired_curv[0,-1,0] = yaw_rate / max(vx, 0.01)
      self.numpy_inputs['prev_desired_curv'][:] = self.full_prev_desired_curv[0, self.temporal_idxs]

    combined_outputs_dict = {**vision_outputs_dict, **policy_outputs_dict}
    if SEND_RAW_PRED:
      combined_outputs_dict['raw_pred'] = np.concatenate([self.vision_output.copy(), self.policy_output.copy()])

    return combined_outputs_dict


def _release_vipc(buf):
  """归还 VisionIPC buffer, 与客户端 recv 的 acquire 配对。

  本树的 msgq 未打零拷贝补丁时 (无 write_and_send / 共享 refcount) VisionBuf 没有
  release() —— 无条件调用会 AttributeError 直接打死 modeld (相机有画面但无 modelV2)。
  """
  if buf is not None and hasattr(buf, 'release'):
    buf.release()


def _make_model(cam_w: int, cam_h: int, chestnut: bool = False):
  if not chestnut and os.getenv("DISABLE_CUDA_BACKEND", "0") != "1":
    try:
      from openpilot.sunnypilot.modeld_v2.gpu_model_state import GpuModelState
      model = GpuModelState(cam_w=cam_w, cam_h=cam_h, chestnut=False)
      cloudlog.warning("Using GpuModelState (CUDA/TensorRT)")
      return model
    except Exception:
      cloudlog.exception("GpuModelState init failed, falling back to tinygrad ModelState")
  return ModelState(cam_w=cam_w, cam_h=cam_h, chestnut=chestnut)


def _candidate_bundle_names() -> list[str]:
  """Bundle names to try, in fallback order: env override, the user's order, default."""
  names = []
  env = os.getenv("MODEL_NAME")
  if env:
    names.append(env)
  names.extend(model_bundle.read_small_order())
  names.append(model_bundle.DEFAULT_NAME)
  seen: set[str] = set()
  out: list[str] = []
  for name in names:
    if name and name not in seen:
      seen.add(name)
      out.append(name)
  return out


def _load_usable_model(context):
  """Load the first bundle that works, skipping the ones that do not.

  Candidates are tried in fallback order; a bundle that fails is logged and the
  next is used. If none loads there is nothing left to fall back to, so instead
  of raising - which would restart modeld into the same dead end, the tight loop
  that produced repeated crashes - the failure is logged in full and retried,
  letting a bundle that is still being downloaded become usable without a storm.
  """
  while True:
    failures = []
    for name in _candidate_bundle_names():
      if model_bundle.bundle_mode(model_bundle.bundle_dir(name)) != "split":
        continue
      try:
        return ModelState(context, model_dir=model_bundle.bundle_dir(name))
      except Exception as e:
        failures.append(f"{name}: {type(e).__name__}: {e}")
        cloudlog.error(f"model bundle {name!r} failed to load: {type(e).__name__}: {e}")
    detail = "; ".join(failures) if failures else "no model bundle directories found"
    cloudlog.error(f"no loadable model bundle; retrying in {MODEL_RETRY_INTERVAL:.0f}s. tried: {detail}")
    time.sleep(MODEL_RETRY_INTERVAL)


def main(demo=False):
  # Fused (single-engine) big model first, the small split bundle otherwise. A
  # big engine that fails to load is marked and the small bundle takes over in
  # this same process - restarting would only retry the engine that just failed.
  # 本树是 openpilot/selfdrive/... 新布局: 顶层 `selfdrive.*` 导入不存在, 需用 openpilot.*
  big = model_bundle.active_big_name()
  if big:
    try:
      try:
        import openpilot.selfdrive.modeld.modeld_bigcombo as _bigcombo
      except ImportError:
        import selfdrive.modeld.modeld_bigcombo as _bigcombo
    except Exception:
      cloudlog.exception(f"big model module unavailable for {big}; using the small bundle")
      model_bundle.mark_big_failed("modeld_bigcombo import failed")
    else:
      try:
        _bigcombo.main(demo=demo, model_name=big)
      except SystemExit:
        raise
      except _bigcombo.BigComboTrtUnavailable as e:
        cloudlog.warning(f"big model {big} unavailable ({e}); falling back to the small bundle")
        model_bundle.mark_big_failed(str(e))
      except Exception as e:
        cloudlog.exception(f"big model {big} failed; falling back to the small bundle")
        model_bundle.mark_big_failed(f"{type(e).__name__}: {e}")
      else:
        raise SystemExit(0)

  cloudlog.warning("modeld init")

  sentry.set_tag("daemon", PROCESS_NAME)
  cloudlog.bind(daemon=PROCESS_NAME)
  setproctitle(PROCESS_NAME)
  config_realtime_process(7, 54)

  # Publish before the vision streams connect: the badge should not sit blank
  # through the whole camera handshake, and the grace period in
  # publish_gpu_state() must not be billed to the first frame.
  publish_gpu_state(Params(), source=SOURCE_SMALL)

  cl_context = None
  if TICI:
    from openpilot.selfdrive.modeld.models.commonmodel_pyx import CLContext
    cl_context = CLContext()
  cloudlog.warning("loading model (CUDA/TensorRT path)")
  model = _load_usable_model(cl_context)
  cloudlog.warning(f"models loaded, modeld starting: bundle={model.model_dir.name}")
  cloudlog.warning(f"camera pairing: frame_id-primary via camera_sync (K={MAX_FRAME_SKEW}, T={TOLERANCE_NS // 1_000_000}ms)")
  cloudlog.warning(f"backend: vision_trt={model.use_trt} policy_trt={model.use_trt_policy} "
                   f"(vision_fail={model.trt_vision_fail_reason or 'none'} policy_fail={model.trt_policy_fail_reason or 'none'})")

  # visionipc clients
  while True:
    available_streams = VisionIpcClient.available_streams("camerad", block=False)
    if available_streams:
      use_extra_client = _VST_WIDE_ROAD in available_streams and _VST_ROAD in available_streams
      main_wide_camera = _VST_ROAD not in available_streams
      break
    time.sleep(.1)

  vipc_client_main_stream = _VST_WIDE_ROAD if main_wide_camera else _VST_ROAD
  vipc_client_main = VisionIpcClient("camerad", vipc_client_main_stream, True)
  vipc_client_extra = VisionIpcClient("camerad", _VST_WIDE_ROAD, True)
  cloudlog.warning(f"vision stream set up, main_wide_camera: {main_wide_camera}, use_extra_client: {use_extra_client}")

  while not vipc_client_main.connect(False):
    time.sleep(0.1)
  while use_extra_client and not vipc_client_extra.connect(False):
    time.sleep(0.1)

  cloudlog.warning(f"connected main cam with buffer size: {vipc_client_main.buffer_len} ({vipc_client_main.width} x {vipc_client_main.height})")
  if use_extra_client:
    cloudlog.warning(f"connected extra cam with buffer size: {vipc_client_extra.buffer_len} ({vipc_client_extra.width} x {vipc_client_extra.height})")

  # messaging
  pm = PubMaster(["modelV2", "drivingModelData", "cameraOdometry"])
  sm = SubMaster(["deviceState", "carState", _MSG_ROAD] + ([_MSG_LIVECAL] if _MSG_LIVECAL else []) +
                 ["driverMonitoringState", "carControl", "liveDelay", "carrotMan", "radarState"])

  publish_state = PublishState()
  params = Params()

  # The selected name, not the loaded one: a fallback bundle can be running while
  # the selection still points at the broken bundle. The change check is about the
  # selection, so keep comparing that; the running bundle is logged at load time.
  loaded_model_name = get_model_name()
  model_check_counter = 0
  # The GPU is not "in use" until a model result has actually gone out; only
  # modeld knows that, so it is what flips the HUD badge to active.
  inference_active = False

  # setup filter to track dropped frames
  frame_dropped_filter = FirstOrderFilter(0., 10., 1. / ModelConstants.MODEL_RUN_FREQ)
  frame_id = 0
  last_vipc_frame_id = 0
  run_count = 0

  model_transform_main = np.zeros((3, 3), dtype=np.float32)
  model_transform_extra = np.zeros((3, 3), dtype=np.float32)
  live_calib_seen = False
  buf_main, buf_extra = None, None
  meta_main = FrameMeta()
  meta_extra = FrameMeta()


  if demo:
    CP = get_demo_car_params()
  else:
    CP = messaging.log_from_bytes(params.get("CarParams", block=True), car.CarParams)
  cloudlog.info("modeld got CarParams: %s", CP.brand)

  # TODO this needs more thought, use .2s extra for now to estimate other delays
  steer_delay = CP.steerActuatorDelay + .2

  DH = DesireHelper()

  while True:
    # Check if model was changed via params
    model_check_counter += 1
    if model_check_counter % 100 == 0:
      current_model_name = _read_model_param(params)
      if current_model_name != loaded_model_name:
        cloudlog.warning(f"Model changed from {loaded_model_name} to {current_model_name}, restarting")
        raise SystemExit(0)
      # usbgpu_present() shells into tinygrad, so keep it off the per-frame path.
      republish_gpu_state(params, inference_active)

    # Pair road/wide by frame id (bounded by exposure time); None = give up this
    # round rather than mispair. Dropped buffers are released for the refcounted
    # VisionIPC stream (on_drop), so advancement does not leak ref counts.
    pair = receive_camera_pair(vipc_client_main, vipc_client_extra if use_extra_client else None, on_drop=_release_vipc)
    if pair is None:
      cloudlog.debug("no camera pair")
      continue
    buf_main, meta_main, buf_extra, meta_extra = pair

    sm.update(0)
    desire = DH.desire
    is_rhd = sm["driverMonitoringState"].isRHD
    frame_id = sm[_MSG_ROAD].frameId
    v_ego = max(sm["carState"].vEgo, 0.)
    lateral_control_params = np.array([v_ego, steer_delay], dtype=np.float32)
    if _MSG_LIVECAL and sm.updated[_MSG_LIVECAL] and sm.seen[_MSG_ROAD] and sm.seen['deviceState']:
      device_from_calib_euler = np.array(sm[_MSG_LIVECAL].rpyCalib, dtype=np.float32)
      dc = DEVICE_CAMERAS[(str(sm['deviceState'].deviceType), str(sm[_MSG_ROAD].sensor))]
      model_transform_main = get_warp_matrix(device_from_calib_euler, dc.ecam.intrinsics if main_wide_camera else dc.fcam.intrinsics, False).astype(np.float32)
      model_transform_extra = get_warp_matrix(device_from_calib_euler, dc.ecam.intrinsics, True).astype(np.float32)
      live_calib_seen = True

    traffic_convention = np.zeros(2)
    traffic_convention[int(is_rhd)] = 1

    vec_desire = np.zeros(model.desire_len, dtype=np.float32)
    if desire >= 0 and desire < model.desire_len:
      vec_desire[desire] = 1

    # tracked dropped frames
    vipc_dropped_frames = max(0, meta_main.frame_id - last_vipc_frame_id - 1)
    frames_dropped = frame_dropped_filter.update(min(vipc_dropped_frames, 10))
    if run_count < 10: # let frame drops warm up
      frame_dropped_filter.x = 0.
      frames_dropped = 0.
    run_count = run_count + 1

    frame_drop_ratio = frames_dropped / (1 + frames_dropped)
    prepare_only = vipc_dropped_frames > 0
    if prepare_only:
      cloudlog.error(f"skipping model eval. Dropped {vipc_dropped_frames} frames")

    inputs:dict[str, np.ndarray] = {
      'desire': vec_desire,
      'traffic_convention': traffic_convention,
      'lateral_control_params': lateral_control_params,
      }

    mt1 = time.perf_counter()
    model_output = model.run(buf_main, buf_extra, model_transform_main, model_transform_extra, inputs, prepare_only)
    mt2 = time.perf_counter()
    model_execution_time = mt2 - mt1

    # 推理/读取完成, 释放 vipc buffer 供 camerad 复用 (与 client recv 的 acquire 配对)
    if buf_extra is not None and buf_extra is not buf_main:
      _release_vipc(buf_extra)
    if buf_main is not None:
      _release_vipc(buf_main)

    # Log GPU memory periodically (every 100 frames) on CUDA/Orin
    if not TICI and frame_id % 100 == 0:
      try:
        import ctypes
        cuda = ctypes.CDLL('libcuda.so.1')
        free_mem = ctypes.c_size_t()
        total_mem = ctypes.c_size_t()
        cuda.cuMemGetInfo_v2(ctypes.byref(free_mem), ctypes.byref(total_mem))
        cloudlog.warning(f"GPU mem: free={free_mem.value>>20}MB total={total_mem.value>>20}MB used={(total_mem.value - free_mem.value)>>20}MB")
      except Exception:
        pass

    if model_output is not None:
      modelv2_send = messaging.new_message('modelV2')
      drivingdata_send = messaging.new_message('drivingModelData')
      posenet_send = messaging.new_message('cameraOdometry')
      # action: 本树走 plan 回退路径(与移植前语义一致), 每帧只算一次 → 热路径零额外开销
      action = get_action_from_plan(model_output)
      fill_model_msg(modelv2_send, model_output, action, publish_state, meta_main.frame_id, meta_extra.frame_id,
                     frame_id, frame_drop_ratio, meta_main.timestamp_eof, model_execution_time, live_calib_seen)

      desire_state = modelv2_send.modelV2.meta.desireState
      l_lane_change_prob = desire_state[log.Desire.laneChangeLeft]
      r_lane_change_prob = desire_state[log.Desire.laneChangeRight]
      lane_change_prob = l_lane_change_prob + r_lane_change_prob
      # CARROT 版 DesireHelper 需要 6 个参数(多了 modelV2 本体 + carrotMan/radarState):
      # 与 modeld_trt_candidate.py:541 的调用保持一致, 否则 TypeError 直接把 modeld 打崩。
      DH.update(sm['carState'], modelv2_send.modelV2, sm['carControl'].latActive, lane_change_prob,
                sm['carrotMan'], sm['radarState'])
      modelv2_send.modelV2.meta.laneChangeState = DH.lane_change_state
      modelv2_send.modelV2.meta.laneChangeDirection = DH.lane_change_direction
      # drivingModelData 由 modelV2 派生(新 API): laneChange* 已落在 modelV2 上, 统一拷贝一次
      fill_driving_model_data(drivingdata_send, modelv2_send)

      fill_pose_msg(posenet_send, model_output, meta_main.frame_id, vipc_dropped_frames, meta_main.timestamp_eof, live_calib_seen)
      pm.send('modelV2', modelv2_send)
      pm.send('drivingModelData', drivingdata_send)
      pm.send('cameraOdometry', posenet_send)
      if not inference_active:
        inference_active = True
        mark_inference_active(params)
    last_vipc_frame_id = meta_main.frame_id


if __name__ == "__main__":
  try:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true', help='A boolean for demo mode.')
    args = parser.parse_args()
    main(demo=args.demo)  # BigCombo dispatch is inside main() (manager calls main() directly)
  except KeyboardInterrupt:
    cloudlog.warning(f"child {PROCESS_NAME} got SIGINT")
  except Exception:
    sentry.capture_exception()
    raise
