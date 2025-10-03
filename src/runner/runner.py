# src/runner/runner.py

import os
from pathlib import Path

# Import all the necessary components from your project structure
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
        Initializes the Runner for a batch of experiments.

        Args:
            project_root_path (Path): The absolute path to the project root.
            scenarios_to_run (list): A list of scenario names to execute (e.g., 
                                     ["question_1a", "question_1a_FlatPrice"]).
        """
        self.project_root = project_root_path
        self.scenarios_to_run = scenarios_to_run
        
        # Define key paths reliably from the absolute project root
        self.data_path = self.project_root / "data"
        self.src_path = self.project_root / "src"
        self.results_path = self.project_root / "results"
        
        self._create_directories()
        print(f"--- Runner initialized for scenarios: {self.scenarios_to_run} ---")

    def _create_directories(self) -> None:
        """Create required output directories for each scenario."""
        for scenario_name in self.scenarios_to_run:
            (self.results_path / scenario_name).mkdir(parents=True, exist_ok=True)
        print("Output directories created.")

    def _run_single_scenario(self, question_name: str):
        """
        Executes the full pipeline for one specific scenario.
        This method contains the logic from your original 'run' method.
        """
        print(f"\n{'='*20} [ STARTING SCENARIO: {question_name} ] {'='*20}")
        try:
            # STEP 1: Load and Process Data
            print(f"\n[1/4] Loading and processing data...")
            loader = DataLoader(input_path="../data", question_name=question_name)
            processor = DataProcessor(loader)
            print("...Data preparation complete.")

            # STEP 2: Build and Solve the Optimization Model
            print(f"\n[2/4] Building and solving the optimization model...")
            model = OptModel(processor.hourly_params, processor.system_params)
            results_df = model.solve()

            # STEP 3 & 4: Summarize and Visualize the Results
            print(f"\n[3/4] Summarizing and visualizing results...")
            if results_df is not None:
                summary = ResultSummary(
                    results_df=results_df, 
                    hourly_params=processor.hourly_params, 
                    system_params=processor.system_params
                )
                summary.print_summary()
                
                visualizer = DataVisualizer(processor)
                visualizer.plot_optimization_results(results_df)

                # --- Good Practice: Save the results to the scenario's folder ---
                output_dir = self.results_path / question_name
                results_df.to_csv(output_dir / "optimal_schedule.csv", index=False)
                # To save the plot: visualizer.plot_optimization_results(results_df, save_path=output_dir / "schedule.png")
                print(f"...Results artifacts saved to: {output_dir.resolve()}")

            else:
                print("...No results to summarize or visualize as the optimization failed.")
        
        except Exception as e:
            print(f"\nAn ERROR occurred during the run for '{question_name}': {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n{'='*20} [ FINISHED SCENARIO: {question_name} ] {'='*20}")

    def run_all_simulations(self):
        """
        The main public method that executes the pipeline for all configured scenarios.
        """
        original_cwd = Path.cwd()
        try:
            # Change CWD to the reliable, absolute 'src' path so utils.py works
            os.chdir(self.src_path)
            
            # Loop through each configured scenario and run it
            for scenario in self.scenarios_to_run:
                self._run_single_scenario(scenario)
        
        finally:
            # Always change back to the original directory
            os.chdir(original_cwd)
            print("\n--- All scenarios have been executed. ---")