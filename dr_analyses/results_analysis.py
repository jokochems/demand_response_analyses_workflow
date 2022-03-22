from typing import Dict

import numpy as np
import pandas as pd
from fameio.source.cli import Config
from fameio.source.loader import load_yaml

from dr_analyses.results_subroutines import (
    add_abs_values,
    add_baseline_load_profile,
    calculate_dynamic_price_time_series,
    add_static_prices,
)
from dr_analyses.workflow_routines import trim_file_name


def calc_basic_load_shifting_results(
    scenario: str, config_convert: Dict, config_workflow: Dict
) -> pd.DataFrame:
    """Create basic results for scenario

    :param str scenario: scenario considered
    :param dict config_convert: config for converting results of AMIRIS run
    :param dict config_workflow: config controlling the workflow
    :return pd.DataFrame results: results including additional columns
    """
    config_convert[Config.OUTPUT] = config_workflow[
        "output_folder"
    ] + trim_file_name(scenario)
    results = pd.read_csv(
        config_convert[Config.OUTPUT] + "/LoadShiftingTrader.csv", sep=";"
    )
    results = results[
        [col for col in results.columns if "Offered" not in col]
    ].dropna()
    add_abs_values(results, ["NetAwardedPower", "StoredMWh"])
    results["ShiftCycleEnd"] = np.where(
        results["CurrentShiftTime"].diff() < 0, 1, 0
    )
    add_baseline_load_profile(results, config_workflow["baseline_load_file"])
    results["LoadAfterShifting"] = (
        results["BaselineLoadProfile"] + results["NetAwardedPower"]
    )
    return results


def obtain_scenario_prices(
    scenario: str, config_convert: Dict, input_folder: str
) -> pd.DataFrame:
    """Obtain price time-series based on results of scenario"""
    yaml_data = load_yaml(scenario)
    load_shifting_data = [
        agent
        for agent in yaml_data["Agents"]
        if agent["Type"] == "LoadShiftingTrader"
    ][0]
    dynamic_components = load_shifting_data["Attributes"]["Policy"][
        "DynamicTariffComponents"
    ]
    power_prices = calculate_dynamic_price_time_series(
        config_convert, dynamic_components
    )
    add_static_prices(load_shifting_data, power_prices)

    return power_prices


def add_price_results():
    pass
