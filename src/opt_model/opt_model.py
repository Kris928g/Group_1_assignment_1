# src/opt_model/opt_model.py

import pandas as pd
import gurobipy as gp
from gurobipy import GRB
from typing import Tuple, Dict, Optional # Import typing hints for clarity

class OptModel:
    """
    Implements and solves the consumer-level flexibility optimization problem.
    This version cleanly separates the extraction of primal and dual results.
    """
    
    def __init__(self, hourly_params: pd.DataFrame, system_params: dict):
        """ Initializes the optimization model with prepared data. """
        self.hourly_params = hourly_params
        self.system_params = system_params
        self.hours = range(len(self.hourly_params))
        self.model = gp.Model("ConsumerFlexibility")
        self.vars = {}
        
        # A dictionary to hold handles to important constraints
        self.constraints = {}

    # --- CHANGE 1: Update the solve method to return a tuple ---
    def solve(self) -> Optional[Tuple[pd.DataFrame, Dict]]:
        """
        Builds the model, solves it, and returns the results.

        Returns:
            A tuple containing:
            - pd.DataFrame: The optimal schedule (primal solution).
            - Dict: A dictionary of key dual values (shadow prices).
            Returns (None, None) if no optimal solution is found.
        """
        self._define_decision_variables()
        self._define_objective_function()
        self._define_constraints()
        
        self.model.setParam('OutputFlag', 0)
        
        print("Solving with Gurobi...")
        self.model.optimize()
        
        if self.model.Status == GRB.OPTIMAL:
            print("...Optimal solution found!")
            # Call the two separate helper methods
            primal_results = self._extract_primal_results()
            dual_results = self._extract_dual_results()
            # Return a tuple with exactly TWO items.
            return primal_results, dual_results
        else:
            print(f"...Optimization finished with status code: {self.model.Status}.")
            # Also return a tuple of two items on failure.
            return None, None

    def _define_decision_variables(self):
        """ Defines the decision variables of the optimization model. """
        self.vars['pv_used'] = self.model.addVars(self.hours, name="pv_used", lb=0)
        self.vars['load'] = self.model.addVars(self.hours, name="load", lb=0)
        self.vars['import'] = self.model.addVars(self.hours, name="import", lb=0)
        self.vars['export'] = self.model.addVars(self.hours, name="export", lb=0)
        self.vars['pv_curtailed'] = self.model.addVars(self.hours, name="pv_curtailed", lb=0)
        
    def _define_objective_function(self):
        """ Defines the objective function: minimize total daily cost. """
        prices = self.hourly_params['energy_price_dkk_kwh']
        import_tariff = self.system_params['import_tariff_dkk_kwh']
        export_tariff = self.system_params['export_tariff_dkk_kwh']
        
        daily_cost = gp.quicksum(
            (self.vars['import'][h] * (prices[h] + import_tariff)) - \
            (self.vars['export'][h] * (prices[h] - export_tariff))
            for h in self.hours
        )
        self.model.setObjective(daily_cost, GRB.MINIMIZE)
        
    def _define_constraints(self):
        """ Defines all the constraints that govern the system's operation. """
        available_pv = self.hourly_params['available_pv_kw']
        min_daily_load = self.system_params['min_daily_energy_kwh']
        max_hourly_load = self.system_params['max_load_power_kw']
        max_import = self.system_params['max_import_kw']
        max_export = self.system_params['max_export_kw']

        self.model.addConstrs((
            self.vars['pv_used'][h] + self.vars['import'][h] == self.vars['load'][h] + self.vars['export'][h]
            for h in self.hours), name="energy_balance"
        )
        self.model.addConstrs((
            self.vars['pv_used'][h] + self.vars['pv_curtailed'][h] == available_pv[h]
            for h in self.hours), name="pv_production_limit"
        )
        
        # --- CHANGE 2: Define the min energy constraint ONLY ONCE and save the handle ---
        # The previous version had a bug where this constraint was added twice.
        self.constraints['min_total_daily_energy'] = self.model.addConstr(
            gp.quicksum(self.vars['load'][h] for h in self.hours) >= min_daily_load, 
            name="min_total_daily_energy"
        )

        self.model.addConstrs((self.vars['load'][h] <= max_hourly_load for h in self.hours), name="max_hourly_load")
        self.model.addConstrs((self.vars['import'][h] <= max_import for h in self.hours), name="max_import")
        self.model.addConstrs((self.vars['export'][h] <= max_export for h in self.hours), name="max_export")

    # --- CHANGE 3: Your old _extract_results is now _extract_primal_results ---
    # Its only job is to return the DataFrame.
    def _extract_primal_results(self) -> pd.DataFrame:
        """
        Extracts the optimal values of all decision variables (primal solution).
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

        results_df['energy_price_dkk_kwh'] = self.hourly_params['energy_price_dkk_kwh'].values
        tariff_import = self.system_params['import_tariff_dkk_kwh']
        tariff_export = self.system_params['export_tariff_dkk_kwh']
        results_df['hourly_cost_dkk'] = (results_df['grid_import_kw'] * (results_df['energy_price_dkk_kwh'] + tariff_import)) - \
                                       (results_df['grid_export_kw'] * (results_df['energy_price_dkk_kwh'] - tariff_export))
        return results_df

    # --- CHANGE 4: This is the new function to correctly handle dual values ---
    def _extract_dual_results(self) -> Dict:
        """
        Extracts the shadow prices (dual values) of key constraints.
        """
        duals = {
            # Use the full, descriptive key that matches what 'summary.py' expects.
            'min_energy_shadow_price_dkk_kwh': self.constraints['min_total_daily_energy'].Pi
        }
        return duals