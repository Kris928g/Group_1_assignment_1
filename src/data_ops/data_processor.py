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
        params = {
            'import_tariff_dkk_kwh': self.loader.bus_params[0]['import_tariff_DKK/kWh'],
            'export_tariff_dkk_kwh': self.loader.bus_params[0]['export_tariff_DKK/kWh'],
            'max_import_kw': self.loader.bus_params[0]['max_import_kW'],
            'max_export_kw': self.loader.bus_params[0]['max_export_kW'],
            'max_load_power_kw': self.loader.appliance_params['load'][0]['max_load_kWh_per_hour'],
            'min_daily_energy_kwh': self.loader.usage_preference[0]['load_preferences'][0]['min_total_energy_per_day_hour_equivalent']
        }
        return params