import warnings

import pyomo.environ as pyo
from numpy import mean


class LoadShiftOptimizationModel:
    """A model to minimize the energy procurement costs for load shifting

    Attributes
    ----------
    normalized_baseline_load: list
        Normalized baseline load values

    energy_price: list
        Energy price values

    availability_up: list
        Availability for shifts in upwards direction (normalized)

    availability_down: list
        Availability for shifts in downwards direction (normalized)

    peak_load_price: float
        Price for peak demand (capacity)

    variable_costs_down: list
        Variable costs for a downshift

    variable_costs_up: list
        Variable costs for a upshift

    shifting_times: list
        List of all allowed shifting times

    interference_time: int
        Maximum allowed time for the shifting in one direction, i.e. maximum
        duration for a downshift or an upshift respectively

    peak_demand_before: float
        The maximum load value, given in MW

    max_capacity_down: float
        The capacity that can be shifted downwards at maximum, given in MW

    max_capacity_up: float
        The capacity that can be shifted downwards at maximum, given in MW

    efficiency: float
        Efficiency for load shifting (between 0 and 1)

    max_activations: int
        Number of maximum activations per year; only applied if boolean switch
        activate_annual_limits in constructor is set to True

    initial_energy_level : float
        Initial energy level to consider when accounting for load shifting
        energy limits in the optimization model

    time_increment: list of int or float
        Defines the time resolution; if nothing is given, a default value of
         1 for each time step is used, i.e. an hourly resolution can be
         depicted

    model: pyo.ConcreteModel
        The actual optimization model

    solver: str
        Solver to use for solving the mathematical optimization problem
    """

    def __init__(
        self,
        normalized_baseline_load,
        energy_price,
        availability_up,
        availability_down,
        peak_load_price,
        variable_costs_down,
        variable_costs_up,
        max_shifting_time,
        interference_time,
        peak_demand_before,
        max_capacity_down,
        max_capacity_up,
        price_sensitivity,
        efficiency=1,
        activate_annual_limits=False,
        max_activations=None,
        initial_energy_level=0,
        time_increment=None,
        solver="gurobi",
    ):
        """Initialize a load shift optimization model

        For parameters, please refer to class attributes documentation.

        Additional parameters
        ---------------------
        max_shifting_time: int
             maximum allowed shifting time. Any positive natural number below
             is assumed to be a feasible shifting time.

        activate_annual_limits: boolean
            If True, introduce annual limit of overall maximum activations
        """
        # Time series data
        self.normalized_baseline_load = normalized_baseline_load
        self.energy_price = energy_price
        self.availability_up = availability_up
        self.availability_down = availability_down
        self.price_sensitivity = price_sensitivity

        # Parameters
        self.peak_load_price = peak_load_price
        self.variable_costs_down = variable_costs_down
        self.variable_costs_up = variable_costs_up
        self.shifting_times = list(range(1, max_shifting_time + 1))
        self.interference_time = interference_time
        self.peak_demand_before = peak_demand_before
        self.max_capacity_down = max_capacity_down
        self.max_capacity_up = max_capacity_up
        self.efficiency = efficiency
        self.activate_annual_limits = activate_annual_limits
        if not time_increment:
            self.time_increment = [1] * len(self.normalized_baseline_load)
        else:
            self.time_increment = time_increment
        self.availability_down_mean = mean(self.availability_down)
        self.availability_up_mean = mean(self.availability_up)
        if max_activations and not activate_annual_limits:
            warnings.warn(
                "You specified the number of maximum activations per year, "
                "but deactivated annual limits. Thus, the `max_activations` "
                "parameter has no effect."
            )
        else:
            if max_activations == 1000000:
                warnings.warn(
                    "You did not specify a value to limit the maximum number "
                    "of activations per year. Thus, the default value of "
                    "'1,000,000' applies. which is equivalent to not limiting "
                    "maximum activations at all."
                )
            self.max_activations = max_activations
        self.initial_energy_level = initial_energy_level
        self.model = None
        self.solver = solver
        self._setup_model()
        self._solve_model()

    def _setup_model(self):
        """Set up the optimization model"""
        model = pyo.ConcreteModel("Load shift optimization model")
        self.model = model

        #  ************* SETS *********************************

        model.T = pyo.Set(
            initialize=range(len(self.normalized_baseline_load)),
            doc="time steps of the model",
        )

        model.H = pyo.Set(
            initialize=self.shifting_times,
            doc="possible shifting times",
        )

        #  ************* VARIABLES *****************************

        model.demand_after = pyo.Var(
            model.T,
            initialize=0,
            within=pyo.NonNegativeReals,
            doc="resulting demand (i.e. capacity) after load shifting",
        )

        model.peak_load = pyo.Var(
            initialize=0,
            within=pyo.NonNegativeReals,
            doc="resulting peak load after load shifting",
        )

        model.dsm_do_shift = pyo.Var(
            model.H,
            model.T,
            initialize=0,
            within=pyo.NonNegativeReals,
            doc="capacity shifted downwards",
        )

        model.dsm_up = pyo.Var(
            model.H,
            model.T,
            initialize=0,
            within=pyo.NonNegativeReals,
            doc="capacity shifted upwards",
        )

        model.balance_dsm_do = pyo.Var(
            model.H,
            model.T,
            initialize=0,
            within=pyo.NonNegativeReals,
            doc="balancing of capacity shifted downwards",
        )

        model.balance_dsm_up = pyo.Var(
            model.H,
            model.T,
            initialize=0,
            within=pyo.NonNegativeReals,
            doc="balancing of capacity shifted upwards",
        )

        model.demand_change = pyo.Var(
            model.T,
            initialize=0,
            within=pyo.NonNegativeReals,
            doc="change in demand due to shifting",
        )

        model.dsm_do_level = pyo.Var(
            model.T,
            initialize=0,
            within=pyo.NonNegativeReals,
            doc="fictitious energy storage level for (initial) downshifts",
        )

        model.dsm_up_level = pyo.Var(
            model.T,
            initialize=0,
            within=pyo.NonNegativeReals,
            doc="fictitious energy storage level for (initial) upshifts",
        )

        #  ************* CONSTRAINTS *****************************

        def _peak_load_definition_rule(model):
            """Peak load is the maximum demand after demand response"""
            for t in model.T:
                lhs = model.peak_load
                rhs = model.demand_after[t]
                model.peak_load_definition.add(t, (lhs >= rhs))

        model.peak_load_definition = pyo.Constraint(model.T, noruleinit=True)
        model.peak_load_definition_build = pyo.BuildAction(
            rule=_peak_load_definition_rule
        )

        def _demand_change_defition_rule(model):
            """Demand change is the sum of upshifts minus downshifts"""
            for t in model.T:
                lhs = model.demand_change[t]
                rhs = sum(
                    model.dsm_up[h, t]
                    + model.balance_dsm_do[h, t]
                    - model.dsm_do_shift[h, t]
                    - model.balance_dsm_up[h, t]
                    for h in self.shifting_times
                )
                model.demand_change_definition.add(t, (lhs == rhs))

        model.demand_change_definition = pyo.Constraint(
            model.T, noruleinit=True
        )
        model.demand_change_definition_build = pyo.BuildAction(
            rule=_demand_change_defition_rule
        )

        def _demand_after_definition_rule(model):
            """Relation determining actual demand after demand response"""
            for t in model.T:
                lhs = model.demand_after[t]
                rhs = (
                    self.normalized_baseline_load[t] * self.peak_demand_before
                    + model.demand_change[t]
                )
                model.demand_after_definition.add(t, (lhs == rhs))

        model.demand_after_definition = pyo.Constraint(
            model.T, noruleinit=True
        )
        model.demand_after_definition_build = pyo.BuildAction(
            rule=_demand_after_definition_rule
        )

        def _capacity_balance_red_rule(model):
            """Load reduction must be balanced by load increase
            within allowed maximum shifting time"""
            for t in model.T:
                for h in self.shifting_times:
                    # main use case
                    if t >= h:
                        lhs = model.balance_dsm_do[h, t]
                        rhs = model.dsm_do_shift[h, t - h] / self.efficiency
                        model.capacity_balance_red.add((h, t), (lhs == rhs))

                    # no balancing for the first time step
                    elif t == model.T.at(1):
                        lhs = model.balance_dsm_do[h, t]
                        rhs = 0
                        model.capacity_balance_red.add((h, t), (lhs == rhs))

        model.capacity_balance_red = pyo.Constraint(
            model.H, model.T, noruleinit=True
        )
        model.capacity_balance_red_build = pyo.BuildAction(
            rule=_capacity_balance_red_rule
        )

        def _capacity_balance_inc_rule(model):
            """Load increase must be balanced by load reduction
            within allowed maximum shifting time"""
            for t in model.T:
                for h in self.shifting_times:
                    # main use case
                    if t >= h:
                        lhs = model.balance_dsm_up[h, t]
                        rhs = model.dsm_up[h, t - h] * self.efficiency
                        model.capacity_balance_inc.add((h, t), (lhs == rhs))

                    # no balancing for the first time step
                    elif t == model.T.at(1):
                        lhs = model.balance_dsm_up[h, t]
                        rhs = 0
                        model.capacity_balance_inc.add((h, t), (lhs == rhs))

        model.capacity_balance_inc = pyo.Constraint(
            model.H, model.T, noruleinit=True
        )
        model.capacity_balance_inc_build = pyo.BuildAction(
            rule=_capacity_balance_inc_rule
        )

        def _no_compensation_red_rule(model):
            """Prevent downwards shifts that cannot be balanced anymore
            within the optimization timeframe"""
            for t in model.T:
                for h in self.shifting_times:

                    if t > model.T.at(-1) - h:
                        # no load reduction anymore (dsm_do_shift = 0)
                        lhs = model.dsm_do_shift[h, t]
                        rhs = 0
                        model.no_compensation_red.add((h, t), (lhs == rhs))

        model.no_compensation_red = pyo.Constraint(
            model.H, model.T, noruleinit=True
        )
        model.no_compensation_red_build = pyo.BuildAction(
            rule=_no_compensation_red_rule
        )

        def _no_compensation_inc_rule(model):
            """Prevent upwards shifts that cannot be balanced anymore
            within the optimization timeframe"""
            for t in model.T:
                for h in self.shifting_times:

                    if t > model.T.at(-1) - h:
                        # no load increase anymore (dsm_up = 0)
                        lhs = model.dsm_up[h, t]
                        rhs = 0
                        model.no_compensation_inc.add((h, t), (lhs == rhs))

        model.no_compensation_inc = pyo.Constraint(
            model.H, model.T, noruleinit=True
        )
        model.no_compensation_inc_build = pyo.BuildAction(
            rule=_no_compensation_inc_rule
        )

        def _availability_red_rule(model):
            """Load reduction must be smaller than or equal to the
            (time-dependent) capacity limit"""
            for t in model.T:
                lhs = sum(
                    model.dsm_do_shift[h, t] + model.balance_dsm_up[h, t]
                    for h in self.shifting_times
                )
                rhs = self.availability_down[t] * self.max_capacity_down
                model.availability_red.add(t, (lhs <= rhs))

        model.availability_red = pyo.Constraint(model.T, noruleinit=True)
        model.availability_red_build = pyo.BuildAction(
            rule=_availability_red_rule
        )

        def _availability_inc_rule(model):
            """Load increase must be smaller than or equal to the
            (time-dependent) capacity limit"""
            for t in model.T:
                lhs = sum(
                    model.dsm_up[h, t] + model.balance_dsm_do[h, t]
                    for h in self.shifting_times
                )
                rhs = self.availability_up[t] * self.max_capacity_up
                model.availability_inc.add(t, (lhs <= rhs))

        model.availability_inc = pyo.Constraint(model.T, noruleinit=True)
        model.availability_inc_build = pyo.BuildAction(
            rule=_availability_inc_rule
        )

        def _dr_storage_red_rule(model):
            """Fictitious demand response storage level for load reductions
            transition equation"""
            for t in model.T:
                # avoid time steps prior to t = 0
                if t > 0:
                    lhs = self.time_increment[t] * sum(
                        (
                            model.dsm_do_shift[h, t]
                            - model.balance_dsm_do[h, t] * self.efficiency
                        )
                        for h in self.shifting_times
                    )
                    rhs = model.dsm_do_level[t] - model.dsm_do_level[t - 1]
                    model.dr_storage_red.add(t, (lhs == rhs))

                elif self.initial_energy_level < 0:
                    red_level_initial = -self.initial_energy_level
                    lhs = model.dsm_do_level[t]
                    rhs = (
                        self.time_increment[t]
                        * sum(
                            model.dsm_do_shift[h, t]
                            for h in self.shifting_times
                        )
                        + red_level_initial
                    )
                    model.dr_storage_red.add(t, (lhs == rhs))

                else:
                    lhs = model.dsm_do_level[t]
                    rhs = self.time_increment[t] * sum(
                        model.dsm_do_shift[h, t] for h in self.shifting_times
                    )
                    model.dr_storage_red.add(t, (lhs == rhs))

        model.dr_storage_red = pyo.Constraint(model.T, noruleinit=True)
        model.dr_storage_red_build = pyo.BuildAction(rule=_dr_storage_red_rule)

        def _dr_storage_inc_rule(model):
            """Fictitious demand response storage level for load increase
            transition equation"""
            for t in model.T:
                # avoid time steps prior to t = 0
                if t > 0:
                    lhs = self.time_increment[t] * sum(
                        (
                            model.dsm_up[h, t] * self.efficiency
                            - model.balance_dsm_up[h, t]
                        )
                        for h in self.shifting_times
                    )
                    rhs = model.dsm_up_level[t] - model.dsm_up_level[t - 1]
                    model.dr_storage_inc.add(t, (lhs == rhs))

                elif self.initial_energy_level > 0:
                    inc_level_initial = self.initial_energy_level
                    lhs = model.dsm_do_level[t]
                    rhs = (
                        self.time_increment[t]
                        * sum(
                            model.dsm_do_shift[h, t]
                            for h in self.shifting_times
                        )
                        + inc_level_initial
                    )
                    model.dr_storage_red.add(t, (lhs == rhs))

                else:
                    lhs = model.dsm_up_level[t]
                    rhs = self.time_increment[t] * sum(
                        model.dsm_up[h, t] for h in self.shifting_times
                    )
                    model.dr_storage_inc.add(t, (lhs == rhs))

        model.dr_storage_inc = pyo.Constraint(model.T, noruleinit=True)
        model.dr_storage_inc_build = pyo.BuildAction(rule=_dr_storage_inc_rule)

        def _dr_storage_limit_red_rule(model):
            """Fictitious demand response storage level for reduction limit"""
            for t in model.T:
                lhs = model.dsm_do_level[t]
                rhs = (
                    self.availability_down_mean
                    * self.max_capacity_down
                    * self.interference_time
                )
                model.dr_storage_limit_red.add(t, (lhs <= rhs))

        model.dr_storage_limit_red = pyo.Constraint(model.T, noruleinit=True)
        model.dr_storage_level_red_build = pyo.BuildAction(
            rule=_dr_storage_limit_red_rule
        )

        def _dr_storage_limit_inc_rule(model):
            """Fictitious demand response storage level for increase limit"""
            for t in model.T:
                lhs = model.dsm_up_level[t]
                rhs = (
                    self.availability_up_mean
                    * self.max_capacity_up
                    * self.interference_time
                )
                model.dr_storage_limit_inc.add(t, (lhs <= rhs))

        model.dr_storage_limit_inc = pyo.Constraint(model.T, noruleinit=True)
        model.dr_storage_level_inc_build = pyo.BuildAction(
            rule=_dr_storage_limit_inc_rule
        )

        def _dr_logical_constraint_rule(model):
            """Similar to equation 10 from Zerrahn and Schill (2015):
            The sum of upwards and downwards shifts must not be greater
            than the (bigger) capacity limit to avoid activation of more than
            overall existing capacity."""
            for t in model.T:
                # sum of load increases and reductions
                lhs = sum(
                    model.dsm_up[h, t]
                    + model.balance_dsm_do[h, t]
                    + model.dsm_do_shift[h, t]
                    + model.balance_dsm_up[h, t]
                    for h in self.shifting_times
                )
                rhs = max(
                    self.availability_down[t] * self.max_capacity_down,
                    self.availability_up[t] * self.max_capacity_up,
                )
                model.dr_logical_constraint.add(t, (lhs <= rhs))

        model.dr_logical_constraint = pyo.Constraint(model.T, noruleinit=True)
        model.dr_logical_constraint_build = pyo.BuildAction(
            rule=_dr_logical_constraint_rule
        )

        # ************* Optional Constraints *****************************

        def _dr_yearly_limit_red_rule(model):
            """Introduce overall annual (energy) limit for load reductions
            resp. overall limit for optimization timeframe considered"""
            if self.activate_annual_limits:
                lhs = sum(
                    sum(model.dsm_do_shift[h, t] for h in self.shifting_times)
                    for t in model.T
                )
                rhs = (
                    self.availability_down_mean
                    * self.max_capacity_down
                    * self.interference_time
                    * self.max_activations
                )
                return lhs <= rhs

            else:
                return pyo.Constraint.Skip

        model.dr_yearly_limit_red = pyo.Constraint(
            rule=_dr_yearly_limit_red_rule
        )

        def _dr_yearly_limit_inc_rule(model):
            """Introduce overall annual (energy) limit for load increases
            resp. overall limit for optimization timeframe considered"""
            if self.activate_annual_limits:
                lhs = sum(
                    sum(model.dsm_up[h, t] for h in self.shifting_times)
                    for t in model.T
                )
                rhs = (
                    self.availability_up_mean
                    * self.max_capacity_up
                    * self.interference_time
                    * self.max_activations
                )
                return lhs <= rhs

            else:
                return pyo.Constraint.Skip

        model.dr_yearly_limit_inc = pyo.Constraint(
            rule=_dr_yearly_limit_inc_rule
        )

        #  ************* OBJECTIVE ****************************

        def _objective_rule(model):
            """Objective expression of the model"""
            overall_energy_costs = 0
            overall_peak_load_costs = 0
            overall_variable_costs = 0

            overall_energy_costs += sum(
                (
                    (
                        self.normalized_baseline_load[t]
                        * self.peak_demand_before
                        + model.demand_change[t]
                    )
                    * (
                        self.energy_price[t]
                        + (model.demand_change[t] * self.price_sensitivity[t])
                    )
                )
                * self.time_increment[t]
                for t in model.T
            )
            overall_peak_load_costs += model.peak_load * self.peak_load_price

            overall_variable_costs += sum(
                (
                    sum(model.dsm_do_shift[h, t] for h in self.shifting_times)
                    + sum(
                        model.balance_dsm_up[h, t] for h in self.shifting_times
                    )
                )
                * self.variable_costs_down[t]
                * self.time_increment[t]
                + (
                    sum(model.dsm_up[h, t] for h in self.shifting_times)
                    + sum(
                        model.balance_dsm_do[h, t] for h in self.shifting_times
                    )
                )
                * self.variable_costs_up[t]
                * self.time_increment[t]
                for t in model.T
            )

            model.overall_energy_costs = pyo.Expression(
                expr=overall_energy_costs
            )
            model.overall_peak_load_costs = pyo.Expression(
                expr=overall_peak_load_costs
            )
            model.overall_variable_costs = pyo.Expression(
                expr=overall_variable_costs
            )
            model.costs = pyo.Expression(
                expr=(
                    overall_energy_costs
                    + overall_peak_load_costs
                    + overall_variable_costs
                )
            )

            return model.costs

        model.objective = pyo.Objective(
            rule=_objective_rule, sense=pyo.minimize
        )

        self.model = model

    def _solve_model(self):
        """Solve the optimization model and return its results"""
        solver = pyo.SolverFactory(self.solver)
        return solver.solve(self.model, keepfiles=False, tee=False)

    def add_results(self, results):
        for key, val in results.items():
            setattr(self, key, val)
