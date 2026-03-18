from config import *

def clear_screen():
    print("\033c", end="")

def menu_content():
    width = shutil.get_terminal_size().columns
    padding = " " * 4  
    divider = f"{BRIGHT_GRAY}" + "─" * width + f"{RESET}"
    title = f"{BOLD}{WHITE}Controller Menu{RESET}"

    options = [
        f"{BOLD}1.{RESET} Process Data",
        f"{BOLD}2.{RESET} Show Metrics",
        f"{BOLD}3.{RESET} Show Plot",
        f"{BOLD}4.{RESET} Train Model (Linear Regression)",
        f"{BOLD}5.{RESET} Variation",
    ]

    print("\n" + divider)
    print(padding + title)
    print(divider)

    for option in options:
        print(padding + option)

    print(divider)

    print("\nEnter your choice (1-5): ")

def processing_failed():
    print(f"\n{BRIGHT_RED}Processing has been terminated{RESET}\n")

def processing_completed(total_time):
    seco = total_time % (24 * 3600)
    hour = seco // 3600
    seco %= 3600
    minu = seco // 60
    seco %= 60

    if hour == 0 and minu == 0:
        print(f"\n{BRIGHT_LIME}ECG data processing successfully completed{RESET}\nTotal time taken: {seco:.2f} seconds\n")
    elif hour == 0:
        print(f"\n{BRIGHT_LIME}ECG data processing successfully completed{RESET}\nTotal time taken: {int(minu)} minutes: {seco:.2f} seconds\n")
    else:
        print(f"\n{BRIGHT_LIME}ECG data processing successfully completed{RESET}\nTotal time taken: {int(hour)} hour: {int(minu)} minutes: {seco:.2f} seconds\n")
