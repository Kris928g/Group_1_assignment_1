# src/opt_model/opt_model_investment.py

import pandas as pd
import gurobipy as gp
from gurobipy import GRB
from typing import Tuple, Dict, Optional

class OptModel_battery:
    """
    Implements a Mixed-Integer Linear Program (MILP) to co-optimize
    battery investment size and daily operational strategy.
    """
    def __init__(self, hourly_params: pd.DataFrame, system_params: dict):
        self.hourly_params = hourly_params
        self.system_params = system_params
        self.hours = range(len(self.hourly_params))
        self.model = gp.Model("BatteryInvestment")
        self.vars = {}
        # This model doesn't need to store constraint handles for duals
        # as the primary output is the investment size.

    def solve(self, capital_cost_per_kwh: float) -> Optional[Tuple[pd.DataFrame, Dict]]:
        """
        Builds and solves the integrated investment model.
        """
        self.capital_cost = capital_cost_per_kwh
        
        self._define_variables()
        self._define_objective()
        self._define_constraints()
        
        self.model.setParam('OutputFlag', 0)
        self.model.optimize()
        
        if self.model.Status == GRB.OPTIMAL:
            return self._extract_primal_results(), self._extract_dual_results()
        else:
            # Add a print statement to see why it might be failing
            print(f"...Investment model finished with non-optimal status: {self.model.Status}")
            return None, None

    def _define_variables(self):
        """ Defines decision variables for both operation and investment. """
        self.vars['pv_used'] = self.model.addVars(self.hours, name="pv_used", lb=0)
        self.vars['load'] = self.model.addVars(self.hours, name="load", lb=0)
        self.vars['import'] = self.model.addVars(self.hours, name="import", lb=0)
        self.vars['export'] = self.model.addVars(self.hours, name="export", lb=0)
        self.vars['pv_curtailed'] = self.model.addVars(self.hours, name="pv_curtailed", lb=0)
        self.vars['charge'] = self.model.addVars(self.hours, name="charge", lb=0)
        self.vars['discharge'] = self.model.addVars(self.hours, name="discharge", lb=0)
        self.vars['soc'] = self.model.addVars(self.hours, name="soc", lb=0)
        self.vars['battery_capacity'] = self.model.addVar(name="battery_capacity", lb=0,)

    def _define_objective(self):
        """ Combines daily operational cost (OPEX) and amortized capital cost (CAPEX). """
        prices = self.hourly_params['energy_price_dkk_kwh']
        import_tariff = self.system_params['import_tariff_dkk_kwh']
        export_tariff = self.system_params['export_tariff_dkk_kwh']
        
        operational_cost = gp.quicksum(
            (self.vars['import'][h] * (prices[h] + import_tariff)) - \
            (self.vars['export'][h] * (prices[h] - export_tariff))
            for h in self.hours
        )
        
        daily_investment_cost = self.capital_cost * self.vars['battery_capacity']

        self.model.setObjective(operational_cost + daily_investment_cost, GRB.MINIMIZE)

    def _define_constraints(self):
        """ Defines constraints linking operation to the chosen investment size. """
        ref_profile = self.hourly_params['reference_load_profile_kw']
        available_pv = self.hourly_params['available_pv_kw']
        
        # --- BUG 1 FIX: Add the missing PV limit constraint ---
        self.model.addConstrs((
            self.vars['pv_used'][h] + self.vars['pv_curtailed'][h] == available_pv[h]
            for h in self.hours), name="pv_production_limit"
        )
        
        self.model.addConstrs((self.vars['load'][h] == ref_profile[h] for h in self.hours), name="fixed_load_profile")
        
        base_battery_params = self.system_params['battery_params']
        base_capacity = base_battery_params['capacity_kwh']

        charge_to_energy_ratio = base_battery_params['max_charge_kw'] / base_capacity
        discharge_to_energy_ratio = base_battery_params['max_discharge_kw'] / base_capacity

        capacity_var = self.vars['battery_capacity']
        self.model.addConstrs((self.vars['soc'][h] <= capacity_var for h in self.hours), name="max_soc")
        self.model.addConstrs((self.vars['charge'][h] <= charge_to_energy_ratio * capacity_var for h in self.hours), name="max_charge")
        self.model.addConstrs((self.vars['discharge'][h] <= discharge_to_energy_ratio * capacity_var for h in self.hours), name="max_discharge")
        
        for h in self.hours:
            prev_soc = 0.5 * capacity_var if h == 0 else self.vars['soc'][h-1]
            self.model.addConstr(
                self.vars['soc'][h] == prev_soc + (self.vars['charge'][h] * base_battery_params['charge_efficiency']) - (self.vars['discharge'][h] / base_battery_params['discharge_efficiency']),
                name=f"soc_update_{h}"
            )
        self.model.addConstr(self.vars['soc'][self.hours[-1]] == 0.5 * capacity_var, name="final_soc")

        self.model.addConstrs((
            self.vars['pv_used'][h] + self.vars['import'][h] + self.vars['discharge'][h] == \
            self.vars['load'][h] + self.vars['export'][h] + self.vars['charge'][h]
            for h in self.hours), name="energy_balance"
        )

    def _extract_primal_results(self) -> pd.DataFrame:
        """ Extracts the optimal values of all decision variables. """
        results = []
        for h in self.hours:
            hour_data = {
                'hour': h,
                'pv_generation_kw': self.vars['pv_used'][h].X,
                'pv_curtailment_kw': self.vars['pv_curtailed'][h].X,
                'flexible_load_kw': self.vars['load'][h].X,
                'grid_import_kw': self.vars['import'][h].X,
                'grid_export_kw': self.vars['export'][h].X,
                # --- BUG 2 FIX: Remove the 'if' condition ---
                # This class always has a battery, so we can always extract these values.
                'battery_charge_kw': self.vars['charge'][h].X,
                'battery_discharge_kw': self.vars['discharge'][h].X,
                'battery_soc_kwh': self.vars['soc'][h].X,
            }
            results.append(hour_data)
        
        results_df = pd.DataFrame(results)

        prices = self.hourly_params['energy_price_dkk_kwh']
        tariff_import = self.system_params['import_tariff_dkk_kwh']
        tariff_export = self.system_params['export_tariff_dkk_kwh']
        results_df['hourly_cost_dkk'] = (results_df['grid_import_kw'] * (prices + tariff_import)) - \
                                       (results_df['grid_export_kw'] * (prices - tariff_export))
        return results_df

    def _extract_dual_results(self) -> Dict:
        """ Also extracts the optimal investment decision. """
        duals = {
            'optimal_battery_size_kwh': self.vars['battery_capacity'].X
        }
        return duals