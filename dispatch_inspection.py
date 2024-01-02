from typing import Dict

import pandas as pd

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


if __name__ == "__main__":
    args = add_args()
    config_file = load_yaml_file(args.file)
    config_dispatch = extract_simple_config(config_file, "config_dispatch")

    for cluster, tariffs in config_dispatch["cases"].items():
        for tariff in tariffs:
            combined_results = read_and_combine_results(
                config_dispatch, cluster, tariff
            )
