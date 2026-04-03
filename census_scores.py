import pandas as pd
from typing import Any, Callable, Optional


def blank(df: Any) -> Any:
    """Helper for specs that produce columns but have no actual logic."""
    return df


def score(df: pd.DataFrame) -> pd.DataFrame: ...
