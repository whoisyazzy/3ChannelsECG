"""
normal.py

Description:
----------
- Calculate normal variations for SCI vs Non-SCI
- Perform Statistic Table
- Mean, Median
- Std
- CV
- Min/Max
- IQR, 5th, 95th
- Skewness
- Kurtosis
"""

"""
Attribute	        Meaning
=============================================================================================================
Mean	            The average value across all samples. Gives a central tendency of the data.
Median	            The middle value when data is sorted. Less affected by outliers than the mean.
Std	                Standard Deviation. Measures how spread out the values are around the mean.
CV	                Coefficient of Variation = Std / Mean. Normalizes variation; useful for comparing metrics.
Min	                The lowest observed value among all data samples.
Max	                The highest observed value among all data samples.
IQR	                Interquartile Range = 75th percentile − 25th percentile. Shows spread of the middle 50%.
5th	                The value below which 5% of the data falls (low-end cutoff). Used to identify lower extreme.
95th	            The value below which 95% of the data falls (high-end cutoff). Marks upper normal boundary.
Skewness	        Measures asymmetry of the data distribution.
    • 0  = symmetric
    • >0 = right-skewed
    • <0 = left-skewed
Kurtosis	        Measures how heavy or light the data tails are.
    • 0  = normal
    • >0 = heavy tails
    • <0 = light tails (less outliers)
"""

from config import *

METRIC_NAME_MAP = {
    'HR': 'Heart Rate (bpm)',
    'RR_mean': 'RR Interval (ms)',
    'SDNN': 'SDNN (ms)',
    'RMSSD': 'RMSSD (ms)',
    'pNN50': 'pNN50 (%)',
    'LF/HF': 'LF/HF ratio',
    'QRS_duration': 'QRS Duration (ms)',
    'QTc': 'QTc (ms)',
    'PR_interval': 'PR Interval (ms)',
}

def compute_metric_stats(values):
    values = [v for v in values if isinstance(v, (int, float)) and not np.isnan(v)]
    if not values:
        return None
    values = np.array(values)
    return {
        "Mean": np.mean(values),
        "Median": np.median(values),
        "Std": np.std(values),
        "CV": np.std(values) / np.mean(values) if np.mean(values) != 0 else np.nan,
        "Min": np.min(values),
        "Max": np.max(values),
        "IQR": np.percentile(values, 75) - np.percentile(values, 25),
        "5th": np.percentile(values, 5),
        "95th": np.percentile(values, 95),
        "Skewness": skew(values),
        "Kurtosis": kurtosis(values),
    }

def get_all_stats_for_group(ecg_group):
    if not ecg_group:
        return {}

    for ecg in ecg_group:
        metric_names = ecg.get_metric_names()
        if metric_names:
            break
    else:
        return {}

    metric_stats = {}
    for metric in metric_names:
        all_values = []
        for ecg in ecg_group:
            values = ecg.get_metric_values(metric)
            if values:
                all_values.extend([v for v in values if isinstance(v, (int, float)) and not np.isnan(v)])
        stats = compute_metric_stats(all_values)
        if stats:
            metric_stats[metric] = stats
    return metric_stats

def display_group_stats_table(stats_dict, group_label):
    if not stats_dict:
        print(f"No data to display for group '{group_label}'")
        return

    # Define the order of stats columns you want to show
    stat_columns = ["Mean", "Median", "Std", "CV", "Min", "Max", "IQR", "5th", "95th", "Skewness", "Kurtosis"]

    headers = ["Metric"] + stat_columns
    rows = []

    for metric, stats in stats_dict.items():
        row = [metric]
        for stat in stat_columns:
            val = stats.get(stat, None)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                row.append("N/A")
            else:
                row.append(f"{val:.3f}" if isinstance(val, (float, int)) else str(val))
        rows.append(row)

    title = f"📊 Normal ECG Metric Ranges ({group_label})"
    print("\n" + "="*len(title))
    print(title)
    print("="*len(title))
    print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))

def run_normal_analysis(ecg_data_list):
    non_sci_group = [ecg for ecg in ecg_data_list if not ecg.get_sci_condition()]
    sci_group = [ecg for ecg in ecg_data_list if ecg.get_sci_condition()]

    non_sci_stats = get_all_stats_for_group(non_sci_group)
    sci_stats = get_all_stats_for_group(sci_group)

    display_group_stats_table(non_sci_stats, "Non-SCI")
    display_group_stats_table(sci_stats, "SCI")