# src/opt_model/opt_model.py

import pandas as pd
import gurobipy as gp
from gurobipy import GRB
from typing import Tuple, Dict, Optional

class OptModel:
    """
    Implements a data-driven optimization model that automatically adapts its
    structure based on the provided parameters. This version corrects the
    constraint logic to ensure all necessary constraints are always applied.
    """
    
    def __init__(self, hourly_params: pd.DataFrame, system_params: dict):
        """ Initializes the optimization model with prepared data. """
        self.hourly_params = hourly_params
        self.system_params = system_params
        self.hours = range(len(self.hourly_params))
        self.model = gp.Model("ConsumerFlexibility_DataDriven")
        self.vars = {}
        self.constraints = {}

    def solve(self) -> Optional[Tuple[pd.DataFrame, Dict]]:
        """ Builds and solves the model based on the data it was initialized with. """
        self._define_variables()
        self._define_objective() # This call was missing in the provided file
        self._define_constraints()
        
        self.model.setParam('OutputFlag', 0)
        
        print("Solving with Gurobi...")
        self.model.optimize()
        
        if self.model.Status == GRB.OPTIMAL:
            print("...Optimal solution found!")
            primal_results = self._extract_primal_results()
            dual_results = self._extract_dual_results()
            return primal_results, dual_results
        else:
            print(f"...Optimization finished with status code: {self.model.Status}.")
            return None, None

    def _define_variables(self):
        """ Defines all necessary decision variables based on the data. """
        self.vars['pv_used'] = self.model.addVars(self.hours, name="pv_used", lb=0)
        self.vars['load'] = self.model.addVars(self.hours, name="load", lb=0)
        self.vars['import'] = self.model.addVars(self.hours, name="import", lb=0)
        self.vars['export'] = self.model.addVars(self.hours, name="export", lb=0)
        self.vars['pv_curtailed'] = self.model.addVars(self.hours, name="pv_curtailed", lb=0)

        if self.system_params.get('problem_type') == 'soft_constraint':
            self.vars['dev_pos'] = self.model.addVars(self.hours, name="dev_pos", lb=0)
            self.vars['dev_neg'] = self.model.addVars(self.hours, name="dev_neg", lb=0)

        if self.system_params.get('has_battery', False):
            self.vars['charge'] = self.model.addVars(self.hours, name="charge", lb=0)
            self.vars['discharge'] = self.model.addVars(self.hours, name="discharge", lb=0)
            self.vars['soc'] = self.model.addVars(self.hours, name="soc", lb=0)

    def _define_objective(self):
        """Builds the objective function based on the problem type."""
        if self.system_params.get('problem_type') == 'soft_constraint':
            print("...Building NORMALIZED objective function (cost vs. comfort).")
            C_I_tot = self.system_params['C_I_tot']
            L_tot = self.system_params['L_tot']
            prices = self.hourly_params['energy_price_dkk_kwh']
            import_tariff = self.system_params['import_tariff_dkk_kwh']
            export_tariff = self.system_params['export_tariff_dkk_kwh']
            
            energy_cost = gp.quicksum(
                (self.vars['import'][h] * (prices[h] + import_tariff)) - \
                (self.vars['export'][h] * (prices[h] - export_tariff))
                for h in self.hours
            )
            discomfort = gp.quicksum(
                self.vars['dev_pos'][h] + self.vars['dev_neg'][h] for h in self.hours
            )
            normalized_objective = (1 / C_I_tot) * energy_cost + (1 / L_tot) * discomfort
            self.model.setObjective(normalized_objective, GRB.MINIMIZE)
        else:
            print("...Building COST-ONLY objective function.")
            prices = self.hourly_params['energy_price_dkk_kwh']
            import_tariff = self.system_params['import_tariff_dkk_kwh']
            export_tariff = self.system_params['export_tariff_dkk_kwh']
            
            energy_cost = gp.quicksum(
                (self.vars['import'][h] * (prices[h] + import_tariff)) - \
                (self.vars['export'][h] * (prices[h] - export_tariff))
                for h in self.hours
            )
            self.model.setObjective(energy_cost, GRB.MINIMIZE)

    # --- THIS METHOD CONTAINS THE FIX ---
    def _define_constraints(self):
        """
        Defines all necessary constraints in a clean, data-driven manner.
        """
        # --- 1. Base constraints (ALWAYS apply) ---
        self.model.addConstrs((
            self.vars['pv_used'][h] + self.vars['pv_curtailed'][h] == self.hourly_params['available_pv_kw'][h]
            for h in self.hours), name="pv_limit"
        )
        self.model.addConstrs((self.vars['import'][h] <= self.system_params['max_import_kw'] for h in self.hours), name="max_import")
        self.model.addConstrs((self.vars['export'][h] <= self.system_params['max_export_kw'] for h in self.hours), name="max_export")

        # --- 2. Load-specific constraints (mutually exclusive) ---
        if self.system_params.get('problem_type') == 'soft_constraint':
            self.model.addConstrs((self.vars['load'][h] <= self.system_params['max_load_power_kw'] for h in self.hours), name="max_load_soft")
            ref_profile = self.hourly_params['reference_load_profile_kw']
            self.model.addConstrs((
                self.vars['load'][h] - ref_profile[h] == self.vars['dev_pos'][h] - self.vars['dev_neg'][h]
                for h in self.hours), name="deviation_definition"
            )
        else: # 'hard_constraint' problem
            self.model.addConstrs((self.vars['load'][h] <= self.system_params['max_load_power_kw'] for h in self.hours), name="max_load_hard")
            self.constraints['min_total_daily_energy'] = self.model.addConstr(
                gp.quicksum(self.vars['load'][h] for h in self.hours) >= self.system_params['min_daily_energy_kwh'], 
                name="min_daily_energy"
            )

        # --- 3. Energy Balance and Battery constraints (mutually exclusive) ---
        if self.system_params.get('has_battery', False):
            # Energy balance WITH battery
            self.model.addConstrs((
                self.vars['pv_used'][h] + self.vars['import'][h] + self.vars['discharge'][h] == \
                self.vars['load'][h] + self.vars['export'][h] + self.vars['charge'][h]
                for h in self.hours), name="energy_balance_with_battery"
            )
            # Add all battery-specific constraints
            bp = self.system_params['battery_params']
            self.model.addConstrs((self.vars['charge'][h] <= bp['max_charge_kw'] for h in self.hours), name="max_charge")
            self.model.addConstrs((self.vars['discharge'][h] <= bp['max_discharge_kw'] for h in self.hours), name="max_discharge")
            self.model.addConstrs((self.vars['soc'][h] <= bp['capacity_kwh'] for h in self.hours), name="max_soc")
            for h in self.hours:
                prev_soc = bp['initial_soc_kwh'] if h == 0 else self.vars['soc'][h-1]
                self.model.addConstr(
                    self.vars['soc'][h] == prev_soc + (self.vars['charge'][h] * bp['charge_efficiency']) - (self.vars['discharge'][h] / bp['discharge_efficiency']),
                    name=f"soc_update_{h}"
                )
            self.model.addConstr(self.vars['soc'][self.hours[-1]] == bp['final_soc_kwh'], name="final_soc")
        else:
            # Energy balance WITHOUT battery
            self.model.addConstrs((
                self.vars['pv_used'][h] + self.vars['import'][h] == self.vars['load'][h] + self.vars['export'][h]
                for h in self.hours), name="energy_balance_no_battery"
            )

    def _extract_primal_results(self) -> pd.DataFrame:
        """ Extracts the PRIMAL solution (the DataFrame). """
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
            if self.system_params.get('problem_type') == 'soft_constraint':
                hour_data['deviation_kw'] = self.vars['dev_pos'][h].X - self.vars['dev_neg'][h].X
            if self.system_params.get('has_battery', False):
                hour_data['battery_charge_kw'] = self.vars['charge'][h].X
                hour_data['battery_discharge_kw'] = self.vars['discharge'][h].X
                hour_data['battery_soc_kwh'] = self.vars['soc'][h].X
            results.append(hour_data)
        
        results_df = pd.DataFrame(results)

        prices = self.hourly_params['energy_price_dkk_kwh']
        tariff_import = self.system_params['import_tariff_dkk_kwh']
        tariff_export = self.system_params['export_tariff_dkk_kwh']
        results_df['hourly_cost_dkk'] = (results_df['grid_import_kw'] * (prices + tariff_import)) - \
                                       (results_df['grid_export_kw'] * (prices - tariff_export))
        return results_df

    def _extract_dual_results(self) -> Dict:
        """ Extracts the DUAL solution (the dictionary of shadow prices). """
        duals = {}
        if 'min_total_daily_energy' in self.constraints:
            duals['min_energy_shadow_price_dkk_kwh'] = self.constraints['min_total_daily_energy'].Pi
        return duals