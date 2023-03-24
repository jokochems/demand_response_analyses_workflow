import pandas as pd

AMIRIS_TIMESTEPS_PER_YEAR = 8760


def cut_leap_days(
    time_series: pd.DataFrame or pd.Series,
) -> pd.DataFrame or pd.Series:
    """Take a time series index with real dates and cut the leap days out"""
    years = sorted(list(set(getattr(time_series.index, "year"))))
    for year in years:
        if is_leap_year(year):
            try:
                time_series.drop(
                    time_series.loc[
                        (time_series.index.year == year)
                        & (time_series.index.month == 12)
                        & (time_series.index.day == 31)
                    ].index,
                    inplace=True,
                )
            except KeyError:
                continue

    return time_series


def is_leap_year(year: int) -> bool:
    """Check whether given year is a leap year or not"""
    leap_year = False

    if year % 4 == 0:
        leap_year = True
    if year % 100 == 0:
        leap_year = False
    if year % 400 == 0:
        leap_year = True

    return leap_year


def create_time_index(start_time: str, end_time: str):
    """Create and return pd.date_range from FAME timestamps"""
    start_time = pd.to_datetime(start_time.replace("_", " ")) + pd.Timedelta(
        "2m"
    )
    end_time = pd.to_datetime(end_time.replace("_", " ")) + pd.Timedelta("2m")
    return pd.date_range(start=start_time, end=end_time, freq="H")[:-1]
