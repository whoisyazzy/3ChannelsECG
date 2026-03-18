"""
handler.py

Description:
----------
- Stores error and warning codes found in the program
- Show error and warning codes
- Clear error and warning codes
- Check if errors are found

"""

from config import *

error_list = []
warning_list = []

def error_handler(msg):
    error_list.append(msg)

def warning_handler(msg):
    warning_list.append(msg)

def show_errors():
    if error_list:
        for err in error_list:
            print(f" - {BRIGHT_RED}❌ ERROR: {err}{RESET}")

def show_warning():
    if warning_list:
        for warn in warning_list:
            print(f" - {BRIGHT_GOLD}⚠️ WARNING: {warn}{RESET}")

def show_all_then_clear_all():
    if error_list:
        for err in error_list:
            print(f" - {BRIGHT_RED}❌ ERROR: {err}{RESET}")
    if warning_list:
        for warn in warning_list:
            print(f" - {BRIGHT_GOLD}⚠️ WARNING: {warn}{RESET}")
    clear_errors()
    clear_warning()

def print_latest_error():
    if error_list:
        print(f" - {BRIGHT_RED}❌ ERROR: {error_list[-1]}{RESET}")

def print_latest_warning():
    if warning_list:
        print(f" - {BRIGHT_GOLD}⚠️ WARNING: {warning_list[-1]}{RESET}")

def clear_errors():
    error_list.clear()

def clear_warning():
    warning_list.clear()