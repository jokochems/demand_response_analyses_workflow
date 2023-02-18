from typing import List

import numpy as np
import pandas as pd
from fameio.source.cli import Options

from dr_analyses.container import Container


def add_abs_values(results: pd.DataFrame, columns: List[str]) -> None:
    """Calculate absolute values for given columns and append them"""
    for col in columns:
        results["Absolute" + col] = results[col].abs()


def add_baseline_load_profile(
    results: pd.DataFrame, cont: Container, key: str
) -> None:
    """Add baseline load profile to results data"""
    baseline_load_profile = pd.read_csv(
        f"{cont.config_workflow['input_folder']}/data/{key.split('_', 1)[0]}/"
        f"{cont.config_workflow['baseline_load_file']}_"
        f"{cont.config_workflow['load_shifting_focus_cluster']}.csv",
        sep=";",
        header=None,
    )[1]
    baseline_peak_load = cont.load_shifting_data["Attributes"][
        "LoadShiftingPortfolio"
    ]["BaselinePeakLoadInMW"]
    baseline_load_profile *= baseline_peak_load
    results["BaselineLoadProfile"] = baseline_load_profile


def calculate_dynamic_price_time_series(
    cont: Container, use_baseline_prices: bool = False
) -> None:
    """Calculate dynamic price time series from energy exchange prices

    :param Container cont: container object with configuration and results info
    :param bool use_baseline_prices: if True, use prices from baseline
    instead of those of current scenario
    """
    if use_baseline_prices:
        power_prices = pd.read_csv(
            cont.config_workflow["output_folder"]
            + cont.trimmed_scenario.split("_")[3]
            + cont.trimmed_baseline_scenario
            + "/EnergyExchangeMulti.csv",
            sep=";",
        )
    else:
        if not cont.config_convert[Options.OUTPUT]:
            raise ValueError(
                "Processing results without aggregating them first "
                "is not implemented."
            )
        power_prices = pd.read_csv(
            cont.config_convert[Options.OUTPUT] + "/EnergyExchangeMulti.csv",
            sep=";",
        )

    power_prices = power_prices[["ElectricityPriceInEURperMWH"]]
    for component in cont.dynamic_components:
        if component["ComponentName"] != "DUMMY":
            conditions = [
                power_prices["ElectricityPriceInEURperMWH"].values
                * component["Multiplier"]
                < component["LowerBound"],
                power_prices["ElectricityPriceInEURperMWH"].values
                * component["Multiplier"]
                > component["UpperBound"],
            ]
            choices = [
                component["LowerBound"],
                component["UpperBound"],
            ]
            power_prices[f"DYNAMIC_{component['ComponentName']}"] = np.select(
                conditions,
                choices,
                power_prices["ElectricityPriceInEURperMWH"].values
                * component["Multiplier"],
            )
        else:
            power_prices["DYNAMIC_POWER_PRICE"] = 0
    power_prices.drop(columns="ElectricityPriceInEURperMWH", inplace=True)

    if use_baseline_prices:
        cont.set_baseline_power_prices(power_prices)
    else:
        cont.set_power_prices(power_prices)


def add_static_prices(cont: Container) -> None:
    """Obtain static prices and add them to power prices time series

    OtherSurchargesInEURPerMWH is the only price component to include
    all static price shares

    :param Container cont: container object with configuration and results
    info
    """
    price_component = cont.load_shifting_data["Attributes"]["Policy"][
        "OtherSurchargesInEURPerMWH"
    ]

    cont.power_prices["STATIC_POWER_PRICE"] = price_component
    cont.baseline_power_prices["STATIC_POWER_PRICE"] = price_component
