# main.py (at the project root)

import sys
from pathlib import Path

# --- The Key Fix: Establish the Absolute Project Root ---
# This line gets the directory where main.py is located. This is our reliable
# project root, no matter where the script is executed from.
PROJECT_ROOT = Path(__file__).resolve().parent

# Add the 'src' directory to Python's path so we can import from it
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

# Now we can import the Runner class
from runner.runner import Runner

if __name__ == "__main__":
    try:
        # Define which scenario to run
        QUESTION_TO_RUN = "question_1a"

        # 1. Instantiate the runner for the specific scenario.
        #    Pass the absolute project_root path to it.
        scenario = Runner(project_root_path=PROJECT_ROOT, question_name=QUESTION_TO_RUN)
        
        # 2. Execute the entire workflow for that scenario.
        scenario.run()

    except Exception as e:
        print(f"\nA critical error occurred in the main workflow: {e}")