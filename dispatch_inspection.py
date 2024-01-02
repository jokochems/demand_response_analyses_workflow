import math
from typing import Dict

import pandas as pd

from dr_analyses.time import cut_leap_days
from dr_analyses.workflow_config import (
    add_args,
    extract_simple_config,
)
from dr_analyses.workflow_routines import load_yaml_file


def read_and_combine_results(
    config_dispatch: Dict, cluster: str, tariff: Dict
):
    """Read and combine energy exchange and load shifting results"""
    file_path = (
        f"{config_dispatch['output_folder']}{cluster}/"
        f"{tariff['scenario']}/"
        f"{config_dispatch['demand_response_scenarios'][tariff['scenario']]}_"
        f"{tariff['dynamic_share']}_dynamic_{tariff['capacity_share']}_LP"
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


if __name__ == "__main__":
    args = add_args()
    config_file = load_yaml_file(args.file)
    config_dispatch = extract_simple_config(config_file, "config_dispatch")

    for cluster, tariffs in config_dispatch["cases"].items():
        for tariff in tariffs:
            combined_results = read_and_combine_results(
                config_dispatch, cluster, tariff
            )
