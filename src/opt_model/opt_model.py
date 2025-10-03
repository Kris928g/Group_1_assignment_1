# src/opt_model/opt_model.py

import pandas as pd
import gurobipy as gp
from gurobipy import GRB

class OptModel:
    """
    Implements and solves the consumer-level flexibility optimization problem
    as described in Question 1.a of the assignment.
    
    This class takes processed data as input, builds a Gurobi Linear Programming
    model, solves it, and returns the results in a structured format.
    """
    
    def __init__(self, hourly_params: pd.DataFrame, system_params: dict):
        """
        Initializes the optimization model with prepared data.

        Args:
            hourly_params (pd.DataFrame): A DataFrame containing all time-series data,
                                          indexed by hour (e.g., prices, available PV).
            system_params (dict): A dictionary containing all single-value system
                                  parameters (e.g., tariffs, min daily energy).
        """
        self.hourly_params = hourly_params
        self.system_params = system_params
        self.hours = range(len(self.hourly_params))
        
        # Create a new Gurobi model
        self.model = gp.Model("ConsumerFlexibility_1a")
        
        # Dictionary to hold our Gurobi variables for easy access
        self.vars = {}

    def solve(self) -> pd.DataFrame:
        """
        The main public method to build the model, solve it, and return the results.

        Returns:
            pd.DataFrame: A DataFrame containing the optimal schedule for all decision
                          variables. Returns None if no optimal solution is found.
        """
        # 1. Define the variables, objective, and constraints
        self._define_decision_variables()
        self._define_objective_function()
        self._define_constraints()
        
        # 2. Suppress Gurobi's console output for a cleaner run
        self.model.setParam('OutputFlag', 0)
        
        # 3. Run the optimization
        print("Solving with Gurobi...")
        self.model.optimize()
        
        # 4. Check the solution status and return results
        if self.model.Status == GRB.OPTIMAL:
            print("...Optimal solution found!")
            return self._extract_results()
        else:
            print(f"...Optimization finished with status code: {self.model.Status}. No optimal solution found.")
            return None

    def _define_decision_variables(self):
        """
        Defines the decision variables of the optimization model based on the
        provided formulation.
        
        - Pᵢ (pv_used): Actual PV production utilized.
        - Lᵢ (load): Power consumed by the flexible load.
        - Iᵢ (import): Power imported from the grid.
        - Eᵢ (export): Power exported to the grid.
        - P_curtailᵢ (pv_curtailed): PV power that is available but not used (wasted).
        """
        # The problem formulation uses Pᵢ for "Actual PV production". We will call it
        # pv_used to be explicit.
        self.vars['pv_used'] = self.model.addVars(self.hours, name="pv_used", lb=0)
        self.vars['load'] = self.model.addVars(self.hours, name="load", lb=0)
        
        # The formulation defines Gᵢ = Iᵢ - Eᵢ. We directly model Iᵢ and Eᵢ as non-negative variables.
        self.vars['import'] = self.model.addVars(self.hours, name="import", lb=0)
        self.vars['export'] = self.model.addVars(self.hours, name="export", lb=0)
        
        # An additional variable is needed to account for curtailed (wasted) PV energy.
        self.vars['pv_curtailed'] = self.model.addVars(self.hours, name="pv_curtailed", lb=0)
        
    def _define_objective_function(self):
        """
        Defines the objective function: minimize the total daily energy cost.
        Objective: min Σ [ Iᵢ(cᵢ + t) - Eᵢ(cᵢ - t) ]
        """
        prices = self.hourly_params['energy_price_dkk_kwh']
        
        import_tariff = self.system_params['import_tariff_dkk_kwh']
        export_tariff = self.system_params['export_tariff_dkk_kwh']

        daily_cost = gp.quicksum(
            self.vars['import'][h] * (prices[h] + import_tariff ) - \
            self.vars['export'][h] * (prices[h] - export_tariff )
            for h in self.hours
        )
        
        self.model.setObjective(daily_cost, GRB.MINIMIZE)
        
    def _define_constraints(self):
        """
        Defines all the constraints that govern the system's operation.
        """
        # Retrieve necessary parameters
        available_pv = self.hourly_params['available_pv_kw']
        min_daily_load = self.system_params['min_daily_energy_kwh']
        max_hourly_load = self.system_params['max_load_power_kw']
        max_import = self.system_params['max_import_kw']
        max_export = self.system_params['max_export_kw']

        # 1. Energy Balance Constraint (for each hour)
        #    Sources (PV Used + Grid Import) = Sinks (Load + Grid Export)
        self.model.addConstrs((
            self.vars['pv_used'][h] + self.vars['import'][h] - self.vars['export'][h] == self.vars['load'][h] 
            for h in self.hours), name="energy_balance"
        )

        # 2. PV Production Limit (for each hour)
        #    The PV power used plus the PV power curtailed must equal what's available.
        self.model.addConstrs((
            self.vars['pv_used'][h] + self.vars['pv_curtailed'][h] == available_pv[h]
            for h in self.hours), name="pv_production_limit"
        )
        
        # 3. Total Daily Energy Consumption (sum over all hours)
        self.model.addConstr(
            gp.quicksum(self.vars['load'][h] for h in self.hours) >= min_daily_load, 
            name="min_total_daily_energy"
        )

        # 4. Hourly Appliance and Grid Limits (for each hour)
        self.model.addConstrs((self.vars['load'][h] <= max_hourly_load for h in self.hours), name="max_hourly_load")
        self.model.addConstrs((self.vars['import'][h] <= max_import for h in self.hours), name="max_import")
        self.model.addConstrs((self.vars['export'][h] <= max_export for h in self.hours), name="max_export")

    def _extract_results(self) -> pd.DataFrame:
        """
        Extracts the optimal values of all decision variables from the solved
        model and returns them as a single pandas DataFrame.
        """
        results = []
        for h in self.hours:
            hour_data = {
                'hour': h,
                'pv_generation_kw': self.vars['pv_used'][h].X,
                'pv_curtailment_kw': self.vars['pv_curtailed'][h].X,
                'flexible_load_kw': self.vars['load'][h].X,
                'grid_import_kw': self.vars['import'][h].X,
                'grid_export_kw': self.vars['export'][h].X,
            }
            results.append(hour_data)
        
        results_df = pd.DataFrame(results)

        # Add input data and calculated costs for comprehensive analysis
        results_df['energy_price_dkk_kwh'] = self.hourly_params['energy_price_dkk_kwh'].values
        tariff_import = self.system_params['import_tariff_dkk_kwh']
        tariff_export = self.system_params['export_tariff_dkk_kwh']
        results_df['hourly_cost_dkk'] = (results_df['grid_import_kw'] * (results_df['energy_price_dkk_kwh'] + tariff_import)) - \
                                       (results_df['grid_export_kw'] * (results_df['energy_price_dkk_kwh'] - tariff_export))
        
        return results_df