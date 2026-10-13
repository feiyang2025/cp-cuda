import os
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from openpilot.common.basedir import BASEDIR


USBGPU_FW_VERSION = "ed4e39b7"
USBGPU_USB_IDS = ((0xADD1, 0x0001), (0x3801, 0x0001))
USB_DEVICES_PATH = Path("/sys/bus/usb/devices")
USBGPU_CHECK_ATTEMPTS = 2
USBGPU_CHECK_RETRY_INTERVAL = 1.0
USBGPU_MIN_POWER_MV = 8000


@dataclass(frozen=True)
class UsbGpuDevice:
  sysfs_name: str
  vendor_id: int
  product_id: int
  speed_mbps: int
  manufacturer: str
  product: str
  busnum: int
  devnum: int
  link_error_count: int


@dataclass(frozen=True)
class UsbGpuPowerStatus:
  voltage_mv: int
  current_ma: int
  fault: bool


def _read(path: Path) -> str:
  try:
    return path.read_text().strip()
  except OSError:
    return ""


def _read_int(path: Path, base: int = 10) -> int:
  try:
    return int(_read(path), base)
  except ValueError:
    return 0


def local_gpu_mode() -> bool:
  """True when inference runs on the device's own GPU instead of a USB bridge.

  Local-GPU mode (Jetson AGX Orin): there is no external USB GPU to enumerate,
  so `helpers.usbgpu_present()` reports whether the local CUDA backend is
  usable. Keep this in step with that function; scanning sysfs here would
  report "not detected" on a machine that is plainly running on its GPU.
  """
  try:
    from openpilot.selfdrive.modeld.helpers import default_tg_backend
    return default_tg_backend() == "CUDA"
  except Exception:
    return False


def is_current_usbgpu_firmware(product: str) -> bool:
  return product == f"custom {USBGPU_FW_VERSION}-CLEAN"


def _controller(device: Path) -> Path | None:
  try:
    return next((parent for parent in device.resolve().parents if parent.name.endswith(".ssusb")), None)
  except OSError:
    return None


def get_usbgpu_devices(devices_path: Path = USB_DEVICES_PATH) -> list[UsbGpuDevice]:
  devices: list[UsbGpuDevice] = []
  try:
    paths = sorted(devices_path.glob("*"), key=lambda path: path.name)
  except OSError:
    return devices

  for path in paths:
    vendor_id = _read_int(path / "idVendor", 16)
    product_id = _read_int(path / "idProduct", 16)
    if (vendor_id, product_id) not in USBGPU_USB_IDS:
      continue
    controller = _controller(path)
    devices.append(UsbGpuDevice(
      sysfs_name=path.name,
      vendor_id=vendor_id,
      product_id=product_id,
      speed_mbps=_read_int(path / "speed"),
      manufacturer=_read(path / "manufacturer"),
      product=_read(path / "product"),
      busnum=_read_int(path / "busnum"),
      devnum=_read_int(path / "devnum"),
      link_error_count=_read_int(controller / "portli", 0) & 0xFFFF if controller is not None else 0,
    ))
  return devices


def get_usbgpu_device(devices_path: Path = USB_DEVICES_PATH) -> UsbGpuDevice | None:
  devices = get_usbgpu_devices(devices_path)
  return devices[0] if len(devices) == 1 else None


def _local_gpu_status(compiled: bool, loading: bool, active: bool, startup_failed: bool,
                      compile_pending: bool) -> str:
  """Local-GPU wording for the same state machine the USB path uses.

  The states stay in the USB path's order so the badge and the settings page
  keep agreeing on which condition wins; only the text changes, because there
  is no USB link or bridge firmware to report on here.
  """
  if startup_failed:
    return "startup failed"
  if loading:
    return "loading"
  if compile_pending:
    return "reboot to compile"
  if active:
    return "active (integrated GPU)"
  if not compiled:
    return "big model not compiled"
  return "ready (integrated GPU)"


def usbgpu_status(compiled: bool, loading: bool, active: bool, startup_failed: bool,
                  devices_path: Path = USB_DEVICES_PATH, compile_pending: bool = False) -> str:
  devices = get_usbgpu_devices(devices_path)
  # A real bridge always wins: only fall back to the local backend when nothing
  # enumerated, so this reports the hardware that is actually doing inference.
  if not devices and local_gpu_mode():
    return _local_gpu_status(compiled, loading, active, startup_failed, compile_pending)
  if not devices:
    return "not detected"
  if len(devices) != 1:
    return "multiple devices"

  device = devices[0]
  if device.speed_mbps < 5000:
    return f"slow USB ({device.speed_mbps} Mbps)"
  if not is_current_usbgpu_firmware(device.product):
    return "firmware mismatch"
  if startup_failed:
    return "startup failed"
  if loading:
    return "loading"
  if compile_pending:
    return "reboot to compile"
  if active:
    return "active"
  if not compiled:
    return "model not compiled"
  return "ready"


def usbgpu_badge_state(compiled: bool, loading: bool, active: bool, startup_failed: bool,
                       compile_pending: bool = False) -> str:
  """Return the prioritized on-road badge state shared by C3 and mici."""
  if startup_failed:
    return "error"
  if loading:
    return "loading"
  if compile_pending:
    return "compile_pending"
  if active:
    return "active"
  if not compiled:
    return "not_compiled"
  return "ready"


def get_usbgpu_power_status(timeout_ms: int = 2000) -> UsbGpuPowerStatus | None:
  """Read the custom bridge INA231/BOB status without starting the GPU."""
  import usb.core
  import usb.util

  device = None
  try:
    for vendor_id, product_id in USBGPU_USB_IDS:
      device = usb.core.find(idVendor=vendor_id, idProduct=product_id)
      if device is not None:
        break
    if device is None:
      return None

    # Firmware vendor request 0xC0 returns uint16 mV, int16 mA, bool fault.
    raw = bytes(device.ctrl_transfer(0xC0, 0xC0, 0, 0, 8, timeout=timeout_ms))
    if len(raw) < 5:
      raise RuntimeError(f"short eGPU power status ({len(raw)} bytes)")
    voltage_mv, current_ma, fault = struct.unpack_from("<HhB", raw)
    return UsbGpuPowerStatus(voltage_mv, current_ma, bool(fault))
  finally:
    if device is not None:
      usb.util.dispose_resources(device)


def check_usbgpu_power(devices_path: Path = USB_DEVICES_PATH) -> str | None:
  """Check switched GPU power without changing PCIe or USB bridge state."""
  device = get_usbgpu_device(devices_path)
  if device is None:
    return "USB not connected"
  if device.speed_mbps < 5000:
    return f"USB link {device.speed_mbps} Mbps"
  if not is_current_usbgpu_firmware(device.product):
    return "firmware mismatch"

  try:
    status = get_usbgpu_power_status()
  except Exception as exc:
    return f"power status unavailable: {exc}"
  if status is None:
    return "USB not connected"
  if status.fault:
    return f"eGPU power fault ({status.voltage_mv} mV, {status.current_ma} mA)"
  if status.voltage_mv < USBGPU_MIN_POWER_MV:
    return f"12V off ({status.voltage_mv} mV)"
  return None


def check_local_gpu(timeout: float = 15.0) -> str | None:
  """Prove the integrated GPU can run a real workload, in local-GPU mode.

  Returns the same error-token shape as check_usbgpu() so the settings page can
  present both paths with one status row.
  """
  code = "from tinygrad import Tensor; x = Tensor.rand(1 << 20).realize(); [x.numpy() for _ in range(8)]"
  env = os.environ.copy()
  python_paths = [os.path.join(BASEDIR, "tinygrad_repo"), BASEDIR]
  python_paths.extend(path for path in env.get("PYTHONPATH", "").split(os.pathsep) if path)
  env.update({"DEV": "CUDA", "GMMU": "0", "PYTHONPATH": os.pathsep.join(dict.fromkeys(python_paths))})
  try:
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                            timeout=timeout, check=False)
  except subprocess.TimeoutExpired:
    return "GPU check timed out"
  if result.returncode != 0:
    return "GPU incompatible"
  return None


def check_usbgpu(devices_path: Path = USB_DEVICES_PATH, timeout: float = 15.0,
                 require_clean_link: bool = True) -> str | None:
  """Run an offroad GPU check, optionally treating any recoverable link error as fatal."""
  device = get_usbgpu_device(devices_path)
  # No bridge enumerated: check whatever backend will actually run inference
  # instead of reporting the USB path's "not connected".
  if device is None and local_gpu_mode():
    return check_local_gpu(timeout)
  if device is None:
    return "USB not connected"
  if device.speed_mbps < 5000:
    return f"USB link {device.speed_mbps} Mbps"
  if not is_current_usbgpu_firmware(device.product):
    return "firmware mismatch"
  link_errors = device.link_error_count

  env = os.environ.copy()
  python_paths = [os.path.join(BASEDIR, "tinygrad_repo"), BASEDIR]
  python_paths.extend(path for path in env.get("PYTHONPATH", "").split(os.pathsep) if path)
  env.update({"DEV": "USB+AMD:LLVM", "GMMU": "0", "PYTHONPATH": os.pathsep.join(dict.fromkeys(python_paths))})
  code = "from tinygrad import Tensor; x = Tensor.rand(1 << 20).realize(); [x.numpy() for _ in range(8)]"
  for attempt in range(USBGPU_CHECK_ATTEMPTS):
    try:
      result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
      return "GPU check timed out"

    if result.returncode == 0:
      break

    output = f"{result.stdout}\n{result.stderr}".lower()
    pcie_not_ready = "pcie link not up" in output or "read(0xb450" in output
    if pcie_not_ready and attempt + 1 < USBGPU_CHECK_ATTEMPTS:
      # Retry in a fresh process, matching modeld's proven USB-PD startup path.
      time.sleep(USBGPU_CHECK_RETRY_INTERVAL)
      continue
    return "12V / PCIe not ready" if pcie_not_ready else "GPU incompatible"

  device_after = get_usbgpu_device(devices_path)
  if device_after is None:
    return "USB disconnected during GPU check"
  if require_clean_link and device_after.link_error_count > link_errors:
    return "USB link errors"
  return None
