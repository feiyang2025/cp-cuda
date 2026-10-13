"""Web API: list, order, switch and remove the model bundles modeld loads.

Two families live side by side under `models/`:
  * split bundles (vision + policy) - the fallback modeld runs, ordered so the
    top entry wins;
  * merged/fused bundles - the single-engine big model modeld tries first, via
    modeld_bigcombo.

Companion to features/egpu_model_select.py, which manages the optional
downloaded eGPU big models in the model cache dir (a different system).

Routes:
  GET  /api/small-models         bundles + fallback order + active entries
  POST /api/small-models/select  choose a bundle (split -> fallback top; merged -> big)
  POST /api/small-models/order   set the split fallback order
  POST /api/small-models/remove  delete a bundle's files
"""
from __future__ import annotations

import shutil
from typing import Any

from aiohttp import web

from openpilot.selfdrive.modeld import model_bundle

from ..services.params import HAS_PARAMS, Params


def build_small_models_payload() -> dict[str, Any]:
  return {
    'ok': True,
    'active': model_bundle.active_name(),
    'big_active': model_bundle.active_big_name(),
    'big_failed': model_bundle.big_failed_reason(),
    'default': model_bundle.DEFAULT_NAME,
    'order': model_bundle.read_small_order(),
    'models': model_bundle.list_bundles(),
  }


async def api_models(_request: web.Request) -> web.Response:
  return web.json_response(build_small_models_payload())


async def _json_body(request: web.Request):
  try:
    body = await request.json()
  except Exception:
    return None
  return body if isinstance(body, dict) else None


def _maybe_reboot(body: dict) -> bool:
  reboot = bool(body.get('reboot'))
  if reboot and HAS_PARAMS and Params is not None:
    try:
      Params().put_bool('DoReboot', True)
    except Exception:
      reboot = False
  return reboot


async def api_select(request: web.Request) -> web.Response:
  body = await _json_body(request)
  if body is None:
    return web.json_response({'ok': False, 'error': 'invalid JSON body'}, status=400)

  name = body.get('name')
  if name is not None and not isinstance(name, str):
    return web.json_response({'ok': False, 'error': 'name must be a string'}, status=400)

  if not name or name == model_bundle.DEFAULT_NAME:
    model_bundle.write_selection(None)
    return web.json_response({'ok': True, **build_small_models_payload(), 'reboot_requested': _maybe_reboot(body)})

  mode = model_bundle.bundle_mode(model_bundle.bundle_dir(name))
  if mode is None:
    return web.json_response({'ok': False, 'error': f'unknown model bundle: {name}'}, status=404)

  try:
    if mode == 'merged':
      # The fused big model is picked separately; routing it into the split order
      # made modeld load a bundle that has no vision/policy metadata at all.
      model_bundle.write_big_selection(name)
    else:
      model_bundle.write_selection(name)
  except ValueError as exc:
    return web.json_response({'ok': False, 'error': str(exc)}, status=400)
  return web.json_response({'ok': True, **build_small_models_payload(), 'reboot_requested': _maybe_reboot(body)})


async def api_order(request: web.Request) -> web.Response:
  body = await _json_body(request)
  if body is None:
    return web.json_response({'ok': False, 'error': 'invalid JSON body'}, status=400)
  names = body.get('names')
  if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
    return web.json_response({'ok': False, 'error': 'names must be a list of strings'}, status=400)
  # model_bundle.write_small_order() drops anything that is not a selectable split
  # bundle, so no per-endpoint mode check is needed here.
  model_bundle.write_small_order(names)
  return web.json_response({'ok': True, **build_small_models_payload()})


async def api_remove(request: web.Request) -> web.Response:
  body = await _json_body(request)
  if body is None:
    return web.json_response({'ok': False, 'error': 'invalid JSON body'}, status=400)
  name = body.get('name')
  if not isinstance(name, str) or not name:
    return web.json_response({'ok': False, 'error': 'name required'}, status=400)

  path = model_bundle.bundle_dir(name)
  mode = model_bundle.bundle_mode(path)
  if mode is None:
    return web.json_response({'ok': False, 'error': f'unknown model bundle: {name}'}, status=404)
  if name == model_bundle.active_name():
    return web.json_response({'ok': False, 'error': 'cannot remove the fallback model'}, status=409)
  if name == model_bundle.active_big_name():
    return web.json_response({'ok': False, 'error': 'cannot remove the model in use'}, status=409)

  try:
    shutil.rmtree(path)
  except OSError as exc:
    return web.json_response({'ok': False, 'error': str(exc)}, status=500)

  # Drop it from the orders so a stale name cannot linger.
  model_bundle.write_small_order([n for n in model_bundle.read_small_order() if n != name])
  if model_bundle.selected_big_name() == name:
    model_bundle.write_big_selection(None)
  return web.json_response({'ok': True, **build_small_models_payload()})


def register(app: web.Application) -> None:
  app.router.add_get('/api/small-models', api_models)
  app.router.add_post('/api/small-models/select', api_select)
  app.router.add_post('/api/small-models/order', api_order)
  app.router.add_post('/api/small-models/remove', api_remove)
