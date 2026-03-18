from config import *
from utils.handler import *

def parse_time_midpoint(time_str):
    # Example input: '0.0s - 60.0s'
    parts = time_str.split('-')
    if len(parts) != 2:
        raise ValueError(f"Unexpected time format: {time_str}")
    
    start_str = parts[0].strip().rstrip('s')
    end_str = parts[1].strip().rstrip('s')
    
    start = float(start_str)
    end = float(end_str)
    return (start + end) / 2

def plot_metric_variation(ecg_data_list, metric_key):
    try:
        metric_name = METRIC_NAME_MAP.get(metric_key)
        if not metric_name:
            warning_handler(f"Unknown metric '{metric_key}' for variation plot.")
            return

        print(f"Plotting variation of metric '{metric_key}' for multiple ECGs...")

        # Prepare figure
        plt.figure(figsize=(10, 6))

        for ecg in ecg_data_list:
            metrics = ecg.get_all_metrics()
            values = metrics.get(metric_name)
            time_labels = metrics.get("Time (s)")

            if values is None or time_labels is None:
                warning_handler(f"Metric '{metric_key}' or Time labels missing for {ecg.get_data_id()}")
                continue

            # Convert time labels to nicer format: "0�5s"
            formatted_labels = [
                f"{int(float(start))}-{int(float(end))}s"
                for label in time_labels
                for start, end in [label.replace("s", "").replace("�", "-").split("-")]
            ]

            x = list(range(len(formatted_labels)))
            plt.plot(x, values, marker='o', label=ecg.get_data_id())

        plt.title(f"Variation of {metric_name}")
        plt.xlabel("Time Interval")
        plt.ylabel(metric_name)
        plt.xticks(ticks=x, labels=formatted_labels, rotation=30, ha='right')
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.show()

    except Exception as e:
        error_handler(f"Failed to plot metric variation: {e}")

def plot_metric_variability(ecg_data_list, metric_key):
    try:
        metric_name = METRIC_NAME_MAP.get(metric_key)
        if not metric_name:
            warning_handler(f"Unknown metric '{metric_key}' for variability plot.")
            return

        print(f"Plotting variability (gradient) of metric '{metric_key}' for multiple ECGs...")

        plt.figure(figsize=(10, 6))

        for ecg in ecg_data_list:
            variation = ecg.get_metric_variation(metric_name)
            time_labels = ecg.get_metric_values("Time (s)")

            if variation is None or time_labels is None:
                warning_handler(f"Variability or Time missing for {ecg.get_data_id()}")
                continue

            # Convert time strings to midpoints
            x_values = [parse_time_midpoint(t) for t in time_labels]
            if len(x_values) != len(variation):
                warning_handler(f"Length mismatch for {ecg.get_data_id()}")
                continue

            plt.plot(x_values, variation, marker='o', label=ecg.get_data_id())

        plt.title(f"Variability (Gradient) of {metric_name}")
        plt.xlabel("Time (s)")
        plt.ylabel(f"{metric_name} variability")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.show()

    except Exception as e:
        error_handler(f"Failed to plot metric variability: {e}")