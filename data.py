"""
data.py

Description:
----------
- Contains class for ECG data
- Storage for metrics, metadata, processing time, ecg properties and etc.
- Setters/Getters

"""

from config import *
from variability import VariabilityECG
class ECGData:
    def __init__(self, data_id, sampling_rate=None, sample_size=None, ecg_signal=None, ecg_info=None, lf_hf=None, processing_time=None):
        self.data_id = data_id                      # unique id of the data
        self.ecg_signal = ecg_signal                # full cleaned signal
        self.ecg_info = ecg_info
        self.variability = VariabilityECG(self.data_id)

        self.sampling_rate = sampling_rate
        self.sample_size = sample_size

        self.lf_hf = lf_hf                          # low-frequency/high frequency ratio
        self.processing_time = processing_time      # time taken to process this data
        self.ecg_metrics_data = defaultdict(list)   # contains relevant ecg metrics
        self.ecg_segments = []                      # Interval of raw signal
        self.metadata = {}                          # metadata of the data
        self.lead_signals = []                      # leads of the signal

    def add_metrics(
        self,
        hr_mean,
        hr_std,
        rr_mean,
        rr_std,
        rr_min,
        rr_max,
        sdsd,
        sdnn,
        rmssd,
        pnn50,
        pr_mean,
        pr_std,
        pr_min,
        pr_max,
        qrs_mean,
        qrs_std,
        qrs_min,
        qrs_max,
        qtc_mean,
        qtc_std,
        t_amp_mean,
        t_amp_std,
        t_amp_min,
        t_amp_max,
        st_level_mean,
        st_level_std,
        timeInterval,
    ):
        # ------------------ Original metrics ------------------
        self.ecg_metrics_data["Time (s)"].append(timeInterval)
        self.ecg_metrics_data["Heart Rate (bpm)"].append(hr_mean)
        self.ecg_metrics_data["RR Interval (ms)"].append(rr_mean)
        self.ecg_metrics_data["PR Interval (ms)"].append(pr_mean)
        self.ecg_metrics_data["SDNN (ms)"].append(sdnn)
        self.ecg_metrics_data["RMSSD (ms)"].append(rmssd)
        self.ecg_metrics_data["pNN50 (%)"].append(pnn50)
        self.ecg_metrics_data["QRS Duration (ms)"].append(qrs_mean)
        self.ecg_metrics_data["QTc (ms)"].append(qtc_mean)
        
        self.ecg_metrics_data["T Wave Amplitude (mV)"].append(t_amp_mean)
         # ------------------ ST segment ------------------
        self.ecg_metrics_data["ST Level Mean (mV)"].append(st_level_mean)
        self.ecg_metrics_data["ST Level Std (mV)"].append(st_level_std)

        # ------------------ Rhythm variability ------------------
        self.ecg_metrics_data["Heart Rate Std (bpm)"].append(hr_std)
        self.ecg_metrics_data["RR Std (ms)"].append(rr_std)
        self.ecg_metrics_data["RR Min (ms)"].append(rr_min)
        self.ecg_metrics_data["RR Max (ms)"].append(rr_max)
        self.ecg_metrics_data["SDSD (ms)"].append(sdsd)

        # ------------------ PR variability ------------------
        self.ecg_metrics_data["PR Std (ms)"].append(pr_std)
        self.ecg_metrics_data["PR Min (ms)"].append(pr_min)
        self.ecg_metrics_data["PR Max (ms)"].append(pr_max)

        # ------------------ QRS variability ------------------
        self.ecg_metrics_data["QRS Std (ms)"].append(qrs_std)
        self.ecg_metrics_data["QRS Min (ms)"].append(qrs_min)
        self.ecg_metrics_data["QRS Max (ms)"].append(qrs_max)

        # ------------------ QTc variability ------------------
        self.ecg_metrics_data["QTc Std (ms)"].append(qtc_std)

        # ------------------ T-wave variability ------------------
        self.ecg_metrics_data["T Wave Std (mV)"].append(t_amp_std)
        self.ecg_metrics_data["T Wave Min (mV)"].append(t_amp_min)
        self.ecg_metrics_data["T Wave Max (mV)"].append(t_amp_max)




    def add_metadata(self, gender, age, lead_list, annotation, sci, nli, ais):
        self.metadata = {
            "Gender": gender,
            "Age": age,
            "Lead": lead_list,
            "Annotation": annotation,
            "SCI_Condition": sci,
            "NLI_Condition": nli,
            "AIS_Severity": ais
        }

    def get_metric_names(self):
        return list(self.ecg_metrics_data.keys())

    def get_metric_values(self, metric_name):
        return self.ecg_metrics_data.get(metric_name, [])

    def get_metric_variation(self, metric_name):
        return self.ecg_metric_variation.get(metric_name)

    def get_num_intervals(self):
        metrics = self.ecg_metrics_data
        if not metrics:
            return 0
        return len(next(iter(metrics.values()), []))

    def get_formatted_metric_value(self, metric_name, index):
        values = self.get_metric_values(metric_name)
        if index >= len(values):
            return "N/A"
        val = values[index]
        if isinstance(val, float):
            return f"{val:.3f}"
        return str(val)

    def add_segment(self, segment):
        self.ecg_segments.append(segment)

    def get_segment(self, index):
        if 0 <= index < len(self.ecg_segments):
            return self.ecg_segments[index]
        else:
            return None

    def set_ecg_attr(self):
        if self.ecg_info is not None:
            self.sampling_rate = self.ecg_info.get("sampling_rate")
        else:
            self.sampling_rate = None

        if self.ecg_signal is not None:
            self.sample_size = len(self.ecg_signal)
        else:
            self.sample_size = 0

    def get_data_id(self):
        return self.data_id

    def get_sampling_rate(self):
        return self.sampling_rate

    def get_sample_size(self):
        return self.sample_size

    def get_ecg_signal(self):
        return self.ecg_signal

    def get_ecg_info(self):
        return self.ecg_info

    def get_lf_hf(self):
        return self.lf_hf

    def get_processing_time(self):
        return self.processing_time

    def get_all_metrics(self):
        return self.ecg_metrics_data

    def get_gender(self):
        return self.metadata.get("Gender", "Unknown")

    def get_age(self):
        return self.metadata.get("Age", "Unknown")

    def get_annotation(self):
        return self.metadata.get("Annotation", "Unknown")

    def get_sci_condition(self):
        return self.metadata.get("SCI_Condition", False)

    def get_nli_condition(self):
        return self.metadata.get("NLI_Condition", None)

    def get_ais_severity(self):
        return self.metadata.get("AIS_Severity", None)

    def get_lead_list(self):
        return self.metadata.get("Lead", [])

    def get_lead_signals(self):
        return self.lead_signals

    def set_lead_signals(self, lead_signals):
        self.lead_signals = lead_signals
    def get_variability(self, method="gradient"):
        if method == "gradient":
            return self.variability.get_gradient_variability()
        if method == "std":
            return self.variability.get_std_variability()
        if method in ("minmax", "p2p"):
            return self.variability.get_p2p_variability()
        return {}
