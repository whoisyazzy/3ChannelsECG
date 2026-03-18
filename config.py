"""
config.py

Description:
----------
- Contains all libraries definition
- Contains macros for signal processing, directories, enable/disable features

"""

# Libraries
import traceback
import time
import shutil
import numbers
import wfdb
import os
import warnings
import sys
import scipy.io
import joblib
import ast
import math
import multiprocessing
from multiprocessing import Process
from email.policy import default
from tkinter import Menu
from collections import Counter
from collections import defaultdict
from turtle import clear

# Plotting Libraries
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from tabulate import tabulate
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator
from matplotlib.lines import Line2D
from scipy.stats import gaussian_kde

# Machine Learning Libraries
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc, confusion_matrix, classification_report

# Statistics
from statistics import mean, median
import seaborn as sns
from scipy.stats import norm
from scipy.stats import iqr, skew, kurtosis

# Signal Processing Libraries
from mffpy import Reader
from neurokit2 import data
import neurokit2 as nk
from scipy.signal import iirnotch, filtfilt

# Directories
ABNORMAL_DATA_DIRECTORY = 'ECGDataAbnormal/'
NORMAL_DATA_DIRECTORY = 'ECGDataNormal/'
CONVERT_DATA_DIRECTORY = 'Convert/'
PHYSIONET_DATA = 'NormalECGData/'
SAVED_FILE = 'Save/'
PHYSIONET_WFDB_ROOT = 'WFDBRecords/'
PHYSIONET_SNOMED_CSV = os.path.join(
    PHYSIONET_WFDB_ROOT,
    'ConditionNames_SNOMED-CT.csv'
)
# Settings
ENABLE_STARTING_ID = False   # Enable to process a specific file when starting

# Macros for signal processing
DATA_START = 'n12_s0'       # Name of the file where processing begins
MAX_DATA_DURATION = 30     # (seconds) trimming size of the signal (600 seconds means signal will be trimmed to 10 minutes)
WINDOW_SIZE =  30       # (seconds) SIZE OF SIGNAL / WINDOW_SIZE = TOTAL SEGMENTS (600 seconds (10 minutes)/300 = 2 segments)
MAX_IDS = None            # set to None to process all available records
DEFAULT_SAMPING_FREQUENCY = 250
DATASET_MODE = "SCI"  # "SCI" or "PHYSIONET"
SCI_WFDB_DATA = 'converted_sci'
# Metric scaling
METRIC_YLIM_MAP = {
    'HR': (20, 120),              # bpm
    'RR_mean': (400, 1400),       # ms
    'SDNN': (0, 150),             # ms
    'RMSSD': (0, 200),            # ms
    'pNN50': (0, 80),             # %
    'LF/HF': (0, 10),             # ratio
    'QRS_duration': (60, 160),    # ms
    'QTc': (500, 300),            # ms
    'PR_interval': (100, 250),    # ms
}

# Macro colors for terminal
BRIGHT_RED          = "\033[91m"
BRIGHT_ORANGE       = "\033[38;5;214m"
BRIGHT_GOLD         = "\033[38;5;220m"
BRIGHT_YELLOW       = "\033[93m"
BRIGHT_LIME         = "\033[38;5;154m"
BRIGHT_GREEN        = "\033[92m"
BRIGHT_SPRING_GREEN = "\033[38;5;48m"
BRIGHT_CYAN         = "\033[96m"
BRIGHT_TURQUOISE    = "\033[38;5;80m"
BRIGHT_BLUE         = "\033[94m"
BRIGHT_INDIGO       = "\033[38;5;99m"
BRIGHT_VIOLET       = "\033[38;5;135m"
BRIGHT_MAGENTA      = "\033[95m"
BRIGHT_GRAY         = "\033[37m"
WHITE               = "\033[97m"
BOLD                = "\033[1m"
RESET               = "\033[0m"

METRIC_NAME_MAP = {
    'HR': 'Heart Rate (bpm)',
    'RR_mean': 'RR Interval (ms)',
    'SDNN': 'SDNN (ms)',
    'RMSSD': 'RMSSD (ms)',
    'pNN50': 'pNN50 (%)',
    'QRS_duration': 'QRS Duration (ms)',
    'QTc': 'QTc (ms)',
    'PR_interval': 'PR Interval (ms)',
}

METRIC_COLOR_LIST = [
    ("HR", BRIGHT_RED),
    ("RR_mean", BRIGHT_ORANGE),
    ("SDNN", BRIGHT_GOLD),
    ("RMSSD", BRIGHT_YELLOW),
    ("QRS_duration", BRIGHT_LIME),
    ("QTc", BRIGHT_GREEN),
    ("PR_interval", BRIGHT_CYAN),
    ("pNN50", BRIGHT_BLUE),
]
