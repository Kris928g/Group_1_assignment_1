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
from opt_model.opt_model_battery import OptModel_battery

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
                results_df, dual_values = model.solve()

                if results_df is not None:
                    summary = ResultSummary(
                        results_df=results_df, 
                        hourly_params=processor.hourly_params, 
                        system_params=processor.system_params,
                        dual_values=dual_values
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

    def run_investment_sizing(self, scenario_name: str, investment_cost_scalar: float = 1.0):
        """
        Runs the integrated investment model to find the optimal battery size.

        Args:
            scenario_name (str): The name of the data scenario to use (e.g., 'question_1c').
            investment_cost_scalar (float): A factor to scale the base investment cost.
                                            1.0 is the base cost, 2.0 is double the cost, etc.
        """
        print(f"\n{'='*20} Starting Investment Sizing for: {scenario_name} {'='*20}")
        print(f"Using investment cost scaling factor: {investment_cost_scalar}")
        
        original_cwd = Path.cwd()
        try:
            os.chdir(self.src_path)
            
            # Load and process the data for the scenario
            loader = DataLoader(input_path="../data", question_name=scenario_name)
            processor = DataProcessor(loader)
            
            # Define the base capital cost
            base_capital_cost_per_kwh = 1/6 # DKK/kWh/day
            scaled_capital_cost = base_capital_cost_per_kwh * investment_cost_scalar
            print(f"Effective capital cost for this run: {scaled_capital_cost} DKK/kWh/day")

            # --- Use the NEW investment model ---
            model = OptModel_battery(processor.hourly_params, processor.system_params)
            results_df, dual_values = model.solve(capital_cost_per_kwh=scaled_capital_cost)
            
            if results_df is not None:
                # --- Update the summary to print the optimal size ---
                # You'll need a small change in summary.py for this
                summary = ResultSummary(
                    results_df=results_df, 
                    hourly_params=processor.hourly_params, 
                    system_params=processor.system_params,
                    dual_values=dual_values
                )
                summary.print_summary()

                visualizer = DataVisualizer(processor, dual_values=dual_values)
                visualizer.plot_optimization_results(results_df, block=False)

                fig = plt.gcf()
                fig.canvas.manager.set_window_title(f"Results for {scaled_capital_cost} DKK/kWh/day")
            else:                
                    print("...No results to summarize or visualize as the optimization failed.")
        except Exception as e:
            print(f"\nAn ERROR occurred during the run: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Always change back to the original directory
            os.chdir(original_cwd)
