from config import *
from utils.handler import *

def plot_histogram_sci(ecg_data_list):
    try:
        print("Plotting histograms for SCI group:")
        num_metrics = len(METRIC_NAME_MAP)
        cols = 3
        rows = (num_metrics + cols - 1) // cols

        # Collect SCI data per metric
        sci_data_dict = {key: [] for key in METRIC_NAME_MAP.keys()}
        for ecg in ecg_data_list:
            if ecg.get_sci_condition():
                metrics = ecg.get_all_metrics()
                for metric_key, metric_name in METRIC_NAME_MAP.items():
                    if metric_key == "LF/HF":
                        continue
                    values = metrics.get(metric_name)
                    if values is None:
                        continue
                    values_array = np.array(values, dtype=np.float64)
                    values_array = values_array[~np.isnan(values_array)]
                    if len(values_array) > 0:
                        sci_data_dict[metric_key].extend(values_array)

        plt.figure(figsize=(5 * cols, 4 * rows))
        plt.suptitle("Histograms of ECG Metrics - SCI Group", fontsize=16)
        plot_index = 1

        for metric_key, metric_name in METRIC_NAME_MAP.items():
            if metric_key == "LF/HF":
                continue
            data = sci_data_dict[metric_key]
            if not data:
                warning_handler(f"No SCI data for metric '{metric_key}'")
                continue
            plt.subplot(rows, cols, plot_index)
            plt.hist(data, bins=30, color='salmon', edgecolor='black')
            plt.title(metric_name)
            plt.ylabel("Frequency")
            plot_index += 1

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.show()

    except Exception as e:
        error_handler(f"Failed to plot SCI histogram: {e}")


def plot_histogram_nonsci(ecg_data_list):
    try:
        print("Plotting histograms for Non-SCI group:")
        num_metrics = len(METRIC_NAME_MAP)
        cols = 3
        rows = (num_metrics + cols - 1) // cols

        # Collect Non-SCI data per metric
        nonsci_data_dict = {key: [] for key in METRIC_NAME_MAP.keys()}
        for ecg in ecg_data_list:
            if not ecg.get_sci_condition():
                metrics = ecg.get_all_metrics()
                for metric_key, metric_name in METRIC_NAME_MAP.items():
                    if metric_key == "LF/HF":
                        continue
                    values = metrics.get(metric_name)
                    if values is None:
                        continue
                    values_array = np.array(values, dtype=np.float64)
                    values_array = values_array[~np.isnan(values_array)]
                    if len(values_array) > 0:
                        nonsci_data_dict[metric_key].extend(values_array)

        plt.figure(figsize=(5 * cols, 4 * rows))
        plt.suptitle("Histograms of ECG Metrics - Non-SCI Group", fontsize=16)
        plot_index = 1

        for metric_key, metric_name in METRIC_NAME_MAP.items():
            if metric_key == "LF/HF":
                continue
            data = nonsci_data_dict[metric_key]
            if not data:
                warning_handler(f"No Non-SCI data for metric '{metric_key}'")
                continue
            plt.subplot(rows, cols, plot_index)
            plt.hist(data, bins=30, color='skyblue', edgecolor='black')
            plt.title(metric_name)
            plt.ylabel("Frequency")
            plot_index += 1

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.show()

    except Exception as e:
        error_handler(f"Failed to plot Non-SCI histogram: {e}")