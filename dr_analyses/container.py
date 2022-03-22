from fameio.source.loader import load_yaml


class Container:
    """Class holding Container objects with config and results information

    :param str scenario: scenario to be analyzed
    :param dict config_workflow: the workflow configuration
    :param dict config_convert: the configuration for converting AMIRIS results
    :param pd.DataFrame or NoneType results: load shifting results from the
    simulation
    :param pd.DataFrame or NoneType power_prices: end consumer power price
    time series
    :param dict or NoneType load_shifting_data: load shifting config from yaml
    """

    def __init__(self, scenario, config_workflow, config_convert):
        self.scenario = scenario
        self.config_workflow = config_workflow
        self.config_convert = config_convert
        self.results = None
        self.power_prices = None
        self.load_shifting_data = None
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

    def set_results(self, results):
        self.results = results

    def set_power_prices(self, power_prices):
        self.power_prices = power_prices

    def set_load_shifting_data(self):
        """Retrieve load shifting config from input yaml"""
        yaml_data = load_yaml(self.scenario)
        self.load_shifting_data = [
            agent
            for agent in yaml_data["Agents"]
            if agent["Type"] == "LoadShiftingTrader"
        ][0]
