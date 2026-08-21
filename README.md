# Census Loader

A Python wrapper around the U.S. Census Bureau API that abstracts away variable codes, dataset endpoints, and FIPS identifiers behind a clean, human-readable interface.

Instead of this:

```python
data = census.acs5.get(
    ("B19013_001E",),
    {"for": "county:*", "in": "state:25"},
    year=2022
)
```

You write this:

```python
cfg = Config(
    "output.pkl", "./data",
    year=2022,
    geo="county_in_state",
    state="Massachusetts",
    series=["MEDIAN_HH_INCOME", "TOTAL_POP", "MEDIAN_RENT"],
)
result = pull_census(cfg)
```

---

## Setup

### Requirements

```
pandas
numpy
census
python-dotenv

```

```bash
pip install -r requirements.txt
```

### API Key

Get a free key at [api.census.gov/data/key_signup.html](https://api.census.gov/data/key_signup.html), then add it to a `.env` file in your project root:

```
CENSUS_API_KEY=your_key_here
```

### Project Structure

```
Census_Loader/
  pyproject.toml
  requirements.txt
  README.md
  .env-example
  src/census_loader/
    __init__.py       # public API re-exports
    utils.py          # Config, loader, discovery tools
    load.py           # pull_census entry point
    series.py         # series catalog, GEO templates, FIPS codes
```

---

## Quickstart

```python
from census_loader import Config, pull_census

cfg = Config(
    "ma_counties.pkl",
    "./output",
    year=2022,
    geo="county_in_state",
    state="Massachusetts",
    series=["TOTAL_POP", "MEDIAN_HH_INCOME", "MEDIAN_RENT"],
)

result = pull_census(cfg)
# result is a dict of DataFrames keyed by friendly name
```

```python
result["Median_Household_Income"]
```
```
  state  state_name  county  county_name        Median_Household_Income
     25  Massachusetts  001  Barnstable County                  82631.0
     25  Massachusetts  003  Berkshire County                   58743.0
     25  Massachusetts  017  Middlesex County                  113880.0
     ...
```

---

## Exploring the Catalog

You never need to open `series.py`. Three discovery functions let you browse, search, and inspect everything from a REPL or notebook.

### Browse categories

```python
from census_loader import available, search, info

available()
```
```
Categories  (pass one to available() to drill down)

  POPULATION               ( 13 series)
    └ TOTAL_POPULATION, AGE_DETAIL
  RACE_ETHNICITY           ( 13 series)
    └ RACE, HISPANIC_ORIGIN
  INCOME                   ( 18 series)
    └ HOUSEHOLD_INCOME, EARNINGS, PUBLIC_ASSISTANCE
  HOUSING                  ( 25 series)
    └ HOUSING_UNITS, TENURE, HOME_VALUE, HOUSING_INFRASTRUCTURE
  ...

  TOTAL                    (169 series)
```

### Drill into a category or subcategory

```python
available("INCOME")
```
```
Category: INCOME  (18 series)

  MEDIAN_HH_INCOME                Median_Household_Income
  MEAN_HH_INCOME                  Mean_Household_Income
  HH_INCOME_BRACKETS              Household_Income_Distribution
  MEDIAN_INCOME_WHITE             Median_HH_Income_White
  ...
```

```python
available("HOUSEHOLD_INCOME")    # subcategory
```

### Search by keyword

```python
search("poverty")
search("median")
search("hispanic")
```

### Full details on a series

```python
info("MEDIAN_HH_INCOME")
```
```
  Key:          MEDIAN_HH_INCOME
  Name:         Median_Household_Income
  Category:     INCOME
  Subcategory:  HOUSEHOLD_INCOME
  Dataset:      acs5
  Variables:    1 code
                  B19013_001E
```

### Browse geography templates

```python
from census_loader import geos

geos()
```
```
Available Geometry Queries:

  state_all
    Query:    {'for': 'state:*'}
    Requires: None

  county_in_state
    Query:    {'for': 'county:*', 'in': 'state:{st}'}
    Requires: state

  tract_in_county
    Query:    {'for': 'tract:*', 'in': 'state:{st}&in=county:{co}'}
    Requires: state, county
  ...
```

---

## Config Reference

```python
Config(
    filename,       # Output filename (auto-corrects to .pkl)
    output_path,    # Directory for output files
    year=2022,      # ACS/PEP vintage year
    geo=...,        # Geography level (see below)
    state=...,      # State name or FIPS code
    county=...,     # County FIPS (3-digit)
    tract=...,      # Tract code
    series=...,     # What to pull (see below)
    batch_size=50,  # Max series per API batch
)
```

### Series selection

The `series` parameter accepts any granularity — individual series, subcategories, categories, or a mix:

```python
series=None                                         # everything (169 series)
series="TOTAL_POP"                                  # one series
series="INCOME"                                     # whole category (18 series)
series="HOUSEHOLD_INCOME"                           # subcategory (9 series)
series=["TOTAL_POP", "INCOME", "MEDIAN_RENT"]       # mix & match
series=["POVERTY", "HOUSEHOLD_INCOME", "TOTAL_POP"] # category + subcategory + series
```

Case-insensitive. Overlapping selections deduplicate automatically.

### Geography

Pass a template name and fill in the required parameters:

```python
# All states (default)
Config(..., geo="state_all")

# All counties in one state
Config(..., geo="county_in_state", state="Massachusetts")

# Tracts in one county
Config(..., geo="tract_in_county", state="Massachusetts", county="017")

# School districts in a state
Config(..., geo="school_district_in_state", state="Massachusetts")

# All ZCTAs
Config(..., geo="zcta_all")
```

State names resolve automatically — `"Massachusetts"` and `"25"` both work.

For edge cases not covered by templates, pass a raw dict:

```python
Config(..., geo={"for": "county:017", "in": "state:25"})
```

---

## Output Format

`pull_census` returns a `dict[str, pd.DataFrame]` and saves a pickle to your output path.

Each DataFrame has geo columns on the left (FIPS codes + human-readable names) and data columns on the right:

```
  state  state_name  county  county_name        Total_Population
     25  Massachusetts  001  Barnstable County           228996.0
     25  Massachusetts  003  Berkshire County             129288.0
```

Column naming depends on the series type:

| Series type | Example key | Column names |
|---|---|---|
| Single variable | `TOTAL_POP` | `Total_Population` |
| Multi-variable | `HOMEOWNERSHIP_RATE` | `Homeownership_Rate__Owner occupied`, `Homeownership_Rate__Total` |
| Group table | `HH_INCOME_BRACKETS` | `Household_Income_Distribution__Less than $10,000`, `Household_Income_Distribution__$10,000 to $14,999`, ... |

Labels are fetched automatically from the Census metadata API.

### Loading saved results

```python
from census_loader import pickle_loader

df = pickle_loader("ma_counties.pkl") # flattens pkl to one dataframe (since only one geo-level can be queried at a time, easy merge.)

```

### Flattening into a single DataFrame

Since every series in a pull shares the same geography, you can merge on the shared geo columns:

```python
from functools import reduce
import pandas as pd

frames = list(data.values())
shared = set(frames[0].columns)
for df in frames[1:]:
    shared &= set(df.columns)

merge_keys = [c for c in shared
              if all(not pd.api.types.is_numeric_dtype(df[c]) for df in frames)]

flat = reduce(
    lambda left, right: pd.merge(left, right, on=merge_keys, how="outer"),
    frames,
)
```

---

## Examples

### County-level dashboard data for one state

```python
cfg = Config(
    "ma_dashboard.pkl", "./output",
    year=2022,
    geo="county_in_state",
    state="Massachusetts",
    series=[
        "TOTAL_POP",
        "MEDIAN_HH_INCOME",
        "MEDIAN_RENT",
        "MEDIAN_HOME_VALUE",
        "HOMEOWNERSHIP_RATE",
        "HH_INCOME_BRACKETS",
    ],
)
pull_census(cfg)
```

### Tract-level deep dive

```python
cfg = Config(
    "middlesex_tracts.pkl", "./output",
    year=2022,
    geo="tract_in_county",
    state="Massachusetts",
    county="017",
    series=["TOTAL_POP", "MEDIAN_HH_INCOME", "POP_65_PLUS"],
)
pull_census(cfg)
```

### Full category pull, all states

```python
cfg = Config(
    "national_income.pkl", "./output",
    year=2022,
    series="INCOME",
)
pull_census(cfg)
```

### School district comparison

```python
cfg = Config(
    "ma_schools.pkl", "./output",
    year=2022,
    geo="school_district_in_state",
    state="Massachusetts",
    series=["TOTAL_POP", "MEDIAN_HH_INCOME", "HH_INCOME_BRACKETS"],
)
pull_census(cfg)
```

---

## API Limits

Free Census API keys allow 500 requests per day with a batch size of 50 variables per request. The loader sleeps 0.5s between calls to stay well under rate limits. Metadata label fetches (for column renaming) are not rate-limited and are cached per session.

---

## Available Categories

| Category | Series | Subcategories |
|---|---|---|
| POPULATION | 13 | TOTAL_POPULATION, AGE_DETAIL |
| RACE_ETHNICITY | 13 | RACE, HISPANIC_ORIGIN |
| NATIVITY_MIGRATION | 11 | NATIVITY, MIGRATION |
| LANGUAGE | 6 | — |
| EDUCATION | 10 | SCHOOL_ENROLLMENT, EDUCATIONAL_ATTAINMENT |
| HOUSEHOLDS | 12 | HOUSEHOLD_TYPE, MARITAL_STATUS, FERTILITY |
| INCOME | 18 | HOUSEHOLD_INCOME, EARNINGS, PUBLIC_ASSISTANCE |
| POVERTY | 12 | ACS_POVERTY, SAIPE_POVERTY |
| HEALTH_INSURANCE | 6 | ACS_HEALTH_INSURANCE, SAHIE_HEALTH_INSURANCE |
| EMPLOYMENT | 15 | EMPLOYMENT_STATUS, OCCUPATION_INDUSTRY, COMMUTING |
| HOUSING | 25 | HOUSING_UNITS, TENURE, HOME_VALUE, HOUSING_INFRASTRUCTURE |
| DISABILITY | 5 | — |
| VETERANS | 4 | — |
| PEP_POPULATION | 6 | — |
| DECENNIAL | 9 | DECENNIAL_REDISTRICTING, DECENNIAL_DHC |
| DATA_PROFILES | 4 | — |
| **Total** | **169** | |
