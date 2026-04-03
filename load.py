import os
import sys
from pathlib import Path
from typing import Optional
import pandas as pd
from .loader import Config, load_census_bureau
from .census_scores import score
from .series import ALL_SERIES, CATEGORIES, SUBCATEGORIES


def pull_census(config: Config, apply_score: bool = False) -> pd.DataFrame | None: ...
