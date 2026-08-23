from pathlib import Path

import pandas as pd
import pytest

import census_loader.utils as utils
from census_loader.series import GEO
from census_loader.utils import Config


def test_geos_reports_required_parameters():
    result = utils.geos(quiet=True)
    assert result["state_all"] == "None"
    assert result["county_in_state"] == "state"
    assert result["block_group_in_state"] == "state, county, tract"
    assert set(result) == set(GEO)


def test_config_formats_state_name_to_fips():
    config = Config("out.csv", Path("."), geo="county_in_state", state="Massachusetts")
    assert config.GEO == {"for": "county:*", "in": "state:25"}


def test_config_accepts_fips_and_preserves_county_and_tract():
    config = Config(
        "out.csv",
        Path("."),
        geo="block_group_in_state",
        state="25",
        county="017",
        tract="4041.00",
    )
    assert config.GEO["in"] == "state:25&in=county:017&in=tract:4041.00"


def test_config_reports_missing_geography_parameter(capsys):
    config = Config("out.csv", Path("."), geo="county_in_state")
    captured = capsys.readouterr().out
    assert config.GEO == {}
    assert "requires parameters: state" in captured


def test_missing_api_key_is_named_and_actionable(monkeypatch, capsys):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)
    config = Config("out.csv", Path("."), series="TOTAL_POP")

    assert utils._load_census_bureau(config) is None
    assert "CENSUS_API_KEY not found" in capsys.readouterr().out


def test_network_paths_are_stubbed(monkeypatch):
    calls = {"raw": [], "wrapped": [], "groups": [], "vars": []}

    def fake_raw(*args):
        calls["raw"].append(args)
        return pd.DataFrame([["Raw place", "1"]], columns=["NAME", "X"])

    def fake_wrapped(*args):
        calls["wrapped"].append(args)
        return pd.DataFrame([["Wrapped place", "2"]], columns=["NAME", "Y"])

    def fake_groups(*args):
        calls["groups"].append(args)
        return {"Y": "Y label"}

    def fake_vars(*args):
        calls["vars"].append(args)
        return {"X": "X label"}

    class FakeCensus:
        def __init__(self, key):
            assert key == "test-key"

        acs5 = object()

    monkeypatch.setattr(utils, "Census", FakeCensus)
    monkeypatch.setattr(utils, "_pull_raw", fake_raw)
    monkeypatch.setattr(utils, "_pull_wrapped", fake_wrapped)
    monkeypatch.setattr(utils, "_fetch_group_labels", fake_groups)
    monkeypatch.setattr(utils, "_fetch_var_labels", fake_vars)
    monkeypatch.setattr(utils.time, "sleep", lambda _: None)

    series = {
        "GROUP": ("Group", "acs5", "group(B01003)"),
        "RAW": ("Raw", "pep", ("X", "Z")),
    }
    config = Config("out.csv", Path("."), geo={"for": "place:*"}, series=series, api_key="test-key")
    result = utils._load_census_bureau(config)

    assert set(result) == {"Group", "Raw"}
    assert calls["wrapped"] == [(FakeCensus.__dict__.get("acs5"), [], "B01003", {"for": "place:*"}, 2022)]
    assert calls["raw"][0][1:] == (["X", "Z"], None, {"for": "place:*"}, 2022, "test-key")
    assert calls["groups"] == [("B01003", "acs5", 2022)]
    assert calls["vars"] == [(["X", "Z"], "pep", 2022)]
