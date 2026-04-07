from typing import Optional, Any
from pathlib import Path
from itertools import islice
import pandas as pd
import requests
from dotenv import load_dotenv
from census import Census
import os, time
from functools import reduce
import pickle
from .series import (
    ALL_SERIES,
    POPULATION,
    RACE_ETHNICITY,
    NATIVITY_MIGRATION,
    LANGUAGE,
    EDUCATION,
    HOUSEHOLDS,
    INCOME,
    POVERTY,
    HEALTH_INSURANCE,
    EMPLOYMENT,
    HOUSING,
    DISABILITY,
    VETERANS,
    PEP_POPULATION,
    DECENNIAL,
    DATA_PROFILES,
    GEO,
    STATE_FIPS,
    FIPS_STATES,
    CATEGORIES,
    SUBCATEGORIES,
)

# ── Dataset dispatch ─────────────────────────────────────────────────────────

_BASE_URL = "https://api.census.gov/data"

RAW_ENDPOINTS = {
    "acs5/flows": "{base}/{yr}/acs/flows",
    "pep": "{base}/{yr}/pep/charv",
    "saipe": "{base}/timeseries/poverty/saipe",
    "saipe/schdist": "{base}/timeseries/poverty/saipe/schdist",
    "sahie": "{base}/timeseries/healthins/sahie",
    "dec/pl": "{base}/2020/dec/pl",
    "dec/dhc": "{base}/2020/dec/dhc",
}

DATASET_DISPATCH = {
    "acs5": lambda c: c.acs5,
    "acs5/subject": lambda c: c.acs5st,
    "acs5/profile": lambda c: c.acs5dp,
    "acs1": lambda c: c.acs1,
    "acs5/flows": RAW_ENDPOINTS["acs5/flows"],
    "pep": RAW_ENDPOINTS["pep"],
    "saipe": RAW_ENDPOINTS["saipe"],
    "saipe/schdist": RAW_ENDPOINTS["saipe/schdist"],
    "sahie": RAW_ENDPOINTS["sahie"],
    "dec/pl": RAW_ENDPOINTS["dec/pl"],
    "dec/dhc": RAW_ENDPOINTS["dec/dhc"],
}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  SERIES RESOLVER — the user-facing abstraction layer                    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

_SUBCATEGORY_FLAT: dict[str, dict] = {}
for _cat, _subs in SUBCATEGORIES.items():
    for _subname, _subdict in _subs.items():
        _SUBCATEGORY_FLAT[_subname] = _subdict


def _resolve_one(token: str) -> dict:
    """
    Resolve a single string token into a series dict.

    Resolution order:
        1. Individual series key  →  "TOTAL_POP", "MEDIAN_RENT"
        2. Category name          →  "INCOME", "HOUSING"
        3. Subcategory name       →  "HOUSEHOLD_INCOME", "COMMUTING"

    Raises KeyError with a helpful message if nothing matches.
    """
    token_upper = token.upper()

    # 1 — exact series key
    if token_upper in ALL_SERIES:
        return {token_upper: ALL_SERIES[token_upper]}

    # 2 — category
    if token_upper in CATEGORIES:
        return CATEGORIES[token_upper]

    # 3 — subcategory
    if token_upper in _SUBCATEGORY_FLAT:
        return _SUBCATEGORY_FLAT[token_upper]

    # Nothing matched — helpful error
    raise KeyError(
        f"'{token}' is not a recognized series, category, or subcategory.\n"
        f"  Use available() to browse, or search('keyword') to find series."
    )


def resolve_series(spec) -> dict:
    """
    Turn a flexible user specification into the internal series dict.

    Accepted inputs
    ---------------
    None                     → ALL_SERIES  (everything)
    "TOTAL_POP"              → single series
    "INCOME"                 → entire category
    "HOUSEHOLD_INCOME"       → subcategory
    ["TOTAL_POP", "INCOME"]  → mix-and-match, merged
    dict                     → pass through (backward compat / power users)

    Returns
    -------
    dict  : {series_key: (name, dataset, variables), ...}
    """
    if spec is None:
        return ALL_SERIES

    if isinstance(spec, dict):
        return spec

    if isinstance(spec, str):
        return _resolve_one(spec)

    if isinstance(spec, (list, tuple)):
        merged = {}
        for token in spec:
            merged.update(_resolve_one(token))
        return merged

    raise TypeError(
        f"series must be None, str, list[str], or dict — got {type(spec).__name__}"
    )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  DISCOVERY — browse & search the catalog without reading series.py      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def available(category: str | None = None) -> None:
    """
    Print what's available in the catalog.

    Call with no args to see categories.
    Pass a category or subcategory name to see its series::

        available()                     # list all categories
        available("INCOME")             # series inside INCOME
        available("HOUSEHOLD_INCOME")   # series inside a subcategory
    """
    if category is None:
        print("Categories  (pass one to available() to drill down)\n")
        for cat_name, cat_dict in CATEGORIES.items():
            subs = list(SUBCATEGORIES.get(cat_name, {}).keys())
            sub_str = f"\n    └ {', '.join(subs)}" if subs else ""
            print(f"  {cat_name:<24s} ({len(cat_dict):>3d} series){sub_str}")
        print(f"\n  {'TOTAL':<24s} ({len(ALL_SERIES):>3d} series)")
        return

    cat_upper = category.upper()

    if cat_upper in CATEGORIES:
        target = CATEGORIES[cat_upper]
        label = f"Category: {cat_upper}"
    elif cat_upper in _SUBCATEGORY_FLAT:
        target = _SUBCATEGORY_FLAT[cat_upper]
        label = f"Subcategory: {cat_upper}"
    else:
        print(f"'{category}' not found. Run available() with no args to see options.")
        return

    print(f"{label}  ({len(target)} series)\n")
    for key, (name, dataset, variables) in target.items():
        print(f"  {key:<30s}  {name}")
    print()


def search(keyword: str) -> list[str]:
    """
    Search the catalog by keyword (case-insensitive).

    Searches series keys AND friendly names::

        search("poverty")
        search("median")
        search("hispanic")

    Returns list of matching series keys.
    """
    kw = keyword.lower()
    hits = []
    for key, (name, _, _) in ALL_SERIES.items():
        if kw in key.lower() or kw in name.lower():
            hits.append(key)

    if not hits:
        print(f"No series matching '{keyword}'.")
        return []

    print(f"Found {len(hits)} series matching '{keyword}':\n")
    for key in hits:
        name = ALL_SERIES[key][0]
        print(f"  {key:<30s}  {name}")
    print()
    return hits


def info(series_key: str) -> None:
    """
    Print full details about a single series::

        info("MEDIAN_HH_INCOME")
    """
    key = series_key.upper()
    if key not in ALL_SERIES:
        print(f"'{series_key}' not found. Try search('{series_key}').")
        return

    name, dataset, variables = ALL_SERIES[key]

    parent_cat = parent_sub = None
    for cat_name, cat_dict in CATEGORIES.items():
        if key in cat_dict:
            parent_cat = cat_name
            for sub_name, sub_dict in SUBCATEGORIES.get(cat_name, {}).items():
                if key in sub_dict:
                    parent_sub = sub_name
            break

    print(f"\n  Key:          {key}")
    print(f"  Name:         {name}")
    print(f"  Category:     {parent_cat or '—'}")
    print(f"  Subcategory:  {parent_sub or '—'}")
    print(f"  Dataset:      {dataset}")
    if isinstance(variables, str):
        print(f"  Variables:    {variables}  (full table group)")
    else:
        print(
            f"  Variables:    {len(variables)} code{'s' if len(variables) > 1 else ''}"
        )
        for v in variables:
            print(f"                  {v}")
    print()


def geos(quiet: Optional[bool] = False) -> None | dict[str, str]:
    """Print available geography queries and their required parameters."""
    requires_remap = {
        "st": "state",
        "co": "county",
        "tr": "tract",
    }
    if not quiet:
        print("Available Geometry Queries:\n")
        for key, val in GEO.items():
            val_str = str(val)
            requires = [
                requires_remap[code]
                for code in ("st", "co", "tr")
                if f"{{{code}}}" in val_str
            ]
            print(f"  {key}")
            print(f"    Query:    {val}")
            print(f"    Requires: {', '.join(requires) if requires else 'None'}")
            print()
        return None
    else:
        """Returns a dict of geo query keys and their required parameters"""
        result = {}
        for key, val in GEO.items():
            val_str = str(val)
            requires = [
                requires_remap[code]
                for code in ("st", "co", "tr")
                if f"{{{code}}}" in val_str
            ]
            result[key] = ", ".join(requires) if requires else "None"
        return result


def pickle_loader(filepath: Path | str) -> pd.DataFrame:
    """
    Load a dict-of-DataFrames pickle and flatten it into a single
    DataFrame by outer-merging on columns shared across all frames.

    Parameters
    ----------
    filepath : Path or str
        Path to the .pkl file.

    Returns
    -------
    pd.DataFrame
        One row per shared-key combination, with all frames' columns merged in.
    """
    with open(filepath, "rb") as f:
        data = pickle.load(f)
    if isinstance(data, pd.DataFrame):
        return data
    if not isinstance(data, dict) or len(data) == 0:
        return pd.DataFrame()
    frames = list(data.values())
    if len(frames) == 1:
        return frames[0]
    shared = set(frames[0].columns)
    for df in frames[1:]:
        shared &= set(df.columns)
    merge_keys = []
    for col in shared:
        if all(not pd.api.types.is_numeric_dtype(df[col]) for df in frames):
            merge_keys.append(col)
    if not merge_keys:
        parts = []
        for name, df in data.items():
            chunk = df.copy()
            chunk.insert(0, "series", name)
            parts.append(chunk)
        return pd.concat(parts, ignore_index=True)
    merged = reduce(
        lambda left, right: pd.merge(left, right, on=merge_keys, how="outer"),
        frames,
    )
    return merged


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CONFIGURATION  OBJECT                                                    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class Config:
    """
    Configuration for a Census Bureau data pull.

    Parameters
    ----------
    filename : str
        Output CSV filename.
    output_path : Path or str
        Directory where output files are saved.
    year : int
        ACS / PEP vintage year (default 2022).
    geo : str or dict
        Geography level — a key from GEO (e.g. "state_all",
        "county_in_state", "tract_in_county") or a raw dict.
    state : str, optional
        State name ("Massachusetts") or FIPS code ("25").
    county : str, optional
        County FIPS code (3-digit, e.g. "017").
    tract : str, optional
        Tract code.
    series : str, list[str], dict, or None
        What to pull.  Accepts any of::

            series=None                                     # everything
            series="TOTAL_POP"                              # one series
            series="INCOME"                                 # whole category
            series="HOUSEHOLD_INCOME"                       # subcategory
            series=["TOTAL_POP", "INCOME", "MEDIAN_RENT"]   # mix & match

        Use ``available()``, ``search()``, ``info()`` to explore options.
    batch_size : int
        Max series per API batch (default 50).
    """

    def __init__(
        self,
        filename: str,
        output_path: Path | str,
        year: int = 2022,
        geo: str | dict | None = None,
        state: str | None = None,
        county: str | None = None,
        tract: str | None = None,
        series: str | list | dict | None = None,
        batch_size: int = 50,
    ) -> None:
        def _validate_geo_inputs(geo, state, county, tract):
            # ── (raw query) ─────────────────────────────
            if isinstance(geo, dict):
                return geo
            # ── None: default to state_all ──────────────────────────────
            if geo is None:
                return GEO["state_all"]
            # ── String key:  validate + resolve ──────────────────────────
            tmp = geos(quiet=True)
            if tmp:
                required_dct = dict(tmp)
            else:
                raise ValueError("Failed to retrieve geo templates for validation.")
            if geo not in required_dct:
                raise ValueError(
                    f"Geo template '{geo}' not recognized. "
                    f"Use geos() to see available templates."
                )
            required_params = [
                p.strip() for p in required_dct[geo].split(",") if p.strip() != "None"
            ]
            missing_params = []
            for param in required_params:
                if param == "state" and state is None:
                    missing_params.append("state")
                elif param == "county" and county is None:
                    missing_params.append("county")
                elif param == "tract" and tract is None:
                    missing_params.append("tract")
            if missing_params:
                raise ValueError(
                    f"Geo template '{geo}' requires parameters: "
                    f"{', '.join(missing_params)}"
                )
            # ── Resolve FIPS + format ────────────────────────────────────
            geo_template = GEO[geo]
            fips_kwargs = {}
            if state is not None:
                fips_kwargs["st"] = STATE_FIPS[state] if state in STATE_FIPS else state
            if county is not None:
                fips_kwargs["co"] = county
            if tract is not None:
                fips_kwargs["tr"] = tract
            return {
                k: v.format(**fips_kwargs) if fips_kwargs else v
                for k, v in geo_template.items()
            }

        if batch_size > 50:
            print(
                f"Warning: batch_size={batch_size} may exceed API limits "
                f"(50 for free key) and cause failures. Use with caution."
            )
        self.FILENAME: str = filename
        self.OUTPUT_PATH: Path = Path(output_path).resolve()
        self.YEAR: int = year
        self.BATCH_SIZE: int = batch_size
        # ── Resolve series spec → internal dict ──────────────────────────
        self._series_input = series
        self.SERIES: dict = resolve_series(series)
        try:
            self.GEO: dict = _validate_geo_inputs(geo, state, county, tract)
        except ValueError as e:
            print(f"Error validating geo inputs, set GEO to None: {e}")
            self.GEO: dict = {}

    def __str__(self) -> str:
        si = self._series_input
        if si is None:
            series_label = f"ALL ({len(self.SERIES)} series)"
        elif isinstance(si, str):
            series_label = f'"{si}" ({len(self.SERIES)} series)'
        elif isinstance(si, (list, tuple)):
            preview = ", ".join(si[:4])
            more = f" + {len(si)-4} more" if len(si) > 4 else ""
            series_label = f"[{preview}{more}] ({len(self.SERIES)} series)"
        else:
            series_label = f"custom dict ({len(self.SERIES)} series)"

        return (
            "Census Bureau Pull Configuration:\n"
            f"  filename    = {self.FILENAME}\n"
            f"  output_path = {self.OUTPUT_PATH}\n"
            f"  year        = {self.YEAR}\n"
            f"  geo         = {self.GEO}\n"
            f"  series      = {series_label}\n"
            f"  batch_size  = {self.BATCH_SIZE}"
        )

    def geo_formatted(self, **fips) -> dict:
        """Return self.GEO with FIPS placeholders re-filled."""
        resolved = {}
        for key, val in fips.items():
            if key == "st" and val in STATE_FIPS:
                resolved[key] = STATE_FIPS[val]
            else:
                resolved[key] = val
        return {k: v.format(**resolved) for k, v in self.GEO.items()}

    def show_series(self) -> None:
        """Print the resolved series that will be pulled."""
        print(f"Resolved series ({len(self.SERIES)}):\n")
        for key, (name, _, _) in self.SERIES.items():
            print(f"  {key:<30s}  {name}")
        print()


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  INTERNAL PULL HELPERS                                                  ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _parse_variables(variables) -> tuple[list[str], str | None]:
    if isinstance(variables, str) and variables.startswith("group("):
        return [], variables[6:-1]
    return list(variables), None


def _pull_wrapped(client_attr, var_list, group_name, geo, year) -> pd.DataFrame:
    if group_name:
        fields = (f"group({group_name})",)
    else:
        fields = ("NAME", *var_list)
    geo_kwargs = {}
    if "for" in geo:
        geo_kwargs["geo"] = {"for": geo["for"]}
        if "in" in geo:
            geo_kwargs["geo"]["in"] = geo["in"]
    data = client_attr.get(fields, geo_kwargs.get("geo", {}), year=year)
    return pd.DataFrame(data)


def _pull_raw(url_template, var_list, group_name, geo, year, api_key) -> pd.DataFrame:
    url = url_template.format(base=_BASE_URL, yr=year)
    if group_name:
        get_param = f"group({group_name})"
    else:
        get_param = "NAME," + ",".join(var_list)
    params = {"get": get_param, "key": api_key}
    params.update(geo)
    if "timeseries" in url:
        params["YEAR"] = str(year)
    resp = requests.get(url, params=params, timeout=120)
    resp.raise_for_status()
    rows = resp.json()
    if not rows or len(rows) < 2:
        return pd.DataFrame()
    return pd.DataFrame(rows[1:], columns=rows[0])


# ── Group variable label cache ───────────────────────────────────────────────

_DATASET_PATHS = {
    "acs5": "acs/acs5",
    "acs5/subject": "acs/acs5/subject",
    "acs5/profile": "acs/acs5/profile",
    "acs1": "acs/acs1",
    "dec/pl": "dec/pl",
    "dec/dhc": "dec/dhc",
}

_group_label_cache: dict[str, dict[str, str]] = {}


def _fetch_group_labels(group_name: str, dataset: str, year: int) -> dict[str, str]:
    """
    Fetch human-readable labels for every variable in a Census group.

    Returns {var_code: short_label} e.g.:
        {"B19001_001E": "Total", "B19001_002E": "Less than $10,000", ...}

    Results are cached per session.  Falls back to empty dict on failure.
    """
    cache_key = f"{dataset}/{year}/{group_name}"
    if cache_key in _group_label_cache:
        return _group_label_cache[cache_key]

    ds_path = _DATASET_PATHS.get(dataset)
    if not ds_path:
        return {}

    if dataset.startswith("dec/"):
        url = f"{_BASE_URL}/2020/{ds_path}/groups/{group_name}.json"
    else:
        url = f"{_BASE_URL}/{year}/{ds_path}/groups/{group_name}.json"

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        raw = resp.json().get("variables", {})

        labels = {}
        for var_code, meta in raw.items():
            label = meta.get("label", var_code)
            # Census labels look like "Estimate!!Total:!!Male:!!65 and 66 years"
            # Strip colons, split on "!!", drop boilerplate prefixes,
            # keep enough context to disambiguate (e.g. "Male - 65 and 66 years")
            parts = [p.strip() for p in label.replace(":", "").split("!!") if p.strip()]
            # Drop leading "Estimate"
            skip = {"Estimate"}
            meaningful = [p for p in parts if p not in skip]
            short = (
                " - ".join(meaningful)
                if meaningful
                else (parts[-1] if parts else var_code)
            )
            labels[var_code] = short

        _group_label_cache[cache_key] = labels
        return labels

    except Exception:
        _group_label_cache[cache_key] = {}
        return {}


def _fetch_var_labels(var_codes: list[str], dataset: str, year: int) -> dict[str, str]:
    """
    Fetch labels for individual variable codes by looking up their parent
    group.  Reuses _fetch_group_labels so the metadata is cached.

    Variable codes follow the pattern TABLE_SEQE (e.g. B25003_002E).
    The group/table name is everything before the underscore-number suffix.

    Returns {var_code: short_label} for the requested codes only.
    """
    # Group var codes by their parent table
    # B25003_002E → B25003,  DP03_0096E → DP03,  S0101_C01_001E → S0101
    tables: dict[str, list[str]] = {}
    for code in var_codes:
        # Walk backwards to find the table prefix:
        # split on '_', the table is everything except the last segment
        # B25003_002E → ["B25003", "002E"] → table = "B25003"
        # S0101_C01_001E → ["S0101", "C01", "001E"] → table = "S0101"
        parts = code.split("_")
        # Table name = first part for B/C tables, or first part for S/DP tables
        # The group name is typically the first segment
        table = parts[0]
        tables.setdefault(table, []).append(code)

    # Fetch each table's full label set (cached after first call)
    result = {}
    for table, codes in tables.items():
        all_labels = _fetch_group_labels(table, dataset, year)
        for code in codes:
            if code in all_labels:
                result[code] = all_labels[code]

    return result


# ── Annotation suffixes to drop from group() pulls ──────────────────────────
_JUNK_SUFFIXES = ("EA", "MA", "M")


def _clean_frame(
    df: pd.DataFrame,
    name: str,
    var_list: list[str],
    group_name: str | None,
    dataset: str = "",
    year: int = 2022,
) -> pd.DataFrame:
    """
    Post-process a raw Census DataFrame into something user-friendly.

    1. Parse NAME column → geo name columns (county_name, etc.)
    2. Resolve FIPS state codes → state names
    3. Drop annotation / margin-of-error columns from group() pulls
    4. Rename variable columns (friendly names or group labels)
    5. Move geo columns to front in sensible order
    6. Cast numeric columns from strings
    """
    df = df.copy()

    # ── 1. Parse NAME into geo name columns ─────────────────────────────
    # Census NAME field examples:
    #   state:   "Massachusetts"
    #   county:  "Norfolk County, Massachusetts"
    #   tract:   "Census Tract 4011, Norfolk County, Massachusetts"
    #   place:   "Boston city, Massachusetts"
    if "NAME" in df.columns:
        if "county" in df.columns:
            df.insert(
                int(df.columns.get_loc("county")) + int(1),
                "county_name",
                df["NAME"].str.split(",").str[0].str.strip(),
            )
        elif "place" in df.columns:
            df.insert(
                int(df.columns.get_loc("place")) + int(1),
                "place_name",
                df["NAME"].str.split(",").str[0].str.strip(),
            )
        elif "tract" in df.columns:
            df.insert(
                int(df.columns.get_loc("tract")) + int(1),
                "tract_name",
                df["NAME"].str.split(",").str[0].str.strip(),
            )
        df = df.drop(columns=["NAME"])

    # ── 2. Add state name alongside FIPS code ───────────────────────────
    if "state" in df.columns:
        state_idx = int(df.columns.get_loc("state")) + int(1)
        if "state_name" not in df.columns:
            df.insert(
                state_idx,
                "state_name",
                df["state"].map(lambda x: FIPS_STATES.get(x, x)),
            )

    # ── 3. Drop annotation / metadata columns from group() pulls ────────
    if group_name is not None:
        drop = [c for c in df.columns if c.endswith(_JUNK_SUFFIXES) or c == "GEO_ID"]
        df = df.drop(columns=[c for c in drop if c in df.columns], errors="ignore")

    # ── 4. Rename variable columns ──────────────────────────────────────
    if group_name is not None:
        labels = _fetch_group_labels(group_name, dataset, year)
        if labels:
            rename_map = {}
            for col in df.columns:
                if col in labels:
                    rename_map[col] = f"{name}__{labels[col]}"
            seen = set()
            safe_map = {}
            for old, new in rename_map.items():
                if new in seen or new in df.columns:
                    safe_map[old] = f"{new} ({old})"
                else:
                    safe_map[old] = new
                    seen.add(new)
            df = df.rename(columns=safe_map)

    elif var_list:
        if len(var_list) == 1:
            df = df.rename(columns={var_list[0]: name})
        else:
            # Multi-var → fetch labels from metadata, prefix with series name
            labels = _fetch_var_labels(var_list, dataset, year)
            rename_map = {}
            for v in var_list:
                if v not in df.columns:
                    continue
                if v in labels:
                    rename_map[v] = f"{name}__{labels[v]}"
                else:
                    rename_map[v] = f"{name}__{v}"  # fallback to raw code
            seen = set()
            safe_map = {}
            for old, new in rename_map.items():
                if new in seen or new in df.columns:
                    safe_map[old] = f"{new} ({old})"
                else:
                    safe_map[old] = new
                    seen.add(new)
            df = df.rename(columns=safe_map)

    # ── 5. Move geo columns to front in a sensible order ───────────────
    _GEO_ORDER = [
        "state",
        "state_name",
        "county",
        "county_name",
        "tract",
        "tract_name",
        "block group",
        "block",
        "place",
        "place_name",
        "zip code tabulation area",
        "metropolitan statistical area/micropolitan statistical area",
        "congressional district",
        "school district (unified)",
        "us",
    ]
    geo_present = [c for c in _GEO_ORDER if c in df.columns]
    other_cols = [c for c in df.columns if c not in geo_present]
    df = df[geo_present + other_cols]

    # ── 6. Cast numeric columns ─────────────────────────────────────────
    for col in df.columns:
        if col not in geo_present:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  MAIN LOADER                                                            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _load_census_bureau(config: Config) -> dict[str, pd.DataFrame] | None:
    """
    Pull Census Bureau data according to *config*.

    Returns a dict of DataFrames keyed by friendly name, or None on failure.
    """
    try:
        load_dotenv()
        api_key = os.getenv("CENSUS_API_KEY")
        if not api_key:
            raise ValueError("CENSUS_API_KEY not found in environment")
    except Exception as e:
        print(f"Invalid / No API Key provided. {e}")
        return None

    try:
        census_client = Census(key=api_key)
    except Exception as e:
        print(f"Error initializing Census client: {e}")
        return None

    series_dict = config.SERIES
    geo = config.GEO
    year = config.YEAR

    frames: dict[str, pd.DataFrame] = {}
    failed: list[tuple[str, str, str]] = []

    def _batched(data: dict, size: int):
        it = iter(data.items())
        for _ in range(0, len(data), size):
            yield dict(islice(it, size))

    for batch in _batched(series_dict, config.BATCH_SIZE):
        for series_id, (name, dataset, variables) in batch.items():
            try:
                var_list, group_name = _parse_variables(variables)
                dispatch = DATASET_DISPATCH.get(dataset)

                if dispatch is None:
                    raise KeyError(f"Unknown dataset '{dataset}' for {series_id}")

                if callable(dispatch):
                    client_attr = dispatch(census_client)
                    df = _pull_wrapped(client_attr, var_list, group_name, geo, year)
                else:
                    df = _pull_raw(dispatch, var_list, group_name, geo, year, api_key)

                df = _clean_frame(df, name, var_list, group_name, dataset, year)
                df.name = name
                frames[name] = df

                var_label = (
                    f"group({group_name})" if group_name else f"{len(var_list)} vars"
                )
                print(f"  ✓ {name:<40s} ({series_id:<30s} [{dataset}] {var_label})")
                time.sleep(0.5)

            except Exception as e:
                failed.append((series_id, name, str(e)))
                print(f"  ✗ {name:<40s} ({series_id}) — {e}")
                time.sleep(0.5)

    if failed:
        print(f"\n⚠  {len(failed)} series failed:")
        for sid, nm, err in failed:
            print(f"    {nm} ({sid}): {err}")

    print(f"\nLoaded {len(frames)} series  |  {len(failed)} failed")
    return frames
