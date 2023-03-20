import os
import shutil
from typing import List, Dict

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


def prepare_tariff_configs(config: Dict, dr_scen: str) -> None:
    """Read, prepare and return load shifting tariff model configs"""
    print(f"Preparing tariff configs for scenario {dr_scen}.")
    tariff_config_template = load_yaml(
        f"{config['template_folder']}tariff_model_config_template.yaml"
    )["Configs"]

    if config["tariff_config"]["mode"] == "from_file":
        prepare_tariffs_from_file(config, dr_scen, tariff_config_template)

    elif config["tariff_config"]["mode"] == "from_workflow":
        prepare_tariffs_skeleton_from_workflow(
            config, dr_scen, tariff_config_template
        )
        print(
            "Creating skeleton only. "
            "Postponing actual tariff configuration to later processing."
        )
        return

    else:
        raise NotImplementedError(
            f"tariff_config mode {config['tariff_config']['mode']} "
            f"not implemented."
        )

    print(f"Tariff configs for scenario {dr_scen} compiled.")


def prepare_tariffs_from_file(
    config: Dict, dr_scen: str, tariff_config_template: Dict
):
    """Prepare tariffs using excel file with tariff models
    and multipliers precalculated"""
    parameterization = obtain_parameterization_from_file(config, dr_scen)

    for el in range(len(parameterization) - 1):
        tariff_config_template.append(tariff_config_template[0].copy())

    for number, (name, values) in enumerate(parameterization.iterrows()):
        tariff_config_template[number]["Name"] = name
        tariff_config_template[number][
            "AverageMarketPriceInEURPerMWH"
        ] = float(values["weighted_average"])
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
        f"{config['template_folder']}tariff_model_configs_{dr_scen}.yaml",
        "w",
    ) as file:
        yaml.dump(
            tariff_model_configs,
            file,
            sort_keys=False,
        )


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
        columns=[
            "multiplier",
            "static_tariff",
            "capacity_tariff",
            "weighted_average",
        ]
    )
    overview = pd.read_excel(
        f"{config['input_folder']}{config['tariff_config']['config_file']}_{dr_scen}.xlsx",
        sheet_name="tariff_shares",
        nrows=36,
        index_col=[0, 1],
    )
    overview = overview[["LP (€/MW*a)", "OTHER_COMPONENTS -> STATIC PARTS"]]
    overview = drop_duplicate_scenarios(overview)
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
    parameterization["capacity_tariff"] = overview["LP (€/MW*a)"]

    for sheet in sheet_names:
        multiplier = pd.read_excel(
            f"{config['input_folder']}{config['tariff_config']['config_file']}_{dr_scen}.xlsx",
            sheet_name=sheet,
            usecols="H:I",
            nrows=13,
            index_col=0,
            header=None,
        )
        index_name = sheet.split("_", 1)[-1].replace("dyn", "dynamic")
        parameterization.at[index_name, "multiplier"] = multiplier.at[
            "multiplier with bounds", 8
        ]
        parameterization.at[index_name, "weighted_average"] = multiplier.at[
            "Weigthed average for consumer", 8
        ]
        parameterization["weighted_average"].fillna(
            method="bfill", inplace=True
        )
        parameterization["weighted_average"].fillna(
            method="ffill", inplace=True
        )
    parameterization.fillna(0, inplace=True)

    return parameterization


def prepare_tariffs_skeleton_from_workflow(
    config: Dict, dr_scen: str, tariff_config_template: Dict
):
    """Prepare tariffs skeleton"""
    step_size = config["tariff_config"]["step_size"]
    shares = list(range(0, 101, step_size))

    parameterization = pd.DataFrame(
        index=pd.MultiIndex.from_product([shares, shares]), columns=["names"]
    )
    parameterization["names"] = (
        parameterization.index.get_level_values(0).astype(str)
        + "_dynamic_"
        + parameterization.index.get_level_values(1).astype(str)
        + "_LP"
    )
    parameterization = drop_duplicate_scenarios(parameterization)

    for el in range(len(parameterization) - 1):
        tariff_config_template.append(tariff_config_template[0].copy())

    for number, (name, values) in enumerate(parameterization.iterrows()):
        tariff_config_template[number]["Name"] = values["names"]

    tariff_model_configs = {"Configs": tariff_config_template}

    with open(
        f"{config['template_folder']}tariff_model_configs_{dr_scen}.yaml",
        "w",
    ) as file:
        yaml.dump(
            tariff_model_configs,
            file,
            sort_keys=False,
        )


def drop_duplicate_scenarios(overview: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicate tariff scenarios

    Scenarios with 100% capacity payment are duplicates;
    keep only the first one, i.e. the one with no dynamic payments
    """
    overview.drop(
        index=overview.loc[
            (overview.index.get_level_values(1) == 100)
            & (overview.index.get_level_values(0) != 0)
        ].index,
        inplace=True,
    )

    return overview


def prepare_tariffs_from_workflow(cont: Container, templates: Dict):
    """Prepare actual tariffs while calculating multipliers
    and payments for each year"""
    baseline_power_prices = pd.read_csv(
        f"{cont.config_workflow['input_folder']}"
        f"{cont.config_workflow['data_sub_folder']}/"
        f"{cont.trimmed_scenario.split('_')[3]}/price_forecast.csv",
        sep=";",
        header=None,
        index_col=0,
    )
    years = list(
        baseline_power_prices.index.str.slice(start=0, stop=4)
        .astype(int)
        .unique()
    )
    baseline_load_profile = pd.read_csv(
        f"{cont.config_workflow['input_folder']}"
        f"{cont.config_workflow['data_sub_folder']}/"
        f"{cont.trimmed_scenario.split('_')[3]}/"
        f"baseline_load_profile_"
        f"{cont.config_workflow['load_shifting_focus_cluster']}.csv",
        sep=";",
        header=None,
        index_col=0,
    )
    peak_load = templates["load_shifting"]["Attributes"][
        "LoadShiftingPortfolio"
    ]["BaselinePeakLoadInMW"]
    baseline_load_profile *= peak_load
    tariff_info = pd.read_csv(
        f"{cont.config_workflow['input_folder']}/tariffs.csv",
        index_col=0,
        header=0,
        sep=";",
    )
    calculate_tariffs_for_dr_scen(
        cont, tariff_info, templates, baseline_load_profile, baseline_power_prices
    )


def calculate_tariffs_for_dr_scen(
    cont: Container,
    tariff_info: pd.DataFrame,
    templates: Dict,
    baseline_load_profile: pd.DataFrame,
    baseline_power_prices: pd.DataFrame,
):
    """Calculate and return different tariff components resp. multipliers"""
    overall_tariff = tariff_info.loc[
        tariff_info["dr_scen"] == int(cont.trimmed_scenario.split("_")[3]),
        "value",
    ].values[0]
    tariff_configs = templates["tariffs"][cont.trimmed_scenario.split("_")[3]]
    for no in range(len(tariff_configs)):
        capacity_tariff = (
            overall_tariff
            * int(tariff_configs[no]["Name"].split("_")[2])
            / 100
        )
        overall_energy_tariff = overall_tariff - capacity_tariff
        dynamic_energy_tariff = (
            overall_energy_tariff
            * int(tariff_configs[no]["Name"].split("_")[0])
            / 100
        )
        multiplier = calculate_multiplier(dynamic_energy_tariff, baseline_load_profile, baseline_power_prices)
        static_energy_tariff = overall_energy_tariff - dynamic_energy_tariff


def calculate_multiplier(
    dynamic_energy_tariff: float,
    baseline_load_profile: pd.DataFrame,
    baseline_power_prices: pd.DataFrame,
) -> float:
    """Calculate and return multiplier for given dynamic tariff"""
    combined_data_set = pd.DataFrame(index=baseline_load_profile.index)
    combined_data_set["load"] = baseline_load_profile
    combined_data_set["price"] = baseline_power_prices
    # TODO: Iterate over years contained in data set ...
    weighted_average_price = (combined_data_set["load"] * combined_data_set["price"]).sum() / combined_data_set["load"].sum()


def read_tariff_configs(config: Dict, dr_scen: str):
    """Read and return load shifting tariff model configs"""
    return load_yaml(
        f"{config['template_folder']}tariff_model_configs_{dr_scen}.yaml"
    )["Configs"]


def read_load_shifting_template(config: Dict) -> Dict:
    """Read and return load shifting tariff model configs"""
    return load_yaml(
        f"{config['template_folder']}load_shifting_config_template.yaml"
    )["Agents"][0]


def read_load_shedding_template(config: Dict) -> Dict:
    """Read and return load shifting tariff model configs"""
    return load_yaml(
        f"{config['template_folder']}load_shedding_config_template.yaml"
    )["Attributes"]


def read_investment_results_template(config: Dict) -> Dict:
    """Read and return pommesinvest investment results used as input"""
    return load_yaml(
        f"{config['template_folder']}investment_results_template.yaml"
    )["Agents"]


def prepare_scenario_dicts(
    templates: Dict, config: Dict
) -> (Dict, Dict, Dict):
    """Prepare dictionaries and return them

    Prepares the following dicts:
    - scenario_files: mapping string name to respective scenario.yaml file
    - investment_expenses: investment expenses per demand response scenario
    - baseline_scenarios: baseline scenario per demand response scenario
    """
    scenario_files = {}
    investment_expenses = {}
    baseline_scenarios = {}

    for dr_scen, dr_scen_name in config["demand_response_scenarios"].items():
        templates["tariffs"][dr_scen] = read_tariff_configs(config, dr_scen)
        scenario = (
            f"{config['input_folder']}/"
            f"{config['scenario_sub_folder']}/"
            f"scenario_wo_dr_{dr_scen}.yaml"
        )
        shutil.copyfile(
            f"{config['template_folder']}/scenario_template_wo_dr.yaml",
            scenario,
        )
        scenario_files[f"{dr_scen}_wo_dr"] = scenario
        baseline_scenarios[dr_scen] = scenario

        for tariff in templates["tariffs"][dr_scen]:
            tariff_name = tariff["Name"]

            scenario = (
                f"{config['input_folder']}/"
                f"{config['scenario_sub_folder']}/"
                f"{dr_scen_name}_{tariff_name}.yaml"
            )
            shutil.copyfile(
                f"{config['template_folder']}/scenario_template_wo_dr.yaml",
                scenario,
            )
            scenario_files[f"{dr_scen}_{tariff_name}"] = scenario

        investment_expenses[dr_scen] = read_investment_expenses(
            config,
            dr_scen,
        )

    return scenario_files, investment_expenses, baseline_scenarios


def read_investment_expenses(config: Dict, dr_scen: str) -> pd.Series:
    """Read and return investment expenses"""
    path = f"{config['input_folder']}/{config['data_sub_folder']}/{dr_scen}/"
    file_name = (
        f"{config['load_shifting_focus_cluster']}_specific_investments.csv"
    )
    return pd.read_csv(path + file_name, sep=";", index_col=0, header=None)


def initialize_scenario_results_dict(config: Dict) -> Dict:
    """Initialize and return scenario results dict"""
    scenario_results = {}
    for dr_scen in config["demand_response_scenarios"]:
        scenario_results[dr_scen] = {}

    return scenario_results


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
    cont.config_make[Options.OUTPUT] = (
        f"{cont.config_workflow['input_folder']}/configs/"
        f"{cont.trimmed_scenario}.pb"
    )


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
    print(f"Converting scenario {cont.trimmed_scenario} results")
    sub_folder_name = cont.trimmed_scenario.split("_")[3]
    cont.config_convert[Options.OUTPUT] = (
        f"{cont.config_workflow['output_folder']}/"
        f"{sub_folder_name}/"
        f"{cont.trimmed_scenario}"
    )
    make_directory_if_missing(
        f"{cont.config_workflow['output_folder']}/{sub_folder_name}/"
    )
    convert_results(
        f"{cont.config_workflow['output_folder']}/"
        f"amiris-output_{sub_folder_name}.pb",
        cont.config_convert,
    )
    print(f"Scenario {cont.trimmed_scenario} results converted")


def store_price_forecast_from_baseline(cont: Container) -> None:
    """Store price forecast obtained from scenario without demand response"""
    baseline_power_price = pd.read_csv(
        f"{cont.config_workflow['output_folder']}"
        f"{cont.trimmed_scenario.split('_')[3]}/"
        f"{cont.trimmed_baseline_scenario}"
        f"/EnergyExchangeMulti.csv",
        sep=";",
    )["ElectricityPriceInEURperMWH"]
    price_forecast = pd.read_csv(
        f"{cont.config_workflow['input_folder']}"
        f"{cont.config_workflow['data_sub_folder']}/"
        f"{cont.trimmed_scenario.split('_')[3]}/price_forecast.csv",
        sep=";",
        header=None,
        index_col=0,
    )
    price_forecast[1] = baseline_power_price.values
    price_forecast.to_csv(
        f"{cont.config_workflow['input_folder']}"
        f"{cont.config_workflow['data_sub_folder']}/"
        f"{cont.trimmed_scenario.split('_')[3]}/price_forecast.csv",
        sep=";",
        header=False,
    )
