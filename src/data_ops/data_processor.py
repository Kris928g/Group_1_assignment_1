import json
import csv
import pandas as pd
from pathlib import Path
from data_ops.data_loader import DataLoader

class DataProcessor:
    """
    Processes raw data from the DataLoader into a structured format suitable for
    an optimization model.

    It creates two main attributes:
    1.  `hourly_params`: A DataFrame containing all parameters that vary by the hour.
    2.  `system_params`: A dictionary containing all system-wide, non-hourly parameters.
    """
    def __init__(self, data_loader: DataLoader):
        """
        Initializes the processor and immediately prepares the data.

        Args:
            data_loader (DataLoader): An instance of DataLoader with loaded raw data.
        """
        self.loader = data_loader
        self.hourly_params = None
        self.system_params = None

        # Run the preparation method upon initialization
        self.prepare_data_for_optimization()
        print("Data has been processed and is ready for the optimization model.")

    def prepare_data_for_optimization(self):
        """
        Orchestrates the data preparation process.
        """
        # First, process hourly data and create the DataFrame
        energy_prices = self.loader.bus_params[0]['energy_price_DKK_per_kWh']
        available_pv_kw = self._calculate_available_pv()

        self.hourly_params = pd.DataFrame({
            'energy_price_dkk_kwh': energy_prices,
            'available_pv_kw': available_pv_kw
        })
        self.hourly_params.index.name = 'hour'

        self.system_params = self._extract_system_parameters()
        
        # Add the reference profile to hourly_params if it exists
        if self.system_params.get('problem_type') == 'soft_constraint':
            self.hourly_params['reference_load_profile_kw'] = self.system_params['reference_load_profile_kw']
        else:
            self.hourly_params['reference_load_profile_kw'] = [0] * 24
        # Second, extract all single-value system parameters into a dictionary
        self.system_params = self._extract_system_parameters()

    def _calculate_available_pv(self) -> list[float]:
        """
        Calculates the actual hourly PV generation potential in kW.
        This is a key processing step: converting a ratio to an absolute value.
        """
        pv_max_power_kw = self.loader.appliance_params['DER'][0]['max_power_kW']
        pv_hourly_ratios = self.loader.der_production[0]['hourly_profile_ratio']
        
        # Calculate the actual available kW for each hour
        return [ratio * pv_max_power_kw for ratio in pv_hourly_ratios]

    def _extract_system_parameters(self) -> dict:
        """
        Extracts all non-hourly parameters into a clean dictionary.
        """
        load_prefs = self.loader.usage_preference[0]['load_preferences'][0]
        params = {
            'import_tariff_dkk_kwh': self.loader.bus_params[0]['import_tariff_DKK/kWh'],
            'export_tariff_dkk_kwh': self.loader.bus_params[0]['export_tariff_DKK/kWh'],
            'import_penalty_dkk_kwh': self.loader.bus_params[0]['penalty_excess_import_DKK/kWh'],
            'export_penalty_dkk_kwh': self.loader.bus_params[0]['penalty_excess_export_DKK/kWh'],
            'max_import_kw': self.loader.bus_params[0]['max_import_kW'],
            'max_export_kw': self.loader.bus_params[0]['max_export_kW'],
            'max_load_power_kw': self.loader.appliance_params['load'][0]['max_load_kWh_per_hour'],
            'min_daily_energy_kwh': self.loader.usage_preference[0]['load_preferences'][0]['min_total_energy_per_day_hour_equivalent']
        }
        if load_prefs.get('hourly_profile_ratio') is not None:
            # This is a "soft constraint" problem
            params['problem_type'] = 'soft_constraint'
            
            # First, calculate the reference profile in kW
            max_load = params['max_load_power_kw']
            ratios = load_prefs['hourly_profile_ratio']
            ref_profile_kw = [r * max_load for r in ratios]
            params['reference_load_profile_kw'] = ref_profile_kw
            
            L_tot = sum(ref_profile_kw)
            params['L_tot'] = L_tot
            
            # C_I^tot: Cost of inflexibly importing the entire reference load
            prices = self.hourly_params['energy_price_dkk_kwh']
            tariff = params['import_tariff_dkk_kwh']
            C_I_tot = sum(ref_profile_kw[h] * (prices[h] + tariff) for h in range(24))
            # Handle case where C_I_tot is zero to avoid division by zero
            params['C_I_tot'] = C_I_tot if C_I_tot > 0 else 1.0

        else:
            # This is a "hard constraint" problem (Question 1a)
            params['problem_type'] = 'hard_constraint'
            params['min_daily_energy_kwh'] = load_prefs.get('min_total_energy_per_day_hour_equivalent')

        # Check for the presence of a battery (Scenario 1c)
        if self.loader.usage_preference[0].get('storage_preferences'):
            print("...Battery data detected. Configuring for battery optimization.")
            params['has_battery'] = True
            storage_prefs = self.loader.usage_preference[0]['storage_preferences'][0]
            battery_specs = next((s for s in self.loader.appliance_params.get('storage', []) if s['storage_id'] == storage_prefs['storage_id']), None)
            
            if battery_specs:
                params['battery_params'] = {
                    'initial_soc_kwh': storage_prefs['initial_soc_ratio'] * battery_specs['storage_capacity_kWh'],
                    'final_soc_kwh': storage_prefs['final_soc_ratio'] * battery_specs['storage_capacity_kWh'],
                    'capacity_kwh': battery_specs['storage_capacity_kWh'],
                    'max_charge_kw': battery_specs['max_charging_power_ratio'],
                    'max_discharge_kw': battery_specs['max_discharging_power_ratio'],
                    'charge_efficiency': battery_specs['charging_efficiency'],
                    'discharge_efficiency': battery_specs['discharging_efficiency']
                }
        else:
            params['has_battery'] = False
            
        return params