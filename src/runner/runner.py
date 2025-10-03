# src/runner/runner.py

import os
from pathlib import Path

# Import all the necessary components
from data_ops.data_loader import DataLoader
from data_ops.data_processor import DataProcessor
from data_ops.data_visualizer import DataVisualizer
from opt_model.opt_model import OptModel # Make sure this class name matches your file

class Runner:
    """
    Orchestrates the full workflow for a single optimization scenario.
    """
    def __init__(self, project_root_path: Path, question_name: str):
        self.project_root = project_root_path
        self.question_name = question_name
        
        # Define paths reliably from the absolute project root
        self.data_path = self.project_root / "data"
        self.src_path = self.project_root / "src"
        
        print(f"--- Runner initialized for Scenario: {self.question_name} ---")

    def run(self):
        """
        Executes the full pipeline: load -> process -> optimize -> visualize.
        """
        original_cwd = Path.cwd()
        try:
            # Change CWD to the reliable, absolute 'src' path
            os.chdir(self.src_path)

            print(f"\n[1/3] Loading and processing data for '{self.question_name}'...")
            loader = DataLoader(input_path="../data", question_name=self.question_name)
            
            # The runner then uses the loader to create the DataProcessor
            processor = DataProcessor(loader)
            print("...Data preparation complete.")

            print(f"\n[2/3] Building and solving the optimization model...")
            
            model = OptModel(processor.hourly_params, processor.system_params)
            results_df = model.solve()

            print(f"\n[3/3] Visualizing results...")
            if results_df is not None:
                visualizer = DataVisualizer(processor)
                # Add self-consumption column for the visualizer if needed
                results_df['pv_self_consumption_kw'] = results_df[['pv_generation_kw', 'flexible_load_kw']].min(axis=1)
                visualizer.plot_optimization_results(results_df)
            else:
                print("...No results to visualize as the optimization failed.")

        except Exception as e:
            print(f"\nAn ERROR occurred during the run: {e}")
            import traceback
            traceback.print_exc() # This gives more detail on errors
        finally:
            # Always change back to the original directory
            os.chdir(original_cwd)
            print(f"\n--- Scenario '{self.question_name}' finished. ---")