import os
from typing import List, Dict

from fameio.scripts.convert_results import run as convert_results
from fameio.scripts.make_config import run as make_config
from fameio.source.cli import Options
from fameio.source.loader import load_yaml

from dr_analyses.container import Container


def make_directory_if_missing(folder: str) -> None:
    """Add directories if missing; works with at maximum 2 sub-levels"""
    if os.path.exists(folder):
        pass
    else:
        if os.path.exists(folder.rsplit("/", 2)[0]):
            path = "./" + folder
            os.mkdir(path)
        else:
            path = "./" + folder.rsplit("/", 2)[0]
            os.mkdir(path)
            subpath = folder
            os.mkdir(subpath)


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


def obtain_load_shifting_tariff_configs(config: Dict):
    """Read and return load shifting tariff model configs"""
    return load_yaml(f"{config['template_folder']}tariff_model_configs.yaml")[
        "Configs"
    ]


def make_scenario_config(cont: Container) -> None:
    """Make a config for a given scenario with absolute path"""
    print(f"Compiling scenario {cont.trimmed_scenario}")
    set_config_make_output(cont)
    make_config(cont.scenario, cont.config_make)
    print(f"Scenario {cont.trimmed_scenario} compiled")


def set_config_make_output(cont: Container) -> None:
    """Define output for compiling AMIRIS protobuffer input"""
    make_directory_if_missing(
        f"{cont.config_workflow['input_folder']}/configs/"
    )
    cont.config_make[
        Options.OUTPUT
    ] = f'{cont.config_workflow["input_folder"]}/configs/{cont.trimmed_scenario}.pb'


def run_amiris(run_properties: Dict, cont: Container) -> None:
    """Run AMIRIS for given run properties and make configuration"""
    if Options.OUTPUT not in cont.config_make.keys():
        set_config_make_output(cont)

    call_amiris = "java -ea -Xmx2000M -cp {} {} {} -f {} -s {}".format(
        run_properties["exe"],
        run_properties["logging"],
        run_properties["main"],
        cont.config_make[Options.OUTPUT],
        run_properties["setup"],
    )
    os.system(call_amiris)


def convert_amiris_results(cont: Container) -> None:
    """Convert AMIRIS results from a previous model run"""
    cont.config_convert[Options.OUTPUT] = (
        cont.config_workflow["output_folder"] + cont.trimmed_scenario
    )
    convert_results(
        cont.config_workflow["output_folder"] + "amiris-output.pb",
        cont.config_convert,
    )
