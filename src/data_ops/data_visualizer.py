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

    def plot_optimization_results(self, results_df: pd.DataFrame, block: bool = True):
        """
        Visualizes the full results from the optimization model.

        Args:
            results_df (pd.DataFrame): The DataFrame with the optimal schedule.
            block (bool): If True, the script will pause until the plot is closed.
                          If False, the script continues after showing the plot.
        """
-
        plt.figure(figsize=(16, 8))
        results_df['pv_self_consumption_kw'] = results_df[['pv_generation_kw', 'flexible_load_kw']].min(axis=1)
        plt.bar(results_df.index, results_df['pv_self_consumption_kw'], label='PV Self-Consumption', color='orange')
        plt.bar(results_df.index, results_df['grid_import_kw'], bottom=results_df['pv_self_consumption_kw'], label='Grid Import', color='skyblue')
        plt.plot(results_df.index, results_df['flexible_load_kw'], 'o-', color='black', label='Optimal Load Schedule', linewidth=2)
        plt.plot(results_df.index, results_df['grid_export_kw'], '--', color='green', label='Grid Export')
        plt.plot(results_df.index, results_df['pv_curtailment_kw'], ':', color='red', marker='x', markersize=5, label='PV Curtailment')
        
        plt.title(f'Optimal Energy Schedule', fontsize=16)
        plt.xlabel('Hour of Day', fontsize=12)

        plt.legend()
        plt.tight_layout()

        plt.show(block=block)