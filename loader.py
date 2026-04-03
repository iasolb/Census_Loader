from typing import Optional, Any
from pathlib import Path
from itertools import islice
import pandas as pd
from dotenv import load_dotenv
from census import Census
import os, time
from .series import ALL_SERIES


class Config:
    """
    Configuration for a Census data pull.


    Parameters
    ----------
    filename : str
        Name of the output CSV file (e.g. "fred_master.csv").
    output_path : Path
        Directory where the CSV will be saved.
    start : str, optional
        Observation start date in 'YYYY-MM-DD' format.
        Defaults to '1990-01-01'.
    series : dict, optional
        Custom series catalog mapping FRED IDs to (friendly_name, native_freq)
        tuples.  When None the full built-in catalog is used.
        Build a custom one by merging category dicts from series.py::
    batch_size : int, number of series called per batch via census API
            from series import
            Config(..., series={})
    """

    def __init__(
        self,
        filename: str,
        output_path: Path | str,
        start: str = "1990-01-01",
        series: Optional[dict] = None,
        batch_size: int = 50,
    ):
        self.FILENAME: str = filename
        self.OUTPUT_PATH: Path = Path(output_path).resolve()
        self.START: str = start
        self.SERIES = series  # None → use ALL_SERIES
        self.BATCH_SIZE: int = batch_size


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

    def pull_all(series_dict: dict) -> pd.DataFrame:
        """
        Pull every series from FRED, resample, and forward-fill.

        Daily series  → weekly MEAN  (captures full week's behavior)
        All others    → weekly LAST  (point-in-time, then ffill fills the gaps)

        Returns a single wide DataFrame indexed by week-ending date.
        """
        frames = {}
        failed = []

        def batch_dictionary(data, batch_size=50):
            it = iter(data.items())
            for i in range(0, len(data), batch_size):
                yield {k: v for k, v in islice(it, batch_size)}

        for batch in batch_dictionary(series_dict, 50):
            for series_id, (name, native_freq) in batch.items():
                try:
                    s = pd.DataFrame(
                        census.acs5.get(
                            # TODO Insert Query.
                        )
                    )
                    s.name = name
                    frames[name] = s
                    print(f"  ✓ {name:<40s} ({series_id:<18s} {native_freq} → {agg})")
                    time.sleep(0.5)  # be nice to the API

                except Exception as e:
                    failed.append((series_id, name, str(e)))
                    print(f"  ✗ {name:<40s} ({series_id}) — {e}")
                    time.sleep(0.5)  # be nice to the API

        df = pd.DataFrame(frames)
        df = df.ffill()
        df.index.name = "date"

        if failed:
            print(f"\n⚠  {len(failed)} series failed:")
            for sid, nm, err in failed:
                print(f"    {nm} ({sid}): {err}")

        print(
            f"\nLoaded {len(frames)} series  |  {df.shape[0]} weeks  |  {df.columns.size} columns"
        )
        return df

    df = pull_all(series_dict)

    return df
