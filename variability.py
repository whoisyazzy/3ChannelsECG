from config import *

class VariabilityECG:
    def __init__(self, data_id):
        self.data_id = data_id

        self._p2p_variability = defaultdict(list)
        self._std_variability = defaultdict(list)
        self._gradient_variability = defaultdict(list)

    # ===== SETTERS =====
    def add_p2p_variability(self, average_bpm, rr_mean, pr_mean, sdnn, rmssd, pnn50, qrs_duration, qtc, timeInterval):
        self._p2p_variability["Heart Rate (bpm)"].append(average_bpm)
        self._p2p_variability["RR Interval (ms)"].append(rr_mean)
        self._p2p_variability["PR Interval (ms)"].append(pr_mean)
        self._p2p_variability["SDNN (ms)"].append(sdnn)
        self._p2p_variability["RMSSD (ms)"].append(rmssd)
        self._p2p_variability["pNN50 (%)"].append(pnn50)
        self._p2p_variability["QRS Duration (ms)"].append(qrs_duration)
        self._p2p_variability["QTc (ms)"].append(qtc)
        self._p2p_variability["Time (s)"].append(timeInterval)

    def add_std_variability(self, average_bpm, rr_mean, pr_mean, sdnn, rmssd, pnn50, qrs_duration, qtc, timeInterval):
        self._std_variability["Heart Rate (bpm)"].append(average_bpm)
        self._std_variability["RR Interval (ms)"].append(rr_mean)
        self._std_variability["PR Interval (ms)"].append(pr_mean)
        self._std_variability["SDNN (ms)"].append(sdnn)
        self._std_variability["RMSSD (ms)"].append(rmssd)
        self._std_variability["pNN50 (%)"].append(pnn50)
        self._std_variability["QRS Duration (ms)"].append(qrs_duration)
        self._std_variability["QTc (ms)"].append(qtc)
        self._std_variability["Time (s)"].append(timeInterval)

    def add_gradient_variability(self, average_bpm, rr_mean, pr_mean, sdnn, rmssd, pnn50, qrs_duration, qtc, timeInterval):
        self._gradient_variability["Heart Rate (bpm)"].append(average_bpm)
        self._gradient_variability["RR Interval (ms)"].append(rr_mean)
        self._gradient_variability["PR Interval (ms)"].append(pr_mean)
        self._gradient_variability["SDNN (ms)"].append(sdnn)
        self._gradient_variability["RMSSD (ms)"].append(rmssd)
        self._gradient_variability["pNN50 (%)"].append(pnn50)
        self._gradient_variability["QRS Duration (ms)"].append(qrs_duration)
        self._gradient_variability["QTc (ms)"].append(qtc)
        self._gradient_variability["Time (s)"].append(timeInterval)

    # ===== GETTERS =====
    def get_p2p_variability(self):
        return dict(self._p2p_variability)

    def get_std_variability(self):
        return dict(self._std_variability)

    def get_gradient_variability(self):
        return dict(self._gradient_variability)

    def get_data_id(self):
        return self.data_id