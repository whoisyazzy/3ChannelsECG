import os
import csv
import time
import argparse
from config import WINDOW_SIZE
from utils.preprocessing.convert import convert_csv_to_dat
from utils.processing.init_processing import init_processing, process_window_segment
import utils.workspace.loader as loader
import joblib
import numpy as np
import shutil
import pandas as pd

FEATURE_MAP = {
    # -------------------------
    # Heart rate & rhythm
    # -------------------------
    "HR_mean":       "Heart Rate (bpm)",
    "HR_std":        "Heart Rate Std (bpm)",

    "RR_mean":       "RR Interval (ms)",
    "RR_std":        "RR Std (ms)",
    "RR_min":        "RR Min (ms)",
    "RR_max":        "RR Max (ms)",
    "SDSD":          "SDSD (ms)",

    # -------------------------
    # HRV (time-domain)
    # -------------------------
    "SDNN_mean":     "SDNN (ms)",
    "RMSSD_mean":    "RMSSD (ms)",
    "pNN50_mean":    "pNN50 (%)",

    # -------------------------
    # Conduction (AV)
    # -------------------------
    "PR_mean":       "PR Interval (ms)",
    "PR_std":        "PR Std (ms)",
    "PR_min":        "PR Min (ms)",
    "PR_max":        "PR Max (ms)",

    # -------------------------
    # Ventricular depolarization
    # -------------------------
    "QRS_mean":      "QRS Duration (ms)",
    "QRS_std":       "QRS Std (ms)",
    "QRS_min":       "QRS Min (ms)",
    "QRS_max":       "QRS Max (ms)",

    # -------------------------
    # Repolarization
    # -------------------------
    "QTc_mean":      "QTc (ms)",
    "QTc_std":       "QTc Std (ms)",

    # -------------------------
    # T-wave morphology
    # -------------------------
    "T_amp":         "T Wave Amplitude (mV)",
    "T_amp_std":     "T Wave Std (mV)",
    "T_min":         "T Wave Min (mV)",
    "T_max":         "T Wave Max (mV)",

    # -------------------------
    # ST segment
    # -------------------------
    "ST_mean":       "ST Level Mean (mV)",
    "ST_std":        "ST Level Std (mV)",
}

def compute_lfhf_for_cache(data_ids, ecg_dir):
    from utils.processing.compute_metrics import compute_global_lf_hf

    lfhf_values = {}

    for data_id in data_ids:
        ecg_path = os.path.join(ecg_dir, f"{data_id}.csv")

        if not os.path.exists(ecg_path):
            raise FileNotFoundError(f"Missing ECG CSV for LFHF: {ecg_path}")

        df = pd.read_csv(ecg_path)

        if "time (s)" not in df.columns or "ecg (V)" not in df.columns:
            raise ValueError(f"Invalid ECG file format: {ecg_path}")

        times = df["time (s)"].values
        delta = times[1] - times[0]
        fs = 1.0 / delta

        value = compute_global_lf_hf(
            df["ecg (V)"].values,
            fs,
            os.path.basename(ecg_path)
        )

        lfhf_values[data_id] = float(value)

    return lfhf_values

def predict_ais_from_cache(
    metrics_csv_path,
    predictions_csv_path,
    nli,
    gender,
    age,
    ecg_dir,
    ais_model_dir="ais_logreg_model",
    output_filename="ais_prediction.csv"
):
    print("\n Running AIS severity prediction...")

    cache_dir = "cache"
    os.makedirs(cache_dir, exist_ok=True)
    output_path = os.path.join(cache_dir, output_filename)
    def encode_gender_local(g):
        g = str(g).strip().upper()
        if g == "M":
            return 1
        if g == "F":
            return 0
        return np.nan
    # -----------------------------
    # Above T6 check
    # -----------------------------
    def is_above_t6_local(nli):
        nli = str(nli).strip().upper()
        if nli.startswith("C"):
            return 1
        if nli.startswith("T"):
            try:
                level = int(nli[1:])
            except ValueError:
                return np.nan
            return 1 if level <= 6 else 0
        return 0

    if is_above_t6_local(nli) != 1:
        print("⚠ Patient Not supported → AIS model not applied.")
        return None

    # -----------------------------
    # Load AIS model
    # -----------------------------
    model = joblib.load(os.path.join(ais_model_dir, "ais_logreg.joblib"))

    with open(os.path.join(ais_model_dir, "ais_threshold.txt")) as f:
        threshold = float(f.readline().strip())

    with open(os.path.join(ais_model_dir, "features.txt")) as f:
        feature_cols = [line.strip() for line in f if line.strip()]

    # -----------------------------
    # Load SCI predictions
    # -----------------------------
    preds = pd.read_csv(predictions_csv_path)

    # Condition labels used during AIS training
    condition_labels = [
        "Sinus Bradycardia",
        "Sinus Tachycardia",
        "Sinus Irregularity",
        "Supraventricular Tachycardia",
        "1 degree atrioventricular block",
        "ST-T Change",
        "T wave Change",
    ]

    # Convert Predicted Labels string → binary 0/1
    for label in condition_labels:
        preds[label] = preds["Predicted Labels"].fillna("").apply(
            lambda x: 1 if label in x else 0
        )

    preds = preds[["Data ID"] + condition_labels]

    # -----------------------------
    # Aggregate ECG metrics
    # -----------------------------
    metrics = pd.read_csv(metrics_csv_path)

    numeric_cols = metrics.select_dtypes(include=[np.number]).columns.tolist()
    metrics = metrics[["Data ID"] + numeric_cols]

    grouped = metrics.groupby("Data ID").mean().reset_index()



    # -----------------------------
    # Merge condition + ECG features
    # -----------------------------
    data = preds.merge(grouped, on="Data ID", how="inner")
    for node_name, feature_name in FEATURE_MAP.items():
        if feature_name not in data.columns:
            raise ValueError(f"Missing metric column required for mapping: {feature_name}")
        data[node_name] = data[feature_name]
    if "LFHF" in feature_cols:
        print("Computing LFHF for inference...")
        data_ids = data["Data ID"].astype(str).tolist()
        lfhf_dict = compute_lfhf_for_cache(data_ids, ecg_dir)
        data["LFHF"] = data["Data ID"].map(lfhf_dict)
    data["Age"] = float(age) if age is not None else np.nan
    data["Gender_binary"] = encode_gender_local(gender)

    # Ensure required features exist
    for col in feature_cols:
        if col not in data.columns:
            data[col] = np.nan

    X = data[feature_cols].astype(float)
    print("\n================ AIS INPUT DEBUG ================")
    print("Feature columns expected by model:")
    print(feature_cols)

    print("\nShape of X:", X.shape)

    print("\nFirst 5 rows of X:")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", None)
    pd.set_option("display.max_colwidth", None)
    print(X)

    print("\nAny NaNs in X?")
    print(X.isna().sum())

    print("=================================================\n")
    # -----------------------------
    #  Predict AIS
    # -----------------------------
    prob = model.predict_proba(X)[:, 1]
    ais_binary = (prob >= threshold).astype(int)

    ais_label = ["AIS C/D" if x == 1 else "AIS A/B" for x in ais_binary]

    result_df = pd.DataFrame({
        "Data ID": data["Data ID"],
        "NLI": nli,
        "Gender": gender,
        "Age": age,
        "AIS Probability (C/D)": prob,
        "Predicted AIS": ais_label
    })

    result_df.to_csv(output_path, index=False)

    print(f" Saved AIS prediction to {output_path}")
    return output_path




LABEL_CONF_MARGIN = {
    "1 degree atrioventricular block": 0.06,
    "ST-T Change":                     0.15,
    "Sinus Bradycardia":               0.02,
    "Sinus Irregularity":              0.10,
    "Sinus Tachycardia":               0.03,
    "Supraventricular Tachycardia":    0.03,
    "T wave Change":                   0.10,
}
DEFAULT_MARGIN = 0.05
def _format_topk(labels, probs, top_k):
    top_idx = np.argsort(probs)[::-1][:top_k]
    parts = [f"{labels[i]}:{probs[i]:.3f}" for i in top_idx]
    return ";".join(parts)

def predict_sci_conditions_from_cache(
    metrics_csv_path,
    model_dir="model_output",
    output_filename="sci_condition_predictions.csv",
    top_k=5
):
    print("\n Running SCI condition prediction...")

    cache_dir = "cache"
    os.makedirs(cache_dir, exist_ok=True)
    output_path = os.path.join(cache_dir, output_filename)

    model_path = os.path.join(model_dir, "multilabel_logreg.joblib")
    features_path = os.path.join(model_dir, "features.txt")
    labels_path = os.path.join(model_dir, "labels.txt")
    thresholds_path = os.path.join(model_dir, "label_thresholds.npy")

    # Load feature + label metadata
    with open(features_path, "r") as f:
        feature_names = [line.strip() for line in f if line.strip()]

    with open(labels_path, "r") as f:
        label_names = [line.strip() for line in f if line.strip()]

    label_thresholds = np.load(thresholds_path)
    if len(label_thresholds) != len(label_names):
        raise ValueError("Threshold count does not match label count.")

    # Aggregate metrics (mean/std/min/max per Data ID)
    df = pd.read_csv(metrics_csv_path)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    df = df[["Data ID"] + numeric_cols]

    grouped = df.groupby("Data ID").agg(["mean", "std", "min", "max"])
    grouped.columns = [f"{col}_{stat}" for col, stat in grouped.columns]
    grouped = grouped.reset_index()

    # Ensure all expected features exist
    for name in feature_names:
        if name not in grouped.columns:
            grouped[name] = np.nan

    X = grouped[feature_names].astype(float)

    model = joblib.load(model_path)
    probs = model.predict_proba(X)

    results = []
    for row_idx, data_id in enumerate(grouped["Data ID"].tolist()):
        row_probs = probs[row_idx]
        predicted = []

        for i, p in enumerate(row_probs):
            label = label_names[i]
            thr = label_thresholds[i]
            margin = LABEL_CONF_MARGIN.get(label, DEFAULT_MARGIN)

            # IMPORTANT: apply threshold + margin
            if p >= (thr + margin):
                predicted.append(label)

        results.append({
            "Data ID": data_id,
            "Predicted Labels": ";".join(predicted),
            "Top K": _format_topk(label_names, row_probs, top_k),
            **{label_names[i]: row_probs[i] for i in range(len(label_names))}
        })

    out_df = pd.DataFrame(results)
    out_df.to_csv(output_path, index=False)

    print(f" Saved predictions to {output_path}\n")
    return output_path
# CSV ROW WRITER (same format)
AMPLITUDE_METRICS = {
    "T Wave Amplitude (mV)",
    "T Wave Std (mV)",
    "T Wave Min (mV)",
    "T Wave Max (mV)",
    "ST Level Mean (mV)",
    "ST Level Std (mV)",
}
def write_metrics_rows(ecg, writer):
    metrics = ecg.get_all_metrics()
    metric_names = ecg.get_metric_names()
    num_intervals = len(metrics.get("Time (s)", []))

    for i in range(num_intervals):
        row = {
            "Data ID": ecg.get_data_id(),
            "Interval": i + 1,
        }

        for name in metric_names:
            values = metrics.get(name, [])
            if i < len(values) and values[i] is not None:
                val = values[i]
                if name in AMPLITUDE_METRICS:
                    val = val * 1000.0

                row[name] = val
            else:
                row[name] = None

        writer.writerow(row)



# MAIN PIPELINE
def build_single_sci_metrics(
    csv_file,
    input_dir,
    output_csv="single_sci_ecg_metrics.csv",
    convert_dir="converted_sci",
    max_duration=None
):
    import os
    import csv
    import time

    start_time = time.time()
    cache_dir = "cache"
    os.makedirs(cache_dir, exist_ok=True)

    # Build full output path inside cache
    output_path = os.path.join(cache_dir, output_csv)
    csv_path = os.path.join(input_dir, csv_file)
    record_id = os.path.splitext(csv_file)[0]

    print(f"\n Processing {record_id}")

    processed = 0
    failed = 0

    with open(output_path, "w", newline="") as f:
        writer = None
        fieldnames = None

        try:
            # Convert CSV → WFDB
            convert_csv_to_dat(
                csv_file,
                abnormal_data_dir=input_dir,
                convert_dir=convert_dir
            )

            # Force loader to use ONLY this file
            loader._sci_iterator = iter([record_id])

            # Load ECG
            ecg = init_processing(max_duration=max_duration)
            if ecg is None:
                raise RuntimeError("init_processing returned None")

            # Sliding window processing
            fs = ecg.get_sampling_rate()
            window_size = int(fs * max_duration)
            step_size = window_size // 6
            end_index = min(len(ecg.get_ecg_signal()), ecg.get_sample_size())

            if end_index >= window_size:
                for win_start in range(0, end_index - window_size + 1, step_size):
                    win_end = win_start + window_size
                    segment = ecg.get_ecg_signal()[win_start:win_end]
                    ecg = process_window_segment(segment, ecg, win_start, win_end)

            # Create CSV header
            metric_names = ecg.get_metric_names()
            fieldnames = ["Data ID", "Interval"] + metric_names
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            # Write metrics
            write_metrics_rows(ecg, writer)

            processed += 1

        except Exception as e:
            failed += 1
            print(f"Failed {record_id}: {e}")

    elapsed = (time.time() - start_time)

    print("\n==============================")
    print(f"Saved: {output_csv}")
    print(f"Processed: {processed}")
    print(f"Failed: {failed}")
    print(f"Time: {elapsed:.2f} sec")
    print("==============================\n")

# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process and predict SCI conditions")
    metrics_output = "sci_ecg_metrics.csv"
    parser.add_argument(
        "--gender",
        type=str,
        required=True,
        help="Patient gender: M or F"
    )
    parser.add_argument(
        "--age",
        type=float,
        required=True,
        help="Patient age"
    )
    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help="Name of the CSV file to process (e.g., n07_s1.csv)"
    )
    parser.add_argument(
    "--nli",
    type=str,
    required=True,
    help="Neurological Level of Injury (e.g., C5, T4)"
)
    parser.add_argument(
        "--max_duration",
        type=float,
        default=None,
        help="Maximum ECG duration in seconds; default uses config value"
    )
    args = parser.parse_args()
    build_single_sci_metrics(
        csv_file=args.csv,
        input_dir="",
        output_csv="sci_ecg_metrics.csv",
        max_duration=args.max_duration
    )
    metrics_path = os.path.join("cache", metrics_output)

    predict_sci_conditions_from_cache(
        metrics_csv_path=metrics_path,
        top_k=5
    )
    predictions_path = os.path.join("cache", "sci_condition_predictions.csv")

    predict_ais_from_cache(
        metrics_csv_path=metrics_path,
        predictions_csv_path=predictions_path,
        nli=args.nli,
        gender=args.gender,
        age=args.age,
        ecg_dir="",   # <-- add this
    )
    convert_dir = "converted_sci"
    if os.path.exists(convert_dir):
        shutil.rmtree(convert_dir)
        print(f"Deleted temporary folder: {convert_dir}")
