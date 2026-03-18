from config import *
RAW_METRICS = [
    "Time (s)",
    "Heart Rate (bpm)",
    "RR Interval (ms)",
    "PR Interval (ms)",
    "SDNN (ms)",
    "RMSSD (ms)",
    "pNN50 (%)",
    "SDSD (ms)",
    "QRS Duration (ms)",
    "QTc (ms)",

]
VAR_METRICS = {
    "Heart Rate Std (bpm)": ["Heart Rate Std (bpm)"],
    "RR Variability (ms)": ["RR Std (ms)", "RR Min (ms)", "RR Max (ms)"],
    "PR Variability (ms)": ["PR Std (ms)", "PR Min (ms)", "PR Max (ms)"],
    "QRS Variability (ms)": ["QRS Std (ms)"],
    "QTc Variability (ms)": ["QTc Std (ms)"],

}
def color_text(text, color):
    return f"{color}{text}{RESET}"

def show_metrics(ecg_data_list):
    print(f"\n================== ECG METRIC VALUES ==================")
    col_colors = {
        0: BRIGHT_RED,
        1: BRIGHT_ORANGE,
        2: BRIGHT_GOLD,
        3: BRIGHT_YELLOW,
        4: BRIGHT_LIME,
        5: BRIGHT_GREEN,
        6: BRIGHT_CYAN,
        7: BRIGHT_BLUE,
        8: BRIGHT_INDIGO,
        9: BRIGHT_VIOLET,
        10: BRIGHT_MAGENTA
    }

    for ecg in ecg_data_list:
        print(f"\nData ID: {ecg.get_data_id()}")
        print( color_text(
        f"Age: {ecg.get_age()} | "
        f"Sex: {ecg.get_gender()} | "
        f"Annotation: {ecg.get_annotation()}",
        BRIGHT_CYAN) )

        metric_names = [m for m in RAW_METRICS if m in ecg.get_metric_names()]
        num_intervals = ecg.get_num_intervals()

        headers = metric_names.copy()
        if "Time (s)" in headers:
            headers.remove("Time (s)")
            insert_index = headers.index("Heart Rate (bpm)") if "Heart Rate (bpm)" in headers else 0
            headers.insert(insert_index, "Time (s)")


        col_widths = {}
        for h in headers:
            max_val_len = max(len(ecg.get_formatted_metric_value(h, i)) for i in range(num_intervals))
            col_widths[h] = max(len(h), max_val_len) + 2  # padding

        interval_width = max(len("Interval"), len(str(num_intervals))) + 2

        # Print header
        header_line = color_text("Interval".ljust(interval_width), BRIGHT_RED)
        for i, h in enumerate(headers):
            color = col_colors.get(i + 1, RESET)
            header_line += color_text(h.ljust(col_widths[h]), color)
        print(header_line)

        # Print rows
        for i in range(num_intervals):
            row_line = color_text(str(i + 1).ljust(interval_width), BRIGHT_RED)
            for j, h in enumerate(headers):
                val_str = ecg.get_formatted_metric_value(h, i)
                color = col_colors.get(j + 1, RESET)
                row_line += color_text(val_str.ljust(col_widths[h]), color)
            print(row_line)

        lf_hf = ecg.get_lf_hf()
        if lf_hf is None or np.isnan(lf_hf):
            print(color_text("Global LF/HF Ratio: Not computable", BRIGHT_GOLD))
        else:
            print(color_text(f"Global LF/HF Ratio: {lf_hf:.3f}", BRIGHT_CYAN))


        print(color_text(f"Processing Time: {ecg.get_processing_time():.3f} s", RESET))
# ================= VARIABILITY INSIDE WINDOWS =================
        print(color_text("\n---------- VARIABILITY INSIDE WINDOWS ----------", BRIGHT_MAGENTA))

        var_headers = []
        for fields in VAR_METRICS.values():
            for f in fields:
                if f not in var_headers and f in ecg.get_metric_names():
                    var_headers.append(f)

        # column widths
        var_col_widths = {}
        for h in var_headers:
            max_len = max(len(ecg.get_formatted_metric_value(h, i)) for i in range(num_intervals))
            var_col_widths[h] = max(len(h), max_len) + 2

        # header
        header_line = color_text("Interval".ljust(interval_width), BRIGHT_RED)
        for i, h in enumerate(var_headers):
            color = col_colors.get(i + 1, RESET)
            header_line += color_text(h.ljust(var_col_widths[h]), color)
        print(header_line)

        # rows (PER WINDOW)
        for i in range(num_intervals):
            row_line = color_text(str(i + 1).ljust(interval_width), BRIGHT_RED)
            for j, h in enumerate(var_headers):
                val = ecg.get_formatted_metric_value(h, i)
                color = col_colors.get(j + 1, RESET)
                row_line += color_text(val.ljust(var_col_widths[h]), color)
            print(row_line)
