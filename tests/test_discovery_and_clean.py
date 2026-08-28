"""Coverage for the discovery helpers, the series resolver, and frame cleaning.

Written against measured coverage: utils.py sat at 52% with `available`,
`search`, `info`, `geos` and most of `_clean_frame`'s parsing untested.

The discovery helpers are the library's whole selling point (readable names
instead of raw Census codes), and they only print, so nothing else would ever
catch them breaking. `_clean_frame` is where a wrong answer is most expensive,
because it renames and reshapes real data quietly.

Offline: `_clean_frame` and the resolver are pure, and the label lookups that
would hit the network are not exercised here.
"""

import pandas as pd
import pytest

from census_loader import ALL_SERIES, CATEGORIES, SUBCATEGORIES
from census_loader.series import GEO
from census_loader.utils import (
    _clean_frame,
    _parse_variables,
    _resolve_one,
    available,
    geos,
    info,
    resolve_series,
    search,
)


def a_series_key():
    """A real key from the catalog, so the tests do not hardcode one that may
    be renamed."""
    return next(iter(ALL_SERIES))


# ── resolve_series ────────────────────────────────────────────────────────


def test_none_resolves_to_everything():
    assert resolve_series(None) is ALL_SERIES


def test_a_dict_passes_through_untouched():
    custom = {"MY_KEY": ("Name", "acs/acs5", ["B01001_001E"])}
    assert resolve_series(custom) is custom


def test_a_single_series_key_resolves_to_one_entry():
    key = a_series_key()
    assert resolve_series(key) == {key: ALL_SERIES[key]}


def test_a_category_name_resolves_to_the_category():
    name = next(iter(CATEGORIES))
    assert resolve_series(name) == CATEGORIES[name]


def test_a_subcategory_name_resolves_without_naming_its_parent():
    parent = next(iter(SUBCATEGORIES))
    sub_name, sub_dict = next(iter(SUBCATEGORIES[parent].items()))
    assert resolve_series(sub_name) == sub_dict


def test_a_list_merges_its_tokens():
    key = a_series_key()
    category = next(iter(CATEGORIES))
    merged = resolve_series([key, category])
    assert key in merged
    for k in CATEGORIES[category]:
        assert k in merged


def test_resolution_is_case_insensitive():
    key = a_series_key()
    assert resolve_series(key.lower()) == {key: ALL_SERIES[key]}


def test_an_unknown_token_points_at_the_discovery_helpers():
    with pytest.raises(KeyError, match="available"):
        _resolve_one("DEFINITELY_NOT_A_REAL_TOKEN")


def test_a_wrong_type_raises_TypeError():
    with pytest.raises(TypeError, match="series must be"):
        resolve_series(3.14)


def test_resolution_order_prefers_a_series_key_over_a_category():
    """Documented order: exact series key, then category, then subcategory.
    Only meaningful if the three namespaces can collide, so this pins the
    precedence rather than assuming they never do."""
    key = a_series_key()
    resolved = resolve_series(key)
    assert len(resolved) == 1


# ── the discovery helpers ─────────────────────────────────────────────────


def test_available_with_no_arguments_lists_every_category(capsys):
    available()
    out = capsys.readouterr().out
    for category in CATEGORIES:
        assert category in out
    assert "TOTAL" in out


def test_available_reports_a_total_matching_the_catalog(capsys):
    available()
    assert str(len(ALL_SERIES)) in capsys.readouterr().out


def test_available_drills_into_a_category(capsys):
    name = next(iter(CATEGORIES))
    available(name)
    out = capsys.readouterr().out
    assert f"Category: {name}" in out


def test_available_drills_into_a_subcategory(capsys):
    parent = next(iter(SUBCATEGORIES))
    sub_name = next(iter(SUBCATEGORIES[parent]))
    available(sub_name)
    assert f"Subcategory: {sub_name}" in capsys.readouterr().out


def test_available_is_case_insensitive(capsys):
    name = next(iter(CATEGORIES))
    available(name.lower())
    assert f"Category: {name}" in capsys.readouterr().out


def test_available_says_so_when_a_name_is_unknown(capsys):
    available("NOT_A_CATEGORY")
    out = capsys.readouterr().out
    assert "not found" in out
    assert "available()" in out          # tells you what to do next


def test_search_matches_a_friendly_name_and_returns_keys(capsys):
    key = a_series_key()
    friendly = ALL_SERIES[key][0]
    hits = search(friendly)
    capsys.readouterr()
    assert key in hits


def test_search_matches_a_catalog_key(capsys):
    key = a_series_key()
    hits = search(key)
    capsys.readouterr()
    assert key in hits


def test_search_is_case_insensitive(capsys):
    key = a_series_key()
    hits = search(key.lower())
    capsys.readouterr()
    assert key in hits


def test_search_returns_an_empty_list_and_says_so(capsys):
    hits = search("zzzz_definitely_no_match_zzzz")
    assert hits == []
    assert "No series matching" in capsys.readouterr().out


def test_info_reports_a_series_with_its_lineage(capsys):
    key = a_series_key()
    info(key)
    out = capsys.readouterr().out
    assert key in out
    assert ALL_SERIES[key][0] in out         # friendly name
    assert "Dataset" in out


def test_info_is_case_insensitive(capsys):
    key = a_series_key()
    info(key.lower())
    assert key in capsys.readouterr().out


def test_info_says_so_when_the_key_is_unknown(capsys):
    info("NOT_A_SERIES")
    out = capsys.readouterr().out
    assert "not found" in out
    assert "search(" in out                 # tells you what to do next


def test_geos_lists_the_templates(capsys):
    geos()
    out = capsys.readouterr().out
    assert "state_all" in out


def test_geos_quiet_returns_the_templates_without_printing(capsys):
    """`_validate_geo_inputs` depends on this returning data rather than
    printing, so it is load bearing rather than a convenience."""
    result = geos(quiet=True)
    assert capsys.readouterr().out == ""
    assert result
    assert dict(result).keys() == GEO.keys()


# ── _parse_variables ──────────────────────────────────────────────────────


def test_a_group_spec_is_recognised_and_unwrapped():
    var_list, group = _parse_variables("group(B19001)")
    assert var_list == []
    assert group == "B19001"


def test_a_variable_list_passes_through_with_no_group():
    var_list, group = _parse_variables(["B01001_001E", "B01001_002E"])
    assert var_list == ["B01001_001E", "B01001_002E"]
    assert group is None


# ── _clean_frame ──────────────────────────────────────────────────────────


def test_a_single_variable_column_is_renamed_to_the_series_name():
    df = pd.DataFrame({"state": ["25"], "B01001_001E": ["100"]})
    out = _clean_frame(df, "total_pop", ["B01001_001E"], None, dataset="acs/acs5", year=2022)
    assert "total_pop" in out.columns
    assert "B01001_001E" not in out.columns


def test_a_county_name_is_split_out_of_the_NAME_field():
    df = pd.DataFrame(
        {
            "NAME": ["Norfolk County, Massachusetts"],
            "state": ["25"],
            "county": ["021"],
            "B01001_001E": ["100"],
        }
    )
    out = _clean_frame(df, "pop", ["B01001_001E"], None, dataset="acs/acs5", year=2022)
    assert out["county_name"].iloc[0] == "Norfolk County"
    assert "NAME" not in out.columns


def test_a_place_name_is_split_out_of_the_NAME_field():
    df = pd.DataFrame(
        {"NAME": ["Boston city, Massachusetts"], "state": ["25"], "place": ["07000"], "V": ["1"]}
    )
    out = _clean_frame(df, "pop", ["V"], None, dataset="acs/acs5", year=2022)
    assert out["place_name"].iloc[0] == "Boston city"


def test_a_tract_name_is_split_out_of_the_NAME_field():
    df = pd.DataFrame(
        {
            "NAME": ["Census Tract 4011, Norfolk County, Massachusetts"],
            "state": ["25"],
            "tract": ["401100"],
            "V": ["1"],
        }
    )
    out = _clean_frame(df, "pop", ["V"], None, dataset="acs/acs5", year=2022)
    assert out["tract_name"].iloc[0] == "Census Tract 4011"


def test_a_state_name_is_added_beside_its_fips_code():
    df = pd.DataFrame({"state": ["25"], "V": ["1"]})
    out = _clean_frame(df, "pop", ["V"], None, dataset="acs/acs5", year=2022)
    assert "state_name" in out.columns
    assert out["state_name"].iloc[0] == "Massachusetts"


def test_an_unknown_fips_code_falls_back_to_the_code_itself():
    """Better than a blank: the row is still identifiable."""
    df = pd.DataFrame({"state": ["99"], "V": ["1"]})
    out = _clean_frame(df, "pop", ["V"], None, dataset="acs/acs5", year=2022)
    assert out["state_name"].iloc[0] == "99"


def test_geography_columns_are_moved_to_the_front():
    df = pd.DataFrame({"V": ["1"], "state": ["25"]})
    out = _clean_frame(df, "pop", ["V"], None, dataset="acs/acs5", year=2022)
    assert list(out.columns)[0] == "state"


def test_value_columns_are_cast_to_numbers():
    df = pd.DataFrame({"state": ["25"], "V": ["1234"]})
    out = _clean_frame(df, "pop", ["V"], None, dataset="acs/acs5", year=2022)
    assert out["pop"].iloc[0] == 1234


def test_geography_columns_keep_their_leading_zeros():
    """A FIPS code is an identifier, not a quantity. Casting it would turn
    '021' into 21 and break every join against it."""
    df = pd.DataFrame({"state": ["25"], "county": ["021"], "V": ["1"]})
    out = _clean_frame(df, "pop", ["V"], None, dataset="acs/acs5", year=2022)
    assert out["county"].iloc[0] == "021"


def test_annotation_columns_are_dropped_from_a_group_pull(monkeypatch):
    """Group pulls come back with margin-of-error and annotation siblings that
    nobody wants. Label lookup is stubbed so this stays offline."""
    import census_loader.utils as utils

    monkeypatch.setattr(utils, "_fetch_group_labels", lambda *a, **k: {})
    df = pd.DataFrame(
        {
            "state": ["25"],
            "B19001_001E": ["100"],
            "B19001_001M": ["5"],
            "B19001_001EA": ["x"],
            "GEO_ID": ["0400000US25"],
        }
    )
    out = _clean_frame(df, "income", [], "B19001", dataset="acs/acs5", year=2022)
    assert "B19001_001M" not in out.columns
    assert "GEO_ID" not in out.columns
    assert "B19001_001E" in out.columns


def test_group_labels_rename_columns_and_collisions_keep_the_raw_code(monkeypatch):
    """Two variables can share a friendly label. The second must not silently
    overwrite the first, so the raw code is appended to disambiguate."""
    import census_loader.utils as utils

    monkeypatch.setattr(
        utils,
        "_fetch_group_labels",
        lambda *a, **k: {"B19001_001E": "Total", "B19001_002E": "Total"},
    )
    df = pd.DataFrame({"state": ["25"], "B19001_001E": ["1"], "B19001_002E": ["2"]})
    out = _clean_frame(df, "income", [], "B19001", dataset="acs/acs5", year=2022)

    renamed = [c for c in out.columns if c.startswith("income__Total")]
    assert len(renamed) == 2
    assert any("B19001_002E" in c for c in renamed)


def test_a_multi_variable_pull_falls_back_to_raw_codes_without_labels(monkeypatch):
    import census_loader.utils as utils

    monkeypatch.setattr(utils, "_fetch_var_labels", lambda *a, **k: {})
    df = pd.DataFrame({"state": ["25"], "V1": ["1"], "V2": ["2"]})
    out = _clean_frame(df, "pop", ["V1", "V2"], None, dataset="acs/acs5", year=2022)
    assert "pop__V1" in out.columns
    assert "pop__V2" in out.columns
