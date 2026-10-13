"""Where the big model and its precompiled artifacts are served from.

Kept in its own file so switching mirrors does not require touching big_model.py:
only this one small module changes.

precompiled.json and firmware/amdgpu are resolved relative to the model URL (see
precompiled_model.ensure_precompiled / firmware.ensure_firmware), so keep the
model file inside <base>/models/.

This module is fork-only: big_model.py only calls pinned_manifest() at the top of
fetch_manifest(). Keep it that way, so a merge cannot conflict on the pin.

Known intentional divergences in upstream files (all "plain http mirror" relaxations,
deletable once the mirror serves TLS, and all greppable by `not in ("http", "https")`):
  * big_model.BigModelManifest.from_dict  - accepts http as well as https
  * big_model.wait_for_manifest_network   - accepts http, and defaults the port by scheme
  * precompiled_model.validate_catalog    - accepts http artifacts on the catalog origin
"""
from __future__ import annotations

MODEL_BASE = "http://op.gitop.vip:82/egpu"

# The branch's own pin, and the extra checkpoints the model picker may offer.
PINNED_MODEL = {
  "model_id": "comma-pr38823-cinque-v2-37bfa141-09d080f3",
  "filename": "big_driving_supercombo.onnx",
  "size": 766_040_736,
  "sha256": "09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec",
  # precompiled.json and firmware/amdgpu resolve relative to this URL, so each
  # model keeps its own directory under egpu/models/.
  "url": f"{MODEL_BASE}/models/cinque-v2/big_driving_supercombo.onnx",
}

OPTIONAL_MODELS = (
  {
    "model_id": "comma-pr38932-cinque-v3-892fc3a1-e758b96d",
    "filename": "big_driving_tinygrad.pkl",
    "size": 776_634_338,
    "sha256": "e758b96df27858ea97122d18554930d04f9f8bda417417074edfb3a72b008d0b",
    # Self-hosted like the pin: precompiled.json and precompiled-runtime.tar.gz
    # resolve relative to this URL.
    "url": f"{MODEL_BASE}/models/cinque-v3/big_driving_tinygrad.pkl",
    # Picker metadata (ignored by BigModelManifest.from_dict): the short name this
    # model is listed under, and that it belongs at the top of the list.
    "label": "CTM V3",
    "picker_first": True,
  },
)

# Big driving models that the remote catalog (op.gitop.vip .../catalog.json) does
# not list. Served from comma's HuggingFace model repo through the hf-mirror
# mirror; the web model manager merges these into the picker, so a new model only
# needs one entry here to become selectable and downloadable anywhere. sha256 is
# the file's git-lfs oid, i.e. the digest the downloader verifies.
#
# These are stateful ("generic") exports - new_img/desire/action_t/traffic_convention
# + state_*, next_state_* out - which build_trt_bundle now compiles (uint8 retyped
# fp16) and stateful_model_state runs, so they are offered as compilable.
HF_MIRROR = "https://hf-mirror.com/commaai/openpilot_driving_models/resolve/main"
BUILTIN_MODELS = (
  {
    "label": "cinque-v3 (HF)",
    "model_id": "comma-pr38932-cinque-v3-hf",
    "filename": "big_driving_supercombo.onnx",
    "size": 766_354_845,
    "sha256": "404a18cfd86d29637d20c697dfde245bb47c666ae016730ab674c65f4d1e1aa4",
    "url": f"{HF_MIRROR}/f78ed37d-afad-4dbc-8050-40ea885eedde/12864/big_driving_supercombo.onnx",
  },
  {
    "label": "HF 导出 1a421175",
    "model_id": "comma-hf-1a421175",
    "filename": "big_driving_supercombo.onnx",
    "size": 766_320_181,
    "sha256": "c7b300083b8dd6ce17545ef52edb6b577e3a805e6372f9f9343090604690242f",
    "url": f"{HF_MIRROR}/1a421175-db71-4e3d-9d62-e2166421b02b/12864/big_driving_supercombo.onnx",
  },
  {
    "label": "HF 导出 870a4823",
    "model_id": "comma-hf-870a4823",
    "filename": "big_driving_supercombo.onnx",
    "size": 792_487_890,
    "sha256": "c392ba1aa1b4b89e850366024fa6c1beac1f1fdc3a7182e3c3b0234c55e08eeb",
    "url": f"{HF_MIRROR}/870a4823-d2ec-4b9a-8015-b947e9901fc7/12864/big_driving_supercombo.onnx",
  },
)

# Schemes the model server may use. Upstream insists on https; this fork's mirror is
# plain http on a LAN, and integrity comes from the mandatory sha256 checks instead.
MODEL_SCHEMES = ("http", "https")


def builtin_manifests() -> list:
  """Validated dicts for BUILTIN_MODELS; a bad entry is skipped, not raised.

  Plain dicts (not manifests) so the caller keeps the 'label' field; used by the
  web model manager so these models are listed even when the remote catalog does
  not know them.
  """
  out = []
  for meta in BUILTIN_MODELS:
    try:
      manifest_from_dict(meta)  # validate
    except Exception:
      continue
    out.append(dict(meta))
  return out


def manifest_from_dict(meta: dict):
  """Build a BigModelManifest from one of the dicts above (lazy: no import cycle)."""
  from openpilot.selfdrive.modeld.big_model import BigModelManifest
  return BigModelManifest.from_dict(dict(meta), meta.get("url", ""))


def optional_manifests() -> list:
  """Validated manifests for OPTIONAL_MODELS; a bad entry is skipped, not raised."""
  out = []
  for meta in OPTIONAL_MODELS:
    try:
      out.append(manifest_from_dict(meta))
    except Exception:
      continue
  return out


def _picker_meta() -> tuple[dict[str, str], tuple[str, ...]]:
  """(sha -> short name, leading shas) collected from the pin and the optional models."""
  labels: dict[str, str] = {}
  leading: list[str] = []
  for meta in (PINNED_MODEL, *OPTIONAL_MODELS):
    sha = meta.get("sha256")
    if not isinstance(sha, str):
      continue
    if isinstance(label := meta.get("label"), str) and label:
      labels.setdefault(sha, label)
    if meta.get("picker_first"):
      leading.append(sha)
  return labels, tuple(dict.fromkeys(leading))


def label_for(sha256: str | None, model_id: str | None = None) -> str | None:
  """Short name for the model picker, or None to keep the caller's fallback.

  The on-device index has no label field and the server catalog may be unreachable
  (LAN mirror down, factory-fresh device), so the branch's own models are named here;
  a label from the server catalog still wins (see egpu_model_select.build_models_payload).
  """
  labels, _ = _picker_meta()
  return labels.get(sha256) if isinstance(sha256, str) else None


def picker_rank(sha256: str | None) -> int:
  """Sort key for the model picker: 0 for the models that are listed first."""
  _, leading = _picker_meta()
  return 0 if isinstance(sha256, str) and sha256 in leading else 1


def pinned_manifest(manifest_url: str):
  """The manifest fetch_manifest() should use, or None to keep upstream's logic.

  A pick in the web UI wins over the pin. An explicit manifest_url (CLI/env
  override) is left to upstream, so this only answers for the branch's default.
  """
  from openpilot.selfdrive.modeld.big_model import DEFAULT_MANIFEST_URL
  from openpilot.selfdrive.modeld.model_catalog import selected_manifest

  chosen = selected_manifest()
  if chosen is not None:
    return chosen
  if manifest_url != DEFAULT_MANIFEST_URL:
    return None
  try:
    return manifest_from_dict(PINNED_MODEL)
  except Exception:
    return None
