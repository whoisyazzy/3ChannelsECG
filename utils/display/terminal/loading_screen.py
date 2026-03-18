from matplotlib.pyplot import annotate
from config import *
from data import *

def format_time(seconds_total):
    """Format seconds into a string: 'X hour: Y minutes: Z.ZZ seconds'"""
    seconds_total = float(seconds_total)
    sec = seconds_total % (24 * 3600)
    hour = int(sec // 3600)
    sec %= 3600
    minu = int(sec // 60)
    sec %= 60

    if hour == 0 and minu == 0:
        return f"{sec:.2f} seconds"
    elif hour == 0:
        return f"{minu} minutes: {sec:.2f} seconds"
    else:
        return f"{hour} hour: {minu} minutes: {sec:.2f} seconds"

def show_loading_data(total_ids):
    print(f"Total ID's processing: {total_ids}")
    print(f"Processing ECG Data for data: N/A")

    print("Lead: Loading...")
    print("Sample size: Loading...")
    print("Sampling rate: Loading...\n")

    print(f"Gender: Loading...")
    print(f"Age: Loading...")
    print(f"SCI Condition: Loading...")
    print(f"NLI Condition: Loading...")
    print(f"AIS Severity: Loading...\n")

def show_current_data(ecg_data: ECGData, total_ids):
    lead_list = ecg_data.get_lead_list()
    lead_display = ", ".join(lead_list) if isinstance(lead_list, list) else str(lead_list)

    sample_size = ecg_data.get_sample_size()
    sampling_rate = ecg_data.get_sampling_rate()
    data_id = ecg_data.get_data_id()

    gender = ecg_data.get_gender()
    age = ecg_data.get_age()
    annotation = ecg_data.get_annotation()
    sci_condition = ecg_data.get_sci_condition()
    nli = ecg_data.get_nli_condition()
    ais = ecg_data.get_ais_severity()

    print(f"Total ID's processing: {total_ids}")
    print(f"Processing ECG Data for data: {data_id}")
    print(f"Lead: {lead_display}")
    print(f"Sample size: {sample_size} samples")
    print(f"Sampling rate: {sampling_rate} Hz\n")

    # Additional metadata display
    print(f"Gender: {gender}")
    print(f"Age: {age}")
    print(f"Annotation: {annotation}")
    print(f"SCI Condition: {'Yes' if sci_condition else 'No'}")
    print(f"NLI Condition: {nli if nli is not None else 'N/A'}")
    print(f"AIS Severity: {ais if ais is not None else 'N/A'}\n")

def loading_screen_data(current_index, total_ids):
    progress_percent = int(((current_index) / total_ids) * 100)
    bar_length = 50
    filled_length = int(bar_length * progress_percent // 100)
    bar = f"{BRIGHT_LIME}" + '█' * filled_length + f"{RESET}" + '-' * (bar_length - filled_length)
    print(f"📂 Processing Data:\n[{bar}] {BRIGHT_LIME}{progress_percent}%{RESET} ({current_index}/{total_ids})\n")

def loading_screen_windows(current_window, total_windows):
    progress_percent = int(((current_window + 1) / total_windows) * 100)
    bar_length = 50
    filled_length = int(bar_length * progress_percent // 100)
    bar = f"{BRIGHT_LIME}" + '█' * filled_length + f"{RESET}" + '-' * (bar_length - filled_length)
    print(f"\r🪟 Analyzing Intervals:\n[{bar}] {BRIGHT_LIME}{progress_percent}%{RESET} ({current_window + 1}/{total_windows})", end='')

def show_loading_data(total_ids):
    print(f"Total ID's processing: {total_ids}")
    print(f"Processing ECG Data for data: N/A")

    print("Lead: Loading...")
    print("Sample size: Loading...")
    print("Sampling rate: Loading...\n")

    print(f"Gender: Loading...")
    print(f"Age: Loading...")
    print(f"Annotation: Loading...")
    print(f"SCI Condition: Loading...")
    print(f"NLI Condition: Loading...")
    print(f"AIS Severity: Loading...\n")

def show_window_time_stats(window_time, total_window_time, estimated_window_time):
    print(f"\n\nWindow processed: {BRIGHT_CYAN}{format_time(window_time)}{RESET}")
    print(f"Total processed window time: {BRIGHT_CYAN}{format_time(total_window_time)}{RESET}")

    if estimated_window_time == 0:
        print(f"Estimated window processing time remaining: calculating...\n")
    else:
        print(f"Estimated window processing time remaining: {BRIGHT_CYAN}{format_time(estimated_window_time)}{RESET}\n")


def show_file_time_stats(file_elapsed, total_time, estimated_file_time, is_first_file=False):
    print(f"\nData processed: {BRIGHT_CYAN}{format_time(file_elapsed)}{RESET}")
    print(f"Total data processing time: {BRIGHT_CYAN}{format_time(total_time)}{RESET}")

    if is_first_file or estimated_file_time == 0:
        print(f"Estimated data processing time remaining: calculating...\n")
    else:
        print(f"Estimated data processing time remaining: {BRIGHT_CYAN}{format_time(estimated_file_time)}{RESET}\n")