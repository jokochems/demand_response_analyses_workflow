from typing import Dict

import pandas as pd
from fameio.source.cli import Config

from dr_analyses.workflow_routines import trim_file_name


def calc_load_shifting_results(
    scenario: str, config_convert: Dict, output_folder: str
) -> None:
    """Calculate results for load shifting"""
    config_convert[Config.OUTPUT] = output_folder + trim_file_name(scenario)
    load_shifting_results = pd.read_csv(
        config_convert[Config.OUTPUT] + "/LoadShiftingTrader.csv", sep=";"
    )
    print("Pause")