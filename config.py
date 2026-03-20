INPUT_FOLDER = "C:\\Users\\ttgw0\\OneDrive - TTLifesciences\\Desktop\\data_preprocess_v2\\In"  # Folder containing Excel files to process
OUTPUT_FOLDER = "C:\\Users\\ttgw0\\OneDrive - TTLifesciences\\Desktop\\data_preprocess_v2\\Out"  # Folder where cleaned files will be written
N_JOBS = -1 # Use all available CPU cores for parallel processing or specify a number (e.g., 4) for limited parallelism


TRANSLATABLE_COLS = [
    "Company Name",
    # "First name",
    # "Last name",
    # "Title",
    # "Location"
]

CRITICAL_COLS = [
    "Company Name",
    "First name",
    "Last name",
    "Title",
    "Location"
]

COLS_TO_CHECK = [
    "Company Name_en",
    "Location",
    "Country"
]