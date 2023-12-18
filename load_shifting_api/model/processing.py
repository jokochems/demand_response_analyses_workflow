from typing import List

import pyomo.environ as pyo


def extract_results(lsm, rounding_precision=4, tolerance=1E-4):
    """Extract and add results for a solved load shift optimization model

    Parameters
    ----------
    lsm: LoadShiftOptimizationModel
        The actual model after solving the optimization model part

    rounding_precision: int
        Round float values to given number of digits to avoid numerical
        artifacts

    tolerance : float
        Define value to be interpreted as zero
    """
    demand_after = [
        round(pyo.value(lsm.model.demand_after[t]), rounding_precision)
        for t in lsm.model.T
    ]
    dsm_up = [
        sum(pyo.value(lsm.model.dsm_up[h, t]) for h in lsm.shifting_times)
        for t in lsm.model.T
    ]
    balance_dsm_do = [
        sum(
            pyo.value(lsm.model.balance_dsm_do[h, t])
            for h in lsm.shifting_times
        )
        for t in lsm.model.T
    ]
    upshift = [
        round(sum(i), rounding_precision) for i in zip(dsm_up, balance_dsm_do)
    ]
    dsm_do_shift = [
        sum(
            pyo.value(lsm.model.dsm_do_shift[h, t]) for h in lsm.shifting_times
        )
        for t in lsm.model.T
    ]
    balance_dsm_up = [
        sum(
            pyo.value(lsm.model.balance_dsm_up[h, t])
            for h in lsm.shifting_times
        )
        for t in lsm.model.T
    ]
    downshift = [
        round(sum(i), rounding_precision)
        for i in zip(dsm_do_shift, balance_dsm_up)
    ]

    demand_after = handle_numerical_precision(demand_after, tolerance)
    upshift = handle_numerical_precision(upshift, tolerance)
    downshift = handle_numerical_precision(downshift, tolerance)

    results = {
        "demand_after": demand_after,
        "upshift": upshift,
        "downshift": downshift,
    }

    lsm.add_results(results)


def handle_numerical_precision(data: List, numerical_tolerance: float):
    """Force values with absolute value smaller than given tolerance to 0"""
    return [el if abs(el) > numerical_tolerance else 0 for el in data]