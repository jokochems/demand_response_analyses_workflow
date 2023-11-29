from typing import Dict
import matplotlib as mpl
mpl.use('Agg')

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dr_analyses.time import create_time_index
from dr_analyses.workflow_routines import make_directory_if_missing


def analyse_price_sensitivity(config: Dict, dr_scen: str, power_margins: Dict):
    """Analyze price sensitivity for given cluster and tariff scenario"""
    residual_load = calculate_residual_load(config, dr_scen)
    consumer_energy_price = calculate_consumer_energy_price(config, dr_scen)
    sensitivity = {}
    price_sensitivity = pd.DataFrame(
        index=residual_load.index, columns=["residual_load", "sensitivity"]
    )
    price_sensitivity["residual_load"] = residual_load
    for iter_year in residual_load.index.year.unique():
        residual_load_iter_year = residual_load.loc[str(iter_year)]
        consumer_energy_price_iter_year = consumer_energy_price.loc[
            str(iter_year)
        ]
        create_price_sensitivity_scatter_plot(
            residual_load_iter_year,
            consumer_energy_price_iter_year,
            config,
            dr_scen,
            iter_year,
        )
        determine_price_sensitivity_proxy(
            residual_load_iter_year,
            consumer_energy_price_iter_year,
            sensitivity,
            iter_year,
            power_margins,
        )
        conditions = [
            residual_load_iter_year
            < sensitivity[iter_year]["residual_load_lower"],
            residual_load_iter_year
            > sensitivity[iter_year]["residual_load_upper"],
        ]
        choices = [0, 0]
        price_sensitivity.loc[str(iter_year), "sensitivity"] = np.select(
            conditions, choices, sensitivity[iter_year]["slope"]
        )
    price_sensitivity = price_sensitivity["sensitivity"]
    path_inputs = (
        f"{config['input_folder']}/"
        f"{config['data_sub_folder']}/"
        f"{config['load_shifting_focus_cluster']}/"
        f"{dr_scen.split('_', 1)[0]}/"
    )
    convert_time_series_index_to_fame_time(
        price_sensitivity,
        save=True,
        path=path_inputs,
        filename=f"price_sensitivity_estimate_{dr_scen}",
    )


def calculate_residual_load(config: Dict, dr_scen: str):
    """Calculate residual load from demand and vRES infeed"""
    dr_scen_short = dr_scen.split("_", 1)[0]
    path_results = (
        f"{config['output_folder']}/"
        f"{config['load_shifting_focus_cluster']}/"
        f"{dr_scen_short}/"
        f"scenario_wo_dr_{dr_scen_short}"
    )
    demand = pd.read_csv(f"{path_results}/DemandTrader.csv", sep=";")
    demand = demand["AwardedEnergyInMWH"].dropna().reset_index(drop=True)
    vres_infeed = pd.read_csv(
        f"{path_results}/VariableRenewableOperator.csv", sep=";"
    )
    vres_infeed = (
        vres_infeed.loc[vres_infeed["OfferedPowerInMW"].notna()]
        .groupby("TimeStep")
        .sum()["OfferedPowerInMW"]
        .reset_index(drop=True)
    )
    residual_load = demand - vres_infeed
    residual_load_index = create_time_index(
        start_time=config["simulation"]["StartTime"],
        end_time=config["simulation"]["StopTime"],
    )
    dummy_df = pd.DataFrame(index=residual_load_index)
    dummy_df = cut_leap_days(dummy_df)
    residual_load.index = dummy_df.index
    return cut_leap_days(residual_load)


def calculate_consumer_energy_price(config: Dict, dr_scen: str):
    """Calculate energy price considering static components and dynamic ones"""
    tariff_case = dr_scen.split("_", 1)[-1]
    path_inputs = (
        f"{config['input_folder']}/"
        f"{config['data_sub_folder']}/"
        f"{config['load_shifting_focus_cluster']}/"
        f"{dr_scen.split('_', 1)[0]}"
    )
    static_price = prepare_tariff_series(
        path_inputs, f"static_payments_{tariff_case}_annual.csv"
    )
    dynamic_multiplier = prepare_tariff_series(
        path_inputs, f"dynamic_multiplier_{tariff_case}_annual.csv"
    )
    electricity_price = prepare_electricity_price(
        config, "EnergyExchangeMulti.csv", dr_scen
    )
    consumer_energy_price = (
        static_price + electricity_price * dynamic_multiplier
    )
    return consumer_energy_price


def prepare_tariff_series(path: str, file_name: str) -> pd.Series:
    """Read, reindex, resample and return tariff series"""
    tariff_series = pd.read_csv(
        f"{path}/{file_name}", sep=";", index_col=0, header=None
    )
    tariff_series.index = pd.to_datetime(
        tariff_series.index.str.replace("_", " ")
    )
    return resample_to_hourly_frequency(tariff_series[1])


def prepare_electricity_price(
    config: Dict, file_name: str, dr_scen: str
) -> pd.Series:
    """Read and preprocess electricity price time series"""
    dr_scen_short = dr_scen.split("_", 1)[0]
    path_outputs = (
        f"{config['output_folder']}/"
        f"{config['load_shifting_focus_cluster']}/"
        f"{dr_scen_short}/"
        f"scenario_wo_dr_{dr_scen_short}"
    )
    electricity_price = pd.read_csv(f"{path_outputs}/{file_name}", sep=";")
    electricity_price_index = create_time_index(
        start_time=config["simulation"]["StartTime"],
        end_time=config["simulation"]["StopTime"],
    )
    dummy_df = pd.DataFrame(index=electricity_price_index)
    dummy_df = cut_leap_days(dummy_df)
    electricity_price.index = dummy_df.index
    return electricity_price["ElectricityPriceInEURperMWH"]


def determine_price_sensitivity_proxy(
    residual_load: pd.Series,
    consumer_energy_price: pd.Series,
    sensitivity: Dict,
    iter_year: int,
    power_margins: Dict[str, float],
):
    """Determine a proxy for price sensitivity for a given year"""
    common_df = pd.DataFrame(
        index=residual_load.index,
        data={
            "residual_load": residual_load,
            "consumer_electricity_price": consumer_energy_price,
        },
    )
    # Evaluate starting point in terms of residual load
    price_lower = common_df["consumer_electricity_price"].min()
    price_upper = common_df["consumer_electricity_price"].max()
    residual_load_lower = common_df.loc[
        common_df["consumer_electricity_price"] == price_lower,
        "residual_load",
    ].max()
    residual_load_upper = common_df.loc[
        common_df["consumer_electricity_price"] == price_upper,
        "residual_load",
    ].min()
    # Determine slope
    slope = (price_upper - price_lower) / float(
        residual_load_upper - residual_load_lower
    )
    sensitivity[iter_year] = {
        "slope": slope,
        "residual_load_lower": residual_load_lower - power_margins["up"],
        "residual_load_upper": residual_load_upper + power_margins["down"],
    }


def create_price_sensitivity_scatter_plot(
    residual_load: pd.Series,
    consumer_energy_price: pd.Series,
    config: Dict,
    dr_scen: str,
    year: int,
):
    """Create a scatter plot for prices over residual load for given year"""
    path_plots = (
        f"{config['input_folder']}/"
        f"{config['data_sub_folder']}/"
        f"{config['load_shifting_focus_cluster']}/"
        f"{dr_scen.split('_', 1)[0]}/"
        f"price_sensitivity/"
    )
    make_directory_if_missing(path_plots)
    fig, ax = plt.subplots(figsize=(15, 5))
    _ = ax.scatter(
        x=residual_load.values,
        y=consumer_energy_price.values,
    )
    _ = plt.title(f"Price sensitivity analysis for {year}")
    _ = plt.xlabel("Residual load in MWh")
    _ = plt.ylabel("Electricity Price in €/MWh")
    _ = plt.tight_layout()
    _ = plt.savefig(
        f"{path_plots}price_sensitivity_for_{year}_{dr_scen}.png", dpi=300
    )
    plt.close()


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


def convert_time_series_index_to_fame_time(
    time_series: pd.DataFrame,
    save: bool,
    path: str,
    filename: str,
) -> pd.DataFrame:
    """Convert index of given time series to FAME time format

    Parameters
    ----------
    time_series: pd.DataFrame
        DataFrame to be converted

    save: boolean
        If True, save converted data to disk

    path: str
        Path to store the data

    filename: str
        File name of the data

    Returns
    -------
    time_series_reindexed: pd.DataFrame
        manipulated DataFrame with FAME time stamps
    """
    time_series_reindexed = time_series.copy()
    time_series_reindexed.index = time_series_reindexed.index.astype(str)
    time_series_reindexed.index = time_series_reindexed.index.str.replace(
        " ", "_"
    )

    if save:
        save_given_data_set_for_fame(time_series_reindexed, path, filename)

    return time_series_reindexed


def save_given_data_set_for_fame(
    data_set: pd.DataFrame or pd.Series, path: str, filename: str
):
    """Save a given data set using FAME time and formatting

    Parameters
    ----------
    data_set: pd.DataFrame or pd.Series
        Data set to be saved (column-wise)

    path: str
        Path to store the data

    filename: str
        File name for storing
    """
    make_directory_if_missing(path)
    if isinstance(data_set, pd.DataFrame):
        if not isinstance(data_set.columns, pd.MultiIndex):
            for col in data_set.columns:
                data_set[col].to_csv(
                    f"{path}{filename}_{col}.csv", header=False, sep=";"
                )
        else:
            for col in data_set.columns:
                data_set[col].to_csv(
                    f"{path}{filename}_{col[0]}_{col[1]}.csv",
                    header=False,
                    sep=";",
                )
    elif isinstance(data_set, pd.Series):
        data_set.to_csv(f"{path}{filename}.csv", header=False, sep=";")
    else:
        raise ValueError("Data set must be of type pd.DataFrame or pd.Series.")
