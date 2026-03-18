"""
convert.py

Description:
----------
- Convert both .mff and .csv files into .mat (MATLAB)
- Trimm signal to specified duration 
- Apply notch filter of 60 Hz

"""

from tkinter import EXCEPTION
from config import *
from utils.handler import *
from utils.preprocessing.notch_filter import *
from utils.preprocessing.trim import *

def convert_csv_to_dat(csv_filename, abnormal_data_dir=ABNORMAL_DATA_DIRECTORY, convert_dir=PHYSIONET_DATA):
    csv_path = os.path.join(abnormal_data_dir, csv_filename)
    record_name = os.path.splitext(csv_filename)[0]
    dat_path = os.path.join(convert_dir, record_name + ".dat")
    hea_path = os.path.join(convert_dir, record_name + ".hea")

    # ✅ Skip if already converted
    if os.path.exists(dat_path) and os.path.exists(hea_path):
        print(f"⏩ Skipped conversion (already exists): {record_name}")
        return os.path.join(convert_dir, record_name)

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        error_handler(f"Failed to read CSV: {csv_filename} — {str(e)}")
        return None

    # Detect columns dynamically
    time_col = None
    voltage_col = None
    for col in df.columns:
        if col.strip().lower() in ["time", "time (s)", "time(s)"]:
            time_col = col
        elif col.strip().lower() in ["voltage", "ecg", "ecg (v)", "ecg(v)"]:
            voltage_col = col

    if time_col is None or voltage_col is None:
        error_handler(f"CSV missing required time or voltage columns: {csv_filename}")
        return None

    time = df[time_col].astype(float).values
    signal = df[voltage_col].astype(float).values * 1_000

    if len(time) < 2:
        error_handler(f"CSV too short to estimate fs: {csv_filename}")
        return None

    dt = np.mean(np.diff(time))
    fs = round(1.0 / dt)

    # Reshape and apply notch filter
    signal = signal.reshape(-1, 1)
    signal = apply_notch_filter(signal, fs)

    os.makedirs(convert_dir, exist_ok=True)

    try:
        wfdb.wrsamp(
            record_name=record_name,
            fs=fs,
            units=['uV'],
            sig_name=['ECG'],
            p_signal=signal,
            fmt=['16'],
            write_dir=convert_dir
        )
        print(f"✅ Converted (CSV to WFDB): {csv_filename} → {record_name}.dat/.hea")
        return os.path.join(convert_dir, record_name)
    except Exception as e:
        error_handler(f"Failed to write WFDB: {csv_filename} — {str(e)}")
        return None



# Converts .mff into .mat
# def convert_mff_to_mat(data_id, fs, normal_data_dir=NORMAL_DATA_DIRECTORY, convert_dir=CONVERT_DATA_DIRECTORY):
#     mff_path = os.path.join(normal_data_dir, data_id)
#     os.makedirs(convert_dir, exist_ok=True)

#     base_id = data_id.replace(".mff", "")
#     mat_path = os.path.join(convert_dir, f"{base_id}.mat")

#     if not os.path.isdir(mff_path):
#         error_handler(f"MFF folder not found: {mff_path}")
#         return None

#     try:
#         reader = Reader(mff_path)
#         signal_dict = reader.get_physical_samples_from_epoch(reader.epochs[0])
#     except Exception as e:
#         error_handler(f"Failed to read MFF or get samples: {e}")
#         return None

#     ecg_channel_name = 'PNSData'
#     if ecg_channel_name not in signal_dict:
#         error_handler(f"Channel '{ecg_channel_name}' not found in MFF")
#         return None

#     ecg_signal = signal_dict[ecg_channel_name]
#     if isinstance(ecg_signal, (tuple, list)):
#         ecg_signal = ecg_signal[0]

#     fs = reader.sampling_rates[ecg_channel_name]
#     ecg_signal = np.atleast_2d(ecg_signal)
#     if ecg_signal.shape[0] < ecg_signal.shape[1]:
#         ecg_signal = ecg_signal.T

#     # ✅ Apply notch filter
#     filtered_signal = np.zeros_like(ecg_signal)
#     for i in range(ecg_signal.shape[1]):
#         try:
#             filtered_signal[:, i] = apply_notch_filter(ecg_signal[:, i], fs)
#         except Exception as e:
#             error_handler(f"Failed to apply notch filter: {e}")

#     mat_dict = {
#         'val': filtered_signal.T.astype(np.float32),  # (leads, samples)
#         'fs': np.array([fs], dtype=np.float32)
#     }

#     scipy.io.savemat(mat_path, mat_dict)
#     print(f"✅ Converted and saved {mat_path}")