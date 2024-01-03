import math
from typing import Dict

import pandas as pd

from dr_analyses.time import cut_leap_days


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
        f"{scenario}/{tariff}/combined_results.csv",
        sep=";",
    )


def read_and_combine_results(
    config_dispatch: Dict, scenario: str, cluster: str, tariff: str
):
    """Read and combine energy exchange and load shifting results"""
    file_path = (
        f"{config_dispatch['output_folder']}{cluster}/{scenario}/{tariff}"
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
            if col not in config_dispatch["columns_to_keep"]
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
    combined["TimeIndex"] = time_index.index
    combined.set_index("TimeIndex", inplace=True)


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


def retrieve_combined_result(
    config_dispatch: Dict, cluster: Dict, tariff: Dict
):
    """Retrieve combined result again for given case"""
    tariff_folder_name = (
        f"scenario_w_dr_{tariff['scenario']}_"
        f"{tariff['dynamic_share']}_dynamic_"
        f"{tariff['capacity_share']}_LP"
    )
    return pd.read_csv(
        f"{config_dispatch['output_folder']}/{cluster}/"
        f"{tariff['scenario']}/{tariff_folder_name}/combined_results.csv",
        sep=";",
        index_col=0,
    )


def slice_combined_result(
    combined_result: pd.DataFrame, config_plotting: Dict
):
    """Slice combined result for plotting purposes"""
    start_iloc = combined_result.index.get_loc(
        config_plotting["single_situation"]["start_time"]
    )
    return combined_result.iloc[
        start_iloc : min(
            len(combined_result) - 1,
            start_iloc + config_plotting["single_situation"]["timesteps"],
        )
    ].drop(columns=["VariableShiftingCosts"])
