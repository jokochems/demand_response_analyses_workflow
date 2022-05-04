import os
from typing import List, Dict

from fameio.scripts.convert_results import run as convert_results
from fameio.scripts.make_config import run as make_config
from fameio.source.cli import Config

from dr_analyses.container import Container


def get_all_yaml_files_in_folder_except(folder: str, file_list: List[str]) -> List[str]:
    """Returns all .yaml files in given folder but not given ones"""
    return [
        folder + "/" + file
        for file in os.listdir(folder)
        if file.endswith(".yaml")
        if file not in file_list
    ]


def make_scenario_config(cont: Container) -> None:
    """Make a config for a given scenario with absolute path"""
    print(f"Compiling scenario {cont.trimmed_scenario}")
    set_config_make_output(cont)
    make_config(cont.scenario, cont.config_make)
    print(f"Scenario {cont.trimmed_scenario} compiled")


def set_config_make_output(cont: Container) -> None:
    """Define output for compiling AMIRIS protobuffer input"""
    cont.config_make[
        Config.OUTPUT
    ] = f'{cont.config_workflow["input_folder"]}/configs/{cont.trimmed_scenario}.pb'


def run_amiris(run_properties: Dict, cont: Container) -> None:
    """Run AMIRIS for given run properties and make configuration"""
    if Config.OUTPUT not in cont.config_make.keys():
        set_config_make_output(cont)

    call_amiris = "java -ea -Xmx2000M -cp {} {} {} -f {} -s {}".format(
        run_properties["exe"],
        run_properties["logging"],
        run_properties["main"],
        cont.config_make[Config.OUTPUT],
        run_properties["setup"],
    )
    os.system(call_amiris)


def convert_amiris_results(cont: Container) -> None:
    """Convert AMIRIS results from a previous model run"""
    cont.config_convert[Config.OUTPUT] = (
        cont.config_workflow["output_folder"] + cont.trimmed_scenario
    )
    convert_results(
        cont.config_workflow["output_folder"] + "amiris-output.pb",
        cont.config_convert,
    )
