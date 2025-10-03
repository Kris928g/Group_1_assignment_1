
import pandas as pd

class ResultSummary:
    """
    Calculates and presents a summary of Key Performance Indicators (KPIs)
    from the optimization results.
    """
    

    def __init__(self, results_df: pd.DataFrame, hourly_params: pd.DataFrame, system_params: dict):
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
        # Store the direct data instead of the whole processor object
        self.hourly_params = hourly_params
        self.system_params = system_params
        
        self.kpis = {}
        self._calculate_kpis()

    def _calculate_kpis(self):
        """Private method to calculate all the important numbers."""
        
        # --- THIS CODE NOW USES self.hourly_params and self.system_params DIRECTLY ---
        # --- NO OTHER CHANGES ARE NEEDED IN THIS METHOD ---
        
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

        # ... (rest of the file is unchanged) ...
        pv_self_consumed = self.results_df[['pv_generation_kw', 'flexible_load_kw']].min(axis=1).sum()
        if self.kpis['total_load_consumption'] > 0:
            self.kpis['self_sufficiency_ratio'] = (pv_self_consumed / self.kpis['total_load_consumption']) * 100
        else: self.kpis['self_sufficiency_ratio'] = 0
        if self.kpis['total_pv_used'] > 0:
            self.kpis['self_consumption_ratio'] = (pv_self_consumed / self.kpis['total_pv_used']) * 100
        else: self.kpis['self_consumption_ratio'] = 0

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
        
        print("\n------------------------------------")