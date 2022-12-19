from typing import Dict, List

import pandas as pd
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
        iter_dict = agent["Attributes"]
    elif group and not subgroup:
        iter_dict = agent["Attributes"][group]
    else:
        if not group:
            raise ValueError(
                "When replacing values for a sub group, "
                "group must also be given!"
            )
        iter_dict = agent["Attributes"][group][subgroup]

    if isinstance(entries, list):
        replace_path_for_list_entries(iter_dict, entries, key)
    elif isinstance(entries, dict):
        replace_using_dict_values(iter_dict, entries, key)
    else:
        raise ValueError("Entries must be of type list or dict.")


def replace_path_for_list_entries(iter_dict: Dict, entries: List, key: str):
    """Replace the pointer to a dedicated file by using key"""
    for k, v in iter_dict.items():
        for entry in entries:
            if entry == k:
                new_value = (
                    f"{v.rsplit('/', 2)[0]}/{key.split('_', 1)[0]}/"
                    f"{v.rsplit('/', 2)[-1]}"
                )
                # Update with value from respective scenario
                iter_dict[k] = new_value


def replace_using_dict_values(iter_dict: Dict, entries: Dict, key: str):
    """Replace previous entries by the once in given dict entries"""
    for k, v in iter_dict.items():
        for entry, value in entries.items():
            if entry == k:
                new_value = value
                # Update with value from respective scenario
                iter_dict[k] = new_value


def add_load_shifting_tariff(
    tariff_configs: List, load_shifting_agent: Dict, key: str
):
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
    :attr list dynamic_components: dynamic tarrif components
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

    def _define_components_mapping(self):
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

    def set_results(self, results: pd.DataFrame):
        self.results = results

    def set_power_prices(self, power_prices: pd.DataFrame):
        self.power_prices = power_prices

    def set_baseline_power_prices(self, baseline_power_prices: pd.DataFrame):
        self.baseline_power_prices = baseline_power_prices

    def set_load_shifting_data_and_dynamic_components(self):
        """Retrieve load shifting config including dynamic tarrif components from input yaml"""
        self.load_shifting_data = [
            agent
            for agent in self.scenario_yaml["Agents"]
            if agent["Type"] == "LoadShiftingTrader"
        ][0]
        self.dynamic_components = self.load_shifting_data["Attributes"][
            "Policy"
        ]["DynamicTariffComponents"]

    def write_results(self):
        self.results.to_csv(
            self.config_convert[Options.OUTPUT]
            + "/LoadShiftingTraderExtended.csv",
            sep=";",
        )

    def write_power_prices(self):
        self.power_prices.to_csv(
            self.config_convert[Options.OUTPUT] + "/ConsumerPowerPrices.csv",
            sep=";",
        )

    def initialize_summary(self):
        self.summary = {}

    def set_summary_series(self):
        self.summary_series = pd.Series(self.summary, name="Summary")

    def write_summary(self):
        """Write parameter summary to disk"""
        self.summary_series.to_csv(
            self.config_convert[Options.OUTPUT] + "/parameter_summary.csv",
            sep=";",
        )

    def add_load_shifting_config(self, key: str, tariff_configs: List[Dict]):
        """Add a load shifting agent to scenario and adjust its configuration"""
        load_shifting_agent = load_yaml(
            f"{self.config_workflow['template_folder']}"
            f"demand_response_config_template.yaml"
        )["Agents"][0]

        replace_yaml_entries(
            load_shifting_agent,
            key,
            entries=[
                "PowerInMW",
                "PowerUpAvailability",
                "PowerDownAvailability",
                "MaximumShiftTimeInHours",
                "BaselineLoadTimeSeries",
                "BaselinePeakLoadInMW",
                "InterferenceTimeInHours",
            ],
            group="LoadShiftingPortfolio",
        )
        add_load_shifting_tariff(tariff_configs, load_shifting_agent, key)
        self.scenario_yaml["Agents"].append(load_shifting_agent)

    def update_config_for_scenario(self):
        """Update time series values for a given scenario"""
        demand_traders = self.get_agents_by_type("DemandTrader")
        predefined_builder = self.get_agents_by_type("PredefinedPlantBuilder")

    def get_agents_by_type(self, agent_type: str) -> List[Dict]:
        """Returns list of agents of given type"""
        return [
            agent
            for agent in self.scenario_yaml["Agents"]
            if agent["Type"] == agent_type
        ]
