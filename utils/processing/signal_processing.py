from config import *

def clean_ecg_signal(raw_signal, fs):
    return nk.ecg_clean(raw_signal, sampling_rate=fs, method="neurokit")

def process_ecg_signal(cleaned_signal, fs):
    processed, info = nk.ecg_process(cleaned_signal, sampling_rate=fs)
    ecg_clean = processed["ECG_Clean"].values
    return ecg_clean, info

def delineate_ecg(cleaned_signal, fs):
    delineate_signals, _ = nk.ecg_delineate(cleaned_signal, sampling_rate=fs, method="dwt")
    return delineate_signals