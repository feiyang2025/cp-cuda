"""Publish the GPU / big-model Params the HUD badge and the settings page read.

These keys have no cereal counterpart, so this is their only writer: without it
the badge's visibility gate (`usbgpu_present or usbgpu_active or usbgpu_loading
or usbgpu_startup_failed`, hud_renderer.py) is never satisfied and the icon is
silently dropped.

Both modeld entry points call the same functions so the small split-bundle path
and the fused big-model path (modeld_bigcombo) cannot drift:

    publish_gpu_state(params, source=..., inference_active=False)   at startup
    mark_inference_active(params)                                   first modelV2 out
    republish_gpu_state(params, inference_active)                   periodic re-probe

`source` is which model is running: SOURCE_SMALL (the split fallback) or
SOURCE_BIG (the fused single-engine model). `BigModelActive` carries that fact
for the HUD/selfdrived. `UsbGpuActive` is deliberately NOT used for it: the USB
cluster consumers (cluster_usb_display, cluster_autorun) read it as "a USB eGPU
owns the bus", which is a different thing from the local GPU running a bundle.
"""
from __future__ import annotations

from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.modeld.helpers import (active_usbgpu_compiled_path, usbgpu_compiled,
                                                usbgpu_present, wait_for_usbgpu_present)

USBGPU_DISCOVERY_GRACE_SECONDS = 5.0
USBGPU_DISCOVERY_POLL_INTERVAL = 0.1

SOURCE_SMALL = "small"
SOURCE_BIG = "big"


def publish_gpu_state(params: Params, source: str = SOURCE_SMALL, inference_active: bool = False) -> bool:
  """Publish the GPU/big-model state at startup; returns whether the GPU is usable.

  `inference_active` is the driver's own evidence that the GPU is doing work: it
  is only true once modelV2 has actually been published.
  """
  present = usbgpu_present()
  compiled = usbgpu_compiled()
  if not present and compiled and params.get_bool("UsbGpuHardwareSeen"):
    # A device that enumerated before may still be settling; give it a short
    # grace period before declaring the GPU gone for this ignition cycle.
    cloudlog.warning(
      f"GPU not present at modeld start; waiting up to {USBGPU_DISCOVERY_GRACE_SECONDS:.1f}s for it to enumerate")
    present = wait_for_usbgpu_present(USBGPU_DISCOVERY_GRACE_SECONDS, USBGPU_DISCOVERY_POLL_INTERVAL)
    if present:
      cloudlog.warning("GPU enumerated during the startup grace period")

  params.put_bool("UsbGpuPresent", present)
  if present or compiled:
    params.put_bool("UsbGpuHardwareSeen", True)
  params.put_bool("UsbGpuCompiled", compiled)
  # UsbGpuLoading only means anything while a model is loading; by now the load
  # already happened (or was skipped), so it is False.
  params.put_bool("UsbGpuLoading", False)
  # UsbGpuActive is reserved for "a USB eGPU owns the model": this tree runs the
  # model on the local GPU, so it stays False and the USB-cluster consumers are
  # not misled. BigModelActive is the honest "the fused big model is loaded".
  params.put_bool("UsbGpuActive", False)
  params.put_bool("BigModelActive", source == SOURCE_BIG)
  params.put_bool("GpuInferenceActive", inference_active)
  state = f"source={source} present={present} compiled={compiled} inference_active={inference_active} big_model={active_usbgpu_compiled_path()}"
  cloudlog.warning(f"gpu state: {state}")
  return present


def mark_inference_active(params: Params) -> None:
  """Flip the badge green: call once, after the first modelV2 has been sent."""
  params.put_bool_nonblocking("GpuInferenceActive", True)
  cloudlog.warning("gpu state: first model output published; inference active")


def republish_gpu_state(params: Params, inference_active: bool = False) -> None:
  """Re-probe the GPU periodically so the badge follows the hardware."""
  present = usbgpu_present()
  params.put_bool_nonblocking("UsbGpuPresent", present)
  if present:
    params.put_bool_nonblocking("UsbGpuHardwareSeen", True)
  params.put_bool_nonblocking("UsbGpuCompiled", usbgpu_compiled())
  params.put_bool_nonblocking("GpuInferenceActive", inference_active)
