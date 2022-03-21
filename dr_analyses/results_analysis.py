from typing import Dict, List

import numpy as np
import pandas as pd
from fameio.source.cli import Config

from dr_analyses.workflow_routines import trim_file_name


def calc_load_shifting_results(
    scenario: str, config_convert: Dict, config_workflow: Dict
) -> None:
    """Calculate results for load shifting"""
    config_convert[Config.OUTPUT] = config_workflow[
        "output_folder"
    ] + trim_file_name(scenario)
    load_shifting_results = pd.read_csv(
        config_convert[Config.OUTPUT] + "/LoadShiftingTrader.csv", sep=";"
    )
    load_shifting_results = load_shifting_results[
        [col for col in load_shifting_results.columns if "Offered" not in col]
    ].dropna()
    add_abs_values(load_shifting_results, ["NetAwardedPower", "StoredMWh"])
    load_shifting_results["ShiftCycleEnd"] = np.where(
        load_shifting_results["CurrentShiftTime"].diff() < 0, 1, 0
    )
    add_baseline_load_profile(load_shifting_results, config_workflow["baseline_load_file"])
    print("Salue")


def add_abs_values(
    load_shifting_results: pd.DataFrame, columns: List[str]
) -> None:
    """Calculate absolute values for given columns and append them"""
    for col in columns:
        load_shifting_results["Absolute" + col] = load_shifting_results[
            col
        ].abs()


def add_baseline_load_profile(load_shifting_results: pd.DataFrame, file_name: str) -> None:
    """Add baseline load profile to results data"""
    baseline_load_profile = pd.read_excel(file_name)["absolute"].values
    load_shifting_results["BaselineLoadProfile"] = baseline_load_profile
