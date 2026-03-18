from config import *

def save_ecg_metrics(ecg_data_list, filename="ecg_metrics.csv"):
    records = []

    for ecg in ecg_data_list:
        metrics = ecg.get_all_metrics()
        num_intervals = len(metrics["Time (s)"])  # assume all keys have same length

        for i in range(num_intervals):
            record = {
                "Data ID": ecg.get_data_id(),
                "Interval": i + 1,
                "Time (s)": metrics["Time (s)"][i],
                "Heart Rate (bpm)": metrics["Heart Rate (bpm)"][i],
                "RR Interval (ms)": metrics["RR Interval (ms)"][i],
                "PR Interval (ms)": metrics["PR Interval (ms)"][i],
                "SDNN (ms)": metrics["SDNN (ms)"][i],
                "RMSSD (ms)": metrics["RMSSD (ms)"][i],
                "pNN50 (%)": metrics["pNN50 (%)"][i],
                "QRS Duration (ms)": metrics["QRS Duration (ms)"][i],
                "QTc (ms)": metrics["QTc (ms)"][i],
            }
            records.append(record)

    df = pd.DataFrame(records)
    df.to_csv(filename, index=False)
    print(f"✅ Saved ECG metrics to: {filename}")
