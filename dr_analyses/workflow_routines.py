import os
from typing import List, Dict

from fameio.scripts.make_config import run as make_config
from fameio.source.cli import Config


def get_all_yaml_files_in_folder_except(
        folder: str, file_list: List[str]
) -> List[str]:
    """Returns all .yaml files in given folder but not given ones"""
    return [
        folder + "/" + file
        for file in os.listdir(folder)
        if file.endswith(".yaml")
        if file not in file_list
    ]


def trim_file_name(
        file_name: str
) -> str:
    """Return the useful part of a scenario name"""
    return file_name.rsplit("/", 1)[1].split(".")[0]


def make_scenario_config(
        scenario: str, config_make: Dict, input_folder: str
) -> None:
    """Make a config for a given scenario with absolute path"""
    trimmed_scenario = trim_file_name(scenario)
    print(f"Compiling scenario {trimmed_scenario}")
    config_make[Config.OUTPUT] = (
            input_folder + "/configs/" + trimmed_scenario + ".pb"
    )
    make_config(scenario, config_make)
    print(f"Scenario {trimmed_scenario} compiled")


def run_amiris(run_properties: Dict[str], config_make: Dict) -> None:
    """Run AMIRIS for given run properties and make configuration"""
    call_amiris = "java -ea -Xmx2000M -cp {} {} {} -f {} -s {}".format(
        run_properties["exe"],
        run_properties["logging"],
        run_properties["main"],
        config_make[Config.OUTPUT],
        run_properties["setup"],
    )
    os.system(call_amiris)


def convert_amiris_results():
    """Convert AMIRIS results from a previous model run"""
    pass
