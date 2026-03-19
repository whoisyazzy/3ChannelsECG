"""
loader.py

Description:
----------
- Read all data files and grants them a unique id
- Record metadata from data files

"""
from utils.workspace.physionet_loader import iterate_physionet_dataset
from logging import warning
from config import *
from utils.display.terminal import *
from utils.handler import *
import os
import wfdb


_file_iterator = None
_records = None
_idx = 0
_sci_iterator = None
def init_sci_file_iterator(directory=SCI_WFDB_DATA):
    global _sci_iterator
    hea_files = sorted([
        os.path.splitext(f)[0]
        for f in os.listdir(directory)
        if f.endswith(".hea")
    ])
    _sci_iterator = iter(hea_files[:MAX_IDS])


def init_file_iterator():
    global _records, _idx
    if _records is None:
        _records = iterate_physionet_dataset(
            base_dir=PHYSIONET_WFDB_ROOT,
            snomed_csv=PHYSIONET_SNOMED_CSV,   # put this in config as discussed
        )
    _idx = 0

def check_max_ids(directory=SCI_WFDB_DATA):
    if DATASET_MODE == "SCI":
        hea_files = [f for f in os.listdir(directory) if f.endswith(".hea")]
        return min(MAX_IDS, len(hea_files)) if MAX_IDS else len(hea_files)

    # PhysioNet (unchanged)
    global _records
    if _records is None:
        init_file_iterator()

    if MAX_IDS is None:
        return len(_records)

    return len(_records)



def load_ecg_record(max_duration=None):
    global _records, _idx
    if DATASET_MODE == "SCI":
        if _sci_iterator is None:
            init_sci_file_iterator()
        return load_sci_record(max_duration=max_duration)
    if _records is None:
        init_file_iterator()

    if _idx >= len(_records):
        return None

    if _idx >= len(_records):
        return None

    rec = _records[_idx]
    _idx += 1
    return rec




def load_sci_record(directory=SCI_WFDB_DATA, max_duration=None):
    global _sci_iterator

    if _sci_iterator is None:
        init_sci_file_iterator(directory)

    try:
        data_id = next(_sci_iterator)   # n17_s0
    except StopIteration:
        return None

    record_path = os.path.join(directory, data_id)

    try:
        record = wfdb.rdrecord(record_path)
    except Exception as e:
        error_handler(f"Failed to read SCI WFDB record {data_id}: {e}")
        return None

    fs = record.fs or DEFAULT_SAMPING_FREQUENCY
    signal = record.p_signal
    lead_names = record.sig_name
    lead_signals = [signal[:, i] for i in range(signal.shape[1])]

    # Trim
    max_samples = int(max_duration * fs)
    if signal.shape[0] > max_samples:
        signal = signal[:max_samples, :]

    patient_id = data_id.split("_")[0]
    session_id = data_id.split("_")[1] if "_" in data_id else None

    return {
        "data_id": data_id,           # n17_s0
        "patient_id": patient_id,     # n17
        "session_id": session_id,
        "fs": fs,
        "raw_signal": signal,
        "lead_names": lead_names,
        "lead_signals": lead_signals,
        "annotation": "SCI",
        "age": None,
        "gender": None,
        "SCI_condition": True,
        "NLI": None,
        "AIS": None,
    }
