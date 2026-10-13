"""Small-model bundle selection.

modeld loads a bundle directory, `models/<Name>/`, holding the vision/policy
metadata, the tinygrad pickles and the TensorRT plans. The order has to come from
somewhere writable, and this tree's Params registry has no "Model" key
(`get`/`put` both raise UnknownKeyName) - registering one would force a native
rebuild - so it is kept in a plain file next to the bundles.

The pick is an ORDERED list: the first usable split bundle is the fallback modeld
starts when no fused big model runs, so "put it on top" and "make it the
fallback" are the same action.

Precedence used by modeld:
    MODEL_NAME env  ->  first usable entry of the order  ->  DEFAULT_NAME
"""
from __future__ import annotations

import os
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent / "models"
ORDER_FILE = MODELS_DIR / ".small_order"              # ordered split bundles (newline separated)
LEGACY_SELECTION_FILE = MODELS_DIR / ".active_model"  # single-name pick from the first revision
BIG_SELECTION_FILE = MODELS_DIR / ".active_big_model"  # big (merged/fused) bundle
DEFAULT_NAME = "CD210"
# Set when the fused big engine failed to load: modeld then starts the small
# bundle instead of restart-looping on an engine that will fail again. Cleared
# by re-selecting the big model from the web picker.
BIG_FAILED_FILE = MODELS_DIR / ".big_model_failed"

# A usable bundle must carry the metadata modeld reads at startup; a half-copied
# directory is ignored rather than silently becoming selectable.
REQUIRED_FILES = (
  "driving_vision_metadata.pkl",
  "driving_policy_metadata.pkl",
)
# The merged (fused, single-engine) layout used by modeld_bigcombo: it is
# dispatched by the name "BigCombo" and reads models/BigCombo.
MERGED_REQUIRED_FILES = ("big_driving_supercombo_metadata.pkl",)
MERGED_ENGINE = "driving_supercombo_fp16.plan"
MERGED_NAME = "BigCombo"


class ModelBundleIncomplete(Exception):
  """A bundle directory exists but lacks files needed to load it."""

  def __init__(self, name: str, missing):
    self.name = name
    self.missing = list(missing)
    super().__init__(f"model bundle {name!r} is incomplete; missing {self.missing}")


def read_small_order() -> list[str]:
  """The user's ordered fallback list (first entry wins), de-duplicated."""
  names: list[str] = []
  try:
    text = ORDER_FILE.read_text(encoding="utf-8")
  except OSError:
    # First run after the single-name revision: seed from that file, but only
    # when it still names a selectable split bundle.
    legacy = _read_name(LEGACY_SELECTION_FILE)
    return [legacy] if legacy and _is_split(legacy) else []
  for line in text.splitlines():
    name = line.strip()
    if name and name not in names:
      names.append(name)
  return names


def _is_split(name: str) -> bool:
  return bundle_mode(MODELS_DIR / name) == "split"


def _is_merged(name: str) -> bool:
  return bundle_mode(MODELS_DIR / name) == "merged"


def write_small_order(names) -> None:
  """Persist the ordered fallback list (empty clears it).

  Names that are not selectable split bundles are dropped here rather than at
  the callers, so no endpoint, the web UI or a legacy seed can put a
  merged/unknown name into the list.
  """
  cleaned: list[str] = []
  for name in names or []:
    name = str(name).strip()
    if name and name not in cleaned and _is_split(name):
      cleaned.append(name)
  if cleaned:
    ORDER_FILE.parent.mkdir(parents=True, exist_ok=True)
    ORDER_FILE.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
  else:
    try:
      ORDER_FILE.unlink()
    except FileNotFoundError:
      pass
  # The single-name file from the first revision would otherwise keep seeding the
  # order from read_small_order().
  try:
    LEGACY_SELECTION_FILE.unlink()
  except FileNotFoundError:
    pass


def selected_name() -> str | None:
  """Highest-priority entry of the fallback list, or None."""
  order = read_small_order()
  return order[0] if order else None


def write_selection(name: str | None) -> None:
  """Move *name* to the top of the fallback list (None clears the whole list).

  Unlike write_small_order this rejects a non-selectable name: the caller is
  naming one specific bundle, so a bad name is an error, not something to filter.
  """
  if not name:
    write_small_order([])
    return
  name = str(name).strip()
  if not name:
    return
  if not _is_split(name):
    raise ValueError(f"not a selectable fallback bundle: {name}")
  order = [n for n in read_small_order() if n != name]
  write_small_order([name, *order])


def _first_usable(order: list[str], mode: str) -> str | None:
  for name in order:
    if bundle_mode(MODELS_DIR / name) == mode:
      return name
  return None


def active_name() -> str:
  """Fallback bundle modeld starts: env override, else the first usable entry."""
  env = os.getenv("MODEL_NAME")
  if env:
    return env
  return _first_usable(read_small_order(), "split") or DEFAULT_NAME


def _read_name(path: Path) -> str | None:
  try:
    name = path.read_text(encoding="utf-8").strip()
  except OSError:
    return None
  return name or None


def _write_name(path: Path, name: str | None) -> None:
  if name:
    name = name.strip()
    if not name:
      return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(name + "\n", encoding="utf-8")
  else:
    try:
      path.unlink()
    except FileNotFoundError:
      pass


def selected_big_name() -> str | None:
  """The selected fused (merged) big-model bundle, or None."""
  return os.getenv("BIG_MODEL_NAME") or _read_name(BIG_SELECTION_FILE)


def write_big_selection(name: str | None) -> None:
  """Persist the big-model pick and clear any previous failure marker.

  A name that is not a usable merged bundle (metadata + engine present) is
  rejected: selecting a directory that cannot load would only fail at boot.
  """
  if name:
    name = str(name).strip()
    if name and not _is_merged(name):
      raise ValueError(f"not a selectable big-model bundle: {name}")
  _write_name(BIG_SELECTION_FILE, name)
  clear_big_failed()


def active_big_name() -> str | None:
  """The fused bundle modeld should try first, or None to go straight to small.

  Returns None once the engine has failed to load, so a broken big model cannot
  keep modeld from starting - the small bundle takes over until the user picks
  the big one again (write_big_selection clears the marker).
  """
  name = selected_big_name()
  if not name or big_failed_reason() is not None:
    return None
  return name


def mark_big_failed(reason: str | None = None) -> None:
  try:
    BIG_FAILED_FILE.write_text((reason or "").strip() + "\n", encoding="utf-8")
  except OSError:
    pass


def clear_big_failed() -> None:
  try:
    BIG_FAILED_FILE.unlink()
  except FileNotFoundError:
    pass


def big_failed_reason() -> str | None:
  try:
    text = BIG_FAILED_FILE.read_text(encoding="utf-8").strip()
  except OSError:
    return None
  return text or None


def bundle_dir(name: str) -> Path:
  return MODELS_DIR / name


def bundle_mode(path: Path) -> str | None:
  """'split', 'merged', or None when the directory is not a usable bundle.

  merged requires the engine next to the metadata: a directory holding only the
  ONNX is not runnable, so it must not be selectable.
  """
  if not path.is_dir():
    return None
  if all((path / f).is_file() for f in REQUIRED_FILES):
    return "split"
  if all((path / f).is_file() for f in MERGED_REQUIRED_FILES) and (path / MERGED_ENGINE).is_file():
    return "merged"
  return None


def is_bundle(path: Path) -> bool:
  return bundle_mode(path) is not None


def list_bundles() -> list[dict]:
  """Every usable bundle, annotated with its key files and whether it is active.

  Split bundles come back in fallback order (the user's order first, then the
  rest) so the web picker can render an ordered list.
  """
  active = active_name()
  order = read_small_order()
  big_active = active_big_name()

  found: dict[str, dict] = {}
  try:
    entries = sorted(MODELS_DIR.iterdir())
  except OSError:
    return []
  for path in entries:
    if path.name.startswith("."):
      continue
    mode = bundle_mode(path)
    if mode is None:
      continue
    files = {f.name: f.stat().st_size for f in path.iterdir() if f.is_file()}
    found[path.name] = {
      "name": path.name,
      "active": path.name == active,
      "big_active": path.name == big_active,
      "mode": mode,
      "vision_trt": (path / "driving_vision_fp16.plan").is_file(),
      "policy_trt": (path / "driving_policy_fp16.plan").is_file(),
      "merged_trt": (path / MERGED_ENGINE).is_file(),
      "size": sum(files.values()),
      "files": sorted(files),
    }

  splits = [name for name, item in found.items() if item["mode"] == "split"]
  ranked = [n for n in order if n in splits] + [n for n in sorted(splits) if n not in order]
  merged = [name for name, item in found.items() if item["mode"] == "merged"]
  return [found[n] for n in ranked + sorted(merged)]
