# main.py (at the project root)

import sys
from pathlib import Path

# Establish the absolute project root and add 'src' to the path
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from runner.runner import Runner

if __name__ == "__main__":
    try:
   
        SCENARIOS_TO_RUN = [
            "question_1a",
            "question_1a_FlatPrice",
            "question_1a_increased_tariff"

        ]

        # 1. Instantiate the runner, passing the project root and the list of scenarios.
        experiment_runner = Runner(project_root_path=PROJECT_ROOT, scenarios_to_run=SCENARIOS_TO_RUN)
        
        # 2. Execute all configured simulations in sequence.
        experiment_runner.run_all_simulations()

    except Exception as e:
        print(f"\nA critical error occurred in the main workflow: {e}")
        import traceback
        traceback.print_exc()