import pyomo.environ as pyo


def extract_results(lsm, rounding_precision=4):
    """Extract and add results for a solved load shift optimization model

    Parameters
    ----------
    lsm: LoadShiftOptimizationModel
        The actual model after solving the optimization model part

    rounding_precision: int
        Round float values to given number of digits to avoid numerical
        artifacts
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

    results = {
        "demand_after": demand_after,
        "upshift": upshift,
        "downshift": downshift,
    }

    lsm.add_results(results)
