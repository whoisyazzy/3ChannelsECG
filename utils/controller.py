"""
controller.py

Description:
----------
- Controller implementation for MVC architecture
- Read user input and excute method accordinly
- Controller can demand to process data, show metrics, show plot, run models when communicating with other elements

"""
from utils.display.terminal import show_variability
from utils.processing.init_processing import *

from utils.display.plot.box_plot import *
from utils.display.plot.ecg_plot import *
from utils.display.plot.histogram import *
from utils.display.plot.variation import *

from utils.display.terminal.loading_screen import *
from utils.display.terminal.scanner import *
from utils.display.terminal.show_menu import *
from utils.display.terminal.show_metrics import *
from utils.display.terminal.show_variability import *

from utils.workspace.loader import *
from utils.workspace.save import *

from utils.handler import *
from utils.normal import *

from model.gradient_derivative import *
from model.min_max import *
from model.computer_std_variability import *
from model.regression import *
from model.normal_distribution import *

def run_controller():
    global ecg_data_list

    menu_content()
    choice = input().strip()

    match choice:
        case "1":
            # PROCESS DATA
            try:
                clear_screen()
                ecg_data_list = process_controller()
            except Exception as e:
                error_handler(f"Failed to process data: {e}")
        case "2":
            # SHOW METRICS
            try:
                metrics_controller()
            except Exception as e:
                error_handler(f"Failed to show metrics: {e}")        
        case "3":
            # SHOW PLOT
            try:
                plot_controller()
            except Exception as e:
                error_handler(f"Failed to show plot: {e}")  
        case "4":
            # MODEL LINEAR REGRSSSION
            try:
                modelTraining_controller()
            except Exception as e:
                error_handler(f"Failed to train model: {e}")  
        case '5':
            try:
                variation_controller()
            except Exception as e:
                error_handler(f"Failed to compute variations: {e}") 
        case _:
            try:
                clear_screen()
            except Exception as e:
                error_handler(f"Failed to refresh: {e}")  

    show_all_then_clear_all()
    return True

def process_controller():
    total_time = 0.0
    recent_times = []
    all_ecg_data = []

    num_ids = check_max_ids()

    init_file_iterator()

    show_all_then_clear_all()

    for i in range(num_ids):
        clear_screen()
        show_loading_data(num_ids)
        loading_screen_data(i, num_ids)

        # Process record (initial load & signal clean)
        ecg = init_processing()

        # Sliding window setup
        window_size = int(ecg.get_sampling_rate() * WINDOW_SIZE)
        step_size = int(window_size / 6)
        end_index = min(len(ecg.get_ecg_signal()), ecg.get_sample_size())
        total_windows = (end_index - window_size) // step_size + 1

        window_total_time = 0.0
        file_start_time = time.time()

        for w, win_start in enumerate(range(0, end_index - window_size + 1, step_size)):
            win_end = win_start + window_size
            segment = ecg.get_ecg_signal()[win_start:win_end]

            # Process current window
            window_start_time = time.time()
            ecg = process_window_segment(segment, ecg, win_start, win_end)
            window_elapsed = time.time() - window_start_time
            window_total_time += window_elapsed

            # ... display progress etc ...
            clear_screen()
            show_current_data(ecg, total_ids=num_ids)
            loading_screen_data(i, num_ids)
            loading_screen_windows(w, total_windows)
            show_window_time_stats(window_elapsed, window_total_time, ((window_total_time / (w + 1)) * (total_windows - (w + 1))))
            file_elapsed = time.time() - file_start_time
            files_completed = i
            avg_file_time = total_time / files_completed if files_completed > 0 else 0
            remaining_files = num_ids - (i + 1)
            estimated_file_time = remaining_files * avg_file_time + max(0, avg_file_time - file_elapsed)
            show_file_time_stats(file_elapsed, total_time + file_elapsed, estimated_file_time)
        
        # File done
        file_elapsed = time.time() - file_start_time
        ecg.processing_time = file_elapsed
        total_time += file_elapsed
        recent_times.append(file_elapsed)
        if len(recent_times) > 10:
            recent_times.pop(0)

        # File time estimates
        if i + 1 < num_ids:
            avg_file_time = total_time / (i + 1)
            estimated_file_time = avg_file_time * (num_ids - (i + 1))
        else:
            estimated_file_time = 0.0

        all_ecg_data.append(ecg)

        show_all_then_clear_all()

    clear_screen()
    loading_screen_data(num_ids, num_ids)
    processing_completed(total_time)

    return all_ecg_data

def metrics_controller():
    print(ecg_data_list)
    show_metrics(ecg_data_list)
   # show_metric_variability(ecg_data_list)
  #  save_ecg_metrics(ecg_data_list, filename="all_ecg_metrics.csv")

    #run_normal_analysis(ecg_data_list)


def plot_controller():
    plot_dict = {ecg.get_data_id(): ecg for ecg in ecg_data_list}
    clear_screen()

    available_data_ids(list(plot_dict.keys())) 

    while True:
        plot_title_prompt()
        show_all_then_clear_all()
        plot_type = input("Plot Type: ").strip().lower()

        if plot_type == "exit":
            clear_screen()
            break

        # === BOX ===
        elif plot_type == "box":
            plot_metrics_prompt()
            metrics_input = input("Metrics: ").strip()
            if not metrics_input:
                selected_metrics = list(METRIC_NAME_MAP.keys())
            else:
                selected_metrics = [m.strip() for m in metrics_input.split(",") if m.strip()]

            invalid_metrics = [m for m in selected_metrics if m not in METRIC_NAME_MAP]
            if invalid_metrics:
                warning_handler(f"Invalid metric name(s): {', '.join(invalid_metrics)}")
                continue

            all_data = list(plot_dict.values())  # Always use all available data

            compare_input = input("Compare SCI and Non-SCI in one window? (y/n): ").strip().lower()

            for metric in selected_metrics:
                if compare_input == 'y':
                    # Single plot with 2 rows: SCI + Non-SCI boxplots
                    p = Process(target=plot_boxplot_SCI, args=(all_data, metric))
                    p.start()
                else:
                    # Normal: all data together in one boxplot
                    p = Process(target=plot_boxplot, args=(all_data, metric, None))
                    p.start()

        # === FULL ECG ===
        elif plot_type == "ecg":
            plot_data_ids_prompt()
            available_data_ids(list(plot_dict.keys())) 

            data_ids_input = input("Data IDs: ").strip()
            selected_ids = [id.strip() for id in data_ids_input.split(",")] if data_ids_input else list(plot_dict.keys())
            selected_data = [plot_dict[i] for i in selected_ids if i in plot_dict]

            if not selected_data:
                warning_handler(f"A selected id: {selected_ids} does not exist")
                continue

            p = Process(target=plot_full_ECG, args=(selected_data,))
            p.start()

        # === HISTOGRAM ===
        elif plot_type == "histogram":
            all_data = list(plot_dict.values())
            p1 = Process(target=plot_histogram_nonsci, args=(all_data,))
            p2 = Process(target=plot_histogram_sci, args=(all_data,))
            p1.start()
            p2.start()

        # === VARIATION ===
        elif plot_type == "variation":
            plot_metrics_prompt()
            metrics_input = input("Metrics: ").strip()
            if not metrics_input:
                selected_metrics = list(METRIC_NAME_MAP.keys())
            else:
                selected_metrics = [m.strip() for m in metrics_input.split(",") if m.strip()]

            for metric in selected_metrics:
                if metric not in METRIC_NAME_MAP:
                    warning_handler(f"Invalid metric name: {metric}")
                    continue

            plot_data_ids_prompt()
            available_data_ids(list(plot_dict.keys())) 

            data_ids_input = input("Data IDs: ").strip()
            selected_ids = [id.strip() for id in data_ids_input.split(",")] if data_ids_input else list(plot_dict.keys())
            selected_data = [plot_dict[i] for i in selected_ids if i in plot_dict]

            if not selected_data:
                warning_handler("No valid data IDs selected.")
                continue

            for metric in selected_metrics:
                p1 = Process(target=plot_metric_variation, args=(selected_data, metric))
                p2 = Process(target=plot_metric_variability, args=(selected_data, metric))
                p1.start()
                p2.start()

        elif plot_type == "variability":
            selected_data_id = input("Enter SCI patient data_id to compare: ").strip()

            processes = []
            for metric_name in METRIC_NAME_MAP.keys():
                p = Process(target=plot_variability_distribution, args=(ecg_data_list, metric_name, selected_data_id))
                p.start()
                processes.append(p)

        else:
            warning_handler(f"Invalid plot type: {plot_type}")

        time.sleep(1)
        show_all_then_clear_all()

def variation_controller():
    print("\nSelect variability calculation method:")
    print("1. Gradient derivative")
    print("2. Min–Max range")
    print("3. Standard deviation")
    
    choice = input("Enter method number (1-3): ").strip()

    if choice == "1":
        print("📈 Using Gradient Derivative method...")
        compute_gradient_derivative(ecg_data_list)  # writes into ecg.variability
        show_metric_variability(ecg_data_list, method="gradient")
    elif choice == "2":
        print("📏 Using Min–Max Range method...")
        compute_minmax_variability(ecg_data_list)   # writes into ecg.variability (p2p)
        show_metric_variability(ecg_data_list, method="minmax")
    elif choice == "3":
        print("📊 Using Standard Deviation method...")
        compute_std_variability(ecg_data_list)      # writes into ecg.variability (std)
        show_metric_variability(ecg_data_list, method="std")
    else:
        warning_handler("Invalid choice")
        return

    # Now you can process `results` however you want
    show_all_then_clear_all()


def modelTraining_controller():
    # Extract metrics and metadata from each ECGData object
    metrics_data = prepare_data_for_model_per_segment(ecg_data_list)

    # Now pass both lists to the regression model
    RegressionModel_Training_per_segment(metrics_data)

