import os

from openpilot.cereal import log
from openpilot.system.hardware.base import HardwareBase, ThermalConfig, ThermalZone

NetworkType = log.DeviceState.NetworkType

THERMAL_ROOT = "/sys/devices/virtual/thermal"


def _thermal_zones(predicate):
  """ThermalZones whose sysfs `type` matches, discovered at runtime.

  A desktop PC exposes no such zones, so this returns nothing there and the
  thermal config stays empty; a Jetson (also reported as "pc") exposes
  cpu-thermal / gpu-thermal / socN-thermal / tj-thermal, which is what feeds
  deviceState.cpuTempC and therefore the HUD's CPU/thermal readout and the
  thermal protection bands.
  """
  try:
    entries = sorted(os.listdir(THERMAL_ROOT))
  except OSError:
    return []

  zones = []
  for entry in entries:
    if not entry.startswith("thermal_zone"):
      continue
    try:
      with open(os.path.join(THERMAL_ROOT, entry, "type")) as f:
        zone_type = f.read().strip()
    except OSError:
      continue
    if zone_type and predicate(zone_type):
      zones.append(ThermalZone(zone_type))
  return zones


class Pc(HardwareBase):
  def get_device_type(self):
    return "pc"

  def get_network_type(self):
    return NetworkType.wifi

  def get_thermal_config(self):
    cpu = _thermal_zones(lambda t: "cpu" in t)
    gpu = _thermal_zones(lambda t: "gpu" in t)
    if not cpu and not gpu:
      return ThermalConfig()
    return ThermalConfig(cpu=cpu or None, gpu=gpu or None)
