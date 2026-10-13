import ast
from pathlib import Path

from openpilot.selfdrive.modeld import gpu_state


UI_DIR = Path(__file__).resolve().parents[1]
MODELD_DIR = UI_DIR.parent / "modeld"
GPU_STATE_PATH = MODELD_DIR / "gpu_state.py"
HUD_PATHS = (
  UI_DIR / "onroad" / "hud_renderer.py",
  UI_DIR / "mici" / "onroad" / "hud_renderer.py",
)


class _FakeParams:
  def __init__(self):
    self.written = {}

  def put_bool(self, key, value):
    self.written[key] = value

  def put_bool_nonblocking(self, key, value):
    self.written[key] = value

  def get_bool(self, key):
    return self.written.get(key, False)


def _method(path: Path, class_name: str, method_name: str) -> ast.FunctionDef:
  tree = ast.parse(path.read_text(encoding="utf-8"))
  cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
  return next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)


def _call_name(call: ast.Call) -> str | None:
  if isinstance(call.func, ast.Attribute):
    return call.func.attr
  if isinstance(call.func, ast.Name):
    return call.func.id
  return None


def test_both_device_huds_render_egpu_badge_with_shared_runtime_state():
  for path in HUD_PATHS:
    render = _method(path, "HudRenderer", "_render")
    calls = [
      node for node in ast.walk(render)
      if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert any(call.func.attr == "_draw_egpu_badge" for call in calls)

    badge = _method(path, "HudRenderer", "_draw_egpu_badge")
    badge_source = ast.unparse(badge)
    assert "badge_w" in badge_source
    assert "rect.width / 2" not in badge_source
    assert "usbgpu_badge_state" in badge_source
    for attr in ("usbgpu_present", "usbgpu_compiled", "usbgpu_compile_pending", "usbgpu_loading", "usbgpu_active", "usbgpu_startup_failed"):
      assert any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "ui_state"
        and node.attr == attr
        for node in ast.walk(badge)
      )
    for state in ("active", "loading", "error", "compile_pending", "not_compiled", "ready"):
      assert repr(state) in badge_source
    assert "eGPU REBOOT" in badge_source


def test_ui_state_reads_modeld_egpu_active_param():
  update_params = _method(UI_DIR / "ui_state.py", "UIState", "update_params")
  assert any(
    isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == "get_bool"
    and node.args
    and isinstance(node.args[0], ast.Constant)
    and node.args[0].value == "UsbGpuActive"
    for node in ast.walk(update_params)
  )


def test_ui_state_distinguishes_current_compile_from_previous_fallback():
  update_params = _method(UI_DIR / "ui_state.py", "UIState", "update_params")
  calls = [node for node in ast.walk(update_params) if isinstance(node, ast.Call)]
  assert any(isinstance(node.func, ast.Name) and node.func.id == "active_usbgpu_compiled_path" for node in calls)
  assert any(isinstance(node.func, ast.Name) and node.func.id == "usbgpu_compile_pending" for node in calls)
  assert not any(
    isinstance(node.func, ast.Attribute)
    and node.func.attr == "get_bool"
    and node.args
    and isinstance(node.args[0], ast.Constant)
    and node.args[0].value == "UsbGpuCompiled"
    for node in calls
  )


def _function(path: Path, function_name: str) -> ast.FunctionDef:
  tree = ast.parse(path.read_text(encoding="utf-8"))
  return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function_name)


def _modeld_function(function_name: str) -> ast.FunctionDef:
  return _function(MODELD_DIR / "modeld.py", function_name)


def _gpu_state_function(function_name: str) -> ast.FunctionDef:
  return _function(GPU_STATE_PATH, function_name)


def _param_writes(node: ast.AST) -> set[str]:
  """Param keys written by put_bool / put_bool_nonblocking inside `node`."""
  keys = set()
  for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
    if not isinstance(call.func, ast.Attribute) or call.func.attr not in ("put_bool", "put_bool_nonblocking"):
      continue
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
      keys.add(call.args[0].value)
  return keys


def _param_writes(node: ast.AST, blocking: bool | None = None) -> dict[str, object]:
  """Map Param key -> written value, for put_bool / put_bool_nonblocking calls.

  Read from the tree rather than the source text so formatting and quote style
  cannot make these assertions fail for the wrong reason.
  """
  writes: dict[str, object] = {}
  for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
    name = _call_name(call)
    if name not in ("put_bool", "put_bool_nonblocking"):
      continue
    if blocking is True and name != "put_bool":
      continue
    if blocking is False and name != "put_bool_nonblocking":
      continue
    if not call.args or not isinstance(call.args[0], ast.Constant) or not isinstance(call.args[0].value, str):
      continue
    value = call.args[1].value if len(call.args) > 1 and isinstance(call.args[1], ast.Constant) else None
    writes[call.args[0].value] = value
  return writes


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
  return [n for n in ast.walk(node) if isinstance(n, ast.Call) and _call_name(n) == name]


def _no_probe(monkeypatch, present=True, compiled=True):
  monkeypatch.setattr(gpu_state, "usbgpu_present", lambda: present)
  monkeypatch.setattr(gpu_state, "usbgpu_compiled", lambda: compiled)
  monkeypatch.setattr(gpu_state, "active_usbgpu_compiled_path", lambda: None)


def test_small_path_publishes_gpu_state_without_claiming_the_big_model(monkeypatch):
  # The badge's visibility gate is driven purely by these Params. The small
  # bundle path publishes them but must not claim the big model is running.
  _no_probe(monkeypatch)
  p = _FakeParams()
  gpu_state.publish_gpu_state(p, source=gpu_state.SOURCE_SMALL)
  assert {"UsbGpuPresent", "UsbGpuCompiled", "UsbGpuHardwareSeen", "UsbGpuLoading", "UsbGpuActive"} <= set(p.written)
  assert p.written["UsbGpuLoading"] is False
  assert p.written["UsbGpuActive"] is False
  assert p.written["BigModelActive"] is False
  assert p.written["GpuInferenceActive"] is False


def test_big_path_publishes_gpu_state_and_marks_the_big_model_active(monkeypatch):
  # The fused big path shares the same writer but declares the big model loaded.
  _no_probe(monkeypatch)
  p = _FakeParams()
  gpu_state.publish_gpu_state(p, source=gpu_state.SOURCE_BIG)
  # UsbGpuActive stays reserved for a USB eGPU; the local big model flags itself
  # separately so the USB-cluster consumers are not misled.
  assert p.written["UsbGpuActive"] is False
  assert p.written["BigModelActive"] is True
  assert p.written["GpuInferenceActive"] is False
  gpu_state.mark_inference_active(p)
  assert p.written["GpuInferenceActive"] is True


def test_modeld_marks_the_gpu_in_use_only_once_it_publishes_a_result():
  # Green must not appear before a result exists: modeld sets it through the
  # shared helper, after the first modelV2 send.
  main = _modeld_function("main")
  send = next(c for c in ast.walk(main)
              if isinstance(c, ast.Call) and _call_name(c) == "send"
              and isinstance(c.args[0], ast.Constant) and c.args[0].value == "modelV2")
  flag = next(c for c in _calls(main, "mark_inference_active"))
  assert flag.lineno > send.lineno

  # And publish_gpu_state starts it False, through the argument, not a constant.
  publish = _gpu_state_function("publish_gpu_state")
  names = [a.arg for a in publish.args.args]
  defaults = dict(zip(names[len(names) - len(publish.args.defaults):], publish.args.defaults))
  assert isinstance(defaults["inference_active"], ast.Constant)
  assert defaults["inference_active"].value is False
  assert _param_writes(publish)["GpuInferenceActive"] is None


def test_badge_goes_green_on_either_gpu_in_use_signal():
  for path in HUD_PATHS:
    badge_source = ast.unparse(_method(path, "HudRenderer", "_draw_egpu_badge"))
    assert "gpu_inference_active" in badge_source
    assert "big_model_active" in badge_source
    # All signals collapse into the one argument the shared state machine reads.
    assert "ui_state.usbgpu_active or ui_state.gpu_inference_active" in badge_source


def test_modeld_refreshes_hotplug_state_after_startup():
  republish = _gpu_state_function("republish_gpu_state")
  assert {"UsbGpuPresent", "UsbGpuCompiled", "UsbGpuHardwareSeen"} <= set(_param_writes(republish, blocking=False))
  # Probe through the same helper the badge's own state is derived from.
  assert _calls(republish, "usbgpu_present")

  # Both must actually be called, not merely defined.
  main = _modeld_function("main")
  assert _calls(main, "republish_gpu_state")
  assert _calls(main, "publish_gpu_state")


def test_modeld_waits_for_a_remembered_egpu_to_enumerate():
  publish = _gpu_state_function("publish_gpu_state")
  source = GPU_STATE_PATH.read_text(encoding="utf-8")
  assert "USBGPU_DISCOVERY_GRACE_SECONDS = 5.0" in source

  reads = {call.args[0].value for call in _calls(publish, "get_bool")
           if call.args and isinstance(call.args[0], ast.Constant)}
  assert "UsbGpuHardwareSeen" in reads

  # Only wait when this device has proven a GPU before and one is compiled.
  guards = [ast.unparse(node.test) for node in ast.walk(publish) if isinstance(node, ast.If)]
  assert any("not present and compiled and" in guard for guard in guards)

  assert any([ast.unparse(a) for a in call.args] == ["USBGPU_DISCOVERY_GRACE_SECONDS", "USBGPU_DISCOVERY_POLL_INTERVAL"]
             for call in _calls(publish, "wait_for_usbgpu_present"))


def test_modeld_retries_transient_egpu_pcie_startup():
  source = (UI_DIR.parent / "modeld" / "modeld.py").read_text(encoding="utf-8")

  assert "USBGPU_INIT_ATTEMPTS = 6" in source
  assert "usbgpu_pcie_not_ready(exc)" in source
  assert "eGPU PCIe link not ready; retrying" in source


def test_modeld_restarts_instead_of_racing_a_timed_out_egpu_loader():
  source = (UI_DIR.parent / "modeld" / "modeld.py").read_text(encoding="utf-8")

  assert "USBGPU_MODEL_LOAD_TIMEOUT = 40" in source
  assert 'params.put_bool("UsbGpuStartupFailed", True)' in source
  assert 'raise RuntimeError("eGPU model loader did not terminate")' in source


def test_modeld_keeps_egpu_loading_until_first_output_is_published():
  source = (UI_DIR.parent / "modeld" / "modeld.py").read_text(encoding="utf-8")

  loaded = source.index("usbgpu_model_loaded = model is not None")
  pending = source.index("usbgpu_startup_pending = usbgpu_model_loaded", loaded)
  first_send = source.index("pm.send('modelV2', modelv2_send)", pending)
  clear = source.index('params.put_bool("UsbGpuLoading", False)', first_send)
  assert loaded < pending < first_send < clear
  assert "eGPU first model output published; startup complete" in source[clear:]


def test_modeld_runs_internal_fallback_on_the_same_frame():
  source = (UI_DIR.parent / "modeld" / "modeld.py").read_text(encoding="utf-8")

  fallback = source[source.index("eGPU model failed, falling back to internal GPU"):]
  failed_set = fallback.index('params.put_bool("UsbGpuStartupFailed", True)')
  loading_clear = fallback.index('params.put_bool("UsbGpuLoading", False)')
  pending_clear = fallback.index("usbgpu_startup_pending = False")
  assert "model = small_model" in fallback
  assert "model_output = model.run(bufs, transforms, inputs, prepare_only)" in fallback
  assert failed_set < loading_clear < pending_clear < fallback.index("model = small_model")


def test_modeld_queues_tmux_capture_for_all_egpu_failure_paths():
  source = (UI_DIR.parent / "modeld" / "modeld.py").read_text(encoding="utf-8")
  carrot_man_source = (UI_DIR.parent / "carrot" / "carrot_man.py").read_text(encoding="utf-8")

  assert 'USBGPU_TMUX_ERROR_REASON = "egpu_error"' in source
  assert 'queue_usbgpu_error_tmux(params, "model load failed")' in source
  assert 'queue_usbgpu_error_tmux(params, "model load timed out")' in source
  assert 'queue_usbgpu_error_tmux(params, "runtime model execution failed")' in source
  assert '"egpu_error"' in carrot_man_source.split("CARROT_EXCEPTION_TMUX_REASONS =", 1)[1].splitlines()[0]


def test_selfdrived_allows_five_seconds_for_egpu_fallback_to_settle():
  source = (UI_DIR.parent / "selfdrived" / "selfdrived.py").read_text(encoding="utf-8")

  assert "def _big_model_settling" in source
  assert "self.big_model_active and not active" in source
  assert "self.big_model_ready_t + 5.0" in source
  assert "and not big_model_settling" in source


def test_tinygrad_retries_interrupted_usb_event_waits():
  source = (UI_DIR.parents[2] / "tinygrad_repo" / "tinygrad" / "runtime" / "support" / "usb.py").read_text(encoding="utf-8")

  assert "rc != libusb.LIBUSB_ERROR_INTERRUPTED" in source
