import os
import scipy.io
import numpy as np
import pandas as pd
from config import *
from utils.handler import *
from config import MAX_IDS
# =====================================================
# Load SNOMED code → name mapping
# =====================================================
def load_snomed_map(csv_path):
    df = pd.read_csv(csv_path)

    return {
        str(row["Snomed_CT"]).strip(): {
            "full_name": row["Full Name"],
            "acronym": row["Acronym Name"]
        }
        for _, row in df.iterrows()
    }

# =====================================================
# Parse .hea manually
# =====================================================
def parse_hea_metadata(hea_path, snomed_map):
    age = None
    gender = "Unknown"
    dx_names = []

    try:
        with open(hea_path, "r") as f:
            for line in f:
                line = line.strip()

                if line.startswith("#Age:"):
                    age = int(line.split(":")[1].strip())

                elif line.startswith("#Sex:"):
                    gender = line.split(":")[1].strip()

                elif line.startswith("#Dx:"):
                    codes = line.split(":")[1].split(",")
                    for code in codes:
                        code = code.strip()
                        if code in snomed_map:
                            dx_names.append(snomed_map[code]["full_name"])
                        else:
                            dx_names.append(f"Unknown({code})")

    except Exception as e:
        warning_handler(f"Failed to parse HEA metadata: {hea_path} ({e})")

    annotation = ", ".join(dx_names) if dx_names else "Unknown"

    return age, gender, annotation

# =====================================================
# Load one record
# =====================================================
def load_physionet_record(base_path, snomed_map):
    hea_path = base_path + ".hea"
    mat_path = base_path + ".mat"

    if not os.path.exists(mat_path) or not os.path.exists(hea_path):
        error_handler(f"Missing .hea or .mat for {base_path}")
        return None

    try:
        # --- Load signal ---
        mat = scipy.io.loadmat(mat_path)
        if "val" not in mat:
            error_handler(f"'val' not found in {mat_path}")
            return None

        signal = mat["val"].T.astype(np.float32)

        # --- Sampling rate from header first line ---
        with open(hea_path, "r") as f:
            first_line = f.readline().split()
            fs = int(first_line[2])

        # --- Metadata ---
        age, gender, annotation = parse_hea_metadata(hea_path, snomed_map)

        data_id = os.path.basename(base_path)
        # --- Enforce MAX_DATA_DURATION ---
        if MAX_DATA_DURATION is not None:
            max_samples = int(fs * MAX_DATA_DURATION)
            if signal.shape[0] > max_samples:
                signal = signal[:max_samples, :]

        return {
            "data_id": data_id,
            "fs": fs,
            "raw_signal": signal,
            "lead_names": [f"Lead{i+1}" for i in range(signal.shape[1])],
            "lead_signals": signal,
            "age": age,
            "gender": gender,
            "annotation": annotation,
            "SCI_condition": False,
            "NLI": None,
            "AIS": None,
        }

    except Exception as e:
        error_handler(f"Failed loading {base_path}: {e}")
        return None

# =====================================================
# Iterate WFDBRecords/01/010/... structure
# =====================================================
def iterate_physionet_dataset(base_dir, snomed_csv):
    snomed_map = load_snomed_map(snomed_csv)
    records = []
    record_count = 0

    for lvl1 in sorted(os.listdir(base_dir)):              # 01, 02
        p1 = os.path.join(base_dir, lvl1)
        if not os.path.isdir(p1):
            continue

        for lvl2 in sorted(os.listdir(p1)):                # 010, 011
            p2 = os.path.join(p1, lvl2)
            if not os.path.isdir(p2):
                continue

            for file in sorted(os.listdir(p2)):
                if file.endswith(".hea"):
                    if MAX_IDS is not None and record_count >= MAX_IDS:
                        print(f"⚠️ Record limit reached (MAX_IDS={MAX_IDS})")
                        return records

                    rec_name = file.replace(".hea", "")
                    base_path = os.path.join(p2, rec_name)
                    rec = load_physionet_record(base_path, snomed_map)

                    if rec:
                        records.append(rec)
                        record_count += 1

    return records
