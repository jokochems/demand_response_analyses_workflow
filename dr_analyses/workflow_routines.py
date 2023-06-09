import os
import shutil
from typing import List, Dict

import numpy as np
import pandas as pd
import yaml
from fameio.scripts.convert_results import run as convert_results
from fameio.scripts.make_config import run as make_config
from fameio.source.cli import Options
from fameio.source.loader import load_yaml

from dr_analyses.container import Container, replace_value


FLH_ASSERTIONS = {
    "hoho_cluster_shift_only": "smaller",
    "hoho_cluster_shift_shed": "smaller",
    "ind_cluster_shift_only": "greater",
    "ind_cluster_shift_shed": "greater",
    "tcs+hoho_cluster_shift_only": "smaller",
    "tcs_cluster_shift_only": "smaller",
}
FLH_THRESHOLD = 2500
REDUCED_TARIFFS = {
    "KWKG levy": {"threshold_in_MW": 1000, "reduced_value": "15 percent"},
    "§ 17f EnWG levy": {
        "threshold_in_MW": 1000,
        "reduced_value": "15 percent",
    },
    "§ 19 (2) StromNEV levy": {"threshold_in_MW": 1000, "reduced_value": 0.25},
}


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
    config: Dict, dr_scen: str, tariff_config_template: List
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
        f"{config['input_folder']}{config['tariff_config']['config_file']}"
        f"_{dr_scen}.xlsx",
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
            f"{config['input_folder']}{config['tariff_config']['config_file']}"
            f"_{dr_scen}.xlsx",
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
    config: Dict, dr_scen: str, tariff_config_template: List
):
    """Prepare tariffs skeleton

    Introduce paths to files containing actual parameterization
    """
    shares_energy = list(
        range(
            config["tariff_config"]["energy"]["min_share"],
            config["tariff_config"]["energy"]["max_share"] + 1,
            config["tariff_config"]["energy"]["step_size"],
        )
    )
    shares_capacity = list(
        range(
            config["tariff_config"]["capacity"]["min_share"],
            config["tariff_config"]["capacity"]["max_share"] + 1,
            config["tariff_config"]["capacity"]["step_size"],
        )
    )

    parameterization = pd.DataFrame(
        index=pd.MultiIndex.from_product([shares_energy, shares_capacity]),
        columns=["names"],
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
        path = f"./inputs/data/{dr_scen}/"
        tariff_config_template[number]["Name"] = values["names"]
        tariff_config_template[number][
            "AverageMarketPriceInEURPerMWH"
        ] = f"{path}average_price_annual.csv"
        tariff_config_template[number][
            "OtherSurchargesInEURPerMWH"
        ] = f"{path}static_payments_{values['names']}_annual.csv"
        tariff_config_template[number][
            "CapacityBasedNetworkChargesInEURPerMW"
        ] = f"{path}capacity_payments_{values['names']}_annual.csv"
        tariff_config_template[number]["DynamicTariffComponents"] = [
            {
                "ComponentName": "POWER_PRICE",
                "Multiplier": f"{path}dynamic_multiplier_{values['names']}_annual.csv",
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
    print(f"Preparing tariffs for scenario {cont.trimmed_scenario}.")
    baseline_power_prices = pd.read_csv(
        f"{cont.config_workflow['input_folder']}"
        f"{cont.config_workflow['data_sub_folder']}/"
        f"{cont.config_workflow['load_shifting_focus_cluster']}/"
        f"{cont.trimmed_scenario.split('_')[3]}/price_forecast.csv",
        sep=";",
        header=None,
        index_col=0,
    )
    baseline_load_profile = pd.read_csv(
        f"{cont.config_workflow['input_folder']}"
        f"{cont.config_workflow['data_sub_folder']}/"
        f"{cont.config_workflow['load_shifting_focus_cluster']}/"
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
    baseline_prices_and_load = create_combined_prices_and_load_data(
        baseline_load_profile, baseline_power_prices
    )
    tariff_info = preprocess_tariff_information(cont, baseline_prices_and_load)
    calculate_tariffs_for_dr_scen(
        cont, tariff_info, templates, baseline_prices_and_load
    )
    print(f"Tariffs for scenario {cont.trimmed_scenario} compiled.")


def create_combined_prices_and_load_data(
    baseline_load_profile: pd.DataFrame,
    baseline_power_prices: pd.DataFrame,
) -> pd.DataFrame:
    """Combine baseline power prices and baseline load"""
    combined_df = pd.DataFrame(index=baseline_load_profile.index)
    combined_df["load"] = baseline_load_profile
    combined_df["price"] = baseline_power_prices
    combined_df["year"] = combined_df.index.str[:4]

    return combined_df.loc[combined_df["year"].astype(int) <= 2045]


def preprocess_tariff_information(
    cont: Container,
    baseline_prices_and_load: pd.DataFrame,
):
    """Preprocess original tariffs and provide basis for tariff calculation

    Original tariffs are calculated out of three building blocks
    that are combined here:
    - volume-weighted average wholesale power price
      (derived from model-endogenous result)
    - state-administered taxes and levies incl. energy-related network charges
      (model-exogenous)
    - capacity-related network charges (model-exogenous)

    Also include sanity check for full load hour range.

    Store original tariff information in dedicated folder and return it
    """
    tariff_component_details = pd.read_excel(
        f"{cont.config_workflow['input_folder']}"
        f"{cont.config_workflow['tariff_config']['config_file']}.xlsx",
        sheet_name=cont.config_workflow["load_shifting_focus_cluster"],
        index_col=0,
    )
    original_tariff_excl_wholesale_and_capacity_price = (
        tariff_component_details.at[
            "SUM EXCL WHOLESALE AND CAPACITY PRICE",
            "Applicable Value in EUR/MWh (incl. possible reductions)",
        ]
    )
    peak_load = extract_annual_peak_load(baseline_prices_and_load)
    annual_consumption = extract_annual_consumption(baseline_prices_and_load)
    check_full_load_hours(cont.config_workflow, peak_load, annual_consumption)

    if tariff_component_details["to be calculated?"].sum() >= 1:
        original_tariff_excl_wholesale_and_capacity_price += (
            calc_tariff_exemptions(
                tariff_component_details, annual_consumption
            )
        )

    specific_capacity_payment = calculate_specific_capacity_payment(
        tariff_component_details, peak_load, annual_consumption
    )

    dr_scen_short = cont.trimmed_scenario.split("_")[3]
    tariff_info = pd.DataFrame(
        index=specific_capacity_payment.index,
        columns=["value", "unit"],
    )
    tariff_info["unit"] = "EUR/MWh"

    tariff_info["value"] = original_tariff_excl_wholesale_and_capacity_price
    tariff_info["value"] += specific_capacity_payment
    volume_weighted_average_price = calculate_average_power_price(
        baseline_prices_and_load
    )
    tariff_info["value"] += np.where(
        volume_weighted_average_price.notna(), volume_weighted_average_price, 0
    )
    tariff_info.to_csv(
        f"{cont.config_workflow['input_folder']}/tariff_configuration/tariffs_"
        f"{cont.config_workflow['load_shifting_focus_cluster']}_"
        f"{dr_scen_short}.csv",
        sep=";",
    )

    return tariff_info


def extract_annual_peak_load(
    baseline_prices_and_load: pd.DataFrame,
) -> pd.DataFrame:
    """Extract the peak load values in MW per year"""
    return baseline_prices_and_load.groupby("year").apply(
        lambda x: np.max(x["load"])
    )


def extract_annual_consumption(
    baseline_prices_and_load: pd.DataFrame,
) -> pd.DataFrame:
    """Extract the annual consumption in MWh"""
    return baseline_prices_and_load.groupby("year").apply(
        lambda x: (x["load"]).sum()
    )


def check_full_load_hours(
    config: Dict, peak_load: pd.DataFrame, annual_consumption: pd.DataFrame
):
    """Perform a sanity check for full load hours"""
    full_load_hours = annual_consumption / peak_load
    comparator = FLH_ASSERTIONS[config["load_shifting_focus_cluster"]]
    msg = (
        f"At least one entry of full load hours data set is not {comparator} "
        f"than {FLH_THRESHOLD}.\n"
        f"Given data set:\n{full_load_hours}"
    )
    if comparator == "smaller":
        assert (full_load_hours < FLH_THRESHOLD).all(), msg
    elif comparator == "greater":
        assert (full_load_hours > FLH_THRESHOLD).all(), msg
    else:
        raise ValueError(f"Unsupported comparator value: {comparator}")


def calc_tariff_exemptions(
    tariff_component_details: pd.DataFrame, annual_consumption: pd.DataFrame
) -> float:
    """Calculate overall specific tariff for components with exemptions"""
    components = tariff_component_details.loc[
        tariff_component_details["to be calculated?"] == 1
    ]
    overall_specific_tariff = 0
    for component_name, values in components.iterrows():
        threshold = REDUCED_TARIFFS[component_name]["threshold_in_MW"]
        reduced_value = REDUCED_TARIFFS[component_name]["reduced_value"]
        if (annual_consumption > threshold).all():
            full_tariff = (
                values["Regular Value in EUR/MWh"]
                * threshold
                / annual_consumption
            )
            if isinstance(reduced_value, str):
                percentage_share = float(reduced_value.split()[0]) / 100
                reduced_value = (
                    values["Regular Value in EUR/MWh"] * percentage_share
                )
            reduced_tariff = (
                reduced_value
                * (annual_consumption - threshold)
                / annual_consumption
            )
            overall_specific_tariff += full_tariff + reduced_tariff
        else:
            overall_specific_tariff += values["Regular Value in EUR/MWh"]

    return overall_specific_tariff


def calculate_specific_capacity_payment(
    tariff_component_details: pd.DataFrame,
    peak_load: pd.DataFrame,
    annual_consumption: pd.DataFrame,
) -> pd.Series:
    """Calculate and return specific capacity payment from network charges"""
    original_capacity_charge = (
        tariff_component_details.at[
            "Capacity-related Network Charges", "Regular Value in EUR/MWh"
        ]
        * 1000
    )  # Price is given in €/kW * a
    overall_capacity_payment = original_capacity_charge * peak_load
    return overall_capacity_payment / annual_consumption


def calculate_tariffs_for_dr_scen(
    cont: Container,
    tariff_info: pd.DataFrame,
    templates: Dict,
    baseline_prices_and_load: pd.DataFrame,
):
    """Calculate and store different tariff components resp. multipliers"""
    overall_tariff = tariff_info["value"]

    tariff_configs = templates["tariffs"][cont.trimmed_scenario.split("_")[3]]
    for no in range(len(tariff_configs)):
        if (
            tariff_configs[no]["Name"]
            == cont.trimmed_scenario.split("_", 4)[-1]
        ):
            tariff_config = tariff_configs[no]
            tariff_components = calculate_tariff_components(
                tariff_config, overall_tariff, baseline_prices_and_load
            )
            for key, component in tariff_components.items():
                component.index = (
                    component.index.astype(str) + "-01-01_00:00:00"
                )
                to_be_replaced = "/data/"
                replacement = (
                    f"{to_be_replaced}"
                    f"{cont.config_workflow['load_shifting_focus_cluster']}/"
                )
                if key != "Multiplier":
                    file_name = replace_value(
                        tariff_config[key],
                        to_be_replaced,
                        replacement,
                        exclude=replacement,
                    )
                    component.to_csv(file_name, header=False, sep=";")
                elif key == "Multiplier":
                    file_name = replace_value(
                        tariff_config["DynamicTariffComponents"][0][key],
                        to_be_replaced,
                        replacement,
                        exclude=replacement,
                    )
                    component.to_csv(file_name, header=False, sep=";")
                else:
                    raise ValueError("Invalid key for tariff configurations.")


def calculate_tariff_components(
    tariff_config: Dict,
    overall_tariff: pd.Series,
    baseline_prices_and_load: pd.DataFrame,
) -> Dict:
    """Calculate tariff components for given tariff model"""
    capacity_share = int(tariff_config["Name"].split("_")[2]) / 100
    dynamic_share = int(tariff_config["Name"].split("_")[0]) / 100
    capacity_tariff = overall_tariff * capacity_share
    overall_energy_tariff = overall_tariff - capacity_tariff
    dynamic_energy_tariff = overall_energy_tariff * dynamic_share
    weighted_average_price = calculate_average_power_price(
        baseline_prices_and_load
    )
    multiplier = dynamic_energy_tariff / weighted_average_price
    capacity_tariff_per_mw = calculate_capacity_tariff_per_mw(
        capacity_tariff, baseline_prices_and_load
    )
    static_energy_tariff = overall_energy_tariff - dynamic_energy_tariff

    tariff_components = {
        "AverageMarketPriceInEURPerMWH": weighted_average_price,
        "OtherSurchargesInEURPerMWH": static_energy_tariff,
        "CapacityBasedNetworkChargesInEURPerMW": capacity_tariff_per_mw,
        "Multiplier": multiplier.fillna(0),
    }

    return tariff_components


def calculate_average_power_price(
    baseline_prices_and_load: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate and return volume-weighted average power price"""
    weighted_average_price = baseline_prices_and_load.groupby("year").apply(
        lambda x: np.average(x["price"], weights=x["load"])
    )
    return weighted_average_price


def calculate_capacity_tariff_per_mw(
    capacity_tariff: pd.Series,
    baseline_prices_and_load: pd.DataFrame,
):
    """Calculate the capacity tariff in EUR/MW from given EUR/MWh value"""
    peak_load = extract_annual_peak_load(baseline_prices_and_load)
    annual_consumption = extract_annual_consumption(baseline_prices_and_load)
    overall_annual_capacity_payment = annual_consumption * capacity_tariff
    return overall_annual_capacity_payment / peak_load


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
) -> (Dict, Dict, Dict, Dict):
    """Prepare dictionaries and return them

    Prepares the following dicts:
    - scenario_files: mapping string name to respective scenario.yaml file
    - investment_expenses: investment expenses per demand response scenario
    - fixed_costs: fixed costs per demand response scenario
    - baseline_scenarios: baseline scenario per demand response scenario
    """
    scenario_files = {}
    investment_expenses = {}
    fixed_costs = {}
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

        investment_expenses[dr_scen] = read_capital_expenses(
            config,
            dr_scen,
            piece_of_information="specific_investments",
        )
        fixed_costs[dr_scen] = read_capital_expenses(
            config,
            dr_scen,
            piece_of_information="fixed_costs",
        )

    return scenario_files, investment_expenses, fixed_costs, baseline_scenarios


def read_capital_expenses(
    config: Dict, dr_scen: str, piece_of_information: str
) -> pd.Series:
    """Read and return investment expenses"""
    path = (
        f"{config['input_folder']}/"
        f"{config['data_sub_folder']}/"
        f"{config['load_shifting_focus_cluster']}/"
        f"{dr_scen}/"
    )
    file_name = (
        f"{config['load_shifting_focus_cluster']}_{piece_of_information}.csv"
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
        f"{cont.config_workflow['load_shifting_focus_cluster']}/"
        f"{cont.trimmed_scenario.split('_')[3]}/price_forecast.csv",
        sep=";",
        header=None,
        index_col=0,
    )
    price_forecast[1] = baseline_power_price.values
    price_forecast.to_csv(
        f"{cont.config_workflow['input_folder']}"
        f"{cont.config_workflow['data_sub_folder']}/"
        f"{cont.config_workflow['load_shifting_focus_cluster']}/"
        f"{cont.trimmed_scenario.split('_')[3]}/price_forecast.csv",
        sep=";",
        header=False,
    )
