# src/runner/runner.py

import os
from pathlib import Path
from matplotlib import pyplot as plt
# Import all the necessary components
from data_ops.data_loader import DataLoader
from data_ops.data_processor import DataProcessor
from data_ops.data_visualizer import DataVisualizer
from opt_model.opt_model import OptModel 
from utils.summary import ResultSummary

class Runner:
    """
    Orchestrates the full workflow for a list of specified optimization scenarios.
    """
    def __init__(self, project_root_path: Path, scenarios_to_run: list):
        """
        Initializes the Runner for a list of scenarios.

        Args:
            project_root_path (Path): The absolute path to the project root.
            scenarios_to_run (list): A list of scenario names to execute.
        """
        self.project_root = project_root_path
        self.scenarios = scenarios_to_run
        
        # Define paths reliably from the absolute project root
        self.data_path = self.project_root / "data"
        self.src_path = self.project_root / "src"
        
        print(f"--- Runner initialized for {len(self.scenarios)} scenarios: {self.scenarios} ---")

    def run_all_scenarios(self):
        """
        Executes the full pipeline for every scenario in the list.
        """
        original_cwd = Path.cwd()
        try:
            # Change CWD to the reliable 'src' path for utils.py to work
            os.chdir(self.src_path)

            # Loop through each configured scenario
            for scenario_name in self.scenarios:
                print(f"\n{'='*20} Starting Scenario: {scenario_name} {'='*20}")
                
                loader = DataLoader(input_path="../data", question_name=scenario_name)
                processor = DataProcessor(loader)

                model = OptModel(processor.hourly_params, processor.system_params)
                results_df = model.solve()

                if results_df is not None:
                    summary = ResultSummary(
                        results_df=results_df, 
                        hourly_params=processor.hourly_params, 
                        system_params=processor.system_params
                    )
                    summary.print_summary()
                    
                    visualizer = DataVisualizer(processor)
                    visualizer.plot_optimization_results(results_df, block=False)
                    
                    # Give each plot window a unique title
                    fig = plt.gcf()
                    fig.canvas.manager.set_window_title(f"Results for {scenario_name}")

                else:
                    print("...No results to summarize or visualize as the optimization failed.")
                
                print(f"{'='*20} Finished Scenario: {scenario_name} {'='*20}")

        except Exception as e:
            print(f"\nAn ERROR occurred during the run: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Always change back to the original directory
            os.chdir(original_cwd)