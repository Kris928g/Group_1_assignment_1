# -----------------------------
# Load Data
# -----------------------------
import json
import csv
import pandas as pd
from pathlib import Path

from pathlib import Path
from dataclasses import dataclass
from logging import Logger
import pandas as pd
import xarray as xr
import numpy as np
import yaml
from utils.utils import load_dataset


class DataLoader:
    """
    Loads energy system input data for a given configuration/question from structured CSV and json files
    and an auxiliary configuration metadata file.
    
    Example usage:
    open interactive window in VSCode,
    >>> cd ../../
    run the script data_loader.py in the interactive window,
    >>> data = DataLoader(input_path='..')
    """
    question: str
    input_path: Path

    def __init__(self, input_path: str, question_name: str):

        self.input_path = Path(input_path)
        self.question = question_name
        self.full_dataset = None
        
        print(f"Loading dataset for question: '{self.question}'...")
        self._load_dataset(self.question)

        try:
            #  load each file and assign it to a named attribute
            self.appliance_params = self._load_data_file(self.question, "appliance_params.json")
            self.bus_params = self._load_data_file(self.question, "bus_params.json")
            self.consumer_params = self._load_data_file(self.question, "consumer_params.json")
            self.der_production = self._load_data_file(self.question, "DER_production.json")
            self.usage_preference = self._load_data_file(self.question, "usage_preference.json")
            
            print("Successfully loaded all data files.")

        except (FileNotFoundError, ValueError) as e:
            # If any file fails to load, we stop the process by re-raising the exception.
            print(f"Error loading data for question '{self.question}'.")
            raise e
        pass

    def _load_dataset(self, question_name: str):

        self.full_dataset = load_dataset(self.question)
        
        if not self.full_dataset:
            raise FileNotFoundError(f"No data was loaded for question '{self.question}'. "
                                    f"Check that the directory '../data/{self.question}' exists and is not empty.")
        pass


    def _load_data_file(self, question_name: str, file_name: str):
        file_key = Path(file_name).stem
        
        try:
            # Look up the data in the already-loaded dictionary
            return self.full_dataset[file_key]
        except KeyError:
            # This error means the file was missing when _load_dataset ran
            raise KeyError(f"Data key '{file_key}' not found in the loaded dataset. "
                           f"Ensure the file '{file_name}' exists in the directory.")
        pass

    def load_aux_data(self, question_name: str, filename: str):
        """
        Placeholder Helper function to Load auxiliary metadata for the scenario/question from a YAML/json file or other formats
        
        Example application: 
        define and call a load_aux_data() function from utils.py to load a specific auxiliary file in the input_path directory
        Save the content as s class attributes, in a dictionary, pd datframe or other: self.aux_data
        Attach key values as class attributes (flattened).
        """
        pass