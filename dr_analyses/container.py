import math
from typing import Dict, List

import pandas as pd
import yaml
from fameio.source.cli import Options
from fameio.source.loader import load_yaml


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
                        "DynamicTariffComponents",
                        "CapacityBasedNetworkChargesInEURPerMW",
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


def update_plant_builders(builders: List[Dict], key: str) -> None:
    """Update PredefinedPlantBuilders with information of resp. scenario"""
    for builder in builders:
        replace_yaml_entries(
            builder,
            key,
            entries=["OpexVarInEURperMWH"],
            group="Prototype",
        )


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
        self.summary = None
        self.summary_series = None
        self._define_components_mapping()

    def _define_components_mapping(self) -> None:
        """Map dynamic identifier to static component value"""
        self.price_components = {
            "POWER_PRICE": {
                "Group": "BusinessModel",
                "Attribute": "AverageMarketPriceInEURPerMWH",
            },
            "EEG_SURCHARGE": {
                "Group": "Policy",
                "Attribute": "EEGSurchargeInEURPerMWH",
            },
            "VOLUMETRIC_NETWORK_CHARGE": {
                "Group": "Policy",
                "Attribute": "VolumetricNetworkChargeInEURPerMWH",
            },
            "OTHER_COMPONENTS": {
                "Group": "Policy",
                "Attribute": [
                    "ElectricityTaxInEURPerMWH",
                    "OtherSurchargesInEURPerMWH",
                ],
            },
        }

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

    def add_load_shifting_config(self, key: str, templates: Dict) -> None:
        """Add a load shifting agent to scenario and adjust configuration"""
        self.add_load_shifting_agent(templates["load_shifting"], key)
        add_load_shifting_tariff(
            templates["tariffs"], templates["load_shifting"], key
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
                "BaselineLoadTimeSeries",
            ],
            group="LoadShiftingPortfolio",
        )
        # Update scalar information with information from file
        potential_parameters = self.read_parameter_info(
            key,
            (
                f"{self.config_workflow['load_shifting_focus_cluster']}"
                f"_potential_parameters_2020.csv"
            ),
        )
        costs_parameters = self.read_parameter_info(
            key,
            (
                f"{self.config_workflow['load_shifting_focus_cluster']}"
                f"_variable_costs_2020.csv"
            ),
        )
        parameters = {
            "PowerInMW": max(
                float(potential_parameters["potential_neg_overall"]),
                float(potential_parameters["potential_pos_overall"]),
            ),
            "MaximumShiftTimeInHours": math.ceil(
                float(potential_parameters["shifting_duration"])
            ),
            "InterferenceTimeInHours": math.ceil(
                min(
                    float(potential_parameters["interference_duration_neg"]),
                    float(potential_parameters["interference_duration_pos"]),
                )
            ),
            "BaselinePeakLoadInMW": float(potential_parameters["max_cap"]),
            "VariableShiftCostsInEURPerMWH": float(
                costs_parameters["variable_costs"]
            ),
        }
        replace_yaml_entries(
            load_shifting_config,
            key,
            entries=parameters,
            group="LoadShiftingPortfolio",
        )

    def read_parameter_info(self, key: str, file_name: str) -> Dict:
        """Read and return parameter info"""
        return pd.read_csv(
            f"{self.config_workflow['input_folder']}/data/"
            f"{key.split('_', 1)[0]}/"
            f"{file_name}",
            index_col=0,
        ).to_dict()["2020"]

    def update_config_for_scenario(
        self, key: str, load_shedding_template: Dict
    ) -> None:
        """Update time series values for a given scenario"""
        demand_trader = self.get_agents_by_type("DemandTrader")[0]  # only one
        predefined_builders = self.get_agents_by_type("PredefinedPlantBuilder")
        self.update_demand_trader(demand_trader, key, load_shedding_template)
        update_plant_builders(predefined_builders, key)
        self.update_contracts_location()

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
        # Update scalar VOLL information with information from file
        parameters = {}
        for shedding_cluster in self.config_workflow["load_shedding_clusters"]:
            parameters[shedding_cluster] = {}
            costs_parameters = self.read_parameter_info(
                key,
                f"{shedding_cluster}_variable_costs_2020.csv",
            )
            parameters[shedding_cluster]["ValueOfLostLoad"] = float(
                costs_parameters["variable_costs_shed"]
            )

        replace_yaml_entries(
            demand_trader,
            key,
            entries=parameters,
            group="Loads",
        )

    def update_contracts_location(self):
        """Update contract location to include load shedding into the analyses"""
        pass

    def save_scenario_yaml(self) -> None:
        """Save 'scenario_yaml' attribute to yaml file"""
        with open(self.scenario, "w") as file:
            yaml.dump(self.scenario_yaml, file, sort_keys=False)
