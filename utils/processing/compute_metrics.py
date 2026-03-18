from config import *

def compute_hrv_metrics(rpeaks, ecg_info, fs):
    if len(rpeaks) < 2:
        return (np.nan,) * 10

    rr = np.diff(rpeaks) / fs * 1000
    if len(rr) < 2:
        return (np.nan,) * 10

    hr = 60000 / rr
    
    rr_mean = np.mean(rr)
    rr_std = np.std(rr)
    rr_min = np.min(rr)
    rr_max = np.max(rr)

    hr_mean = np.mean(hr)
    hr_std = np.std(hr)
    sdsd = np.std(np.diff(rr)) if len(rr) >= 3 else np.nan

    try:
        hrv_time = nk.hrv_time(ecg_info, sampling_rate=fs)
        sdnn = hrv_time['HRV_SDNN'].values[0]
        rmssd = hrv_time['HRV_RMSSD'].values[0]
        pnn50 = hrv_time['HRV_pNN50'].values[0]
    except Exception:
        sdnn = np.nan
        rmssd = np.nan
        pnn50 = np.nan

    return (
        hr_mean, hr_std,
        rr_mean, rr_std, rr_min, rr_max,
        sdnn, rmssd, pnn50,sdsd
    )

def compute_global_lf_hf(ecg_signal, fs, data_id):
    ecg_signal = np.squeeze(ecg_signal)
    if ecg_signal.ndim != 1:
        raise ValueError(f"Expected 1D ECG signal, got shape: {ecg_signal.shape}")
        
    processed_signal, info = nk.ecg_process(ecg_signal, sampling_rate=fs)
    hrv_freq = nk.hrv_frequency(info, sampling_rate=fs)
    lf_hf = hrv_freq['HRV_LFHF'].values[0]
    return lf_hf

def compute_qrs_duration(delineate_signals, fs):
    if "ECG_Q_Peaks" not in delineate_signals or "ECG_S_Peaks" not in delineate_signals:
        return (np.nan,) * 4

    q_peaks = np.where(delineate_signals["ECG_Q_Peaks"] == 1)[0]
    s_peaks = np.where(delineate_signals["ECG_S_Peaks"] == 1)[0]

    valid_pairs = []
    for q in q_peaks:
        s_candidates = s_peaks[s_peaks > q]
        if len(s_candidates) == 0:
            continue
        s = s_candidates[0]
        if (s - q) / fs > 0.15:
            continue
        valid_pairs.append((q, s))

    if not valid_pairs:
        return (np.nan,) * 4

    q_indices = np.array([q for q, _ in valid_pairs])
    s_indices = np.array([s for _, s in valid_pairs])
    qrs_durations_ms = (s_indices - q_indices) / fs * 1000

    return (
    np.mean(qrs_durations_ms),
    np.std(qrs_durations_ms),
    np.min(qrs_durations_ms),
    np.max(qrs_durations_ms),
)

def compute_qtc(delineate_signals, rpeaks, fs):
    required_keys = ["ECG_Q_Peaks", "ECG_T_Offsets"]
    if not all(k in delineate_signals for k in required_keys):
        return (np.nan, np.nan)

    q_peaks = np.where(delineate_signals["ECG_Q_Peaks"] == 1)[0]
    t_offsets = np.where(delineate_signals["ECG_T_Offsets"] == 1)[0]

    valid_pairs = []
    for q in q_peaks:
        t_candidates = t_offsets[t_offsets > q]
        if len(t_candidates) == 0:
            continue
        t = t_candidates[0]
        valid_pairs.append((q, t))

    if not valid_pairs or len(rpeaks) < 2:
        return (np.nan, np.nan)

    q_indices = np.array([q for q, _ in valid_pairs])
    t_indices = np.array([t for _, t in valid_pairs])
    qt_intervals_sec = (t_indices - q_indices) / fs
    qt_mean = np.mean(qt_intervals_sec)
    qt_std = np.std(qt_intervals_sec)
    rr_intervals = np.diff(rpeaks) / fs
    mean_rr = np.mean(rr_intervals)
    qtc_mean = (qt_mean / np.sqrt(mean_rr)) * 1000
    qtc_std  = (qt_std  / np.sqrt(mean_rr)) * 1000
    return qtc_mean, qtc_std


def compute_pr_interval(delineate_signals, rpeaks, fs):
    if "ECG_P_Onsets" not in delineate_signals:
        return (np.nan,) * 4

    p_onsets = np.where(delineate_signals["ECG_P_Onsets"] == 1)[0]
    r_peaks = rpeaks

    valid_intervals = []
    for p in p_onsets:
        r_following = r_peaks[r_peaks > p]
        if len(r_following) == 0:
            continue
        r = r_following[0]
        pr_interval = (r - p) / fs
        if 0.06 < pr_interval < 0.3:  # physiological range: 60–300 ms
            valid_intervals.append(pr_interval * 1000)  # ms

    if len(valid_intervals) == 0:
        return (np.nan,) * 4

    return (
        np.mean(valid_intervals),
        np.std(valid_intervals),
        np.min(valid_intervals),
        np.max(valid_intervals),
    )
def compute_t_wave_amplitude(ecg_signal, delineate_signals):
    if "ECG_T_Peaks" not in delineate_signals:
        return (np.nan,) * 4

    t_peaks = np.where(delineate_signals["ECG_T_Peaks"] == 1)[0]
    if len(t_peaks) < 2:
        return (np.nan,) * 4

    baseline = np.median(ecg_signal)
    GAIN = 1000.0
    t_amps = [(ecg_signal[t] - baseline) / GAIN for t in t_peaks]

    t_amps = np.array(t_amps)

    return (
        np.mean(t_amps),
        np.std(t_amps),
        np.min(t_amps),
        np.max(t_amps),
    )
def compute_st_level(ecg_signal, delineate_signals, fs):
    if "ECG_T_Onsets" not in delineate_signals:
        return (np.nan, np.nan)

    t_onsets = np.where(delineate_signals["ECG_T_Onsets"] == 1)[0]
    if len(t_onsets) < 2:
        return (np.nan, np.nan)

    baseline = np.median(ecg_signal)
    offset = int(-0.03 * fs)  # 30 ms before onset

    st_levels = []
    for t in t_onsets:
        idx = t + offset
        if 0 <= idx < len(ecg_signal):
            GAIN = 1000.0
            st = (ecg_signal[idx] - baseline) / GAIN
            st_levels.append(st)

    if len(st_levels) < 2:
        return (np.nan, np.nan)

    st_levels = np.array(st_levels)

    return (
        np.mean(st_levels),
        np.std(st_levels),
    )
