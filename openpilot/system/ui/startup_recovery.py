#!/usr/bin/env python3
# ruff: noqa: TID251 -- bootstrap display must not import the regular UI/native dependency graph
"""Small recovery display that works without any SCons-built Python modules."""
import argparse
import os
from pathlib import Path
import struct
import time

import pyray as rl

from openpilot.common.network_info import label_with_port, start_ip_monitor
from openpilot.common.startup_recovery import RecoveryUpdate

ROOT = Path(__file__).resolve().parents[3]
EVENT = struct.Struct('llHHi')
TOUCH_DEVICE = '/dev/input/by-path/platform-894000.i2c-event'
LABELS = {
  'idle': {
    'ko': '시작 실패 · 업데이트 대기',
    'en': 'Startup failed · waiting for update',
    'zh': '启动失败 · 等待更新',
  },
  'waiting': {
    'ko': '새 수정본을 기다리고 있습니다',
    'en': 'Waiting for a new fix',
    'zh': '正在等待新的修复版本',
  },
  'updating': {
    'ko': '업데이트 중 · 전원을 유지하세요',
    'en': 'Updating · keep power connected',
    'zh': '更新中 · 请保持供电',
  },
  'failed': {
    'ko': '업데이트 실패 · 다시 시도하세요',
    'en': 'Update failed · tap to retry',
    'zh': '更新失败 · 点击重试',
  },
  'rebooting': {
    'ko': '업데이트 완료 · 재부팅 중',
    'en': 'Update complete · rebooting',
    'zh': '更新完成 · 正在重启',
  },
}
AUTO = {
  'ko': '30초마다 자동 재시도 · 새 수정본을 받으면 재부팅',
  'en': 'Auto-retry every 30s · reboot only after a new update',
  'zh': '每30秒自动重试 · 收到新版本后重启',
}
BUTTON = {'ko': 'Git pull 후 재부팅', 'en': 'Git pull & reboot', 'zh': 'Git pull 后重启'}
BUSY = {'ko': '업데이트 중…', 'en': 'Please wait', 'zh': '更新中…'}


def read_device_language():
  """Read LanguageSetting without importing the native Params graph.

  The bootstrap recovery display must run before SCons-built modules exist, so
  it reads the plain ``/data/params/d`` value directly and falls back to Korean.
  """
  for path in (Path('/data/params/d/LanguageSetting'),):
    try:
      value = path.read_text().strip()
    except OSError:
      continue
    if value:
      value = value.removeprefix('main_')
      if value.startswith('zh'):
        return 'zh'
      if value.startswith('ko'):
        return 'ko'
      return 'en'
  return 'ko'


def localized(table, lang, fallback='en'):
  return table.get(lang) or table.get(fallback) or next(iter(table.values()), '')



def device_size():
  try:
    model = Path('/sys/firmware/devicetree/base/model').read_text().strip('\x00\n').lower()
  except OSError:
    model = ''
  return (2160, 1080) if model in ('comma tici', 'comma tizi', 'comma c3', 'comma c3x') else (536, 240)


def wake_display():
  panel = Path('/sys/class/backlight/panel0-backlight')
  try:
    (panel / 'bl_power').write_text('0')
    maximum = int((panel / 'max_brightness').read_text())
    (panel / 'brightness').write_text(str(maximum // 2))
  except (OSError, ValueError):
    pass


class TouchPress:
  """Track actual slot-0 presses; Raylib supplies transformed coordinates."""
  def __init__(self):
    self.fd = None
    self.slot = 0
    self.down = False
    self.previous = False
    self.saw_mt = False
    if os.name != 'posix':
      return
    try:
      self.fd = os.open(TOUCH_DEVICE, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
      pass

  def pressed(self):
    if self.fd is None:
      return rl.is_mouse_button_pressed(0)
    try:
      data = os.read(self.fd, EVENT.size * 128)
    except BlockingIOError:
      return False
    except OSError:
      self.close()
      return False
    pressed = False
    for offset in range(0, len(data) - EVENT.size + 1, EVENT.size):
      _, _, kind, code, value = EVENT.unpack_from(data, offset)
      if kind == 3 and code == 0x2f:
        self.slot = value
      elif kind == 3 and code == 0x39:
        self.saw_mt = True
        if self.slot == 0:
          self.down = value != -1
      elif kind == 1 and code == 0x14a and not self.saw_mt:
        self.down = value != 0
      elif kind == 0 and code == 0:
        pressed |= self.down and not self.previous
        self.previous = self.down
    return pressed

  def close(self):
    if self.fd is not None:
      os.close(self.fd)
      self.fd = None


def fit_text(font, text, size, width):
  text = ' '.join(text.split())
  if rl.measure_text_ex(font, text, size, 0).x <= width:
    return text
  while text and rl.measure_text_ex(font, text + '...', size, 0).x > width:
    text = text[:-1]
  return text + '...'


def draw_screen(font, width, height, state, reason, address, lang='ko'):
  scale = min(width / 536, height / 240)
  x = (width - 536 * scale) / 2
  y = (height - 240 * scale) / 2
  status, detail = state

  def line(text, top, size, color=rl.WHITE):
    fitted = fit_text(font, text, size * scale, 504 * scale)
    rl.draw_text_ex(font, fitted, rl.Vector2(x + 16 * scale, y + top * scale), size * scale, 0, color)

  def bilingual(table, primary_top, secondary_top, primary_size, secondary_size):
    primary = localized(table, lang)
    line(primary, primary_top, primary_size)
    secondary = table.get('en', '')
    if secondary and secondary != primary:
      line(secondary, secondary_top, secondary_size, rl.LIGHTGRAY)

  rl.clear_background(rl.Color(17, 22, 29, 255))
  bilingual(LABELS[status], 12, 41, 24, 14)
  line(address, 62, 15, rl.Color(120, 195, 255, 255))
  lines = (detail or reason).splitlines()
  for i, text in enumerate([s for s in lines if s.strip()][-3:]):
    line(text, 87 + i * 17, 13, rl.LIGHTGRAY)
  bilingual(AUTO, 145, 161, 13, 11)
  button = rl.Rectangle(x + 16 * scale, y + 182 * scale, 504 * scale, 48 * scale)
  busy = status in ('updating', 'rebooting')
  rl.draw_rectangle_rounded(button, .15, 8, rl.DARKGRAY if busy else rl.Color(33, 104, 200, 255))
  table = BUSY if busy else BUTTON
  primary = localized(table, lang)
  secondary = table.get('en', '')
  for text, top, size in ((primary, 185, 21), (secondary if secondary != primary else '', 212, 12)):
    if not text:
      continue
    size *= scale
    tw = rl.measure_text_ex(font, text, size, 0).x
    rl.draw_text_ex(font, text, rl.Vector2(x + (536 * scale - tw) / 2, y + top * scale), size, 0, rl.WHITE)
  return button


def load_recovery_font(lang, size, codepoints):
  """Pick a font that can actually render the primary language.

  Pretendard has no Hanzi, so Chinese uses the baked CJK bitmap atlas. Korean
  and English keep the original Pretendard outline font with a glyph subset.
  """
  if lang == 'zh':
    cjk = ROOT / 'openpilot/selfdrive/assets/fonts/OpenpilotCJK-Regular.fnt'
    if cjk.exists():
      return rl.load_font(str(cjk))
  glyph_buffer = rl.ffi.new('int[]', codepoints)
  return rl.load_font_ex(str(ROOT / 'openpilot/selfdrive/assets/fonts/Pretendard-Medium.ttf'),
                         size, rl.ffi.cast('int *', glyph_buffer), len(codepoints))


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--reason', default='Startup failed')
  parser.add_argument('--log', type=Path)
  parser.add_argument('--preview', type=Path, help='Save a desktop preview; never update or reboot')
  parser.add_argument('--big', action='store_true', help='Preview the C3 layout')
  args = parser.parse_args()
  if not args.preview and os.environ.get('CARROT_STARTUP_RECOVERY') != '1':
    raise SystemExit('Recovery actions are available only from the failed-startup launcher.')
  lang = read_device_language()
  reason = args.reason
  if args.log:
    try:
      with args.log.open('rb') as log:
        log.seek(max(0, args.log.stat().st_size - 4000))
        reason += '\n' + log.read().decode('utf-8', 'replace')
    except OSError:
      pass
  width, height = (2160, 1080) if args.big else device_size()
  if args.preview:
    rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN)
  rl.init_window(width, height, 'Startup recovery')
  rl.set_target_fps(20)
  rl.set_exit_key(0)
  characters = ''.join(''.join(v.values()) for v in LABELS.values())
  characters += ''.join(AUTO.values()) + ''.join(BUTTON.values()) + ''.join(BUSY.values()) + reason
  codepoints = sorted(set(range(32, 127)) | {ord(c) for c in characters if ord(c) >= 32})
  font = load_recovery_font(lang, round(28 * min(width / 536, height / 240)), codepoints)
  rl.set_texture_filter(font.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
  if args.preview:
    target = rl.load_render_texture(width, height)
    rl.begin_texture_mode(target)
    draw_screen(font, width, height, ('idle', ''), reason, '192.168.0.10:6999', lang)
    rl.end_texture_mode()
    preview = rl.load_image_from_texture(target.texture)
    rl.image_flip_vertical(preview)
    rl.export_image(preview, str(args.preview.resolve()))
    rl.unload_image(preview)
    rl.unload_render_texture(target)
    rl.unload_font(font)
    rl.close_window()
    return
  touch = TouchPress()
  update = RecoveryUpdate(ROOT)
  next_check = time.monotonic() + 5
  was_busy = False
  wake_display()
  start_ip_monitor()
  try:
    while not rl.window_should_close():
      busy = update.state[0] in ('updating', 'rebooting')
      if was_busy and not busy:
        next_check = time.monotonic() + 30
      was_busy = busy
      if not busy and time.monotonic() >= next_check:
        update.start(automatic=True)
        next_check = time.monotonic() + 30
      rl.begin_drawing()
      button = draw_screen(font, width, height, update.state, reason, label_with_port(6999), lang)
      rl.end_drawing()
      if touch.pressed():
        position = rl.get_touch_position(0) if touch.fd is not None else rl.get_mouse_position()
        if rl.check_collision_point_rec(position, button):
          update.start()
      time.sleep(.001)
  finally:
    touch.close()
    rl.unload_font(font)
    rl.close_window()


if __name__ == '__main__':
  main()
