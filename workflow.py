from fameio.source.cli import Config

from dr_analyses.helpers import (
    get_all_yaml_files_in_folder_except,
    trim_file_name
)
from fameio.scripts.convert_results import run as convert_results
from fameio.scripts.make_config import run as make_config

input_folder = "C:/Users/koch_j0/AMIRIS/asgard/input/demand_response"

config_make = {
    Config.LOG_LEVEL: "warn",
    Config.OUTPUT: input_folder + "/configs/",
    Config.LOG_FILE: None,
    # Config.NUM_PROCESSES: 1,
}



if __name__ == "__main__":
    to_ignore = ["schema.yaml"]
    scenario_files = get_all_yaml_files_in_folder_except(
        input_folder, to_ignore
    )
    for scenario in scenario_files:
        config_make[Config.OUTPUT] = (
            config_make[Config.OUTPUT] + trim_file_name(scenario) + ".pb"
        )
        make_config(scenario, config_make)
