from config import *
from utils.handler import *

def plot_boxplot(ecg_data_list, metric_key, sci_only=None):
    try:
        if metric_key not in METRIC_NAME_MAP:
            warning_handler(f"Invalid metric '{metric_key}' for boxplot.")
            return

        metric_name = METRIC_NAME_MAP[metric_key]
        data_for_box = []
        labels = []

        for ecg in ecg_data_list:
            # If filtering SCI/non-SCI
            if sci_only is not None:
                if sci_only and not ecg.get_sci_condition():
                    continue
                if not sci_only and ecg.get_sci_condition():
                    continue

            values = ecg.get_metric_values(metric_name)
            if values:
                clean = [v for v in values if v is not None and not np.isnan(v)]
                if clean:
                    data_for_box.append(clean)
                    labels.append(ecg.get_data_id())

        if not data_for_box:
            warning_handler(f"No data found for metric '{metric_key}' with current SCI filter.")
            return

        plt.figure(figsize=(max(8, len(labels) * 1.5), 6))
        plt.boxplot(data_for_box, labels=labels, patch_artist=True)

        sci_label = " (SCI Only)" if sci_only else " (Non-SCI Only)" if sci_only is False else ""
        plt.title(f"Boxplot of {metric_name}{sci_label}")
        plt.xlabel("Data ID")
        plt.ylim(*METRIC_YLIM_MAP[metric_key])
        plt.ylabel(metric_name)
        plt.xticks(rotation=45, ha='right')
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        plt.close('all')

    except Exception as e:
        error_handler(f"Failed to plot boxplot: {e}")

def plot_boxplot_SCI(ecg_data_list, metric_key):
    import matplotlib.pyplot as plt
    import numpy as np

    try:
        if metric_key not in METRIC_NAME_MAP:
            warning_handler(f"Invalid metric '{metric_key}' for combined boxplot.")
            return

        metric_name = METRIC_NAME_MAP[metric_key]

        # Separate data for SCI and Non-SCI
        sci_data = []
        sci_labels = []
        nonsci_data = []
        nonsci_labels = []

        for ecg in ecg_data_list:
            values = ecg.get_metric_values(metric_name)
            if not values:
                continue
            clean_values = [v for v in values if v is not None and not np.isnan(v)]
            if not clean_values:
                continue

            if ecg.get_sci_condition():
                sci_data.append(clean_values)
                sci_labels.append(ecg.get_data_id())
            else:
                nonsci_data.append(clean_values)
                nonsci_labels.append(ecg.get_data_id())

        if not sci_data and not nonsci_data:
            warning_handler(f"No data found for metric '{metric_key}' in both SCI and Non-SCI groups.")
            return

        # Create figure with 2 subplots stacked vertically
        plt.figure(figsize=(max(10, max(len(sci_labels), len(nonsci_labels)) * 1.2), 10))

        # SCI plot
        ax1 = plt.subplot(2, 1, 1)
        if sci_data:
            ax1.boxplot(sci_data, labels=sci_labels, patch_artist=True)
            ax1.set_title(f"{metric_name} (SCI Patients)")
            ax1.set_ylabel(metric_name)
            ax1.set_ylim(*METRIC_YLIM_MAP[metric_key])
            ax1.set_xticklabels(sci_labels, rotation=45, ha='right')
            ax1.grid(True)
        else:
            ax1.text(0.5, 0.5, "No SCI data available", ha='center', va='center')
            ax1.axis('off')

        # Non-SCI plot
        ax2 = plt.subplot(2, 1, 2)
        if nonsci_data:
            ax2.boxplot(nonsci_data, labels=nonsci_labels, patch_artist=True)
            ax2.set_title(f"{metric_name} (Non-SCI Patients)")
            ax2.set_xlabel("Data ID")
            ax2.set_ylabel(metric_name)
            ax2.set_ylim(*METRIC_YLIM_MAP[metric_key])
            ax2.set_xticklabels(nonsci_labels, rotation=45, ha='right')
            ax2.grid(True)
        else:
            ax2.text(0.5, 0.5, "No Non-SCI data available", ha='center', va='center')
            ax2.axis('off')

        plt.tight_layout()
        plt.show()
        plt.close('all')

    except Exception as e:
        error_handler(f"Failed to plot combined boxplot: {e}")
