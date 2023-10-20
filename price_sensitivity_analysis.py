import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

PATH_IN = r"Y:\koch_j0\amiris\demand_response\demand_response_analyses_workflow\results\ind_cluster_shift_only\95\scenario_w_dr_95_100_dynamic_0_LP"  # noqa: E501
PATH_OUT = "./calculations/price_sensitivity/"
FILE_NAME = r"EnergyExchangeMulti_ind_shift_only_95_100_dyn_0_LP_MO_price_sensitivity.xlsx"


def analyse_price_sensitivity(path: str, file_name: str):
    """Analyse the per year price sensitivity"""
    data = pd.read_excel(f"{path}/{file_name}", index_col=0)
    slope = pd.DataFrame(columns=["price_sensitivity_estimate"])
    for val in data.index.str[:4].unique():
        filtered = data.loc[data.index.str[:4] == val]
        create_price_sensitivity_scatter_plot(filtered, val)
        filtered.to_csv(f"{PATH_OUT}price_sensitivity_for_{val}.csv", sep=";")
        slope.loc[
            val, "price_sensitivity_estimate"
        ] = create_price_duration_curve_plot(filtered, val)
    slope.to_csv(f"{PATH_OUT}price_sensitivity_estimate.csv", sep=";")
    slope = slope.astype("float64")
    slope_hourly = resample_to_hourly_frequency(slope)
    slope_hourly.to_csv(f"{PATH_OUT}price_sensitivity_estimate_hourly.csv", sep=";", header=False)


def create_price_sensitivity_scatter_plot(filtered: pd.DataFrame, val: str):
    """Create a price sensitivity scatter plot"""
    _ = plt.scatter(
        x=filtered["PLANNED_ElectricityPriceInEURperMWH"].values,
        y=filtered["Price_Difference/Flex_Load"].values,
    )
    _ = plt.title(f"Price sensitivity for {val}")
    _ = plt.xlabel("Electricity Price in €/MWh")
    _ = plt.ylabel("Price sensitivity in €/MWh/MWh")
    _ = plt.savefig(f"{PATH_OUT}price_sensitivity_for_{val}.png", dpi=300)
    plt.close()


def create_price_duration_curve_plot(
    filtered: pd.DataFrame, val: str
) -> float:
    """Create a plot for a price duration curve"""
    price_duration_curve = filtered[
        "PLANNED_ElectricityPriceInEURperMWH"
    ].sort_values(ascending=True)
    price_duration_curve.index = range(len(price_duration_curve))
    fig, ax = plt.subplots(figsize=(15, 5))
    _ = price_duration_curve.plot(ax=ax)
    _ = plt.title(f"Price duration curve for {val}")
    _ = plt.xlabel("time in hours")
    _ = plt.ylabel("Electricity Price in €/MWh")
    slope = create_linear_regression(price_duration_curve, ax)
    _ = plt.savefig(f"{PATH_OUT}price_duration_curve_for_{val}.png", dpi=300)
    plt.close()
    return slope


def create_linear_regression(data: pd.Series, ax: matplotlib.axes) -> float:
    """Create a linear regression for given pd.Series"""
    slope, intercept, r, _, __ = stats.linregress(data.index, data.values)
    _ = ax.plot(
        data.index,
        intercept + slope * data.index,
        "k",
        linestyle="--",
        label="linear fit",
    )
    _ = plt.annotate(f"$r^{2}$: {r ** 2}", xy=(0, 0.95 * data.values.max()))
    return slope


def resample_to_hourly_frequency(
    data: pd.Series or pd.DataFrame,
    end_year: int = 2034,
) -> pd.Series or pd.DataFrame:
    """Resamples a given time series to hourly frequency

    Parameters
    ----------
    data: pd.Series or pd.DataFrame
        Data to be resampled

    end_year: int
        Last year of time series

    Returns
    -------
    resampled_data: pd.Series or pd.DataFrame
        Data in hourly resolution
    """
    resampled_data = data.copy()
    resampled_data.loc[f"{end_year + 1}-01-01 00:00:00"] = resampled_data.iloc[
        -1
    ]
    resampled_data.index = pd.to_datetime(pd.Series(resampled_data.index))
    resampled_data = resampled_data.resample("H").interpolate("ffill")[:-1]
    resampled_data = cut_leap_days(resampled_data)

    return resampled_data


def cut_leap_days(time_series):
    """Take a time series index with real dates and cut the leap days out

    Actual time stamps cannot be interpreted. Instead consider 8760 hours
    of a synthetical year

    Parameters
    ----------
    time_series : pd.Series or pd.DataFrame
        original time series with real life time index

    Returns
    -------
    time_series : pd.Series or pd.DataFrame
        Time series, simply cutted down to 8 760 hours per year
    """
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


def is_leap_year(year):
    """Check whether given year is a leap year or not

    Parameters:
    -----------
    year: :obj:`int`
        year which shall be checked

    Returns:
    --------
    leap_year: :obj:`boolean`
        True if year is a leap year and False else
    """
    leap_year = False

    if year % 4 == 0:
        leap_year = True
    if year % 100 == 0:
        leap_year = False
    if year % 400 == 0:
        leap_year = True

    return leap_year


if __name__ == "__main__":
    analyse_price_sensitivity(PATH_IN, FILE_NAME)
