import math
from typing import Dict, List

import numpy as np
import numpy_financial as npf
import pandas as pd
from fameio.source.cli import Options

from dr_analyses.container import Container
from dr_analyses.results_subroutines import (
    add_abs_values,
    add_baseline_load_profile,
    add_static_prices,
    calculate_dynamic_price_time_series,
)

AMIRIS_TIMESTEPS_PER_YEAR = 8760


def calc_load_shifting_results(cont: Container, key: str) -> None:
    """Create shifting results for scenario and add them to Container object

    :param Container cont: container object holding configuration
    :param str key: Identifier for current scenario
    """
    cont.config_convert[Options.OUTPUT] = (
        cont.config_workflow["output_folder"] + cont.trimmed_scenario
    )
    results = pd.read_csv(
        f"{cont.config_convert[Options.OUTPUT]}/LoadShiftingTrader.csv",
        sep=";",
    )

    results = (
        results[[col for col in results.columns if "Offered" not in col]]
        .dropna()
        .reset_index(drop=True)
    )
    add_abs_values(results, ["NetAwardedPower", "StoredMWh"])
    results["ShiftCycleEnd"] = np.where(
        results["CurrentShiftTime"].diff() < 0, 1, 0
    )
    add_baseline_load_profile(results, cont, key)
    results["LoadAfterShifting"] = (
        results["BaselineLoadProfile"] + results["NetAwardedPower"]
    )
    cont.set_results(results)


def calculate_net_present_values(
    cont: Container, dr_scen: str, investment_expenses: Dict
) -> float:
    """Calculate and return net present values for demand response investments made
    :return: DataFrame holding net present values for the respective case
    """
    investment_expenses = investment_expenses[dr_scen.split("_", 1)[0]]
    installed_power = cont.load_shifting_data["Attributes"][
        "LoadShiftingPortfolio"
    ]["PowerInMW"]
    cont.set_investment_expenses(
        investment_expenses.iloc[0, 0] * installed_power
    )
    interest_rate = cont.config_workflow["interest_rate"]
    cash_flows = [-cont.investment_expenses]
    cash_flows.extend(extract_load_shifting_cashflows(cont))
    npv = npf.npv(interest_rate, cash_flows)

    return npv


def extract_load_shifting_cashflows(cont: Container) -> List:
    """Extract annual cashflows from raw load shifting results

    Opportunity revenues: the reduction in payments compared to the baseline
    Costs: Variable shifting costs
    """
    cashflows = []
    payment_columns = ["TotalPayments", "CapacityPayment"]

    for i in range(math.ceil(len(cont.results) / AMIRIS_TIMESTEPS_PER_YEAR)):
        if (i + 1) * AMIRIS_TIMESTEPS_PER_YEAR > len(cont.results) + 1:
            stop = len(cont.results) + 1
        else:
            stop = (i + 1) * AMIRIS_TIMESTEPS_PER_YEAR

        baseline_annual_payments = (
            cont.results[[f"Baseline{col}" for col in payment_columns]]
            .loc[i * AMIRIS_TIMESTEPS_PER_YEAR : stop]
            .sum(axis=1)
            .sum()
        )
        shifting_annual_payments = (
            cont.results[[f"Shifting{col}" for col in payment_columns]]
            .loc[i * AMIRIS_TIMESTEPS_PER_YEAR : stop]
            .sum(axis=1)
            .sum()
        )

        # Baseline payments are assumed higher
        # cost savings are opportunity revenues
        opportunity_revenues = (
            baseline_annual_payments - shifting_annual_payments
        )
        costs = (
            cont.results["VariableShiftingCosts"]
            .loc[i * AMIRIS_TIMESTEPS_PER_YEAR : stop]
            .sum()
        )

        cashflows.append(opportunity_revenues - costs)

    return cashflows


def add_discounted_payments_to_results(
    cols: List[str], cont: Container
) -> None:
    """Add discounted energy payment columns to results

    :param list(str) cols: Columns for which discounted values shall be added
    :param Container cont: object holding results
    """
    for i in range(math.ceil(len(cont.results) / AMIRIS_TIMESTEPS_PER_YEAR)):
        if (i + 1) * AMIRIS_TIMESTEPS_PER_YEAR > len(cont.results) + 1:
            stop = len(cont.results) + 1
        else:
            stop = (i + 1) * AMIRIS_TIMESTEPS_PER_YEAR

        for col in cols:
            cont.results[f"Discounted{col}"] = 0
            cont.results[f"Discounted{col}"].loc[
                i * AMIRIS_TIMESTEPS_PER_YEAR : stop
            ] = cont.results[f"{col}"].loc[
                i * AMIRIS_TIMESTEPS_PER_YEAR : stop
            ] * (
                1 + cont.config_workflow["interest_rate"]
            ) ** (
                -i
            )


def obtain_scenario_and_baseline_prices(cont: Container) -> None:
    """Obtain price time-series based on results of scenario and for baseline

    The baseline prices (baseline = no demand response, i.e. the situation
    before load shifting) differ in so far, as they do not include
    any price repercussion.

    :param Container cont: container object holding configuration
    """
    cont.set_load_shifting_data_and_dynamic_components()
    calculate_dynamic_price_time_series(cont)
    calculate_dynamic_price_time_series(cont, use_baseline_prices=True)
    add_static_prices(cont)


def add_power_payments(
    cont: Container, use_baseline_prices_for_comparison: bool = True
) -> None:
    """Add power payments to results DataFrame

    :param Container cont: container object holding configuration and results
    :param bool use_baseline_prices_for_comparison: indicating
    whether to use baseline power prices for comparison
    """
    cont.results["BaselineTotalPayments"] = 0
    cont.results["ShiftingTotalPayments"] = 0
    for col in cont.power_prices.columns:

        if use_baseline_prices_for_comparison:
            price = cont.baseline_power_prices[col]
        else:
            price = cont.power_prices[col]
        cont.results[f"Baseline{col}Payment"] = (
            cont.results["BaselineLoadProfile"] * price
        )

        cont.results["BaselineTotalPayments"] += cont.results[
            f"Baseline{col}Payment"
        ]
        cont.results[f"Shifting{col}Payment"] = (
            cont.results["LoadAfterShifting"] * cont.power_prices[col]
        )

        cont.results["ShiftingTotalPayments"] += cont.results[
            f"Shifting{col}Payment"
        ]


def add_capacity_payments(cont: Container) -> None:
    """Calculate annual capacity payments and include these
    as one single payment happening every 8760 hours (= rows)

    :param Container cont: container object holding configuration and results
    """
    cont.results["BaselineCapacityPayment"] = 0
    cont.results["ShiftingCapacityPayment"] = 0
    capacity_charge = cont.load_shifting_data["Attributes"]["Policy"][
        "CapacityBasedNetworkChargesInEURPerMW"
    ]
    for i in range(math.ceil(len(cont.results) / AMIRIS_TIMESTEPS_PER_YEAR)):
        if (i + 1) * 8760 > len(cont.results) + 1:
            stop = len(cont.results) + 1
        else:
            stop = (i + 1) * 8760
        cont.results.at[i * 8760, "BaselineCapacityPayment"] = (
            cont.results["BaselineLoadProfile"].loc[i * 8760 : stop].max()
            * capacity_charge
        )
        cont.results.at[i * 8760, "ShiftingCapacityPayment"] = (
            cont.results["LoadAfterShifting"].loc[i * 8760 : stop].max()
            * capacity_charge
        )


def write_results(cont: Container) -> None:
    """Write load shifting results and consumer price time series to disk"""
    cont.write_results()
    cont.write_power_prices()
