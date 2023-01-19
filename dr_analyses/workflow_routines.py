import os
from typing import List, Dict

import numpy as np
import pandas as pd
import yaml
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


def prepare_tariff_configs(config: Dict, dr_scen: str):
    """Read, prepare and return load shifting tariff model configs"""
    print(f"Preparing tariff configs for scenario {dr_scen}.")
    tariff_config_template = load_yaml(
        f"{config['template_folder']}tariff_model_config_template.yaml"
    )["Configs"]

    parameterization = obtain_parameterization_from_file(config, dr_scen)

    for el in range(len(parameterization)):
        tariff_config_template.append(tariff_config_template[0].copy())
    tariff_config_template = tariff_config_template[:-1]

    for number, (name, values) in enumerate(parameterization.iterrows()):
        tariff_config_template[number]["Name"] = name
        tariff_config_template[number]["OtherSurchargesInEURPerMWH"] = float(
            values["static_tariff"]
        )
        tariff_config_template[number][
            "CapacityBasedNetworkChargesInEURPerMW"
        ] = float(values["capacity_tariff"])

        if not values["multiplier"] > 0:
            component_name = "DUMMY"
        else:
            component_name = "POWER_PRICE"
        tariff_config_template[number]["DynamicTariffComponents"] = [
            {
                "ComponentName": component_name,
                "Multiplier": float(values["multiplier"]),
                "LowerBound": -500,
                "UpperBound": 3000,
            }
        ]

    tariff_model_configs = {"Configs": tariff_config_template}

    with open(
        f"{config['template_folder']}tariff_model_configs_{dr_scen}.yaml", "w"
    ) as file:
        yaml.dump(
            tariff_model_configs,
            file,
            sort_keys=False,
        )

    print(f"Tariff configs for scenario {dr_scen} compiled.")
    return tariff_config_template


def obtain_parameterization_from_file(
    config: Dict, dr_scen: str
) -> pd.DataFrame:
    """Obtain data to derive parameterization from Excel file"""
    sheet_names = [
        f"Multiplier_{dynamic_share}_dyn_{capacity_share}_LP"
        for dynamic_share in [20, 40, 60, 80, 100]
        for capacity_share in [0, 20, 40, 60, 80]
    ]
    parameterization = pd.DataFrame(
        columns=["multiplier", "static_tariff", "capacity_tariff"]
    )
    overview = pd.read_excel(
        f"{config['input_folder']}{config['tariff_config_file']}_{dr_scen}.xlsx",
        sheet_name="tariff_shares",
        nrows=36,
        index_col=[0, 1],
    )
    overview = overview[["LP (€/kW*a)", "OTHER_COMPONENTS -> STATIC PARTS"]]
    overview["new_index"] = (
        overview.index.get_level_values(0).astype(str)
        + "_dynamic_"
        + overview.index.get_level_values(1).astype(str)
        + "_LP"
    )
    overview.set_index("new_index", inplace=True)
    parameterization["static_tariff"] = overview[
        "OTHER_COMPONENTS -> STATIC PARTS"
    ]
    parameterization["capacity_tariff"] = overview["LP (€/kW*a)"]

    for sheet in sheet_names:
        multiplier = pd.read_excel(
            f"{config['input_folder']}{config['tariff_config_file']}_{dr_scen}.xlsx",
            sheet_name=sheet,
            usecols="H:I",
            nrows=8,
            index_col=0,
            header=None,
        )
        index_name = sheet.split("_", 1)[-1].replace("dyn", "dynamic")
        parameterization.at[index_name, "multiplier"] = multiplier.at[
            "multiplier with bounds", 8
        ]
    parameterization.fillna(0, inplace=True)

    return parameterization


def read_tariff_configs(config: Dict, dr_scen: str):
    """Read and return load shifting tariff model configs"""
    return load_yaml(
        f"{config['template_folder']}tariff_model_configs_{dr_scen}.yaml"
    )["Configs"]


def read_load_shifting_template(config: Dict) -> Dict:
    """Read and return load shifting tariff model configs"""
    return load_yaml(
        f"{config['template_folder']}" f"load_shifting_config_template.yaml"
    )["Agents"][0]


def read_load_shedding_template(config: Dict) -> Dict:
    """Read and return load shifting tariff model configs"""
    return load_yaml(
        f"{config['template_folder']}" f"load_shedding_config_template.yaml"
    )["Attributes"]


def read_investment_expenses(config: Dict, dr_scen: str) -> pd.Series:
    """Read and return investment expenses"""
    path = f"{config['input_folder']}/{config['data_sub_folder']}/{dr_scen.split('_', 1)[0]}/"
    file_name = f"{config['load_shifting_focus_cluster']}_specific_investments.csv"
    return pd.read_csv(path + file_name, sep=";", index_col=0)


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
