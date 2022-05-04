from typing import List

import numpy as np
import pandas as pd
from fameio.source.cli import Config

from dr_analyses.container import Container


def add_abs_values(results: pd.DataFrame, columns: List[str]) -> None:
    """Calculate absolute values for given columns and append them"""
    for col in columns:
        results["Absolute" + col] = results[col].abs()


def add_baseline_load_profile(results: pd.DataFrame, file_name: str) -> None:
    """Add baseline load profile to results data"""
    baseline_load_profile = pd.read_excel(file_name)["absolute"].values
    results["BaselineLoadProfile"] = baseline_load_profile


def calculate_dynamic_price_time_series(
    cont: Container, use_baseline_prices=False
) -> None:
    """Calculate dynamic price time series from energy exchange prices

    :param Container cont: container object with configuration and results info
    :param boolean use_baseline_prices: if True, use prices from baseline
    instead of those of current scenario
    """
    if use_baseline_prices:
        power_prices = pd.read_csv(
            cont.config_workflow["output_folder"]
            + cont.trimmed_baseline_scenario
            + "/EnergyExchange.csv",
            sep=";",
        )
    else:
        power_prices = pd.read_csv(
            cont.config_convert[Config.OUTPUT] + "/EnergyExchange.csv", sep=";"
        )

    power_prices = power_prices[["ElectricityPriceInEURperMWH"]]
    for component in cont.dynamic_components:
        conditions = [
            power_prices["ElectricityPriceInEURperMWH"].values * component["Multiplier"]
            < component["LowerBound"],
            power_prices["ElectricityPriceInEURperMWH"].values * component["Multiplier"]
            > component["UpperBound"],
        ]
        choices = [
            component["LowerBound"],
            component["UpperBound"],
        ]
        power_prices[component["ComponentName"]] = np.select(
            conditions,
            choices,
            power_prices["ElectricityPriceInEURperMWH"].values
            * component["Multiplier"],
        )
    power_prices.drop(columns="ElectricityPriceInEURperMWH", inplace=True)

    if use_baseline_prices:
        cont.set_baseline_power_prices(power_prices)
    else:
        cont.set_power_prices(power_prices)


def add_static_prices(cont: Container) -> None:
    """Obtain static prices and add them to power prices time series

    :param Container cont: container object with configuration and results info
    """
    dynamic_components_list = [
        col
        for col in cont.power_prices.columns
        if "ElectricityPriceInEURperMWH" not in col
    ]
    static_components_list = list(
        set(cont.price_components.keys()) - set(dynamic_components_list)
    )
    for component in static_components_list:
        price_component = 0
        component_data = cont.load_shifting_data["Attributes"][
            cont.price_components[component]["Group"]
        ]
        if isinstance(cont.price_components[component]["Attribute"], list):
            for attribute in cont.price_components[component]["Attribute"]:
                price_component += component_data[attribute]
        else:
            price_component = component_data[
                cont.price_components[component]["Attribute"]
            ]

        cont.power_prices[component] = price_component
