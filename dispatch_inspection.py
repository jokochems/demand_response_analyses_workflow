import math
import os
from typing import Dict

import numpy as np
import pandas as pd

from dr_analyses.time import cut_leap_days
from dr_analyses.workflow_config import (
    add_args,
    extract_simple_config,
)
from dr_analyses.workflow_routines import load_yaml_file


def derive_combined_results(
    config_dispatch: Dict, scenario: str, cluster: str, tariff: str
):
    """Create combined results for case currently evaluated"""
    combined_results = read_and_combine_results(
        config_dispatch, scenario, cluster, tariff
    )
    combined_results = add_variable_shifting_costs(
        config_dispatch,
        cluster,
        scenario,
        combined_results,
    )
    combined_results = add_price_estimate(
        config_dispatch,
        cluster,
        scenario,
        tariff,
        combined_results,
    )
    combined_results.to_csv(
        f"{config_dispatch['output_folder']}{cluster}/"
        f"{scenario}/scenario_w_dr_{scenario}_"
        f"{tariff.split('_', 4)[-1]}/"
        f"combined_results.csv",
        sep=";",
    )


def read_and_combine_results(
    config_dispatch: Dict, scenario: str, cluster: str, tariff: str
):
    """Read and combine energy exchange and load shifting results"""
    file_path = (
        f"{config_dispatch['output_folder']}{cluster}/" f"{scenario}/{tariff}"
    )
    load_shifting_trader_results = pd.read_csv(
        f"{file_path}/LoadShiftingTraderExtended.csv",
        sep=";",
    )
    energy_exchange_results = pd.read_csv(
        f"{file_path}/EnergyExchangeMulti.csv", sep=";"
    )
    combined = pd.concat(
        [energy_exchange_results, load_shifting_trader_results], axis=1
    )
    set_time_index(combined)
    return combined.drop(
        columns=[
            col
            for col in combined.columns
            if col
            not in [
                "ElectricityPriceInEURperMWH",
                "NetAwardedPower",
                "BaselineLoadProfile",
                "LoadAfterShifting",
            ]
        ]
    )


def set_time_index(combined: pd.DataFrame):
    """Define and set a time index for DataFrame"""
    years = math.floor(combined.shape[0] / 8760)
    time_index = cut_leap_days(
        pd.Series(
            index=pd.date_range(
                start="2020-01-01 00:00:00",
                end=f"{2020 + years - 1}-12-31 23:00:00",
                freq="H",
            ),
            data=0,
        )
    )
    combined["new_index"] = time_index.index
    combined.set_index("new_index", inplace=True)


def add_variable_shifting_costs(
    config_dispatch: Dict,
    cluster: str,
    scenario: str,
    combined_results: pd.DataFrame,
) -> pd.DataFrame:
    """Add the variable shifting costs for given cluster and scenario"""
    variable_costs = pd.read_csv(
        f"{config_dispatch['input_folder']}"
        f"{config_dispatch['data_sub_folder']}/"
        f"{cluster}/{scenario}/{cluster}_variable_costs.csv",
        sep=";",
        index_col=0,
        header=None,
    )
    variable_costs.index = pd.to_datetime(
        variable_costs.index.str.replace("_", " ")
    )
    combined_results["VariableShiftingCosts"] = variable_costs[1]
    years = math.floor(combined_results.shape[0] / 8760)
    combined_results.loc[f"{2020 + years}-01-01 00:00:00"] = np.nan
    combined_results.at[
        f"{2020 + years}-01-01 00:00:00", "VariableShiftingCosts"
    ] = variable_costs.loc[f"{2020 + years}-01-01 00:00:00"]
    combined_results["VariableShiftingCosts"] = combined_results[
        "VariableShiftingCosts"
    ].interpolate()
    return combined_results[:-1]


def add_price_estimate(
    config_dispatch: Dict,
    cluster: str,
    scenario: str,
    tariff: str,
    combined_results: pd.DataFrame,
) -> pd.DataFrame:
    """Add the price estimate used for scheduling for cluster and scenario"""
    price_sensitivity = pd.read_csv(
        f"{config_dispatch['input_folder']}"
        f"{config_dispatch['data_sub_folder']}/"
        f"{cluster}/{scenario}/price_sensitivity_estimate_"
        f"{scenario}_{tariff.split('_', 4)[-1]}.csv",
        sep=";",
        index_col=0,
        header=None,
    )
    price_sensitivity.index = pd.to_datetime(
        price_sensitivity.index.str.replace("_", " ")
    )
    combined_results["ElectricityPriceEstimateInEURperMWH"] = (
        combined_results["ElectricityPriceInEURperMWH"]
        + combined_results["NetAwardedPower"] * price_sensitivity[1]
    )
    return combined_results


if __name__ == "__main__":
    args = add_args()
    config_file = load_yaml_file(args.file)
    config_dispatch = extract_simple_config(config_file, "config_dispatch")

    # Add combined results for all simulations run so far
    for cluster in next(os.walk(config_dispatch["output_folder"]))[1]:
        if cluster not in config_dispatch["all_clusters"]:
            continue
        else:
            for scenario in next(
                os.walk(f"{config_dispatch['output_folder']}/{cluster}")
            )[1]:
                for tariff in os.listdir(
                    f"{config_dispatch['output_folder']}/{cluster}/"
                    f"{scenario}"
                ):
                    if "wo_dr" not in tariff:
                        try:
                            derive_combined_results(
                                config_dispatch, scenario, cluster, tariff
                            )
                        except FileNotFoundError:
                            print(
                                f"Failed for cluster: {cluster}; "
                                f"scenario: {scenario}; tariff: {tariff}."
                            )
                    else:
                        continue

    # TODO: Add plotting for dedicated cases
