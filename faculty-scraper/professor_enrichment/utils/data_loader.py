# coldemail/faculty-scraper/professor_enrichment/utils/data_loader.py

import os


def list_university_csvs(data_dir):
    """
    Scans the data directory and returns a list of all CSV files.
    
    Args:
        data_dir: Path to the data directory
        
    Returns:
        List of CSV filenames (e.g., ['berkeley.csv', 'ucla.csv', ...])
    """
    if not os.path.exists(data_dir):
        return []
    
    csv_files = [
        f for f in os.listdir(data_dir)
        if f.endswith(".csv") and os.path.isfile(os.path.join(data_dir, f))
    ]
    
    return sorted(csv_files)


def get_csv_path(data_dir, csv_name):
    """Returns the full path to a CSV file."""
    return os.path.join(data_dir, csv_name)

