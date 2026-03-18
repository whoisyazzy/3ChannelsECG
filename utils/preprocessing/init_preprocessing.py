from config import *
from utils.handler import *
from utils.preprocessing.notch_filter import *
from utils.preprocessing.trim import *
from utils.preprocessing.convert import *

# Check if file already performed conversion and trimming
def init_pre_processing(normal_data_dir=NORMAL_DATA_DIRECTORY, abnormal_data_dir=ABNORMAL_DATA_DIRECTORY, convert_dir=PHYSIONET_DATA):
    warnings.filterwarnings("ignore", message="categories.xml not found or of wrong type.*")

    os.makedirs(convert_dir, exist_ok=True)

    # Convert CSV files to .mat (if not already converted)
    csv_files = [f for f in os.listdir(abnormal_data_dir) if f.endswith(".csv")]
    for file in csv_files:
        data_id = os.path.splitext(file)[0]
        mat_path = os.path.join(convert_dir, f"{data_id}.mat")

        if os.path.exists(mat_path):
            print(f"✅ Already converted (CSV): {file}")
        else:
            try:
                print(f"🔄 Converting (CSV): {file}")
                convert_csv_to_dat(file, abnormal_data_dir, convert_dir)
            except Exception as e:
                error_handler(f"Failed to convert CSV: {file} {e}")
                continue
    show_all_then_clear_all()

    # # Trim all .mat files in convert_dir
    # mat_files = [f for f in os.listdir(convert_dir) if f.endswith('.mat')]

    # for mat_file in mat_files:
    #     mat_path = os.path.join(convert_dir, mat_file)
    #     try:
    #         trim_data_to_duration(mat_path, convert_dir)
    #     except Exception as e:
    #         error_handler(f"Failed to trim record: {mat_file}")

    # ✅ Handle .mff files
    # mff_ids = [f for f in os.listdir(normal_data_dir) if f.endswith('.mff') and os.path.isdir(os.path.join(normal_data_dir, f))]
    # for data_id in mff_ids:
    #     base_id = data_id.replace(".mff", "")
    #     mat_path = os.path.join(convert_dir, f"{base_id}.mat")

    #     reader = Reader(os.path.join(normal_data_dir, data_id))
    #     fs = reader.sampling_rates.get("PNSData", None)
    #     if fs is None:
    #         warning_handler(f"Sampling rate not found for {data_id}, setting default sampling rate to 1000 Hz")
    #         fs = 1000

    #     if os.path.exists(mat_path):
    #         print(f"✅ Already converted (MFF): {data_id}")
    #     else:
    #         print(f"🔄 Converting (MFF): {data_id}")
    #         try:
    #             convert_mff_to_mat(data_id, fs)
    #         except Exception as e:
    #             error_handler(f"Failed to convert MFF: {data_id} {e}")
    #             continue
        
    #     try:
    #         trim_data_to_duration(mat_path)
    #     except Exception as e:
    #         error_handler(f"Failed to trim data: {data_id} {e}")
    #     show_all_then_clear_all()        