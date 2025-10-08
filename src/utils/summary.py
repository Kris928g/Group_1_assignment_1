
import pandas as pd

class ResultSummary:
    """
    Calculates and presents a summary of Key Performance Indicators (KPIs)
    from the optimization results.
    """
    

    def __init__(self, results_df: pd.DataFrame, hourly_params: pd.DataFrame, system_params: dict, dual_values: dict):
        """
        Initializes the summary generator with the results and prepared input data.

        Args:
            results_df (pd.DataFrame): The DataFrame with the optimal schedule.
            hourly_params (pd.DataFrame): The DataFrame with prepared hourly inputs.
            system_params (dict): The dictionary with prepared system-wide inputs.
        """
        if not isinstance(results_df, pd.DataFrame) or results_df.empty:
            raise ValueError("A non-empty results DataFrame is required.")
        
        self.results_df = results_df
        self.hourly_params = hourly_params
        self.system_params = system_params
        self.dual_values = dual_values
        
        self.kpis = {}
        self._calculate_kpis()

    def _calculate_kpis(self):
        """Private method to calculate all the important numbers."""
        
        # --- Energy Totals (kWh) ---
        self.kpis['total_pv_available'] = self.hourly_params['available_pv_kw'].sum()
        self.kpis['total_pv_used'] = self.results_df['pv_generation_kw'].sum()
        self.kpis['total_pv_curtailed'] = self.results_df['pv_curtailment_kw'].sum()
        self.kpis['total_load_consumption'] = self.results_df['flexible_load_kw'].sum()
        self.kpis['total_grid_import'] = self.results_df['grid_import_kw'].sum()
        self.kpis['total_grid_export'] = self.results_df['grid_export_kw'].sum()
        
        # --- Financial Totals (DKK) ---
        self.kpis['net_daily_cost'] = self.results_df['hourly_cost_dkk'].sum()
        
        prices = self.hourly_params['energy_price_dkk_kwh']
        tariffs = self.system_params
        self.kpis['cost_of_imports'] = (self.results_df['grid_import_kw'] * (prices + tariffs['import_tariff_dkk_kwh'])).sum()
        self.kpis['revenue_from_exports'] = (self.results_df['grid_export_kw'] * (prices - tariffs['export_tariff_dkk_kwh'])).sum()

        pv_self_consumed = self.results_df[['pv_generation_kw', 'flexible_load_kw']].min(axis=1).sum()
        if self.kpis['total_load_consumption'] > 0:
            self.kpis['self_sufficiency_ratio'] = (pv_self_consumed / self.kpis['total_load_consumption']) * 100
        else: self.kpis['self_sufficiency_ratio'] = 0
        if self.kpis['total_pv_used'] > 0:
            self.kpis['self_consumption_ratio'] = (pv_self_consumed / self.kpis['total_pv_used']) * 100
        else: self.kpis['self_consumption_ratio'] = 0

        if self.system_params.get('has_battery', False):
            # Calculate total energy flows for the battery
            total_charged = self.results_df['battery_charge_kw'].sum()
            total_discharged = self.results_df['battery_discharge_kw'].sum()
            
            self.kpis['total_battery_charge_kwh'] = total_charged
            self.kpis['total_battery_discharge_kwh'] = total_discharged
            
            # Calculate round-trip efficiency
            if total_charged > 0.001: # Avoid division by zero
                efficiency = (total_discharged / total_charged) * 100
                self.kpis['battery_round_trip_efficiency_percent'] = efficiency
            else:
                self.kpis['battery_round_trip_efficiency_percent'] = 0


    def print_summary(self):
        """Prints a formatted summary of the calculated KPIs to the console."""
        
        print("\n--- Optimization Result Summary ---")
        
        # --- Financial Summary ---
        print("\n[ Financials ]")
        net_cost = self.kpis['net_daily_cost']
        if net_cost >= 0:
            print(f"  Net Daily Cost: {net_cost:.2f} DKK")
        else:
            print(f"  Net Daily Profit: {-net_cost:.2f} DKK")
        print(f"  - Cost of Imports: {self.kpis['cost_of_imports']:.2f} DKK")
        print(f"  - Revenue from Exports: {self.kpis['revenue_from_exports']:.2f} DKK")

        # --- Energy Flow Summary ---
        print("\n[ Energy Flow (kWh) ]")
        print(f"  Total Load Consumption: {self.kpis['total_load_consumption']:.2f} kWh")
        print(f"  - Grid Import: {self.kpis['total_grid_import']:.2f} kWh")
        print(f"  - Grid Export: {self.kpis['total_grid_export']:.2f} kWh")

        # --- PV Performance Summary ---
        print("\n[ PV Performance ]")
        print(f"  Available PV Generation: {self.kpis['total_pv_available']:.2f} kWh")
        print(f"  - PV Used (Consumed + Exported): {self.kpis['total_pv_used']:.2f} kWh")
        print(f"  - PV Curtailed (Wasted): {self.kpis['total_pv_curtailed']:.2f} kWh")
        
        # --- Ratios ---
        print("\n[ Performance Ratios ]")
        print(f"  Self-Sufficiency Ratio: {self.kpis['self_sufficiency_ratio']:.1f}% (of load met by own PV)")
        print(f"  Self-Consumption Ratio: {self.kpis['self_consumption_ratio']:.1f}% (of used PV that supplied the load)")


        print("\n[ Economic Insights (Shadow Prices) ]")
        if 'min_energy_shadow_price_dkk_kwh' in self.dual_values:
            # This is for the "hard constraint" problem (1a)
            shadow_price = self.dual_values['min_energy_shadow_price_dkk_kwh']
            marginal_cost = shadow_price # .Pi for ">=" in a min problem is already positive
            
            if abs(marginal_cost) < 0.0001:
                print("  Marginal Cost of Energy: 0.000 DKK/kWh")
                print("    (The minimum energy constraint is non-binding)")
            else:
                print(f"  Marginal Cost of Energy: {marginal_cost:.3f} DKK/kWh")
                print("    (This is the cost to supply one extra kWh of flexible load)")
        
        elif 'hourly_marginal_price_dkk_kwh' in self.dual_values:
            # This is for the "soft constraint" problem (1b, 1c)
            hourly_prices = self.dual_values['hourly_marginal_price_dkk_kwh']
            avg_marginal_price = sum(hourly_prices) / len(hourly_prices)
            min_marginal_price = min(hourly_prices)
            max_marginal_price = max(hourly_prices)
            
            print(f"  Average Hourly Marginal Price: {avg_marginal_price:.3f} DKK/kWh")
            print(f"  - Min Hourly Price: {min_marginal_price:.3f} DKK/kWh")
            print(f"  - Max Hourly Price: {max_marginal_price:.3f} DKK/kWh")
            print("    (This is the internal economic value of energy for the consumer each hour)")
        
        else:
            print("  No applicable dual values were calculated for this scenario.")
        
        if 'total_battery_charge_kwh' in self.kpis:
            print("\n[ Battery Performance ]")
            print(f"  Total Energy Charged: {self.kpis['total_battery_charge_kwh']:.2f} kWh")
            print(f"  Total Energy Discharged: {self.kpis['total_battery_discharge_kwh']:.2f} kWh")
            print(f"  Round-trip Efficiency: {self.kpis['battery_round_trip_efficiency_percent']:.1f}%")

        if self.system_params.get('has_battery', False):
            if 'optimal_battery_size_kwh' in self.dual_values:
                capacity = self.dual_values['optimal_battery_size_kwh']
                print(f"  Optimal Battery Capacity: {capacity:.2f} kWh (Chosen by model)")

        print("\n------------------------------------")