"""Tests for the predicate decoding, the catalog exports, and the input guards.

Every assertion here was proven to FAIL against the code as it stood before
these fixes, then pass after. The negative controls (an unmapped code, a
non-PEP dataset, a valid geo) pass in both states on purpose: they exist to
catch a fix that overreaches, not to confirm one that works.

The frames are built by hand rather than fetched: these are pure
post-processing paths, so a live API call would add flakiness and prove less.
"""

import pandas as pd
import pytest

from census_loader import ALL_SERIES, CATEGORIES, PREDICATES, SUBCATEGORIES
from census_loader import series as series_mod
from census_loader import utils


# ── the catalog is reachable from the package root ────────────────────────


def test_composites_are_re_exported():
    """The catalog's own docstring describes a hierarchy, so that hierarchy
    has to be importable without reaching into a private module."""
    import census_loader

    for symbol in ("ALL_SERIES", "CATEGORIES", "SUBCATEGORIES", "PREDICATES"):
        assert hasattr(census_loader, symbol)
        assert symbol in census_loader.__all__


@pytest.mark.parametrize("ghost", ["AGE_SEX", "HOUSEHOLD_INCOME", "DEMOGRAPHICS", "INCOME_POVERTY"])
def test_docstring_cites_no_nonexistent_symbols(ghost):
    """The docstring used to give import examples for names this catalog has
    never contained, which is worse than no example."""
    assert ghost not in (series_mod.__doc__ or "")


@pytest.mark.parametrize("real", ["TOTAL_POPULATION", "AGE_DETAIL", "POPULATION", "INCOME", "ALL_SERIES"])
def test_docstring_cites_only_real_symbols(real):
    assert real in (series_mod.__doc__ or "")
    assert hasattr(series_mod, real)


# ── predicate codes decode into labels ────────────────────────────────────


def test_pep_codes_decode_to_labels():
    """PEP returns its breakdown dimensions as bare integers. PREDICATES has
    always held their meaning; nothing applied it, so pulls shipped raw codes."""
    df = pd.DataFrame({"state": ["25"], "RACE": ["2"], "SEX": ["1"], "POP": ["100"]})
    out = utils._clean_frame(df, "pop_by_race", ["POP"], None,
                            dataset="pep/charagegroups", year=2022)
    assert out["RACE"].iloc[0] == "Black_Alone"
    assert out["SEX"].iloc[0] == "Male"


def test_decoded_column_keeps_the_original_code():
    """The raw code is preserved beside the label. It is what the column used
    to hold, so anything downstream joining on the number keeps working, and
    it stays numeric for exactly that reason."""
    df = pd.DataFrame({"state": ["25"], "RACE": ["2"], "POP": ["100"]})
    out = utils._clean_frame(df, "x", ["POP"], None,
                            dataset="pep/charagegroups", year=2022)
    assert "RACE_code" in out.columns
    assert int(out["RACE_code"].iloc[0]) == 2


def test_sahie_uses_its_own_prefix():
    """SAHIE's columns are named differently from PEP's and must not be
    decoded with PEP's maps."""
    df = pd.DataFrame({"state": ["25"], "SEXCAT": ["2"], "AGECAT": ["0"], "PCTUI": ["5.1"]})
    out = utils._clean_frame(df, "uninsured", ["PCTUI"], None,
                            dataset="timeseries/healthins/sahie", year=2022)
    assert out["SEXCAT"].iloc[0] == "Female"
    assert out["AGECAT"].iloc[0] == "Under_65"


def test_decoded_labels_survive_the_numeric_cast():
    """The final pass casts every non-geo column with errors='coerce', which
    turns text into NaN. Decoded labels are held out by name; without that
    exemption this whole feature silently produces NaN."""
    df = pd.DataFrame({"state": ["25"], "RACE": ["1"], "POP": ["5"]})
    out = utils._clean_frame(df, "x", ["POP"], None,
                            dataset="pep/charagegroups", year=2022)
    assert pd.notna(out["RACE"].iloc[0])
    assert isinstance(out["RACE"].iloc[0], str)


# ── negative controls: the decoder must not overreach ─────────────────────


def test_unrecognised_code_is_preserved_not_blanked():
    """A category appearing upstream that the map does not know must not blank
    the column. No decode happened, so the column is left as it always was."""
    df = pd.DataFrame({"state": ["25"], "RACE": ["99"], "POP": ["1"]})
    out = utils._clean_frame(df, "x", ["POP"], None,
                            dataset="pep/charagegroups", year=2022)
    assert pd.notna(out["RACE"].iloc[0])
    assert int(out["RACE"].iloc[0]) == 99
    assert "RACE_code" not in out.columns


def test_non_predicate_dataset_is_untouched():
    """An ACS frame may coincidentally carry a column named RACE. It is not a
    PEP code and must not be rewritten."""
    df = pd.DataFrame({"state": ["25"], "RACE": ["2"], "B01001_001E": ["100"]})
    out = utils._clean_frame(df, "y", ["B01001_001E"], None,
                            dataset="acs/acs5", year=2022)
    assert "RACE_code" not in out.columns
    assert int(out["RACE"].iloc[0]) == 2


# ── input guards fail loudly ──────────────────────────────────────────────


def test_bad_geo_raises_instead_of_building_a_broken_config(tmp_path):
    """The guard raises an actionable ValueError. Config used to catch it,
    print it, and continue with an empty GEO, so the failure surfaced much
    later as something unrelated-looking."""
    with pytest.raises(ValueError):
        utils.Config("out", tmp_path, series="POPULATION",
                     geo="not_a_real_geo_template")


def test_valid_geo_still_builds(tmp_path):
    cfg = utils.Config("out", tmp_path, series="POPULATION",
                       geo="county_in_state", state="MA", county="021")
    assert cfg.GEO


def test_batch_size_chunking_is_gone():
    """BATCH_SIZE chunked the series dict, which changed nothing: each series
    already got its own request. The no-op was removed rather than left
    looking meaningful."""
    import inspect

    src = inspect.getsource(utils)
    assert "def _batched(" not in src
    assert "for batch in _batched" not in src
