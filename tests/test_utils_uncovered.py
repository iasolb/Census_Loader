"""Coverage for the remaining utils.py helper and edge branches.

These tests stay offline. Where a network/client boundary is involved, the
boundary itself is patched and the fake is asserted to have been used so a
missed patch fails loudly instead of quietly reaching outward.
"""

from pathlib import Path
import pickle

import pandas as pd
import pytest

from census_loader import ALL_SERIES
import census_loader.utils as utils
from census_loader.utils import Config, info, pickle_loader


def _write_pickle(tmp_path, payload, name="data.pkl"):
    path = tmp_path / name
    with open(path, "wb") as fh:
        pickle.dump(payload, fh)
    return path


def test_pickle_loader_returns_dataframe_payload_verbatim(tmp_path):
    df = pd.DataFrame({"state": ["25"], "value": [1]})
    path = _write_pickle(tmp_path, df)

    out = pickle_loader(path)

    pd.testing.assert_frame_equal(out, df)


@pytest.mark.parametrize("payload", [{}, []])
def test_pickle_loader_returns_empty_frame_for_empty_or_non_dict_payload(tmp_path, payload):
    path = _write_pickle(tmp_path, payload)

    out = pickle_loader(path)

    assert out.empty


def test_pickle_loader_returns_the_only_frame_in_a_dict(tmp_path):
    df = pd.DataFrame({"state": ["25"], "value": [1]})
    path = _write_pickle(tmp_path, {"Series A": df})

    out = pickle_loader(path)

    pd.testing.assert_frame_equal(out, df)


def test_pickle_loader_outer_merges_on_shared_text_columns(tmp_path):
    left = pd.DataFrame({"state": ["25"], "county": ["021"], "left_value": [1]})
    right = pd.DataFrame({"state": ["25"], "county": ["021"], "right_value": [2]})
    path = _write_pickle(tmp_path, {"Left": left, "Right": right})

    out = pickle_loader(path).sort_index(axis=1)
    expected = pd.DataFrame(
        {"state": ["25"], "county": ["021"], "left_value": [1], "right_value": [2]}
    ).sort_index(axis=1)

    pd.testing.assert_frame_equal(out, expected)


def test_pickle_loader_concatenates_when_only_shared_columns_are_numeric(tmp_path):
    alpha = pd.DataFrame({"value": [1], "alpha_only": [10]})
    beta = pd.DataFrame({"value": [2], "beta_only": [20]})
    path = _write_pickle(tmp_path, {"Alpha": alpha, "Beta": beta})

    out = pickle_loader(path)

    assert list(out["series"]) == ["Alpha", "Beta"]
    assert out.loc[0, "alpha_only"] == 10
    assert pd.isna(out.loc[0, "beta_only"])
    assert pd.isna(out.loc[1, "alpha_only"])
    assert out.loc[1, "beta_only"] == 20


def test_info_reports_group_series_as_full_table_group(capsys):
    key = next(k for k, (_, _, variables) in ALL_SERIES.items() if isinstance(variables, str))

    info(key)

    out = capsys.readouterr().out
    assert key in out
    assert "full table group" in out


def test_config_raises_when_geo_templates_cannot_be_loaded(monkeypatch, tmp_path):
    monkeypatch.setattr(utils, "geos", lambda quiet=True: None)

    with pytest.raises(ValueError, match="Failed to retrieve geo templates"):
        Config("out.csv", tmp_path, geo="state_all")


def test_config_raises_for_missing_county_and_tract(tmp_path):
    with pytest.raises(ValueError, match="requires parameters: county, tract"):
        Config("out.csv", tmp_path, geo="block_group_in_state", state="25")


def test_config_warns_on_large_batch_size_and_formats_preview_geo_and_series(capsys, tmp_path):
    series_keys = list(ALL_SERIES)[:5]
    config = Config(
        "out.csv",
        tmp_path,
        geo={"for": "tract:*", "in": "state:{st}&in=county:{co}"},
        series=series_keys,
        batch_size=99,
    )

    created = capsys.readouterr().out
    assert "batch_size=99" in created

    shown = str(config)
    assert " + 1 more" in shown
    assert "[" in shown and "]" in shown

    assert config.geo_formatted(st="Massachusetts", co="021") == {
        "for": "tract:*",
        "in": "state:25&in=county:021",
    }

    config.show_series()
    out = capsys.readouterr().out
    assert f"Resolved series ({len(config.SERIES)})" in out
    for key in series_keys:
        assert key in out


def test_pull_wrapped_uses_group_field_and_geo_filters():
    calls = []

    class FakeClient:
        def get(self, fields, geo, year=2022):
            calls.append((fields, geo, year))
            return [{"NAME": "Massachusetts", "state": "25"}]

    out = utils._pull_wrapped(
        FakeClient(),
        [],
        "B01001",
        {"for": "county:*", "in": "state:25"},
        2021,
    )

    assert calls == [(("group(B01001)",), {"for": "county:*", "in": "state:25"}, 2021)]
    assert out.to_dict(orient="records") == [{"NAME": "Massachusetts", "state": "25"}]


def test_pull_wrapped_uses_name_plus_var_list_without_geo_when_for_is_absent():
    calls = []

    class FakeClient:
        def get(self, fields, geo, year=2022):
            calls.append((fields, geo, year))
            return [{"NAME": "Massachusetts", "B01001_001E": "10"}]

    out = utils._pull_wrapped(FakeClient(), ["B01001_001E"], None, {"in": "state:25"}, 2022)

    assert calls == [(("NAME", "B01001_001E"), {}, 2022)]
    assert out.to_dict(orient="records") == [{"NAME": "Massachusetts", "B01001_001E": "10"}]


def test_pull_raw_formats_request_and_adds_year_for_timeseries(monkeypatch):
    request_calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [["NAME", "PCTUI", "state"], ["Massachusetts", "5.1", "25"]]

    def fake_get(url, params=None, timeout=None):
        request_calls.append((url, params, timeout))
        return FakeResponse()

    monkeypatch.setattr(utils.requests, "get", fake_get)

    out = utils._pull_raw(
        utils.RAW_ENDPOINTS["sahie"],
        ["PCTUI"],
        None,
        {"for": "state:*"},
        2023,
        "test-key",
    )

    assert len(request_calls) == 1
    url, params, timeout = request_calls[0]
    assert "timeseries/healthins/sahie" in url
    assert params == {"get": "NAME,PCTUI", "key": "test-key", "for": "state:*", "YEAR": "2023"}
    assert timeout == 120
    assert out.to_dict(orient="records") == [{"NAME": "Massachusetts", "PCTUI": "5.1", "state": "25"}]


def test_pull_raw_returns_empty_frame_when_api_rows_are_missing(monkeypatch):
    request_calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [["NAME", "state"]]

    def fake_get(url, params=None, timeout=None):
        request_calls.append((url, params, timeout))
        return FakeResponse()

    monkeypatch.setattr(utils.requests, "get", fake_get)

    out = utils._pull_raw(
        utils.RAW_ENDPOINTS["pep"],
        [],
        "PEPANNRES",
        {"for": "state:*"},
        2022,
        "test-key",
    )

    assert len(request_calls) == 1
    assert request_calls[0][1]["get"] == "group(PEPANNRES)"
    assert out.empty


def test_fetch_group_labels_uses_decennial_url_parses_labels_and_caches(monkeypatch):
    utils._group_label_cache.clear()
    request_urls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "variables": {
                    "B19001_001E": {"label": "Estimate!!Total:"},
                    "B19001_002E": {"label": "Estimate!!Total:!!Less than $10,000"},
                    "B19001_003E": {},
                }
            }

    def fake_get(url, timeout=None):
        request_urls.append((url, timeout))
        return FakeResponse()

    monkeypatch.setattr(utils.requests, "get", fake_get)

    first = utils._fetch_group_labels("B19001", "dec/pl", 2022)
    second = utils._fetch_group_labels("B19001", "dec/pl", 2022)

    assert len(request_urls) == 1
    assert request_urls[0] == (
        "https://api.census.gov/data/2020/dec/pl/groups/B19001.json",
        30,
    )
    assert first == second
    assert first["B19001_001E"] == "Total"
    assert first["B19001_002E"] == "Total - Less than $10,000"
    assert first["B19001_003E"] == "B19001_003E"


def test_fetch_group_labels_returns_empty_for_unknown_dataset():
    utils._group_label_cache.clear()

    assert utils._fetch_group_labels("B19001", "not-a-dataset", 2022) == {}


def test_fetch_group_labels_reports_failures_and_caches_empty(monkeypatch, capsys):
    utils._group_label_cache.clear()
    request_calls = []

    def fake_get(url, timeout=None):
        request_calls.append((url, timeout))
        raise RuntimeError("boom")

    monkeypatch.setattr(utils.requests, "get", fake_get)

    first = utils._fetch_group_labels("B19001", "acs5", 2022)
    second = utils._fetch_group_labels("B19001", "acs5", 2022)

    out = capsys.readouterr().out
    assert len(request_calls) == 1
    assert first == second == {}
    assert "label lookup failed for B19001 (acs5/2022): boom" in out
    assert "falling back to raw variable codes for this group" in out


def test_fetch_var_labels_groups_codes_by_table(monkeypatch):
    calls = []

    def fake_fetch_group_labels(group_name, dataset, year):
        calls.append((group_name, dataset, year))
        if group_name == "B25003":
            return {"B25003_001E": "Total", "B25003_002E": "Owner occupied"}
        if group_name == "S0101":
            return {"S0101_C01_001E": "Total population"}
        return {}

    monkeypatch.setattr(utils, "_fetch_group_labels", fake_fetch_group_labels)

    out = utils._fetch_var_labels(
        ["B25003_001E", "B25003_002E", "S0101_C01_001E", "UNKNOWN_001E"],
        "acs5",
        2022,
    )

    assert calls == [
        ("B25003", "acs5", 2022),
        ("S0101", "acs5", 2022),
        ("UNKNOWN", "acs5", 2022),
    ]
    assert out == {
        "B25003_001E": "Total",
        "B25003_002E": "Owner occupied",
        "S0101_C01_001E": "Total population",
    }


def test_clean_frame_disambiguates_colliding_multi_var_labels(monkeypatch):
    monkeypatch.setattr(
        utils,
        "_fetch_var_labels",
        lambda *a, **k: {"V1": "Repeated", "V2": "Repeated"},
    )

    df = pd.DataFrame({"state": ["25"], "V1": ["1"], "V2": ["2"]})

    out = utils._clean_frame(df, "series", ["V1", "V2"], None, dataset="acs5", year=2022)

    assert "series__Repeated" in out.columns
    assert "series__Repeated (V2)" in out.columns


def test_load_census_bureau_handles_census_client_init_failure(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)

    constructed = []
    sleep_calls = []

    def fake_census(key):
        constructed.append(key)
        raise RuntimeError("bad constructor")

    monkeypatch.setattr(utils, "Census", fake_census)
    monkeypatch.setattr(utils.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    config = Config("out.csv", tmp_path, series="TOTAL_POP", api_key="test-key")

    assert utils._load_census_bureau(config) is None
    assert constructed == ["test-key"]
    assert sleep_calls == []
    assert "Error initializing Census client: bad constructor" in capsys.readouterr().out


def test_load_census_bureau_continues_past_unknown_dataset(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(utils, "load_dotenv", lambda: None)

    constructed = []
    sleep_calls = []
    wrapped_calls = []

    class FakeCensus:
        def __init__(self, key):
            constructed.append(key)
            self.acs5 = object()

    def fake_wrapped(client_attr, var_list, group_name, geo, year):
        wrapped_calls.append((client_attr, var_list, group_name, geo, year))
        return pd.DataFrame({"NAME": ["Massachusetts"], "B01001_001E": ["10"], "state": ["25"]})

    monkeypatch.setattr(utils, "Census", FakeCensus)
    monkeypatch.setattr(utils, "_pull_wrapped", fake_wrapped)
    monkeypatch.setattr(utils, "_fetch_group_labels", lambda *a: {})
    monkeypatch.setattr(utils, "_fetch_var_labels", lambda *a: {})
    monkeypatch.setattr(utils.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    config = Config(
        "out.csv",
        tmp_path,
        series={
            "GOOD": ("Good", "acs5", ("B01001_001E",)),
            "BAD": ("Bad", "not-real", ("X",)),
        },
        api_key="test-key",
    )

    out = utils._load_census_bureau(config)

    assert constructed == ["test-key"]
    assert len(wrapped_calls) == 1
    assert sleep_calls == [0.5, 0.5]
    assert set(out) == {"Good"}
    stdout = capsys.readouterr().out
    assert "Unknown dataset 'not-real' for BAD" in stdout
    assert "Loaded 1 series  |  1 failed" in stdout
