"""
Placeholder for main function to execute the model runner. This function creates a single/multiple instance of the Runner class, prepares input data,
and runs a single/multiple simulation.

Suggested structure:
- Import necessary modules and functions.
- Define a main function to encapsulate the workflow (e.g. Create an instance of your the Runner class, Run a single simulation or multiple simulations, Save results and generate plots if necessary.)
- Prepare input data for a single simulation or multiple simulations.
- Execute main function when the script is run directly.
"""
# main.py

# src/main.py

import os
from pathlib import Path

# --- Since main.py is inside 'src', all imports are now direct ---
from data_ops.data_loader import DataLoader
from data_ops.data_processor import DataProcessor
from data_ops.data_visualizer import DataVisualizer

def main():
    """
    Main function to run the entire data processing and optimization workflow.
    """
    print("--- Starting the Demand-Side Flexibility Analysis ---")

    # --- The Solution: Set the Current Working Directory ---
    # We get the directory where this script (main.py) is located.
    # This will be the absolute path to your 'src' folder.
    src_directory = Path(__file__).parent
    
    # We change the current working directory to 'src'.
    # Now, when utils.py runs, its relative path '../data' will correctly
    # point from 'src' up to the project root and then into 'data'.
    os.chdir(src_directory)
    print(f"Working directory changed to: {Path.cwd()}")

    # --- Configuration ---
    # This path is now relative to the 'src' directory.
    DATA_PATH = "../data" 
    QUESTION_NAME = "question_1a"

    try:
        # --- STEP 1: LOAD RAW DATA ---
        print(f"\n[1/4] Loading raw data for scenario: '{QUESTION_NAME}'...")
        loader = DataLoader(input_path=DATA_PATH, question_name=QUESTION_NAME)
        print("...Data loading complete.")

        # --- STEP 2: PROCESS DATA ---
        print("\n[2/4] Processing data for the optimization model...")
        processor = DataProcessor(loader)
        print("...Data processing complete.")

        # --- STEP 3: VISUALIZE INPUTS ---
        print("\n[3/4] Visualizing processed input data...")
        visualizer = DataVisualizer(processor)
        visualizer.plot_input_data()
        print("...Input data plot displayed.")

        # --- STEP 4: SOLVE THE OPTIMIZATION PROBLEM (Placeholder) ---
        print("\n[4/4] Solving the optimization problem (Placeholder)...")
        # (Your future optimization code from opt_model.py goes here)

    except FileNotFoundError as e:
        print(f"\nERROR: A data file was not found. Please check your paths.")
        print(f"Details: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()