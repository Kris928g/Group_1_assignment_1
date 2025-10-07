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
        self._define_objective() 
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
        # --- Base energy flow variables (created for ALL scenarios) ---
        # These represent the fundamental choices the optimizer can make each hour.
        # All are non-negative (lower bound lb=0).
        self.vars['pv_used'] = self.model.addVars(self.hours, name="pv_used", lb=0)          # Power from PV that is actively used (kW)
        self.vars['load'] = self.model.addVars(self.hours, name="load", lb=0)                # Power consumed by the flexible load (kW)
        self.vars['import'] = self.model.addVars(self.hours, name="import", lb=0)            # Power imported from the grid (kW)
        self.vars['export'] = self.model.addVars(self.hours, name="export", lb=0)            # Power exported to the grid (kW)
        self.vars['pv_curtailed'] = self.model.addVars(self.hours, name="pv_curtailed", lb=0)  # Available PV power that is wasted (kW)

        # --- Conditional variables for the "soft constraint" model ---
        # These are only created if the data contains a reference load profile.
        if self.system_params.get('problem_type') == 'soft_constraint':
            # These two variables are used to linearize the absolute value |L - L_ref|.
            # Their sum will represent the total "discomfort" or deviation.
            self.vars['dev_pos'] = self.model.addVars(self.hours, name="dev_pos", lb=0)      # Amount the load is ABOVE the reference profile (kW)
            self.vars['dev_neg'] = self.model.addVars(self.hours, name="dev_neg", lb=0)      # Amount the load is BELOW the reference profile (kW)

        # --- Conditional variables for the battery model ---
        # These are only created if the data indicates a battery is present.
        if self.system_params.get('has_battery', False):
            # These variables model the battery's operation.
            self.vars['charge'] = self.model.addVars(self.hours, name="charge", lb=0)        # Power flowing INTO the battery (kW)
            self.vars['discharge'] = self.model.addVars(self.hours, name="discharge", lb=0)  # Power flowing OUT of the battery (kW)
            self.vars['soc'] = self.model.addVars(self.hours, name="soc", lb=0)              # State of Charge: Energy stored in the battery (kWh)

def _define_objective(self):
        """Builds the objective function based on the problem type detected in the data."""
        
        # --- DATA-DRIVEN LOGIC: Check if this is a "soft constraint" problem ---
        if self.system_params.get('problem_type') == 'soft_constraint':
            # This block implements the normalized multi-objective function from the image.
            print("...Building NORMALIZED objective function (cost vs. comfort).")
            
            # Retrieve the normalization factors pre-calculated by the DataProcessor.
            C_I_tot = self.system_params['C_I_tot'] # Benchmark cost to import the entire reference load (DKK)
            L_tot = self.system_params['L_tot']     # Total energy of the reference load (kWh)

            # --- Part 1: Calculate the actual energy cost (in DKK) ---
            prices = self.hourly_params['energy_price_dkk_kwh']
            import_tariff = self.system_params['import_tariff_dkk_kwh']
            export_tariff = self.system_params['export_tariff_dkk_kwh']
            energy_cost = gp.quicksum(
                (self.vars['import'][h] * (prices[h] + import_tariff)) - \
                (self.vars['export'][h] * (prices[h] - export_tariff))
                for h in self.hours
            )
            
            # --- Part 2: Calculate the total discomfort (in kWh) ---
            # This is the sum of deviations from the reference profile.
            # It's the linearized version of Σ|L - L_ref|.
            discomfort = gp.quicksum(
                self.vars['dev_pos'][h] + self.vars['dev_neg'][h] for h in self.hours
            )
            
            # --- Part 3: Combine into the final normalized objective ---
            # Each part is scaled by its benchmark, making them dimensionless and addable.
            # The optimizer will now minimize this combined "dissatisfaction score".
            normalized_objective = (1 / C_I_tot) * energy_cost + (1 / L_tot) * discomfort
            self.model.setObjective(normalized_objective, GRB.MINIMIZE)
            
        else: # This is the original 'hard_constraint' problem (like Question 1a)
            # This block builds the simple cost-only objective function.
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

def _define_constraints(self):
        # --- 1. Base constraints (ALWAYS apply to all scenarios) ---
        # The total PV used and curtailed must equal what's available from the sun.
        self.model.addConstrs((
            self.vars['pv_used'][h] + self.vars['pv_curtailed'][h] == self.hourly_params['available_pv_kw'][h]
            for h in self.hours), name="pv_limit"
        )
        # Enforce the physical/contractual limits on grid interaction.
        self.model.addConstrs((self.vars['import'][h] <= self.system_params['max_import_kw'] for h in self.hours), name="max_import")
        self.model.addConstrs((self.vars['export'][h] <= self.system_params['max_export_kw'] for h in self.hours), name="max_export")

        # --- 2. Load-specific constraints (mutually exclusive based on problem type) ---
        if self.system_params.get('problem_type') == 'soft_constraint':
            # For the soft constraint model, the load is flexible.
            # It's constrained by its maximum physical power limit.
            self.model.addConstrs((self.vars['load'][h] <= self.system_params['max_load_power_kw'] for h in self.hours), name="max_load_soft")
            
            # This crucial constraint linearizes the absolute value in the objective function.
            # It links the actual load to the deviation variables: load - reference = positive_dev - negative_dev.
            ref_profile = self.hourly_params['reference_load_profile_kw']
            self.model.addConstrs((
                self.vars['load'][h] - ref_profile[h] == self.vars['dev_pos'][h] - self.vars['dev_neg'][h]
                for h in self.hours), name="deviation_definition"
            )
        else: # This is the 'hard_constraint' problem (like Question 1a)
            # The load is also flexible, constrained by its maximum power.
            self.model.addConstrs((self.vars['load'][h] <= self.system_params['max_load_power_kw'] for h in self.hours), name="max_load_hard")
            
            # This is the key constraint for 1a: total daily consumption must meet a minimum.
            self.constraints['min_total_daily_energy'] = self.model.addConstr(
                gp.quicksum(self.vars['load'][h] for h in self.hours) >= self.system_params['min_daily_energy_kwh'], 
                name="min_daily_energy"
            )

        # --- 3. Energy Balance and Battery constraints (mutually exclusive based on data) ---
        if self.system_params.get('has_battery', False):
            # This block is executed only if battery data was detected.
            # Energy balance WITH battery: Sources must equal Sinks.
            self.constraints['energy_balance'] = self.model.addConstrs((
                self.vars['pv_used'][h] + self.vars['import'][h] + self.vars['discharge'][h] == \
                self.vars['load'][h] + self.vars['export'][h] + self.vars['charge'][h]
                for h in self.hours), name="energy_balance_with_battery"
            )
            # Add all battery-specific physical constraints.
            bp = self.system_params['battery_params']
            self.model.addConstrs((self.vars['charge'][h] <= bp['max_charge_kw'] for h in self.hours), name="max_charge")
            self.model.addConstrs((self.vars['discharge'][h] <= bp['max_discharge_kw'] for h in self.hours), name="max_discharge")
            self.model.addConstrs((self.vars['soc'][h] <= bp['capacity_kwh'] for h in self.hours), name="max_soc")
            
            # This loop defines the battery's state-of-charge dynamics over time.
            for h in self.hours:
                # Get the SOC from the previous hour, or the initial SOC for the first hour.
                prev_soc = bp['initial_soc_kwh'] if h == 0 else self.vars['soc'][h-1]
                # SOC_now = SOC_before + Energy_in (with efficiency loss) - Energy_out (with efficiency loss).
                self.model.addConstr(
                    self.vars['soc'][h] == prev_soc + (self.vars['charge'][h] * bp['charge_efficiency']) - (self.vars['discharge'][h] / bp['discharge_efficiency']),
                    name=f"soc_update_{h}"
                )
            # Enforce that the battery must end the day at a specific energy level.
            self.model.addConstr(self.vars['soc'][self.hours[-1]] == bp['final_soc_kwh'], name="final_soc")
        else:
            # If no battery is present, use the simpler energy balance equation.
            self.constraints['energy_balance'] = self.model.addConstrs((
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
        """
        Extracts the DUAL solution (shadow prices), adapting to the problem type.
        """
        duals = {}
        
        if 'min_total_daily_energy' in self.constraints:
            duals['min_energy_shadow_price_dkk_kwh'] = self.constraints['min_total_daily_energy'].Pi
            

        elif self.system_params.get('problem_type') == 'soft_constraint' and 'energy_balance' in self.constraints:
            # The raw .Pi value is normalized. We must "un-scale" it.
            C_I_tot = self.system_params.get('C_I_tot', 1)
            energy_balance_constrs = self.constraints['energy_balance']
            
            raw_duals = [energy_balance_constrs[h].Pi for h in self.hours]
            
            # Un-scale each hourly dual to convert it back to DKK/kWh
            unscaled_duals = [d * C_I_tot for d in raw_duals]
            duals['hourly_marginal_price_dkk_kwh'] = unscaled_duals
            
        return duals