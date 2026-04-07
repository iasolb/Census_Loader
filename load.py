import os
import sys
from pathlib import Path
from typing import Optional
import pickle
from functools import reduce
import pandas as pd
from .utils import Config, _load_census_bureau
from .series import ALL_SERIES, CATEGORIES, SUBCATEGORIES

# PUBLIC API


def pull_census(config: Config) -> dict[str, pd.DataFrame] | None:
    """
    Pull Census Bureau data and optionally apply scoring.

    Returns a dict of DataFrames keyed by friendly name, or None on failure.
    Each DataFrame has rows = geographies and columns = variables + geo IDs.
    The result is persisted as a pickle for lossless round-tripping.
    """
    cfg = config if isinstance(config, Config) else None
    if cfg is None:
        print("Incorrect Configuration Format.")
        return None

    if cfg._series_input is not None:
        print(f"Custom series selection: {len(cfg.SERIES)} series to pull.")

    result = _load_census_bureau(config=config)
    if result is None:
        return None
    else:
        output = result
    # ── Persist ──────────────────────────────────────────────────────────
    config.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    fname = config.FILENAME
    if not fname.endswith(".pkl"):
        fname = fname.rsplit(".", 1)[0] + ".pkl" if "." in fname else fname + ".pkl"
    pkl_file = config.OUTPUT_PATH / fname

    with open(pkl_file, "wb") as f:
        pickle.dump(output, f)
    print(f"\n  Saved → {pkl_file}")

    return output
