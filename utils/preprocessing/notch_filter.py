from config import *
from utils.handler import *

def apply_notch_filter(signal, fs, notch_freq=60.0, quality_factor=30.0):
    if signal.shape[0] < 10:
        warning_handler("Signal too short for notch filter; skipping.")
        return signal
    b, a = iirnotch(w0=notch_freq, Q=quality_factor, fs=fs)
    return filtfilt(b, a, signal, axis=0)