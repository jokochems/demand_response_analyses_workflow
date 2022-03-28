import os
from typing import List, Dict

from fameio.scripts.convert_results import run as convert_results
from fameio.scripts.make_config import run as make_config
from fameio.source.cli import Config

from dr_analyses.container import Container


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


def trim_file_name(file_name: str) -> str:
    """Return the useful part of a scenario name"""
    return file_name.rsplit("/", 1)[1].split(".")[0]


def make_scenario_config(cont: Container) -> None:
    """Make a config for a given scenario with absolute path"""
    trimmed_scenario = trim_file_name(cont.scenario)
    print(f"Compiling scenario {trimmed_scenario}")
    cont.config_make[
        Config.OUTPUT
    ] = f'{cont.config_workflow["input_folder"]}/configs/{trimmed_scenario}.pb'

    make_config(cont.scenario, cont.config_make)
    print(f"Scenario {trimmed_scenario} compiled")


def run_amiris(run_properties: Dict, config_make: Dict) -> None:
    """Run AMIRIS for given run properties and make configuration"""
    call_amiris = "java -ea -Xmx2000M -cp {} {} {} -f {} -s {}".format(
        run_properties["exe"],
        run_properties["logging"],
        run_properties["main"],
        config_make[Config.OUTPUT],
        run_properties["setup"],
    )
    os.system(call_amiris)


def convert_amiris_results(cont: Container) -> None:
    """Convert AMIRIS results from a previous model run"""
    cont.config_convert[Config.OUTPUT] = cont.config_workflow[
        "output_folder"
    ] + trim_file_name(cont.scenario)
    convert_results(
        cont.config_workflow["output_folder"] + "amiris-output.pb",
        cont.config_convert,
    )
