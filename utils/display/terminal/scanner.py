from config import *

def available_data_ids(pids):
    print("Available Data IDs:")
    index_width = len(str(len(pids)))
    
    for i, pid in enumerate(pids, 1):
        index_str = f"{i}.".ljust(index_width + 2)
        print(f"{BRIGHT_RED}{index_str}{RESET} {pid}")

def plot_title_prompt():
    print(f"\n{BRIGHT_CYAN}{BOLD}Enter the plot type:\n{RESET}")
    print(f"{BRIGHT_RED}1:{RESET} 'BOX'")
    print(f"{BRIGHT_RED}2:{RESET} 'HISTOGRAM'")
    print(f"{BRIGHT_RED}3:{RESET} 'VARIATION'")
    print(f"{BRIGHT_RED}4:{RESET} 'ECG'")
    print(f"{BRIGHT_RED}5:{RESET} Enter 'EXIT' to exit")

def plot_metrics_prompt():
    print(f"{BRIGHT_CYAN}{BOLD}Enter metrics to plot (comma-separated), or press Enter to plot all:{RESET}")
    print(f"{BRIGHT_CYAN}Options:\n{RESET}")
    print(f"{BRIGHT_RED}1:{RESET}HR")
    print(f"{BRIGHT_RED}2:{RESET}RR_mean")
    print(f"{BRIGHT_RED}3:{RESET}SDNN")
    print(f"{BRIGHT_RED}4:{RESET}RMSSD")
    print(f"{BRIGHT_RED}5:{RESET}QRS_duration")
    print(f"{BRIGHT_RED}6:{RESET}QTc")
    print(f"{BRIGHT_RED}7:{RESET}PR_interval")
    print(f"{BRIGHT_RED}8:{RESET}pNN50\n")

def plot_data_ids_prompt():
    print(f"{BRIGHT_CYAN}{BOLD}Enter data IDs to compare (comma-separated), or press Enter to use all available:{RESET}")


