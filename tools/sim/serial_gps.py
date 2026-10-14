#!/usr/bin/env python3
"""4G-module GPS (NMEA on /dev/ttyUSB1) -> openpilot gpsLocationExternal.

The Qualcomm SimTech 4G modem exposes NMEA sentences on a USB-CDC serial port.
Parse GGA (lat/lon/alt/fix) and RMC (speed/bearing) and publish
gpsLocationExternal (only with a valid fix, flags=1).

Env: GPS_PORT (default /dev/ttyUSB1), GPS_BAUD (default 115200)
"""
import math
import os
import signal
import sys
import time

import serial

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
  sys.path.insert(0, ROOT)

from openpilot.cereal import log
from openpilot.cereal.messaging import PubMaster, new_message

PORT = os.getenv("GPS_PORT", "/dev/ttyUSB1")
BAUD = int(os.getenv("GPS_BAUD", "115200"))
# SIMCom SIM7600 的 AT 口（GNSS 默认关闭，需 AT+CGPS=1 打开后 NMEA 才从 NMEA 口出来）
AT_PORT = os.getenv("GPS_AT_PORT", "/dev/ttyUSB2")
AT_BAUD = int(os.getenv("GPS_AT_BAUD", "115200"))

_shutdown = False


def _on_signal(signum, frame) -> None:
  global _shutdown
  _shutdown = True


def _at_once(cmd: str, wait: float = 0.4) -> None:
  try:
    s = serial.Serial(AT_PORT, AT_BAUD, timeout=1.0)
    s.reset_input_buffer()
    s.write((cmd + "\r\n").encode())
    time.sleep(wait)
    s.read(200)
    s.close()
  except Exception:
    pass


def enable_gnss() -> None:
  """SIM7600 GNSS 默认关闭；上电后必须 AT+CGPS=1，否则 NMEA 口无输出。"""
  try:
    s = serial.Serial(AT_PORT, AT_BAUD, timeout=1.0)
  except Exception as e:
    print(f"GPS: AT port {AT_PORT} open failed: {e} (GNSS 可能仍关闭)", flush=True)
    return

  def at(cmd: str, wait: float = 0.5) -> str:
    s.reset_input_buffer()
    s.write((cmd + "\r\n").encode())
    time.sleep(wait)
    return s.read(300).decode("ascii", "ignore").strip().replace("\r\n", " ")

  try:
    at("AT")
    status = at("AT+CGPS?")
    print(f"GPS: AT+CGPS? -> {status!r}", flush=True)
    if "+CGPS: 1" in status:
      print("GPS: GNSS 已开启", flush=True)
    else:
      resp = at("AT+CGPS=1")
      print(f"GPS: AT+CGPS=1 -> {resp!r}", flush=True)
  except Exception as e:
    print(f"GPS: enable_gnss err {e}", flush=True)
  finally:
    s.close()



def nmea_to_deg(raw: str) -> float | None:
  """ddmm.mmmm -> decimal degrees; '' -> None."""
  if not raw:
    return None
  try:
    d = float(raw)
  except ValueError:
    return None
  deg = int(d / 100)
  minutes = d - deg * 100
  return deg + minutes / 60.0


def main() -> None:
  signal.signal(signal.SIGINT, _on_signal)
  signal.signal(signal.SIGTERM, _on_signal)

  pm = PubMaster(["gpsLocationExternal"])
  enable_gnss()  # 上电后先打开 GNSS，否则 NMEA 口无输出
  print(f"GPS: opening {PORT} @ {BAUD} (NMEA)", flush=True)
  ser = serial.Serial(PORT, BAUD, timeout=1.0)

  fix = False
  lat = lon = alt = 0.0
  speed_kts = 0.0
  bearing = 0.0
  last_pub = 0.0

  try:
    while not _shutdown:
      try:
        line = ser.readline().decode("ascii", "ignore").strip()
        receive_mono_ns = time.monotonic_ns()
        receive_realtime_ns = time.time_ns()
      except Exception as e:
        print(f"GPS: read err {e}", flush=True)
        time.sleep(1)
        continue
      if not line.startswith("$"):
        continue
      parts = line.split(",")
      if parts[0] in ("$GPGGA", "$GNGGA") and len(parts) >= 10:
        lat = nmea_to_deg(parts[2])
        lon = nmea_to_deg(parts[4])
        if parts[2] and parts[2].endswith("S"):
          lat = -lat
        if parts[4] and parts[4].endswith("W"):
          lon = -lon
        try:
          alt = float(parts[9])
        except ValueError:
          alt = 0.0
        fix = parts[6] not in ("", "0")
      elif parts[0] in ("$GPRMC", "$GNRMC") and len(parts) >= 9:
        try:
          speed_kts = float(parts[7]) if parts[7] else 0.0
        except ValueError:
          speed_kts = 0.0
        try:
          bearing = float(parts[8]) if parts[8] else 0.0
        except ValueError:
          bearing = 0.0

      now = receive_mono_ns * 1e-9
      if fix and lat is not None and lon is not None and (now - last_pub) >= 1.0:
        last_pub = now
        dat = new_message("gpsLocationExternal", valid=True, logMonoTime=receive_mono_ns)
        dat.gpsLocationExternal = {
          "unixTimestampMillis": receive_realtime_ns // 1_000_000,
          "flags": 1,
          "horizontalAccuracy": 5.0,
          "verticalAccuracy": 10.0,
          "speedAccuracy": 0.5,
          "bearingAccuracyDeg": 1.0,
          "vNED": [0.0, 0.0, 0.0],
          "bearingDeg": bearing,
          "latitude": lat,
          "longitude": lon,
          "altitude": alt,
          "speed": speed_kts * 0.514444,  # kt -> m/s
          "source": log.GpsLocationData.SensorSource.ublox,
        }
        pm.send("gpsLocationExternal", dat)
  finally:
    try:
      ser.close()
    except Exception:
      pass
    _at_once("AT+CGPS=0")  # 随 OP 退出关闭 GNSS
    print("GPS: closed, GNSS off", flush=True)


if __name__ == "__main__":
  main()
