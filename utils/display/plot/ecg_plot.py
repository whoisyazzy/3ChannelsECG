from config import *
from utils.handler import *

def plot_full_ECG(ecg_list):
    try:
        if not ecg_list:
            warning_handler("No ECG data provided to plot.")
            return

        total_leads = sum(len(ecg.get_lead_signals()) for ecg in ecg_list)
        if total_leads == 0:
            warning_handler("No lead signals found in provided ECG data.")
            return

        # Create subplots for all leads of all selected ECGs
        fig, axes = plt.subplots(total_leads, 1, figsize=(12, 3 * total_leads), sharex=True)
        if total_leads == 1:
            axes = [axes]

        ax_idx = 0
        for ecg in ecg_list:
            fs = ecg.ecg_info.get('sampling_rate', None)
            if fs is None:
                warning_handler(f"Sampling rate missing for {ecg.get_data_id()}. Skipping.")
                continue

            lead_signals = ecg.get_lead_signals()
            lead_names = ecg.get_lead_list()

            if not lead_signals:
                warning_handler(f"No lead signals found for {ecg.get_data_id()}. Skipping.")
                continue

            time = np.arange(len(lead_signals[0])) / fs

            for i, signal in enumerate(lead_signals):
                lead_name = lead_names[i] if i < len(lead_names) else f"Lead {i+1}"
                ax = axes[ax_idx]
                ax.plot(time, signal*1000, color='blue')
                ax.set_title(f"{lead_name} - {ecg.get_data_id()}")
                ax.set_ylim(-1000, 1000)
                ax.set_ylabel("Amplitude (mV)")
                ax.grid(True)
                ax_idx += 1

        axes[-1].set_xlabel("Time (s)")
        plt.tight_layout()
        plt.show()

    except Exception as e:
        error_handler(f"Failed to plot full ECG signals: {e}")

def plot_debug_ecg(ecg_data, lead_index=0, max_seconds=10):
    if not ecg_data:
        print("❌ No ECG data provided.")
        return

    signal = ecg_data["lead_signals"][lead_index]
    fs = ecg_data["fs"]
    data_id = ecg_data["data_id"]
    lead_name = ecg_data["lead_names"][lead_index]

    max_samples = int(max_seconds * fs)
    signal = signal[:max_samples]
    time_axis = np.arange(len(signal)) / fs

    plt.figure(figsize=(12, 4))
    plt.plot(time_axis, signal, color="blue")
    plt.title(f"ECG Debug Plot: {data_id} - {lead_name}")
    plt.xlabel("Time (seconds)")
    plt.ylabel("Amplitude (mV)")
    plt.grid(True)
    plt.tight_layout()
    plt.show()
