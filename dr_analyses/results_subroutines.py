from typing import Dict, List

import pandas as pd
from fameio.source.cli import Config


# Map dynamic identifier to static component value
price_components = {
    "POWER_PRICE": {
        "Group": "BusinessModel",
        "Attribute": "AverageMarketPriceInEURPerMWH",
    },
    "EEG_SURCHARGE": {
        "Group": "Policy",
        "Attribute": "EEGSurchargeInEURPerMWH",
    },
    "VOLUMETRIC_NETWORK_CHARGE": {
        "Group": "Policy",
        "Attribute": "VolumetricNetworkChargeInEURPerMWH",
    },
    "OTHER_COMPONENTS": {
        "Group": "Policy",
        "Attribute": [
            "ElectricityTaxInEURPerMWH",
            "OtherSurchargesInEURPerMWH",
        ],
    },
}


def add_abs_values(results: pd.DataFrame, columns: List[str]) -> None:
    """Calculate absolute values for given columns and append them"""
    for col in columns:
        results["Absolute" + col] = results[col].abs()


def add_baseline_load_profile(results: pd.DataFrame, file_name: str) -> None:
    """Add baseline load profile to results data"""
    baseline_load_profile = pd.read_excel(file_name)["absolute"].values
    results["BaselineLoadProfile"] = baseline_load_profile


def calculate_dynamic_price_time_series(
    config_convert: Dict, dynamic_components: List
) -> pd.DataFrame:
    """Calculate dynamic price time series from energy exchange prices"

    :param dict config_convert: config for converting results of AMIRIS run 
    :param list dynamic_components: dynamic tariff component 
    with name, multiplier and bounds
    :return pd.DataFrame power_prices: power prices 
    with dynamic tariff components
    """ ""
    power_prices = pd.read_csv(
        config_convert[Config.OUTPUT] + "/EnergyExchange.csv", sep=";"
    )
    power_prices = power_prices[["ElectricityPriceInEURperMWH"]]
    for component in dynamic_components:
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
        power_prices[component["ComponentName"]] = np.select(
            conditions,
            choices,
            power_prices["ElectricityPriceInEURperMWH"].values
            * component["Multiplier"],
        )
    power_prices.drop(columns="ElectricityPriceInEURperMWH", inplace=True)

    return power_prices


def add_static_prices(
    load_shifting_data: Dict, power_prices: pd.DataFrame
) -> None:
    """Obtain static prices and add them to power prices time series

    :param dict load_shifting_data: parameterization of LoadShiftingTrader
    :param pd.DataFrame power_prices: time series data for dynamic prices
    """
    dynamic_components_list = [
        col
        for col in power_prices.columns
        if "ElectricityPriceInEURperMWH" not in col
    ]
    static_components_list = list(
        set(price_components.keys()) - set(dynamic_components_list)
    )
    for component in static_components_list:
        price_component = 0
        component_data = load_shifting_data["Attributes"][
            price_components[component]["Group"]
        ]
        if isinstance(price_components[component]["Attribute"], list):
            for attribute in price_components[component]["Attribute"]:
                price_component += component_data[attribute]
        else:
            price_component = component_data[
                price_components[component]["Attribute"]
            ]

        power_prices[component] = price_component
