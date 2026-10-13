"""Compile a downloaded fused big-model ONNX into a local TensorRT bundle.

The big-model page switches modeld to a downloaded model, but a fused ONNX has to
be turned into a TensorRT engine first - a minutes-long, CPU-heavy build. That is
build_trt_bundle's job; this feature exposes it as a job so the page can offer a
"compile" button.

Only stateless fused ``.onnx`` deliveries can be compiled. The ``.pkl``
(chunked/precompiled) deliveries target an AMD runtime this device does not have,
so they are rejected. Compiling reads the artifact from the model cache and writes
plan+metadata into ``models/<NAME>/`` - the layout modeld_bigcombo loads - so a
compiled model then appears under the local fused section and can be selected there.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aiohttp import web

from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.modeld import build_trt_bundle, model_bundle, model_catalog

_job_lock = threading.Lock()
_job: dict[str, Any] = {"state": "idle"}

# Only ASCII letters/digits survive; everything else collapses to '_'.
_SAFE_RE = re.compile(r"[^A-Za-z0-9]+")


def _slug(text: str | None) -> str | None:
  if not text:
    return None
  name = _SAFE_RE.sub("_", str(text)).strip("_")
  return name.upper() or None


def _slug_from_url(url: str | None) -> str | None:
  if not url:
    return None
  try:
    parts = [p for p in urlparse(url).path.split("/") if p]
  except Exception:
    return None
  if "models" in parts:
    i = parts.index("models")
    if i + 1 < len(parts):
      return parts[i + 1]
  return parts[-2] if len(parts) >= 2 else None


def bundle_name_for(label: str | None = None, model_id: str | None = None,
                    filename: str | None = None, url: str | None = None) -> str | None:
  """A short, unique bundle name for a model.

  The label is what the page shows ("CTM V2") and is unique per model, so it is
  preferred. The URL directory slug is the next best key; the model_id token after
  ``pr<digits>-`` collides (CTM V2 and CTM V3 both live under cinque), so it is only
  a last resort.
  """
  model_token = None
  if model_id:
    m = re.search(r"pr\d+[-_]([A-Za-z0-9]+)", model_id)
    model_token = m.group(1) if m else None
  stem = re.sub(r"^big_driving_", "", Path(filename).stem) if filename else None
  for raw in (label, _slug_from_url(url), model_token, stem):
    name = _slug(raw)
    if name:
      return name
  return None


def _set(**kw: Any) -> None:
  with _job_lock:
    _job.update(kw)


def compile_status() -> dict[str, Any]:
  with _job_lock:
    return dict(_job)


def _run(sha: str, name: str, onnx: Path) -> None:
  bundle = model_bundle.MODELS_DIR / name

  def progress(msg: str) -> None:
    _set(log=msg)
    cloudlog.info(f"[compile {name}] {msg}")

  try:
    result = build_trt_bundle.compile_bundle(bundle, onnx, progress=progress)
    _set(state="done", log=f"built {Path(result['plan']).name}", plan_bytes=result["plan_bytes"])
    cloudlog.warning(f"[compile {name}] done: {result['plan']} ({result['plan_bytes'] / 1e6:.1f} MB)")
  except Exception as e:
    cloudlog.exception(f"[compile {name}] failed")
    _set(state="error", error=f"{type(e).__name__}: {e}", log="failed")


def _meta_for(sha: str) -> dict | None:
  for item in model_catalog.list_models():
    if item.get("sha256") == sha:
      return item
  return None


async def api_compile_start(request: web.Request) -> web.Response:
  try:
    body = await request.json()
  except Exception:
    return web.json_response({"ok": False, "error": "invalid JSON body"}, status=400)
  if not isinstance(body, dict):
    return web.json_response({"ok": False, "error": "invalid JSON body"}, status=400)

  sha = body.get("sha")
  if not isinstance(sha, str) or not sha:
    return web.json_response({"ok": False, "error": "sha required"}, status=400)

  artifact = model_catalog.artifact_path(sha)
  if artifact is None:
    return web.json_response({"ok": False, "error": "model artifact not found on disk"}, status=404)
  if artifact.suffix != ".onnx":
    return web.json_response(
      {"ok": False, "error": "该模型是 AMD 专用的 .pkl 包，本机无法编译为 TensorRT"}, status=409)

  meta = _meta_for(sha) or {}
  name = _slug(body.get("name")) if isinstance(body.get("name"), str) else None
  if not name:
    name = bundle_name_for(meta.get("model_id"), filename=artifact.name, url=meta.get("url"))
  if not name:
    return web.json_response({"ok": False, "error": "无法从模型名推导 bundle 名字"}, status=400)

  existing = model_bundle.bundle_mode(model_bundle.MODELS_DIR / name)
  if existing == "merged":
    return web.json_response({"ok": False, "error": f"{name} 已编译", **compile_status()}, status=409)
  if existing is not None:
    return web.json_response({"ok": False, "error": f"已存在同名 {existing} bundle: {name}"}, status=409)

  with _job_lock:
    running = _job.get("state") == "running"
  if running:
    return web.json_response({"ok": False, "error": "已有编译任务在进行", **compile_status()}, status=409)

  _set(state="running", name=name, sha=sha, log="queued", plan_bytes=None, error=None)
  threading.Thread(target=_run, args=(sha, name, artifact), name=f"compile-{name}", daemon=True).start()
  return web.json_response({"ok": True, **compile_status()}, status=202)


async def api_compile_status(_request: web.Request) -> web.Response:
  return web.json_response({"ok": True, **compile_status()})


def register(app: web.Application) -> None:
  app.router.add_post("/api/egpu/models/compile", api_compile_start)
  app.router.add_get("/api/egpu/models/compile", api_compile_status)
