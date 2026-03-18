"""
processing.py

Description:
----------
- Clean ECG signal
- Find and Calculate ECG metrics througth "Window Sliding Method"
- Heart Rate (bpm) (bpm)
- RR Interval (ms), PR Interval (ms)
- SDNN (ms), RMSDD (ms)
- QRS Duration (ms), Qtc (ms)
- pNN50 (%)
- Calculate LF/HF ratio of the signal
"""

"""
Metric                  Description
======================================================================================================================|
Heart Rate (bpm)              The average heart rate over the recording (in beats per minute).                                           
RR Interval (ms)        Time between successive R-peaks (in milliseconds). It is the inverse of heart rate.                                      
PR Interval (ms)        Time from start of the P wave to start of QRS complex. Reflects atrioventricular (AV) conduction.                                
SDNN (ms)               Standard deviation of all normal-to-normal (NN) RR intervals. It’s a time-domain **HRV** metric.  
RMSSD (ms)              Root Mean Square of Successive Differences between adjacent RR intervals.                                                  
pNN50 (%)               Percentage of adjacent RR intervals differing by more than 50 ms.                                 
QRS Duration (ms)       Duration of the QRS complex (ventricular depolarization).                                         
QTc (ms)                Corrected QT interval (ventricular depolarization + repolarization), adjusted for HR.             

"""

from config import *
from utils.display.plot.ecg_plot import *
from utils.workspace.loader import *
from utils.processing.compute_metrics import *
from utils.processing.signal_processing import *
from utils.display.terminal import *
from utils.handler import *

from data import ECGData

def init_processing():
    record_data = load_ecg_record()
    if record_data is None:
        error_handler(f"Failed to load record")
        return None

    data_id = record_data['data_id']
    fs = record_data['fs']
    raw_signal = record_data['raw_signal']
    lead_names = record_data['lead_names']
    lead_signals = record_data['lead_signals']
    age = record_data['age']
    gender = record_data['gender']
    annotation = record_data['annotation']
    sci_condition = record_data['SCI_condition']
    nli = record_data['NLI']
    ais = record_data['AIS']
    
    if DATASET_MODE == "PHYSIONET":
    # Use Lead II (index 1) for multi-lead ECG
        cleaned_signal = clean_ecg_signal(raw_signal[:, 0], fs)
    else:
    # SCI or single-lead ECG
        cleaned_signal = clean_ecg_signal(raw_signal[:, 0], fs)

    ecg_signal, ecg_info = process_ecg_signal(cleaned_signal, fs)

    if ecg_signal is None or ecg_info is None:
        error_handler(f"ECG processing failed for data ID: {data_id}")
        return None

    ecg = ECGData(data_id)
    ecg.ecg_signal = ecg_signal
    ecg.ecg_info = ecg_info
    ecg.set_ecg_attr()
    # LF/HF RATIO CALCULATION
 #   try:
  #      ecg.lf_hf = compute_global_lf_hf(ecg.ecg_signal, ecg.sampling_rate, ecg.data_id)
   # except Exception as e:
    #    warning_handler(f"Could not compute LF/HF ratio: {e}")
    ecg.lead_names = lead_names
    ecg.lead_signals = lead_signals

    ecg.add_metadata(
        gender=gender,
        age=age,
        lead_list=lead_names,
        annotation=annotation,
        sci=sci_condition,
        nli=nli,
        ais=ais
    )
    return ecg

def process_window_segment(segment, ecg, start, end):
    ecg.add_segment(segment)
    try:
        ecg_segment, info_segment = nk.ecg_process(segment, sampling_rate=ecg.get_sampling_rate())
        delineate = delineate_ecg(segment, ecg.get_sampling_rate())

        rpeaks = info_segment["ECG_R_Peaks"]
        # HRV METRICS CALCULATION
        try:
            (
            hr_mean, hr_std,
            rr_mean, rr_std, rr_min, rr_max,
            sdnn, rmssd, pnn50, sdsd
        ) = compute_hrv_metrics(
            rpeaks, info_segment, ecg.get_sampling_rate())
        except Exception as e:
            warning_handler(f"Could not compute HRV metrics: {e}")
        # PR INTERVAL CALCULATION
        try:
            (
            pr_mean, pr_std, pr_min, pr_max
        ) = compute_pr_interval(
            delineate, rpeaks, ecg.get_sampling_rate()
        )
        except Exception as e:
            warning_handler(f"Could not compute PR Interval: {e}")
        # QRS DURATION CALCULATION
        try:
            qrs_mean, qrs_std, qrs_min, qrs_max = compute_qrs_duration(delineate, ecg.get_sampling_rate())
            
        except Exception as e:
            warning_handler(f"Could not compute QRS duration: {e}")
        # QTc CALCULATION
        try:
            qtc_mean, qtc_std = compute_qtc(
            delineate, rpeaks, ecg.get_sampling_rate()
        )
        except Exception as e:
            warning_handler(f"Could not compute QTc: {e}")

        time_interval = f"{start/ecg.get_sampling_rate():.1f}s - {end/ecg.get_sampling_rate():.1f}s"
        try:
            (
            t_amp_mean, t_amp_std,
            t_amp_min, t_amp_max ) = compute_t_wave_amplitude(segment, delineate)
        

        except Exception as e:
            warning_handler(f"Could not compute T wave amplitude: {e}")
        try:
            st_mean, st_std = compute_st_level(
                segment,
                delineate,
                ecg.get_sampling_rate()
            )
        except Exception as e:
            warning_handler(f"Could not compute ST level: {e}")
        ecg.add_metrics(
            # Rhythm
            hr_mean=hr_mean,
            hr_std=hr_std,
            rr_mean=rr_mean,
            rr_std=rr_std,
            rr_min=rr_min,
            rr_max=rr_max,
            sdsd=sdsd,

            # HRV
            sdnn=sdnn,
            rmssd=rmssd,
            pnn50=pnn50,

            # Conduction
            pr_mean=pr_mean,
            pr_std=pr_std,
            pr_min=pr_min,
            pr_max=pr_max,

            # Depolarization
            qrs_mean=qrs_mean,
            qrs_std=qrs_std,
            qrs_min=qrs_min,
            qrs_max=qrs_max,

            # Repolarization
            qtc_mean=qtc_mean,
            qtc_std=qtc_std,

            # Morphology
            t_amp_mean=t_amp_mean,
            t_amp_std=t_amp_std,
            t_amp_min=t_amp_min,
            t_amp_max=t_amp_max,

            # ST segment
            st_level_mean=st_mean,
            st_level_std=st_std,

            timeInterval=time_interval,
        )
    except Exception as e:
        error_handler(f"Failed to process window {start}-{end}: {e}")
    return ecg
