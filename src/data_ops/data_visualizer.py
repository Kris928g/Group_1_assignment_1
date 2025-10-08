import json
import csv
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from data_ops.data_processor import DataProcessor

class DataVisualizer:
    """
    Visualizes the prepared input data and the optimization results.
    """
    def __init__(self, data_processor: DataProcessor):
        """
        Initializes the visualizer with processed data.

        Args:
            data_processor (DataProcessor): A DataProcessor instance that has already
                                           prepared the data.
        """
        self.processor = data_processor
        sns.set_theme(style="whitegrid")

    def plot_input_data(self):
        """
        Creates a dual-axis plot of the key hourly inputs for the optimization model:
        energy price and available PV generation.
        """
        fig, ax1 = plt.subplots(figsize=(12, 6))

        # Plot Energy Price on the first y-axis
        color = 'tab:blue'
        ax1.set_xlabel('Hour of Day')
        ax1.set_ylabel('Energy Price (DKK/kWh)', color=color)
        ax1.plot(self.processor.hourly_params.index, self.processor.hourly_params['energy_price_dkk_kwh'], color=color, marker='o', label='Energy Price')
        ax1.tick_params(axis='y', labelcolor=color)

        # Create a second y-axis for PV generation
        ax2 = ax1.twinx()
        color = 'tab:green'
        ax2.set_ylabel('Available PV Generation (kW)', color=color)
        ax2.bar(self.processor.hourly_params.index, self.processor.hourly_params['available_pv_kw'], color=color, alpha=0.6, label='Available PV')
        ax2.tick_params(axis='y', labelcolor=color)

        plt.title('Optimization Input Data')
        fig.tight_layout()
        plt.show()

# In src/data_ops/data_visualizer.py

    def plot_optimization_results(self, results_df: pd.DataFrame, block: bool = True):
        """
        Visualizes the full energy balance using side-by-side stacked bars
        for sources and sinks, keeping all bars above the zero line.

        Args:
            results_df (pd.DataFrame): The DataFrame with the optimal schedule.
            block (bool): Controls whether the plot pauses script execution.
        """
        fig, ax1 = plt.subplots(figsize=(18, 9))
        hours = results_df.index
        bar_width = 0.4 # Width for each of the two bars

        # --- Left Y-Axis (ax1): Power Flows (kW) ---
        ax1.set_xlabel('Hour of Day', fontsize=12)
        ax1.set_ylabel('Power (kW)', fontsize=12)

        # --- Bar Group 1 (Left Side): SOURCES ---
        # 1. PV Generation is the base source
        ax1.bar(hours - bar_width/2, results_df['pv_generation_kw'], width=bar_width, label='PV Generation', color='gold')
        
        # 2. Battery Discharge is stacked on top of PV
        if 'battery_discharge_kw' in results_df.columns:
            ax1.bar(hours - bar_width/2, results_df['battery_discharge_kw'], bottom=results_df['pv_generation_kw'], width=bar_width, label='Battery Discharge', color='lightcoral')

        # 3. Grid Import is stacked on top of everything
        bottom_for_import = results_df['pv_generation_kw'].copy()
        if 'battery_discharge_kw' in results_df.columns:
            bottom_for_import += results_df['battery_discharge_kw']
        ax1.bar(hours - bar_width/2, results_df['grid_import_kw'], bottom=bottom_for_import, width=bar_width, label='Grid Import', color='deepskyblue')
        
        # --- Bar Group 2 (Right Side): SINKS ---
        # 1. Load Served is the base sink
        ax1.bar(hours + bar_width/2, results_df['flexible_load_kw'], width=bar_width, label='Load Served', color='dimgray')
        
        # 2. Battery Charging is stacked on top of the load
        if 'battery_charge_kw' in results_df.columns:
            ax1.bar(hours + bar_width/2, results_df['battery_charge_kw'], bottom=results_df['flexible_load_kw'], width=bar_width, label='Battery Charge', color='mediumpurple')

        # 3. Grid Export is stacked on top of all sinks
        bottom_for_export = results_df['flexible_load_kw'].copy()
        if 'battery_charge_kw' in results_df.columns:
            bottom_for_export += results_df['battery_charge_kw']
        ax1.bar(hours + bar_width/2, results_df['grid_export_kw'], bottom=bottom_for_export, width=bar_width, label='Grid Export', color='mediumseagreen')

        # --- Right Y-Axis (ax2): Battery State of Charge (kWh) ---
        if 'battery_soc_kwh' in results_df.columns:
            ax2 = ax1.twinx()
            color = 'tab:blue'
            ax2.set_ylabel('Battery State of Charge (Ratio)', color=color, fontsize=12)

            battery_capacity = 0
            if 'battery_params' in self.processor.system_params:
                battery_capacity = self.processor.system_params['battery_params'].get('capacity_kwh', 0)
            elif 'optimal_battery_size_kwh' in results_df: # Assuming we pass it back via the df for plotting
                 battery_capacity = results_df['optimal_battery_size_kwh'].iloc[0]

            if battery_capacity > 0:
                soc_ratio = results_df['battery_soc_kwh'] / battery_capacity
            else:
                soc_ratio = results_df['battery_soc_kwh'] * 0 # Set to zero if no capacity
            ax2.plot(hours, soc_ratio, color=color, marker='.', linestyle=':', linewidth=2.5, label='Battery SOC')
            ax2.tick_params(axis='y', labelcolor=color)
            ax2.set_ylim(0, 1.1)

        # --- Final Touches ---
        fig.suptitle('Optimal Energy Schedule & Battery Performance', fontsize=16)
        ax1.grid(True, which='both', linestyle='--', linewidth=0.5)
        ax1.axhline(0, color='black', linewidth=0.8)
        ax1.set_xticks(hours)
        
        # Combine legends from both axes
        lines, labels = ax1.get_legend_handles_labels()
        if 'ax2' in locals():
            lines2, labels2 = ax2.get_legend_handles_labels()
            # Manually order the legend for better grouping
            # Sources first, then Sinks, then SOC
            order = [0, 1, 2, 3, 4, 5] # Adjust if you have more/fewer items
            ax1.legend([lines[i] for i in order] + lines2, [labels[i] for i in order] + labels2, loc='upper left', fontsize=10, ncol=2)
        else:
            ax1.legend(loc='upper left', fontsize=10, ncol=2)

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show(block=block)