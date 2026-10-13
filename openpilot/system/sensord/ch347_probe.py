#!/usr/bin/env python3
"""Probe the LSM6DS3 that hangs off the CH347 USB-I2C bridge.

The CH347 has no in-tree kernel driver on JetPack 7, so it is reached through
WCH's userspace library and the HID node. Two HID interfaces are exposed and
only one carries the SPI/I2C function: opening the other one makes the kernel
HID read block forever and wedges the whole device until it re-enumerates, so
the interface is picked from sysfs and never probed.

Usage:
  python3 ch347_probe.py             # one scan
  python3 ch347_probe.py --loop      # keep polling, print each successful read
  python3 ch347_probe.py --dev /dev/hidraw4
"""
from __future__ import annotations

import argparse
import ctypes
import glob
import os
import sys
import time
from pathlib import Path

WHO_AM_I_REG = 0x0F
LSM6_ADDRS = (0x6B, 0x6A)
WHO_AM_I_IDS = {0x69: "LSM6DS3", 0x6A: "LSM6DS3TR-C"}
CH347_VID_PID = (0x1A86, (0x55DB, 0x55DC))

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "third_party" / "ch347" / "lib"


def lib_path() -> str:
  machine = os.uname().machine
  arch = {"x86_64": "x64", "aarch64": "aarch64"}.get(machine, "x64")
  for candidate in (LIB_DIR / arch / "dynamic" / "libch347.so", LIB_DIR / "x64" / "dynamic" / "libch347.so"):
    if candidate.is_file():
      return str(candidate)
  raise SystemExit(f"libch347.so not found under {LIB_DIR}")


def hys_read(dev: str, key: str) -> str | None:
  base = os.path.basename(dev)
  try:
    for line in Path(f"/sys/class/hidraw/{base}/device/uevent").read_text().splitlines():
      if line.startswith(key):
        return line[len(key):]
  except OSError:
    pass
  return None


def ch347_input_index(dev: str) -> int | None:
  """Return the HID interface index for a WCH multi-function node, else None."""
  hid_id = hys_read(dev, "HID_ID=")
  if not hid_id:
    return None
  try:
    _bus, vid, pid = (int(x, 16) for x in hid_id.split(":"))
  except ValueError:
    return None
  if vid != CH347_VID_PID[0] or pid not in CH347_VID_PID[1]:
    return None
  phys = hys_read(dev, "HID_PHYS=") or ""
  pos = phys.rfind("/input")
  return int(phys[pos + 6:]) if pos != -1 else -1


def pick_device(explicit: str | None) -> str:
  if explicit:
    return explicit
  candidates = []
  for dev in sorted(glob.glob("/dev/hidraw*")):
    idx = ch347_input_index(dev)
    if idx is not None:
      candidates.append((idx, dev))
  if not candidates:
    raise SystemExit("no CH347 (1a86:55db/55dc) hidraw node found")
  # interface 1 is SPI/I2C, interface 0 is UART/control (do not touch it)
  idx, dev = max(candidates)
  print(f"CH347 HID interface {idx} -> {dev}")
  return dev


class Ch347:
  def __init__(self, dev: str):
    self.lib = ctypes.CDLL(lib_path())
    lib = self.lib
    lib.CH347OpenDevice.restype = ctypes.c_int
    lib.CH347CloseDevice.argtypes = [ctypes.c_int]
    lib.CH347SetTimeout.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong]
    lib.CH347I2C_Set.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.CH347I2C_Set.restype = ctypes.c_bool
    if hasattr(lib, "CH347I2C_SetDelaymS"):
      lib.CH347I2C_SetDelaymS.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.CH347StreamI2C.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    lib.CH347StreamI2C.restype = ctypes.c_bool

    # The deployment lib opens /dev/hidraw<arg+2> from an index, not a path.
    n = int(dev.rsplit("hidraw", 1)[1])
    self.fd = lib.CH347OpenDevice(ctypes.c_ulong(n - 2).value)
    if self.fd < 0:
      raise SystemExit(f"CH347OpenDevice(index {n - 2}) failed")
    lib.CH347SetTimeout(self.fd, 2000, 2000)
    lib.CH347I2C_Set(self.fd, 0x02)  # 400 kHz, LSM6DS3 fast mode

  def read(self, addr: int, reg: int) -> int | None:
    w = (ctypes.c_ubyte * 2)(addr << 1, reg)
    r = (ctypes.c_ubyte * 1)(0)
    if not self.lib.CH347StreamI2C(self.fd, 2, w, 1, r):
      return None
    return r[0]

  def close(self):
    if self.fd >= 0:
      self.lib.CH347CloseDevice(self.fd)
      self.fd = -1


def who_am_i(ch: Ch347) -> tuple[int, int] | None:
  for addr in LSM6_ADDRS:
    value = ch.read(addr, WHO_AM_I_REG)
    if value in WHO_AM_I_IDS:
      return addr, value
  return None


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--dev", help="CH347 hidraw node (default: auto-detect)")
  ap.add_argument("--loop", action="store_true", help="poll until the IMU answers")
  args = ap.parse_args()

  ch = Ch347(pick_device(args.dev))
  try:
    if not args.loop:
      found = who_am_i(ch)
      if found is None:
        print("IMU did not respond (check CH347 <-> IMU SDA/SCL/3V3/GND wiring)")
        return 1
      addr, value = found
      print(f"IMU OK: addr=0x{addr:02X} WHO_AM_I=0x{value:02X} ({WHO_AM_I_IDS[value]})")
      return 0

    print("polling 0x6B/0x6A ... (Ctrl-C to stop)")
    while True:
      found = who_am_i(ch)
      stamp = time.strftime("%H:%M:%S")
      if found is None:
        print(f"[{stamp}] no response")
      else:
        addr, value = found
        print(f"[{stamp}] IMU OK addr=0x{addr:02X} WHO_AM_I=0x{value:02X} ({WHO_AM_I_IDS[value]})")
      time.sleep(1.0)
  except KeyboardInterrupt:
    return 0
  finally:
    ch.close()


if __name__ == "__main__":
  sys.exit(main())
