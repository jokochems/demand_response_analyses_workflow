import math
import os
from typing import Dict, List, Any

import pandas as pd
import yaml
from fameio.source.cli import Options
from fameio.source.loader import load_yaml

from dr_analyses.time import cut_leap_days, create_time_index


def trim_file_name(file_name: str) -> str:
    """Return the useful part of a scenario name"""
    return file_name.rsplit("/", 1)[1].split(".")[0]


def replace_yaml_entries(
    agent: Dict,
    key: str,
    entries: List or Dict,
    group: str = None,
    subgroup: str = None,
) -> None:
    """Replace entries for values in particular aggregation level

    If group is not given, replace top level Attributes.
    Else, replace values in a given group or subgroup.

    Wraps the following functionalities:
    * If entries is of instance list,
      replace by changing the string pointing to file location.
    * If entries is of instance dict,
      replace entries for keys by the given values.
    """
    if not group:
        to_iterate = agent["Attributes"]
    elif group and not subgroup:
        to_iterate = agent["Attributes"][group]
    else:
        if not group:
            raise ValueError(
                "When replacing values for a sub group, "
                "group must also be given!"
            )
        to_iterate = agent["Attributes"][group][subgroup]

    if isinstance(to_iterate, dict):
        if isinstance(entries, list):
            replace_path_for_list_entries(to_iterate, entries, key)
        elif isinstance(entries, dict):
            replace_using_dict_values(to_iterate, entries)
        else:
            raise ValueError(
                "Parameter 'entries' must be of type list or dict."
            )
    elif isinstance(to_iterate, list):
        if isinstance(entries, list):
            replace_path_within_list(to_iterate, entries, key)
        elif isinstance(entries, dict):
            replace_values_within_list(to_iterate, entries)
        else:
            raise ValueError(
                "Parameter 'entries' must be of type list or dict."
            )
    else:
        raise ValueError(
            "Extraction lead to invalid type. Cannot replace yaml entries."
        )


def replace_path_for_list_entries(
    to_iterate: Dict, entries: List, key: str
) -> None:
    """Replace the pointer to a dedicated file by using key"""
    for k, v in to_iterate.items():
        for entry in entries:
            if entry == k:
                new_value = (
                    f"{v.rsplit('/', 2)[0]}/{key.split('_', 1)[0]}/"
                    f"{v.rsplit('/', 2)[-1]}"
                )
                # Update with value from respective scenario
                to_iterate[k] = new_value


def replace_using_dict_values(to_iterate: Dict, entries: Dict) -> None:
    """Replace previous entries by the once in given dict entries"""
    for k, v in to_iterate.items():
        for entry, value in entries.items():
            if entry == k:
                new_value = value
                # Update with value from respective scenario
                to_iterate[k] = new_value


def replace_path_within_list(
    to_iterate: List[Dict], entries: List, key: str
) -> None:
    """Replace values of list-structured attribute by replacing path"""
    for el in to_iterate:
        for k, v in el.items():
            for entry in entries:
                if entry == k:
                    try:
                        new_value = (
                            f"{v.rsplit('/', 2)[0]}/{key.split('_', 1)[0]}/"
                            f"{v.rsplit('/', 2)[-1]}"
                        )
                        # Update with value from respective scenario
                        el[k] = new_value
                    except AttributeError:
                        continue


def replace_values_within_list(to_iterate: List[Dict], entries: Dict) -> None:
    """Replace values of list-structured attribute by replacing based on dict entries"""
    for el in to_iterate:
        for k, v in el.items():
            for entry, entry_val in entries.items():
                if not isinstance(v, float):
                    if entry in v and k in entry_val:
                        new_value = entry_val[k]
                        # Update with value from respective scenario
                        el[k] = new_value
                else:
                    continue


def add_load_shifting_tariff(
    tariff_configs: List, load_shifting_agent: Dict, key: str
) -> None:
    """Add load shifting tariff for the respective scenario"""
    for tariff in tariff_configs:
        if key.split("_", 1)[-1] == tariff["Name"]:
            replace_yaml_entries(
                load_shifting_agent,
                key,
                entries={
                    param: tariff[param]
                    for param in [
                        "OtherSurchargesInEURPerMWH",
                        "CapacityBasedNetworkChargesInEURPerMW",
                        "DynamicTariffComponents",
                    ]
                },
                group="Policy",
            )
            replace_yaml_entries(
                load_shifting_agent,
                key,
                entries={
                    "AverageMarketPriceInEURPerMWH": tariff[
                        "AverageMarketPriceInEURPerMWH"
                    ]
                },
                group="BusinessModel",
            )


def save_to_fame_time_series(ts: pd.DataFrame, config: Dict, key: str):
    """Save given time series to FAME format for given scenario (key)"""
    ts.index = ts.index.astype(str).str.replace(" ", "_")
    ts.to_csv(
        f"{config['input_folder']}"
        f"{config['data_sub_folder']}/"
        f"{config['load_shifting_focus_cluster']}/"
        f"{key.split('_')[0]}/price_forecast.csv",
        header=False,
        sep=";",
    )


def replace_value(
    value: str, to_be_replaced: str, replacement: str, exclude: str
) -> str:
    """Replace string to_be_replaced with replacement except exclude in value"""
    if exclude not in value:
        substrings = value.split(to_be_replaced)
        new_string = f"{substrings[0]}{replacement}{substrings[-1]}"
        return new_string
    else:
        return value


class Container:
    """Class holding Container objects with config and results information

    :attr str scenario: scenario to be analyzed (full path)
    :attr dict config_workflow: the workflow configuration
    :attr dict config_convert: the configuration for converting AMIRIS results
    :attr str trimmed_scenario: scenario to be analyzed (name only)
    :attr str trimmed_baseline_scenario: baseline scenario (name only)
    :attr pd.DataFrame or NoneType results: load shifting results from the
    simulation
    :attr pd.DataFrame or NoneType power_prices: end consumer power price
    time series
    :attr pd.DataFrame or NoneType baseline_power_prices: end consumer power price
    time series for the baseline load case (no price repercussions due to shifting)
    :attr dict or NoneType load_shifting_data: load shifting config from yaml
    :attr list dynamic_components: dynamic tariff components
    :attr list or NoneType cashflows: annual load shifting cashflows,
    i.e. (opportunity) revenues - expenses
    :attr float or NoneType investment_expenses: load shifting investment
    :attr float or NoneType npv: net present value of load shifting investment
    :attr float or NoneType annuity: annuity of load shifting investment
    :attr dict or NoneType summary: parameter summary retrieved from results
    :attr dict or pd.Series summary_series: parameter summary as Series
    """

    def __init__(
        self,
        scenario,
        config_workflow,
        config_convert,
        config_make,
        baseline_scenario,
    ):
        self.scenario = scenario
        self.config_workflow = config_workflow
        self.config_convert = config_convert
        self.config_make = config_make
        self.trimmed_scenario = trim_file_name(scenario)
        self.trimmed_baseline_scenario = trim_file_name(baseline_scenario)
        self.scenario_yaml = load_yaml(self.scenario)
        self.results = None
        self.power_prices = None
        self.baseline_power_prices = None
        self.load_shifting_data = None
        self.dynamic_components = None
        self.cashflows = None
        self.investment_expenses = None
        self.npv = None
        self.npv_per_capacity = None
        self.annuity = None
        self.summary = None
        self.summary_series = None

    def set_results(self, results: pd.DataFrame) -> None:
        self.results = results

    def set_power_prices(self, power_prices: pd.DataFrame) -> None:
        self.power_prices = power_prices

    def set_baseline_power_prices(
        self, baseline_power_prices: pd.DataFrame
    ) -> None:
        self.baseline_power_prices = baseline_power_prices

    def set_load_shifting_data_and_dynamic_components(self) -> None:
        """Retrieve load shifting config incl. dynamic tariff components from input yaml"""
        self.load_shifting_data = [
            agent
            for agent in self.scenario_yaml["Agents"]
            if agent["Type"] == "LoadShiftingTrader"
        ][0]
        self.dynamic_components = self.load_shifting_data["Attributes"][
            "Policy"
        ]["DynamicTariffComponents"]

    def write_results(self) -> None:
        self.results.to_csv(
            self.config_convert[Options.OUTPUT]
            + "/LoadShiftingTraderExtended.csv",
            sep=";",
        )

    def write_power_prices(self) -> None:
        self.power_prices.to_csv(
            self.config_convert[Options.OUTPUT] + "/ConsumerPowerPrices.csv",
            sep=";",
        )

    def initialize_summary(self) -> None:
        self.summary = {}

    def set_summary_series(self) -> None:
        self.summary_series = pd.Series(self.summary, name="Summary")

    def write_summary(self) -> None:
        """Write parameter summary to disk"""
        self.summary_series.to_csv(
            self.config_convert[Options.OUTPUT] + "/parameter_summary.csv",
            sep=";",
        )

    def adapt_simulation_time_frame(self, simulation_parameters: Dict):
        """Adapt the simulation time frame according to config"""
        simulation = self.scenario_yaml["GeneralProperties"]["Simulation"]
        simulation["StartTime"] = simulation_parameters["StartTime"]
        simulation["StopTime"] = simulation_parameters["StopTime"]

    def adapt_shortage_capacity(self, shortage_capacity: float) -> None:
        """Adapt the capacity of artificial shortage units to given value"""
        shortage_agent = [
            agent
            for agent in self.scenario_yaml["Agents"]
            if agent["Id"] == 2017
        ][0]
        shortage_agent["Attributes"]["InstalledPowerInMW"] = shortage_capacity

    def add_load_shifting_config(self, key: str, templates: Dict) -> None:
        """Add a load shifting agent to scenario
        and adjust its tariff configuration"""
        add_load_shifting_tariff(
            templates["tariffs"][key.split("_", 1)[0]],
            templates["load_shifting"],
            key,
        )
        self.scenario_yaml["Agents"].append(templates["load_shifting"])

    def add_load_shifting_agent(
        self, load_shifting_config: Dict, key: str
    ) -> None:
        """Add load shifting agent sceleton incl. technical parameters"""
        # Update time series information
        replace_yaml_entries(
            load_shifting_config,
            key,
            entries=[
                "PowerUpAvailability",
                "PowerDownAvailability",
                "VariableShiftCostsInEURPerMWH",
                "BaselineLoadTimeSeries",
            ],
            group="LoadShiftingPortfolio",
        )
        # Update scalar information with information from file
        investment_year = int(self.config_workflow["investment_year"])
        if investment_year > 2030 or investment_year < 2020:
            raise ValueError(
                "Investment year must be >= 2020 and <= 2030 in order"
                "to simulate load shifting performance over lifetime."
            )
        potential_parameters = self.read_parameter_info(
            key,
            (
                f"{self.config_workflow['load_shifting_focus_cluster']}"
                f"_potential_parameters_{investment_year}.csv"
            ),
        ).to_dict()[str(investment_year)]
        interference_duration = math.ceil(
            min(
                float(potential_parameters["interference_duration_neg"]),
                float(potential_parameters["interference_duration_pos"]),
            )
        )
        power = float(
            self.read_parameter_info(
                key,
                (
                    f"installed_capacity_ts_"
                    f"{self.config_workflow['load_shifting_focus_cluster']}_"
                    f"{self.config_workflow['load_shifting_focus_cluster']}.csv"
                ),
                sep=";",
                header=None,
            ).at[f"{investment_year}-01-01_00:00:00", 1]
        )
        parameters = {
            "PowerInMW": power,
            "MaximumShiftTimeInHours": math.ceil(
                float(potential_parameters["shifting_duration"])
            ),
            "InterferenceTimeInHours": interference_duration,
            "EnergyLimitUpInMWH": interference_duration * power * 100,
            "EnergyLimitDownInMWH": interference_duration * power * 100,
            "BaselinePeakLoadInMW": float(potential_parameters["max_cap"]),
            "MaximumActivations": int(
                float(potential_parameters["maximum_activations_year"])
            ),
        }
        replace_yaml_entries(
            load_shifting_config,
            key,
            entries=parameters,
            group="LoadShiftingPortfolio",
        )

    def read_parameter_info(
        self, key: str, file_name: str, sep: str = ",", header: int = 0
    ) -> pd.DataFrame:
        """Read and return parameter info"""
        return pd.read_csv(
            f"{self.config_workflow['input_folder']}/"
            f"{self.config_workflow['data_sub_folder']}/"
            f"{self.config_workflow['load_shifting_focus_cluster']}/"
            f"{key.split('_', 1)[0]}/"
            f"{file_name}",
            index_col=0,
            sep=sep,
            header=header,
        )

    def update_opex_for_scenario(self, key: str) -> None:
        """Update OPEX time series values for a given scenario"""
        predefined_builders = self.get_agents_by_type("PredefinedPlantBuilder")
        for builder in predefined_builders:
            replace_yaml_entries(
                builder,
                key,
                entries=["OpexVarInEURperMWH"],
                group="Prototype",
            )

    def update_load_shedding_config(
        self, key: str, load_shedding_template: Dict
    ):
        """Update load shedding config for a given scenario"""
        demand_trader = self.get_agents_by_type("DemandTrader")[0]
        self.update_demand_trader(demand_trader, key, load_shedding_template)

    def get_agents_by_type(self, agent_type: str) -> List[Dict]:
        """Returns list of agents of given type"""
        return [
            agent
            for agent in self.scenario_yaml["Agents"]
            if agent["Type"] == agent_type
        ]

    def update_demand_trader(
        self, demand_trader: Dict, key: str, load_shedding_template
    ) -> None:
        """Update DemandTrader with load shedding information of resp. scenario"""
        # replace config with the one including price-based shedding
        replace_yaml_entries(
            demand_trader,
            key,
            entries=load_shedding_template,
        )
        # adjust values to respective scenario
        replace_yaml_entries(
            demand_trader,
            key,
            entries=["DemandSeries"],
            group="Loads",
        )

    def add_investment_capacities_for_scenario(
        self, key: str, investment_results: Dict
    ):
        """Append investments for dedicated scenario to scenario.yaml"""
        predefined_invest_builders = [
            agent
            for agent in investment_results
            if agent["Type"] == "PredefinedPlantBuilder"
        ]
        for builder in predefined_invest_builders:
            replace_yaml_entries(
                builder,
                key,
                entries=["InstalledPowerInMW"],
            )
        self.scenario_yaml["Agents"].extend(investment_results)

    def create_dummy_price_forecast(self, key: str):
        """Create a dummy price forecast file containing only 0 entries"""
        start_time = self.scenario_yaml["GeneralProperties"]["Simulation"][
            "StartTime"
        ]
        end_time = self.scenario_yaml["GeneralProperties"]["Simulation"][
            "StopTime"
        ]
        time_index = create_time_index(start_time, end_time)
        dummy_forecast = pd.DataFrame(
            index=time_index, columns=["forecast"], data=0
        )
        save_to_fame_time_series(
            cut_leap_days(dummy_forecast), self.config_workflow, key
        )

    def update_price_forecast(self, key: str):
        """Update price forecast in scenario.yaml file"""
        price_forecaster = self.get_agents_by_type("PriceForecasterFile")[0]
        replace_yaml_entries(
            agent=price_forecaster,
            key=key,
            entries=["PriceForecastInEURperMWH"],
        )

    def change_contract_location(self, path_to_new_contracts: str) -> None:
        """Change the contract location to one of the subfolders in order to account for changes"""
        contracts = []
        contract_files = [
            path_to_new_contracts + "/" + file
            for file in os.listdir(path_to_new_contracts)
            if "IGNORE_" not in file and file.endswith(".yaml")
        ]
        for file in contract_files:
            contracts.extend(load_yaml(file)["Contracts"])
        self.scenario_yaml["Contracts"] = contracts

    def save_scenario_yaml(self) -> None:
        """Save 'scenario_yaml' attribute to yaml file"""
        with open(self.scenario, "w") as file:
            yaml.dump(self.scenario_yaml, file, sort_keys=False)

    def add_cashflows(self, cashflows: List):
        """Save cashflow results in container object"""
        self.cashflows = cashflows

    def add_npv(self, npv: float):
        """Save net present value (NPV) results in container object"""
        self.npv = npv
    
    def add_npv_per_capacity(self, npv_per_capacity: float):
        """Save NPV per capacity in container object"""
        self.npv_per_capacity = npv_per_capacity
    
    def add_annuity(self, annuity: float):
        """Save annuity results in container object"""
        self.annuity = annuity

    def set_investment_expenses(self, investment_expenses: float):
        """Set investment expenses for load shifting focus cluster"""
        self.investment_expenses = investment_expenses

    def get_number_of_simulated_year(self) -> int:
        """Return the number of the simulated year

        0 = start year, where investment occur; 1 = first year"""
        return (
            int(
                self.scenario_yaml["GeneralProperties"]["Simulation"][
                    "StartTime"
                ][:4]
            )
            - 2019
            + 1
        )

    def update_all_paths_with_focus_cluster(self):
        """Update all paths in yaml with load shifting focus cluster"""
        data_location_to_be_replaced = "/data/"
        data_location_replacement = (
            f"{data_location_to_be_replaced}"
            f"{self.config_workflow['load_shifting_focus_cluster']}/"
        )
        cluster_string_to_be_replaced = "ind_cluster_shift_only"
        cluster_string_replacement = self.config_workflow[
            "load_shifting_focus_cluster"
        ]
        for agent in self.scenario_yaml["Agents"]:
            if "Attributes" in agent:
                for key, val in agent["Attributes"].items():
                    self.replace_recursively(
                        agent["Attributes"],
                        key,
                        val,
                        cluster_string_to_be_replaced,
                        cluster_string_replacement,
                    )
                    self.replace_recursively(
                        agent["Attributes"],
                        key,
                        val,
                        data_location_to_be_replaced,
                        data_location_replacement,
                    )

    def replace_recursively(
        self,
        agent: Dict,
        key: str,
        value: Any,
        to_be_replaced: str,
        replacement: str,
    ):
        """Recursively replaces value when given string is found in `value`"""
        if isinstance(value, str):
            if to_be_replaced in value:
                agent[key] = replace_value(
                    value, to_be_replaced, replacement, exclude=replacement
                )
        elif isinstance(value, dict):
            for k, v in value.items():
                self.replace_recursively(
                    value, k, v, to_be_replaced, replacement
                )
        elif isinstance(value, list):
            for item in value:
                for k, v in item.items():
                    self.replace_recursively(
                        item, k, v, to_be_replaced, replacement
                    )
        elif isinstance(value, int) or isinstance(value, float):
            pass
        else:
            raise ValueError(
                f"Unexpected type of `{value}`. Should be either str/list/dict."
            )
