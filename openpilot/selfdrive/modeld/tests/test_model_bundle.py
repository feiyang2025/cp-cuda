"""model_bundle: the writers are the safety boundary, so test them as such.

Every write path (web endpoints, legacy seed) goes through these functions, so a
non-selectable name must never end up persisted no matter who calls them.
"""
import pytest

from openpilot.selfdrive.modeld import model_bundle


@pytest.fixture
def models_dir(tmp_path, monkeypatch):
  d = tmp_path / "models"
  d.mkdir()
  monkeypatch.setattr(model_bundle, "MODELS_DIR", d)
  monkeypatch.setattr(model_bundle, "ORDER_FILE", d / ".small_order")
  monkeypatch.setattr(model_bundle, "LEGACY_SELECTION_FILE", d / ".active_model")
  monkeypatch.setattr(model_bundle, "BIG_SELECTION_FILE", d / ".active_big_model")
  monkeypatch.setattr(model_bundle, "BIG_FAILED_FILE", d / ".big_model_failed")
  return d


def _split(models_dir, name):
  d = models_dir / name
  d.mkdir()
  for f in model_bundle.REQUIRED_FILES:
    (d / f).write_bytes(b"x")
  return d


def _merged(models_dir, name):
  d = models_dir / name
  d.mkdir()
  for f in model_bundle.MERGED_REQUIRED_FILES:
    (d / f).write_bytes(b"x")
  (d / model_bundle.MERGED_ENGINE).write_bytes(b"x")
  return d


def test_merged_requires_the_engine(models_dir):
  _merged(models_dir, "Big")
  assert model_bundle.bundle_mode(models_dir / "Big") == "merged"

  # A directory holding only the ONNX/metadata is not runnable.
  only = models_dir / "OnlyOnnx"
  only.mkdir()
  (only / model_bundle.MERGED_REQUIRED_FILES[0]).write_bytes(b"x")
  assert model_bundle.bundle_mode(only) is None


def test_write_small_order_drops_non_split_names(models_dir):
  _split(models_dir, "A")
  _merged(models_dir, "B")
  model_bundle.write_small_order(["B", "A", "missing"])
  assert model_bundle.read_small_order() == ["A"]


def test_write_selection_rejects_non_split(models_dir):
  _merged(models_dir, "B")
  with pytest.raises(ValueError):
    model_bundle.write_selection("B")


def test_write_big_selection_validates_merged(models_dir):
  _split(models_dir, "A")
  _merged(models_dir, "B")
  with pytest.raises(ValueError):
    model_bundle.write_big_selection("A")

  model_bundle.write_big_selection("B")
  assert model_bundle.selected_big_name() == "B"
  model_bundle.write_big_selection(None)
  assert model_bundle.selected_big_name() is None


def test_legacy_seed_is_ignored_when_not_a_split_bundle(models_dir):
  _merged(models_dir, "B")
  (models_dir / ".active_model").write_text("B", encoding="utf-8")
  assert model_bundle.read_small_order() == []


def test_active_name_is_the_first_usable_split(models_dir):
  _split(models_dir, "A")
  _split(models_dir, "B")
  model_bundle.write_small_order(["B", "A"])
  assert model_bundle.active_name() == "B"


def test_active_big_name_clears_once_marked_failed(models_dir):
  _merged(models_dir, "B")
  model_bundle.write_big_selection("B")
  assert model_bundle.active_big_name() == "B"
  model_bundle.mark_big_failed("boom")
  assert model_bundle.active_big_name() is None


def test_incomplete_bundle_names_the_missing_files(models_dir, monkeypatch):
  from openpilot.selfdrive.modeld import modeld

  d = models_dir / "Half"
  d.mkdir()
  (d / "driving_vision_metadata.pkl").write_bytes(b"x")
  monkeypatch.setattr(modeld, "get_model_dir", lambda: d)
  with pytest.raises(model_bundle.ModelBundleIncomplete) as exc:
    modeld.ModelState(None)
  assert "driving_policy_metadata.pkl" in exc.value.missing
