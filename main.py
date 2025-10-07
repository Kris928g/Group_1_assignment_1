# main.py (at the project root)

import sys
from pathlib import Path
import matplotlib.pyplot as plt

# Establish the absolute project root and add 'src' to the path
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from runner.runner import Runner

if __name__ == "__main__":
    try:
   
        SCENARIOS_TO_RUN = [
            "question_1b",
            "question_1c"
              ]

        runner = Runner(project_root_path=PROJECT_ROOT, scenarios_to_run=SCENARIOS_TO_RUN)
        
        runner.run_all_scenarios()
        print("\nAll scenarios processed. Displaying plots.")
        print("Close any plot window to exit the program.")
        plt.show()

    except Exception as e:
        print(f"\nA critical error occurred in the main workflow: {e}")
        import traceback
        traceback.print_exc()