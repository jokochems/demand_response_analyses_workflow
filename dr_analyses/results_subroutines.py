import math
from typing import List, Dict

import numpy as np
import pandas as pd
from fameio.source.cli import Options

from dr_analyses.container import Container
from dr_analyses.time import cut_leap_days, create_time_index, AMIRIS_TIMESTEPS_PER_YEAR


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
            f"{cont.config_workflow['output_folder']}"
            f"{cont.trimmed_scenario.split('_')[3]}/"
            f"{cont.trimmed_baseline_scenario}"
            f"/EnergyExchangeMulti.csv",
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

            if cont.config_workflow["tariff_config"]["mode"] == "from_file":
                multiplier = component["Multiplier"]
                calculate_dynamic_price_component_from_file(
                    power_prices, component, multiplier
                )
            elif (
                cont.config_workflow["tariff_config"]["mode"]
                == "from_workflow"
            ):
                multiplier = pd.read_csv(
                    component["Multiplier"], sep=";", header=None, index_col=0
                )
                calculate_dynamic_price_component_from_workflow(
                    cont, power_prices, component, multiplier
                )
            else:
                raise ValueError("Invalid tariff configuration mode selected!")

        else:
            power_prices["DYNAMIC_POWER_PRICE"] = 0
    power_prices.drop(columns="ElectricityPriceInEURperMWH", inplace=True)

    if use_baseline_prices:
        cont.set_baseline_power_prices(power_prices)
    else:
        cont.set_power_prices(power_prices)


def calculate_dynamic_price_component_from_workflow(
    cont: Container,
    power_prices: pd.DataFrame,
    component: Dict,
    multiplier: pd.DataFrame,
) -> None:
    """Calculate and return the values for a dynamic component"""
    power_prices = create_fame_time_index(power_prices, cont)

    to_concat = []
    for year, group in power_prices["ElectricityPriceInEURperMWH"].groupby(
        power_prices.index.str[:4]
    ):
        conditions = [
            group.values
            * multiplier.loc[multiplier.index.str[:4] == year, 1].values[0]
            < component["LowerBound"],
            group.values
            * multiplier.loc[multiplier.index.str[:4] == year, 1].values[0]
            > component["UpperBound"],
        ]
        choices = [
            component["LowerBound"],
            component["UpperBound"],
        ]
        to_concat.extend(
            list(
                np.select(
                    conditions,
                    choices,
                    group.values
                    * multiplier.loc[
                        multiplier.index.str[:4] == year, 1
                    ].values[0],
                )
            )
        )
    power_prices[f"DYNAMIC_{component['ComponentName']}"] = to_concat


def create_fame_time_index(ts: pd.DataFrame, cont: Container) -> pd.DataFrame:
    """Replace existing index of DataFrame with a FAME time index"""
    start_time = cont.scenario_yaml["GeneralProperties"]["Simulation"][
        "StartTime"
    ]
    end_time = cont.scenario_yaml["GeneralProperties"]["Simulation"][
        "StopTime"
    ]
    time_index = create_time_index(start_time, end_time)
    dummy_series = pd.Series(index=time_index, data=0)
    dummy_series = cut_leap_days(dummy_series)
    ts.set_index(dummy_series.index, inplace=True)
    ts.index = ts.index.astype(str).str.replace(" ", "_")

    return ts


def calculate_dynamic_price_component_from_file(
    power_prices: pd.DataFrame, component: Dict, multiplier: float
):
    """Calculate and return the values for a dynamic component"""
    conditions = [
        power_prices["ElectricityPriceInEURperMWH"].values * multiplier
        < component["LowerBound"],
        power_prices["ElectricityPriceInEURperMWH"].values * multiplier
        > component["UpperBound"],
    ]
    choices = [
        component["LowerBound"],
        component["UpperBound"],
    ]
    power_prices[f"DYNAMIC_{component['ComponentName']}"] = np.select(
        conditions,
        choices,
        power_prices["ElectricityPriceInEURperMWH"].values * multiplier,
    )


def add_static_prices(cont: Container) -> None:
    """Obtain static prices and add them to power prices time series

    OtherSurchargesInEURPerMWH is the only price component to include
    all static price shares

    :param Container cont: container object with configuration and results
    info
    """
    if cont.config_workflow["tariff_config"]["mode"] == "from_workflow":
        price_component = pd.read_csv(
            cont.load_shifting_data["Attributes"]["Policy"][
                "OtherSurchargesInEURPerMWH"
            ],
            sep=";",
            index_col=0,
            header=None,
        )
        cont.power_prices = extract_static_price(
            price_component, cont.power_prices
        )
        cont.baseline_power_prices = extract_static_price(
            price_component, cont.baseline_power_prices
        )

    if cont.config_workflow["tariff_config"]["mode"] == "from_file":
        price_component = cont.load_shifting_data["Attributes"]["Policy"][
            "OtherSurchargesInEURPerMWH"
        ]
        cont.power_prices["STATIC_POWER_PRICE"] = price_component
        cont.baseline_power_prices["STATIC_POWER_PRICE"] = price_component


def extract_static_price(
    price_component: pd.DataFrame, power_price_ts: pd.DataFrame
) -> pd.DataFrame:
    """Extract static price and append it to power price time series"""
    to_concat = []
    for year, group in power_price_ts.groupby(power_price_ts.index.str[:4]):
        static_value = price_component.loc[
            price_component.index.str[:4] == year, 1
        ].values[0]
        group["STATIC_POWER_PRICE"] = static_value
        to_concat.append(group)

    return pd.concat(to_concat)


def derive_lifetime_from_simulation_horizon(cont: Container) -> int:
    """Return the simulation horizon in years"""
    return math.ceil(len(cont.results) / AMIRIS_TIMESTEPS_PER_YEAR)


def calculate_annuity_factor(n, interest) -> float:
    """Return annuity factor for given number of years and interest rate"""
    return ((1 + interest) ** n * interest) / ((1 + interest) ** n - 1)
