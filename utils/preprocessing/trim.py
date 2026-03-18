from config import *
from utils.handler import *

# Trimming signal to 10 minutes
def trim_data_to_duration(mat_path, duration_limit=MAX_DATA_DURATION):
    try:
        mat = scipy.io.loadmat(mat_path)

        if "val" not in mat or "fs" not in mat:
            error_handler(f"MAT file missing 'val' or 'fs': {mat_path}")
            return False

        signals = mat["val"]
        fs = float(mat["fs"].squeeze())

        max_samples = int(duration_limit * fs)

        print(f"Trimming check for {mat_path}: signal length={signals.shape[1]}, max_samples={max_samples}")

        if signals.shape[1] > max_samples:
            trimmed_signals = signals[:, :max_samples]
            scipy.io.savemat(mat_path, {
                'val': trimmed_signals.astype(np.float32),
                'fs': np.array([[fs]], dtype=np.float32)
            })
            print(f"✂️ Trimmed {mat_path} to {duration_limit} seconds")
            return True
        else:
            print(f"No trimming needed for {mat_path}")
            return True

    except Exception as e:
        error_handler(f"Error trimming {mat_path}: {e}")
        return False
