"""
Tests for the Census Bureau pull loop and network entry point.

All network calls are faked at the boundary:
  - census_loader.utils.Census  (wrapped client constructor)
  - census_loader.utils.requests.get  (raw HTTP calls)
  - census_loader.utils.time.sleep    (rate-limit delay)
  - census_loader.utils.load_dotenv   (must not touch .env)

No real API key is used. If a patch is missed the test fails loudly.
"""

from pathlib import Path

import pandas as pd
import pytest

import census_loader.utils as utils
from census_loader.utils import Config, DATASET_DISPATCH, _load_census_bureau
from census_loader import load as load_module


# ── Shared fake shapes ────────────────────────────────────────────────────────

_FAKE_RAW_ROWS = [["NAME", "B01001_001E", "state"], ["Massachusetts", "7000000", "25"]]


def _fake_response(rows=None):
    """Return a minimal fake requests.Response."""
    if rows is None:
        rows = _FAKE_RAW_ROWS

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return rows

    return _Resp()


def _make_fake_census_class(key_check=None):
    """
    Build a FakeCensus class that records construction.
    *key_check* – if given, assert the key matches that value.
    """

    class FakeCensus:
        constructed_with = []

        def __init__(self, key):
            if key_check is not None:
                assert key == key_check, f"Census() got key={key!r}, expected {key_check!r}"
            FakeCensus.constructed_with.append(key)
            # Provide stub dataset attrs used by DATASET_DISPATCH lambdas
            self.acs5 = _FakeClient("acs5")
            self.acs5st = _FakeClient("acs5st")
            self.acs5dp = _FakeClient("acs5dp")
            self.acs1 = _FakeClient("acs1")

    return FakeCensus


class _FakeClient:
    """Mimics a census package sub-client (e.g. c.acs5)."""

    def __init__(self, name):
        self._name = name
        self.calls = []

    def get(self, fields, geo, year=2022):
        self.calls.append((fields, geo, year))
        # Return a list-of-dicts (what the wrapped client returns)
        row = {"NAME": "Massachusetts", "state": "25"}
        for f in fields:
            if f not in row:
                row[f] = "123"
        return [row]


# ── 1. API-key guard ─────────────────────────────────────────────────────────

def test_missing_api_key_returns_none_and_names_variable(monkeypatch, capsys):
    """With CENSUS_API_KEY absent and load_dotenv a no-op, returns None."""
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)

    cfg = Config("out.pkl", Path("."), series="TOTAL_POP")
    result = _load_census_bureau(cfg)

    assert result is None
    out = capsys.readouterr().out
    assert "CENSUS_API_KEY" in out


# ── 2. Explicit key on Config is preferred over environment ──────────────────

def test_explicit_api_key_takes_precedence(monkeypatch, capsys):
    """Config.api_key is used even when CENSUS_API_KEY env is not set."""
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)
    monkeypatch.setattr(utils.time, "sleep", lambda _: None)

    FakeCensus = _make_fake_census_class(key_check="explicit-key")
    monkeypatch.setattr(utils, "Census", FakeCensus)
    monkeypatch.setattr(utils, "_pull_wrapped", lambda *a: pd.DataFrame({"NAME": ["MA"], "state": ["25"]}))
    monkeypatch.setattr(utils, "_fetch_group_labels", lambda *a: {})
    monkeypatch.setattr(utils, "_fetch_var_labels", lambda *a: {})

    series = {"TOTAL_POP": ("Total Population", "acs5", ("B01001_001E",))}
    cfg = Config("out.pkl", Path("."), series=series, api_key="explicit-key")
    result = _load_census_bureau(cfg)

    assert result is not None
    assert FakeCensus.constructed_with == ["explicit-key"]


# ── 3. Successful pull of two series returns a dict keyed by friendly names ──

def test_successful_pull_returns_frames_keyed_by_friendly_name(monkeypatch):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)
    monkeypatch.setattr(utils.time, "sleep", lambda _: None)

    FakeCensus = _make_fake_census_class()
    monkeypatch.setattr(utils, "Census", FakeCensus)

    wrapped_calls = []

    def fake_wrapped(client_attr, var_list, group_name, geo, year):
        wrapped_calls.append((var_list, group_name))
        return pd.DataFrame({"NAME": ["Massachusetts"], "B01001_001E": ["7000000"], "state": ["25"]})

    monkeypatch.setattr(utils, "_pull_wrapped", fake_wrapped)
    monkeypatch.setattr(utils, "_fetch_group_labels", lambda *a: {})
    monkeypatch.setattr(utils, "_fetch_var_labels", lambda *a: {})

    series = {
        "SER_A": ("Series Alpha", "acs5", ("B01001_001E",)),
        "SER_B": ("Series Beta", "acs5", ("B01001_002E",)),
    }
    cfg = Config("out.pkl", Path("."), series=series, api_key="test-key")
    result = _load_census_bureau(cfg)

    assert result is not None
    assert set(result.keys()) == {"Series Alpha", "Series Beta"}
    assert isinstance(result["Series Alpha"], pd.DataFrame)
    assert isinstance(result["Series Beta"], pd.DataFrame)
    assert len(wrapped_calls) == 2


# ── 4. One failing series does not abort the rest ────────────────────────────

def test_one_failing_series_does_not_abort_others(monkeypatch, capsys):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)
    monkeypatch.setattr(utils.time, "sleep", lambda _: None)

    monkeypatch.setattr(utils, "Census", _make_fake_census_class())

    def fake_wrapped(client_attr, var_list, group_name, geo, year):
        if "FAIL" in var_list:
            raise RuntimeError("simulated network error")
        return pd.DataFrame({"NAME": ["MA"], "GOOD": ["1"], "state": ["25"]})

    monkeypatch.setattr(utils, "_pull_wrapped", fake_wrapped)
    monkeypatch.setattr(utils, "_fetch_group_labels", lambda *a: {})
    monkeypatch.setattr(utils, "_fetch_var_labels", lambda *a: {})

    series = {
        "GOOD_SER": ("Good Series", "acs5", ("GOOD",)),
        "BAD_SER":  ("Bad Series",  "acs5", ("FAIL",)),
    }
    cfg = Config("out.pkl", Path("."), series=series, api_key="test-key")
    result = _load_census_bureau(cfg)

    assert result is not None
    assert "Good Series" in result
    assert "Bad Series" not in result

    out = capsys.readouterr().out
    assert "BAD_SER" in out or "Bad Series" in out


# ── 5. Rate-limit delay is called once per series ────────────────────────────

def test_rate_limit_sleep_called_once_per_series(monkeypatch):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)

    sleep_calls = []
    monkeypatch.setattr(utils.time, "sleep", lambda t: sleep_calls.append(t))

    monkeypatch.setattr(utils, "Census", _make_fake_census_class())
    monkeypatch.setattr(utils, "_pull_wrapped", lambda *a: pd.DataFrame({"NAME": ["MA"], "X": ["1"], "state": ["25"]}))
    monkeypatch.setattr(utils, "_fetch_group_labels", lambda *a: {})
    monkeypatch.setattr(utils, "_fetch_var_labels", lambda *a: {})

    series = {
        "S1": ("Name1", "acs5", ("X",)),
        "S2": ("Name2", "acs5", ("X",)),
        "S3": ("Name3", "acs5", ("X",)),
    }
    cfg = Config("out.pkl", Path("."), series=series, api_key="test-key")
    _load_census_bureau(cfg)

    assert len(sleep_calls) == 3


# ── 5b. Sleep is called even when a series fails ────────────────────────────

def test_rate_limit_sleep_called_on_failure_too(monkeypatch):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)

    sleep_calls = []
    monkeypatch.setattr(utils.time, "sleep", lambda t: sleep_calls.append(t))
    monkeypatch.setattr(utils, "Census", _make_fake_census_class())

    def fake_wrapped(*a):
        raise RuntimeError("boom")

    monkeypatch.setattr(utils, "_pull_wrapped", fake_wrapped)
    monkeypatch.setattr(utils, "_fetch_group_labels", lambda *a: {})
    monkeypatch.setattr(utils, "_fetch_var_labels", lambda *a: {})

    series = {
        "FAIL1": ("Fail1", "acs5", ("X",)),
        "FAIL2": ("Fail2", "acs5", ("Y",)),
    }
    cfg = Config("out.pkl", Path("."), series=series, api_key="test-key")
    _load_census_bureau(cfg)

    assert len(sleep_calls) == 2


# ── 6. Group pull vs variable-list pull take different paths ─────────────────

def test_group_pull_passes_group_name_in_request(monkeypatch):
    """When variables is 'group(BXXXXX)', the group path is taken."""
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)
    monkeypatch.setattr(utils.time, "sleep", lambda _: None)
    monkeypatch.setattr(utils, "Census", _make_fake_census_class())

    wrapped_calls = []

    def fake_wrapped(client_attr, var_list, group_name, geo, year):
        wrapped_calls.append({"var_list": var_list, "group_name": group_name})
        return pd.DataFrame({"NAME": ["MA"], "state": ["25"]})

    monkeypatch.setattr(utils, "_pull_wrapped", fake_wrapped)
    monkeypatch.setattr(utils, "_fetch_group_labels", lambda *a: {})

    series = {"GRP": ("Group Pull", "acs5", "group(B01001)")}
    cfg = Config("out.pkl", Path("."), series=series, api_key="test-key")
    _load_census_bureau(cfg)

    assert len(wrapped_calls) == 1
    call = wrapped_calls[0]
    assert call["group_name"] == "B01001"
    assert call["var_list"] == []


def test_variable_list_pull_passes_var_list_in_request(monkeypatch):
    """When variables is a tuple, the var-list path is taken."""
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)
    monkeypatch.setattr(utils.time, "sleep", lambda _: None)
    monkeypatch.setattr(utils, "Census", _make_fake_census_class())

    wrapped_calls = []

    def fake_wrapped(client_attr, var_list, group_name, geo, year):
        wrapped_calls.append({"var_list": var_list, "group_name": group_name})
        return pd.DataFrame({"NAME": ["MA"], "B01001_001E": ["7000000"], "state": ["25"]})

    monkeypatch.setattr(utils, "_pull_wrapped", fake_wrapped)
    monkeypatch.setattr(utils, "_fetch_group_labels", lambda *a: {})
    monkeypatch.setattr(utils, "_fetch_var_labels", lambda *a: {})

    series = {"VAR": ("Var Pull", "acs5", ("B01001_001E", "B01001_002E"))}
    cfg = Config("out.pkl", Path("."), series=series, api_key="test-key")
    _load_census_bureau(cfg)

    assert len(wrapped_calls) == 1
    call = wrapped_calls[0]
    assert call["group_name"] is None
    assert "B01001_001E" in call["var_list"]


# ── 7. Dispatch routes to wrapped client vs raw endpoint ─────────────────────

def test_dispatch_wrapped_and_raw_take_different_paths(monkeypatch):
    """
    acs5 → callable dispatch → _pull_wrapped
    pep  → string URL → _pull_raw

    Uses real DATASET_DISPATCH keys.
    """
    assert "acs5" in DATASET_DISPATCH
    assert callable(DATASET_DISPATCH["acs5"])
    assert "pep" in DATASET_DISPATCH
    assert isinstance(DATASET_DISPATCH["pep"], str)

    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)
    monkeypatch.setattr(utils.time, "sleep", lambda _: None)
    monkeypatch.setattr(utils, "Census", _make_fake_census_class())

    wrapped_calls = []
    raw_calls = []

    def fake_wrapped(client_attr, var_list, group_name, geo, year):
        wrapped_calls.append((var_list, group_name))
        return pd.DataFrame({"NAME": ["MA"], "B01001_001E": ["1"], "state": ["25"]})

    def fake_raw(url_template, var_list, group_name, geo, year, api_key):
        raw_calls.append((url_template, var_list))
        return pd.DataFrame({"NAME": ["MA"], "POP": ["1"], "state": ["25"]})

    monkeypatch.setattr(utils, "_pull_wrapped", fake_wrapped)
    monkeypatch.setattr(utils, "_pull_raw", fake_raw)
    monkeypatch.setattr(utils, "_fetch_group_labels", lambda *a: {})
    monkeypatch.setattr(utils, "_fetch_var_labels", lambda *a: {})

    series = {
        "ACS_SER": ("ACS Series",  "acs5", ("B01001_001E",)),
        "PEP_SER": ("PEP Series",  "pep",  ("POP",)),
    }
    cfg = Config("out.pkl", Path("."), series=series, api_key="test-key")
    result = _load_census_bureau(cfg)

    assert result is not None
    assert "ACS Series" in result
    assert "PEP Series" in result
    assert len(wrapped_calls) == 1
    assert len(raw_calls) == 1
    # The raw call must have received the pep URL template
    assert "pep" in raw_calls[0][0].lower() or "charv" in raw_calls[0][0].lower()


# ── 8. pull_census end-to-end with tmp_path ──────────────────────────────────

def test_pull_census_end_to_end_writes_pickle(monkeypatch, tmp_path):
    """
    pull_census() should return the frames dict AND write a .pkl into
    tmp_path.  No writes outside tmp_path.
    """
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)
    monkeypatch.setattr(utils.time, "sleep", lambda _: None)
    monkeypatch.setattr(utils, "Census", _make_fake_census_class())

    def fake_wrapped(client_attr, var_list, group_name, geo, year):
        return pd.DataFrame({"NAME": ["MA"], "B01001_001E": ["7000000"], "state": ["25"]})

    monkeypatch.setattr(utils, "_pull_wrapped", fake_wrapped)
    monkeypatch.setattr(utils, "_fetch_group_labels", lambda *a: {})
    monkeypatch.setattr(utils, "_fetch_var_labels", lambda *a: {})

    series = {"TOTAL_POP": ("Total Population", "acs5", ("B01001_001E",))}
    cfg = Config(
        filename="census_test.pkl",
        output_path=tmp_path,
        series=series,
        api_key="test-key",
    )

    result = load_module.pull_census(cfg)

    assert result is not None
    assert "Total Population" in result
    assert isinstance(result["Total Population"], pd.DataFrame)

    pkl_file = tmp_path / "census_test.pkl"
    assert pkl_file.exists(), "pull_census must write a .pkl into OUTPUT_PATH"

    import pickle
    with open(pkl_file, "rb") as f:
        loaded = pickle.load(f)
    assert "Total Population" in loaded
