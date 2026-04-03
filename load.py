import os
import sys
from pathlib import Path
from typing import Optional
import pandas as pd
from .loader import Config, load_census_bureau
from .census_scores import score
from .series import ALL_SERIES, CATEGORIES, SUBCATEGORIES


def pull_census(config: Config, apply_scores: bool = False) -> pd.DataFrame | None:
    cfg = config if isinstance(config, Config) else None
    if cfg is None:
        print("Incorrect Configuration Format.")
        return None
    if cfg.SERIES != ALL_SERIES:
        print("Custom series catalog provided. Pulling subset of Census Bureau data.")
    raw = pd.DataFrame(load_census_bureau(config=config))
    if apply_scores:
        output = score(raw)
    else:
        output = raw
    config.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = config.OUTPUT_PATH / config.FILENAME
    pd.DataFrame(output).to_csv(out_file)
    print(f"\nSaved → {out_file}")
    return output
