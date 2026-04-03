from typing import Optional, Any
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from census import Census
import os, time
from .series import ALL_SERIES


class Config:
    """
    Configuration for a FRED data pull.

    Parameters
    ----------
    filename : str
        Name of the output CSV file (e.g. "fred_master.csv").
    output_path : Path
        Directory where the CSV will be saved.
    start : str, optional
        Observation start date in 'YYYY-MM-DD' format.
        Defaults to '1990-01-01'.
    resample_rule : str, optional
        Pandas resample frequency string.  Controls the output granularity.
        Defaults to 'W-FRI' (weeks ending Friday).
    mean_freqs : set[str], optional
        Set of native-frequency codes whose series should be aggregated
        via MEAN when resampling (e.g. daily series averaged into weekly
        buckets).  All other frequencies use LAST.
        Defaults to {'D'} — daily series are averaged; everything else
        takes the last observation per period.
    series : dict, optional
        Custom series catalog mapping FRED IDs to (friendly_name, native_freq)
        tuples.  When None the full built-in catalog is used.
        Build a custom one by merging category dicts from series.py::

            from series import INFLATION, LABOR
            Config(..., series={**INFLATION, **LABOR})
    """

    def __init__(
        self,
        filename: str,
        output_path: Path | str,
        start: str = "1990-01-01",
        series: Optional[dict] = None,
    ):
        self.FILENAME = filename
        self.OUTPUT_PATH = Path(output_path).resolve()
        self.START = start
        self.SERIES = series  # None → use ALL_SERIES


def load_census_bureau(config: Config) -> pd.DataFrame | None:
    """
    Placeholder function for loading Census Bureau data.

    Parameters
    ----------
    config : Config
    Configuration object containing parameters for the data pull.
    """
    try:
        load_dotenv()
        apikey = os.getenv("CENSUS_API_KEY")
    except Exception as e:
        print(f"Invalid / No API Key provided. {e}")
        return None
    try:
        census = Census(key=apikey)
    except Exception as e:
        print(f"Error initializing Census client: {e}")
        return None
    series_dict = config.SERIES if config.SERIES is not None else ALL_SERIES

    ...
    return pd.DataFrame()  # Placeholder return value
