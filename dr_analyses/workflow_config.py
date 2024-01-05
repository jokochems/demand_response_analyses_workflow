import shutil

import yaml
from fameio.source.cli import Options, ResolveOptions
import argparse
from typing import Dict

from fameio.source.loader import load_yaml


def add_args():
    """Add command line argument for config file"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--file",
        required=False,
        default="./config.yml",
        help="Specify input config file",
    )
    return parser.parse_args()


def extract_simple_config(config: Dict, key):
    """Extract config part to control the workflow"""
    return config[key]


def extract_config_plotting(config: Dict):
    """Extract config part to control the plotting"""
    config_plotting = config["config_plotting"]
    if "x_label" in config_plotting:
        if config_plotting["x_label"] == "None":
            config_plotting["x_label"] = None
    config_plotting["figsize"] = {"bar": {}, "heatmap": {}, "line": {}}
    for key in config_plotting["figsize"]:
        try:
            config_plotting["figsize"][key] = (
                config_plotting["width"].pop(key),
                config_plotting["height"].pop(key),
            )
        except KeyError:
            continue
    _ = config_plotting.pop("width")
    _ = config_plotting.pop("height")

    return config_plotting


def extract_fame_config(config: Dict, key: str):
    """Extract config part to control fameio"""
    fame_config_str_keys = config[key]
    fame_config = {}
    for config_option, config_value in fame_config_str_keys.items():
        for option in Options:
            if config_option.split(".")[1] == option.name:
                if config_value == "None":
                    config_value = None
                elif isinstance(config_value, str) and "." in config_value:
                    if config_value.split(".")[0] == "ResolveOptions":
                        config_value = [
                            resolve_option
                            for resolve_option in ResolveOptions
                            if resolve_option.name
                            == config_value.split(".")[1]
                        ][0]
                fame_config[option] = config_value

    return fame_config


def update_run_properties(
    default_run_properties: Dict,
    dr_scen: str,
    config: Dict,
):
    """Create a duplicate of fameSetup.yaml and adjust output file"""
    tariff_string = (
        f"{config['tariff_config']['energy']['min_share']}-"
        f"{config['tariff_config']['energy']['max_share']}_dynamic_"
        f"{config['tariff_config']['capacity']['min_share']}-"
        f"{config['tariff_config']['capacity']['max_share']}_LP"
    )

    new_file_name = (
        f"{default_run_properties['setup'].split('.')[0]}_"
        f"{config['load_shifting_focus_cluster']}_{dr_scen}_{tariff_string}"
    )
    if "optional_file_add_on" in config:
        new_file_name += config["optional_file_add_on"]
    new_setup_file = f"{new_file_name}.yaml"

    shutil.copyfile(
        f"{default_run_properties['setup']}",
        new_setup_file,
    )
    fame_setup = load_yaml(new_setup_file)
    fame_setup["outputFilePrefix"] = (
        f"{fame_setup['outputFilePrefix']}_"
        f"{config['load_shifting_focus_cluster']}_{dr_scen}_{tariff_string}"
    )
    if "optional_file_add_on" in config:
        fame_setup["outputFilePrefix"] += config["optional_file_add_on"]

    with open(new_setup_file, "w") as file:
        yaml.dump(fame_setup, file, sort_keys=False)

    run_properties = default_run_properties.copy()
    run_properties["setup"] = new_setup_file

    return run_properties
