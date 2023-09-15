import warnings
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
    derive_lifetime_from_simulation_horizon,
    calculate_annuity_factor,
)
from dr_analyses.time import AMIRIS_TIMESTEPS_PER_YEAR


def calc_load_shifting_results(cont: Container, key: str) -> None:
    """Create shifting results for scenario and add them to Container object

    :param Container cont: container object holding configuration
    :param str key: Identifier for current scenario
    """
    results = pd.read_csv(
        f"{cont.config_convert[Options.OUTPUT]}/LoadShiftingTrader.csv",
        sep=";",
    )

    # Hack: Shift output for variable costs from optimizer
    # to align with other results
    results["VariableShiftingCostsFromOptimiser"] = results[
        "VariableShiftingCostsFromOptimiser"
    ].shift(periods=1)
    results.set_index(["AgentId", "TimeStep"], inplace=True)
    results = (
        results[[col for col in results.columns if "Offered" not in col]]
        .dropna(how="all")
        .reset_index(drop=False)
    )
    check_for_rescheduling(results)
    add_abs_values(results, ["NetAwardedPower", "StoredMWh"])
    results["ShiftCycleEnd"] = np.where(
        results["CurrentShiftTime"].diff() < 0, 1, 0
    )
    add_baseline_load_profile(results, cont, key)
    results["LoadAfterShifting"] = (
        results["BaselineLoadProfile"] + results["NetAwardedPower"]
    )

    cont.set_results(results)


def check_for_rescheduling(results: pd.DataFrame):
    """Raise a warning in case rescheduling occured"""
    n_years = derive_lifetime_from_simulation_horizon(results)
    scheduling_events = results["VariableShiftingCostsFromOptimiser"].count()
    if scheduling_events != n_years:
        warnings.warn(
            "WARNING: RESCHEDULING OCCURRED!"
            f"Simulated years: {n_years}; "
            f"Scheduling events: {scheduling_events}"
        )


def calculate_net_present_value(
    cont: Container,
    dr_scen: str,
    investment_expenses: Dict,
    fixed_costs: Dict,
) -> float:
    """Calculate and return net present value for demand response investment made
    :return float: net present value for the respective case
    """
    investment_expenses = investment_expenses[dr_scen.split("_", 1)[0]]
    installed_power = cont.load_shifting_data["Attributes"][
        "LoadShiftingPortfolio"
    ]["PowerInMW"]
    year_index = int(cont.config_workflow["investment_year"]) - 2020
    cont.set_investment_expenses(
        investment_expenses.iloc[year_index, 0] * installed_power
    )
    interest_rate = cont.config_workflow["interest_rate"]
    cash_flows = [-cont.investment_expenses]
    cash_flows.extend(
        extract_load_shifting_cashflows(cont, dr_scen, fixed_costs)
    )
    npv = npf.npv(interest_rate, cash_flows)

    return npv


def extract_load_shifting_cashflows(
    cont: Container, dr_scen: str, fixed_costs: Dict
) -> List:
    """Extract annual cashflows from raw load shifting results

    Opportunity revenues: the reduction in payments compared to the baseline
    Costs: Variable shifting costs and fixed costs
    """
    cashflows = []
    payment_columns = ["TotalPayments", "CapacityPayment"]
    year_index_shift = int(cont.config_workflow["investment_year"]) - 2020

    for i in range(derive_lifetime_from_simulation_horizon(cont.results)):
        if (i + 1) * AMIRIS_TIMESTEPS_PER_YEAR >= len(cont.results):
            stop = len(cont.results) - 1
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
        variable_costs = (
            cont.results["VariableShiftingCostsFromOptimiser"]
            .loc[i * AMIRIS_TIMESTEPS_PER_YEAR : stop]
            .sum()
        )
        annual_fixed_costs = (
            cont.load_shifting_data["Attributes"]["LoadShiftingPortfolio"][
                "PowerInMW"
            ]
        ) * fixed_costs[dr_scen.split("_", 1)[0]][1].iloc[i + year_index_shift]

        cashflows.append(
            opportunity_revenues - variable_costs - annual_fixed_costs
        )

    return cashflows


def calculate_net_present_value_per_capacity(
    cont: Container,
) -> float:
    """Calculate net present value per flexible load shifting capacity"""
    installed_capacity = cont.load_shifting_data["Attributes"][
        "LoadShiftingPortfolio"
    ]["PowerInMW"]
    return cont.npv / installed_capacity


def calculate_load_shifting_annuity(cont: Container) -> float:
    """Calculate load shifting annuity

    There are two modes:
    - "single_year": Use for single year simulation
    and calculate load shifting annuities based on situation
    in that one particular year
    - "multiple_years": Use for multiple years (lifetime) simulation
    and calculate load shifting annuities based on situation
    over the demand response investments lifetime

    :return float: annuity for the respective case
    """
    mode = cont.config_workflow["annuity_mode"]
    n_years = return_number_of_simulated_years(cont, mode)
    annuity_factor = calculate_annuity_factor(
        n_years, cont.config_workflow["interest_rate"]
    )
    if mode == "multiple_years":
        annuity = cont.npv * annuity_factor
    elif mode == "single_year":
        invest_annuity = -cont.investment_expenses * annuity_factor
        simulated_year = cont.get_number_of_simulated_year()
        simulation_year_discounted_cashflow = (
            cont.cashflows[0]
            * (1 + cont.config_workflow["interest_rate"]) ** -simulated_year
        )
        annuity = invest_annuity + simulation_year_discounted_cashflow
    else:
        raise ValueError(
            f"`annuity_mode` must be one of ['multiple_years', 'single_year']"
            f"You passed an invalid value: {mode}."
        )

    return annuity


def return_number_of_simulated_years(cont: Container, mode: str):
    """Return the number of simulated years"""
    if mode == "multiple_years":
        n_years = derive_lifetime_from_simulation_horizon(cont.results)
    elif mode == "single_year":
        n_years = cont.config_workflow["lifetime"]
    else:
        raise ValueError(
            f"`annuity_mode` must be one of ['multiple_years', 'single_year']"
            f"You passed an invalid value: {mode}."
        )

    return n_years


def add_discounted_payments_to_results(
    cols: List[str], cont: Container
) -> None:
    """Add discounted energy payment columns to results

    :param list(str) cols: Columns for which discounted values shall be added
    :param Container cont: object holding results
    """
    cont.results.reset_index(inplace=True, drop=True)
    year_index_shift = int(cont.config_workflow["investment_year"]) - 2020
    for col in cols:
        cont.results[f"Discounted{col}"] = 0
    for i in range(derive_lifetime_from_simulation_horizon(cont.results)):
        if (i + 1) * AMIRIS_TIMESTEPS_PER_YEAR >= len(cont.results):
            stop = i * AMIRIS_TIMESTEPS_PER_YEAR + len(cont.results) - 1
        else:
            stop = (i + 1) * AMIRIS_TIMESTEPS_PER_YEAR

        for col in cols:
            cont.results[f"Discounted{col}"].loc[
                i * AMIRIS_TIMESTEPS_PER_YEAR : stop
            ] = cont.results[f"{col}"].loc[
                i * AMIRIS_TIMESTEPS_PER_YEAR : stop
            ] * (
                1 + cont.config_workflow["interest_rate"]
            ) ** (
                -(i + year_index_shift)
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
    power_prices = cont.power_prices.reset_index(drop=True)
    baseline_power_prices = cont.baseline_power_prices.reset_index(drop=True)

    for col in power_prices.columns:

        if use_baseline_prices_for_comparison:
            price = baseline_power_prices[col]
        else:
            price = power_prices[col]
        cont.results[f"Baseline{col}Payment"] = (
            cont.results["BaselineLoadProfile"] * price
        )

        cont.results["BaselineTotalPayments"] += cont.results[
            f"Baseline{col}Payment"
        ]
        cont.results[f"Shifting{col}Payment"] = (
            cont.results["LoadAfterShifting"] * power_prices[col]
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

    if cont.config_workflow["tariff_config"]["mode"] == "from_file":
        capacity_charge = cont.load_shifting_data["Attributes"]["Policy"][
            "CapacityBasedNetworkChargesInEURPerMW"
        ]
        calculate_capacity_payments_from_file(cont, capacity_charge)
    elif cont.config_workflow["tariff_config"]["mode"] == "from_workflow":
        capacity_charge = pd.read_csv(
            cont.load_shifting_data["Attributes"]["Policy"][
                "CapacityBasedNetworkChargesInEURPerMW"
            ],
            index_col=0,
            sep=";",
            header=None,
        )
        calculate_capacity_payments_from_workflow(cont, capacity_charge)

    else:
        raise ValueError("Invalid tariff configuration mode selected!")


def calculate_capacity_payments_from_file(
    cont: Container, capacity_charge: float
):
    """Calculate capacity payment obligations"""
    for i in range(derive_lifetime_from_simulation_horizon(cont.results)):
        if (i + 1) * AMIRIS_TIMESTEPS_PER_YEAR >= len(cont.results):
            stop = i * AMIRIS_TIMESTEPS_PER_YEAR + len(cont.results) - 1
        else:
            stop = (i + 1) * AMIRIS_TIMESTEPS_PER_YEAR
        cont.results.at[
            i * AMIRIS_TIMESTEPS_PER_YEAR, "BaselineCapacityPayment"
        ] = (
            cont.results["BaselineLoadProfile"]
            .loc[i * AMIRIS_TIMESTEPS_PER_YEAR : stop]
            .max()
            * capacity_charge
        )
        cont.results.at[
            i * AMIRIS_TIMESTEPS_PER_YEAR, "ShiftingCapacityPayment"
        ] = (
            cont.results["LoadAfterShifting"]
            .loc[i * AMIRIS_TIMESTEPS_PER_YEAR : stop]
            .max()
            * capacity_charge
        )


def calculate_capacity_payments_from_workflow(
    cont: Container, capacity_charge: pd.DataFrame
):
    """Calculate capacity payment obligations"""
    results = cont.results.copy()
    results = results.set_index(cont.power_prices.index)
    to_concat = []
    for year, group in results.groupby(results.index.str[:4]):
        group.at[group.iloc[0].name, "BaselineCapacityPayment"] = (
            group["BaselineLoadProfile"].max()
            * capacity_charge.loc[
                capacity_charge.index.str[:4] == year, 1
            ].values[0]
        )
        group.at[group.iloc[0].name, "ShiftingCapacityPayment"] = (
            group["LoadAfterShifting"].max()
            * capacity_charge.loc[
                capacity_charge.index.str[:4] == year, 1
            ].values[0]
        )
        to_concat.append(group)

    cont.results = pd.concat(to_concat)


def write_results(cont: Container) -> None:
    """Write load shifting results and consumer price time series to disk"""
    cont.write_results()
    cont.write_power_prices()
