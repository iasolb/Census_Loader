import pytest

from census_loader.series import ALL_SERIES, CATEGORIES, SUBCATEGORIES
from census_loader.utils import _resolve_one, resolve_series


def test_catalog_integrity():
    friendly_names = [entry[0] for entry in ALL_SERIES.values()]
    assert len(friendly_names) == len(set(friendly_names))

    for key, entry in ALL_SERIES.items():
        assert _resolve_one(key) == {key: entry}
        assert isinstance(entry, tuple) and len(entry) == 3
        variables = entry[2]
        if isinstance(variables, tuple):
            assert len(variables) == len(set(variables)), key

    category_keys = set()
    for category, series in CATEGORIES.items():
        category_keys.update(series)
        assert category in SUBCATEGORIES
        for subcategory, subseries in SUBCATEGORIES[category].items():
            assert set(subseries).issubset(series)
    assert category_keys == set(ALL_SERIES)


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("TOTAL_POP", {"TOTAL_POP"}),
        ("INCOME", set(CATEGORIES["INCOME"])),
        ("HOUSEHOLD_INCOME", set(SUBCATEGORIES["INCOME"]["HOUSEHOLD_INCOME"])),
        (["TOTAL_POP", "MEDIAN_RENT"], {"TOTAL_POP", "MEDIAN_RENT"}),
    ],
)
def test_resolve_series_single_group_and_mix(spec, expected):
    assert set(resolve_series(spec)) == expected


def test_resolve_series_none_and_dict_passthrough():
    custom = {"CUSTOM": ("Custom", "acs5", ("X",))}
    assert resolve_series(None) is ALL_SERIES
    assert resolve_series(custom) is custom


def test_resolve_one_is_case_insensitive():
    assert _resolve_one("median_hh_income") == {"MEDIAN_HH_INCOME": ALL_SERIES["MEDIAN_HH_INCOME"]}


def test_unknown_series_has_actionable_error():
    with pytest.raises(KeyError, match=r"available\(\).*search\('keyword'\)"):
        _resolve_one("not_a_series")


def test_invalid_series_type_has_named_error():
    with pytest.raises(TypeError, match="series must be"):
        resolve_series(42)
