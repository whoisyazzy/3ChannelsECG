from config import *
from utils.handler import *

def color_text(text, color):
    return f"{color}{text}{RESET}"

def _coerce_lists(d):
    out = {}
    if not d:
        return out
    for k, v in d.items():
        try:
            import numpy as np
            if isinstance(v, np.ndarray):
                v = v.tolist()
        except Exception:
            pass
        out[k] = [float(x) if x is not None else float("nan") for x in v]
    return out

def show_metric_variability(ecg_data_list, method="gradient"):
    """
    Display variability table from ECGData objects.
    Supports method in {"gradient","std","minmax"} with graceful fallbacks.
    """
    print("\n================== ECG METRIC VARIABILITY ==================")

    col_colors = {
        0: BRIGHT_RED, 1: BRIGHT_ORANGE, 2: BRIGHT_GOLD, 3: BRIGHT_YELLOW,
        4: BRIGHT_LIME, 5: BRIGHT_GREEN, 6: BRIGHT_CYAN, 7: BRIGHT_BLUE,
        8: BRIGHT_INDIGO, 9: BRIGHT_VIOLET, 10: BRIGHT_MAGENTA
    }

    for ecg in ecg_data_list:
        print(f"\nData ID: {ecg.get_data_id()}")

        data = None

        # 1) Preferred: embedded VariabilityECG holder
        if hasattr(ecg, "variability"):
            if method == "gradient" and hasattr(ecg.variability, "get_gradient_variability"):
                data = ecg.variability.get_gradient_variability()
            elif method in ("std", "standard", "sd") and hasattr(ecg.variability, "get_std_variability"):
                data = ecg.variability.get_std_variability()
            elif method in ("minmax", "p2p") and hasattr(ecg.variability, "get_p2p_variability"):
                data = ecg.variability.get_p2p_variability()

        # 2) Legacy gradient getter (original code path)
        if not data and method == "gradient" and hasattr(ecg, "get_gradient_variability"):
            data = ecg.get_gradient_variability()

        # 3) Legacy dict used by STD/Min–Max calculators
        if not data and hasattr(ecg, "ecg_metric_variation"):
            data = ecg.ecg_metric_variation

        data = _coerce_lists(data)

        if not data:
            print("⚠️ No variability data found.")
            continue

        metric_names = list(data.keys())
        num_intervals = len(next(iter(data.values()), []))
        headers = ["Interval"] + metric_names

        # widths
        col_widths = {"Interval": max(len("Interval"), len(str(num_intervals))) + 2}
        for metric, vals in data.items():
            max_val_len = max((len(f"{v:.3f}") for v in vals), default=6)
            col_widths[metric] = max(len(metric), max_val_len) + 2

        # header
        header_line = "".join(
            color_text(h.ljust(col_widths[h]), col_colors.get(i % len(col_colors), RESET))
            for i, h in enumerate(headers)
        )
        print(header_line)

        # rows
        for i in range(num_intervals):
            row_line = ""
            for j, h in enumerate(headers):
                color = col_colors.get(j % len(col_colors), RESET)
                if h == "Interval":
                    val = str(i + 1)
                else:
                    vals = data.get(h, [])
                    val = f"{vals[i]:.3f}" if i < len(vals) else "N/A"
                row_line += color_text(val.ljust(col_widths[h]), color)
            print(row_line)
