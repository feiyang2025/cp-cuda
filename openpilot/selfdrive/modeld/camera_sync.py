"""Pair current camera frames by frame sequence, bounded by exposure time.

Two alignment signals are checked together: the frame id says "same position in
the stream" (the strong signal - camerad's FrameSync stamps one global id per
exposure across all cameras), the exposure start time says "same physical moment"
(a loose sanity bound). A pair is accepted only when both hold; otherwise the
camera whose exposure is older is advanced, so a lagging stream self-corrects
instead of mispairing.

Measured on the decoupled webcam camerad (2026-10-13): road-vs-wide frame_id is 0
or 1 for 99.9% of frames, while |Δsof| runs 19 ms (p50) to 87 ms (max) - well over
one 50 ms frame. The exposure gate therefore cannot be tight or it would reject
most valid pairs, so the frame-id gate carries the decision and the time gate is
only a wide upper bound. On a tightly synced camera both signals pass anyway.
"""
from __future__ import annotations

import time

# Frame ids are global (one per exposure across cameras); the decoupled wide
# stream lags by at most 1-2 frames.
MAX_FRAME_SKEW = 2
# Loose upper bound: this device's road/wide exposures differ by up to ~87 ms.
TOLERANCE_NS = 120_000_000
MAX_TRIES = 10


class FrameMeta:
  frame_id: int = 0
  timestamp_sof: int = 0
  timestamp_eof: int = 0

  def __init__(self, vipc=None):
    if vipc is not None:
      self.frame_id, self.timestamp_sof, self.timestamp_eof = vipc.frame_id, vipc.timestamp_sof, vipc.timestamp_eof


def receive_camera_pair(main, extra=None, *, tolerance_ns: int = TOLERANCE_NS, max_frame_skew: int = MAX_FRAME_SKEW,
                        max_tries: int = MAX_TRIES, deadline_s: float | None = None, on_drop=None):
  """Return the next exposure pair, or None after a timeout / bounded resync.

  A single camera returns its newest frame immediately. With two, a pair is
  accepted only when both ``|Δsof| <= tolerance_ns`` and
  ``|Δframe_id| <= max_frame_skew``; otherwise the camera with the older
  exposure is advanced and the check repeats, bounded by ``max_tries`` and an
  optional wall-clock ``deadline_s``. When neither criterion can be met within
  the budget the frame is dropped (None) rather than mispaired.

  ``on_drop`` is called with every buffer that is acquired but not returned (the
  ones superseded while advancing, and both on a timeout). Pass a release
  callback on a refcounted VisionIPC stream so dropped frames are returned to
  the server; leave it None on a stream that does not acquire.
  """
  def _drop(buf):
    if on_drop is not None and buf is not None:
      on_drop(buf)

  main_buf = main.recv()
  main_meta = FrameMeta(main)
  if main_buf is None:
    return None
  if extra is None:
    return main_buf, main_meta, main_buf, main_meta

  extra_buf = extra.recv()
  extra_meta = FrameMeta(extra)
  start = time.monotonic()
  for _ in range(max_tries):
    if main_buf is None or extra_buf is None:
      _drop(main_buf)
      _drop(extra_buf)
      return None
    d_sof = main_meta.timestamp_sof - extra_meta.timestamp_sof
    d_id = main_meta.frame_id - extra_meta.frame_id
    if abs(d_sof) <= tolerance_ns and abs(d_id) <= max_frame_skew:
      return main_buf, main_meta, extra_buf, extra_meta
    if deadline_s is not None and time.monotonic() - start > deadline_s:
      _drop(main_buf)
      _drop(extra_buf)
      return None
    # Advance whichever camera is behind in exposure time.
    if d_sof < 0:
      _drop(main_buf)
      main_buf = main.recv()
      main_meta = FrameMeta(main)
    else:
      _drop(extra_buf)
      extra_buf = extra.recv()
      extra_meta = FrameMeta(extra)
  _drop(main_buf)
  _drop(extra_buf)
  return None
