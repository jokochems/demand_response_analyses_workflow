import pandas as pd
from fameio.source.cli import Config
from fameio.source.loader import load_yaml

from dr_analyses.workflow_routines import trim_file_name


class Container:
    """Class holding Container objects with config and results information

    :attr str scenario: scenario to be analyzed
    :attr dict config_workflow: the workflow configuration
    :attr dict config_convert: the configuration for converting AMIRIS results
    :attr pd.DataFrame or NoneType results: load shifting results from the
    simulation
    :attr pd.DataFrame or NoneType power_prices: end consumer power price
    time series
    :attr dict or NoneType load_shifting_data: load shifting config from yaml
    :attr dict or NoneType summary: parameter summary retrieved from results
    """

    def __init__(self, scenario, config_workflow, config_convert):
        self.scenario = scenario
        self.config_workflow = config_workflow
        self.config_convert = config_convert
        self.results = None
        self.power_prices = None
        self.load_shifting_data = None
        self.summary = None
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

    def set_load_shifting_data(self):
        """Retrieve load shifting config from input yaml"""
        yaml_data = load_yaml(self.scenario)
        self.load_shifting_data = [
            agent
            for agent in yaml_data["Agents"]
            if agent["Type"] == "LoadShiftingTrader"
        ][0]

    def write_results(self):
        self.results.to_csv(
            self.config_convert[Config.OUTPUT]
            + "/LoadShiftingTraderExtended.csv",
            sep=";"
        )

    def write_power_prices(self):
        self.power_prices.to_csv(
            self.config_convert[Config.OUTPUT]
            + "/ConsumerPowerPrices.csv",
            sep=";"
        )

    def initialize_summary(self):
        self.summary = dict()

    def write_summary(self):
        """Write parameter summary to disk"""
        summary_series = pd.Series(self.summary, name="Summary")
        summary_series.to_csv(
            self.config_convert[Config.OUTPUT] + "/parameter_summary.csv",
            sep=";",
        )
