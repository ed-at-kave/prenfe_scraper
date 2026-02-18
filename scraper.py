#!/usr/bin/env python3
"""
RENFE Real-time Train Scraper - Cloud Run HTTP Server

Fetches train fleet data from RENFE API and processes two data flows:
- general-prenfe: All trains (uploaded to GCS)
- prenfe-cat: Regional trains - all R* + RG1 + RL* + RT* (uploaded to GCS)

Deployment: Cloud Run service triggered by Cloud Scheduler at intervals:
- 05:00-05:59 CET: Every 5 minutes
- 06:00-09:59 CET: Every 2 minutes
- 10:00-15:59 CET: Every 10 minutes
- 16:00-18:59 CET: Every 2 minutes
- 19:00-23:59 CET: Every 5 minutes
- 00:00-04:59 CET: Sleep (no queries)
"""

import requests
import json
import os
from datetime import datetime, timedelta
import logging
from pathlib import Path
from google.cloud import storage
from flask import Flask

# Configuration
BASE_URL = "https://tiempo-real.renfe.com"
FLOTA_ENDPOINT = "/renfe-visor/flota.json"
FULL_URL = BASE_URL + FLOTA_ENDPOINT
INTERVAL_SECONDS = 60  # 1 minute
OUTPUT_DIR = Path("data")
LOGS_DIR = Path("logs")
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Log retention: 2.5 hours = 150 minutes
LOG_RETENTION_SECONDS = 2.5 * 3600  # 9000 seconds

# Cloud Storage configuration
GCS_BUCKET_NAME = "beta-tests"
GCS_FOLDER_NAME = "prenfe-data"
GCS_ENABLED = True  # Set to False to disable cloud uploads


def setup_logger(name, log_file):
    """
    Set up a logger with timed rotation (2.5 hours)
    
    Args:
        name (str): Logger name
        log_file (str): Log file path
    
    Returns:
        logging.Logger: Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers = []
    
    # File handler with rotation based on time
    # interval=1, when='S' means rotate every second (we'll use custom cleanup)
    handler = logging.FileHandler(log_file)
    handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# Set up loggers for each flow
general_logger = setup_logger('general-prenfe', LOGS_DIR / 'general-prenfe.log')
cat_logger = setup_logger('prenfe-cat', LOGS_DIR / 'prenfe-cat.log')

# Session for connection pooling
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
})

# Initialize Cloud Storage client (will use Application Default Credentials)
gcs_client = None
if GCS_ENABLED:
    try:
        gcs_client = storage.Client()
        gcs_bucket = gcs_client.bucket(GCS_BUCKET_NAME)
        general_logger.info(f"Cloud Storage initialized: gs://{GCS_BUCKET_NAME}/{GCS_FOLDER_NAME}")
    except Exception as e:
        general_logger.warning(f"Failed to initialize Cloud Storage: {e}. Uploads disabled.")
        GCS_ENABLED = False


def fetch_flota_data():
    """
    Fetch the flota.json payload from RENFE

    Returns:
        dict: The JSON payload or None if request fails
    """
    try:
        # Add cache-busting parameter with current timestamp
        params = {'v': int(datetime.now().timestamp() * 1000)}
        response = session.get(FULL_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        general_logger.info(f"Successfully fetched flota.json - {len(data)} items")
        return data
    except requests.exceptions.RequestException as e:
        general_logger.error(f"Failed to fetch flota.json: {e}")
        return None
    except json.JSONDecodeError as e:
        general_logger.error(f"Failed to parse JSON: {e}")
        return None


def filter_cat_trains(data):
    """
    Filter data to only include regional trains (all R*, RG1, RL*, RT*)
    - R*: Main regional network (R1-R17)
    - RG1: Girona regional trains
    - RL3, RL4: Lleida regional (Rodalies Lleida)
    - RT1, RT2: Tarragona regional (Tram)

    Args:
        data (list or dict): The flota data

    Returns:
        list or dict: Filtered data
    """
    if data is None:
        return data

    # Extract trenes array if wrapped in dict
    trains_list = data.get('trenes', []) if isinstance(data, dict) and 'trenes' in data else data

    if isinstance(trains_list, list):
        return [
            item for item in trains_list
            if isinstance(item, dict) and item.get('codLinea', '').upper() in (
                'R1', 'R2', 'R2N', 'R2S', 'R3', 'R4', 'R7', 'R8', 'R11', 'R13', 'R14', 'R15', 'R16', 'R17',
                'RG1', 'RL3', 'RL4', 'RT1', 'RT2'
            )
        ]

    return data


def analyze_flota_data(data):
    """
    Perform checks on the flota data

    Args:
        data (dict or list): The flota data to analyze

    Returns:
        dict: Analysis results with train counts by line
    """
    analysis = {
        'total_trains': 0,
        'line_counts': {},
    }

    if data is None:
        return analysis

    # Extract trenes array if wrapped in dict
    trains_list = data.get('trenes', []) if isinstance(data, dict) and 'trenes' in data else data

    if isinstance(trains_list, list):
        analysis['total_trains'] = len(trains_list)
        # Count trains by line code
        for item in trains_list:
            if isinstance(item, dict):
                line_code = item.get('codLinea', 'UNKNOWN').upper()
                analysis['line_counts'][line_code] = analysis['line_counts'].get(line_code, 0) + 1

    return analysis


def process_general_flow(data):
    """
    Process data for general-prenfe flow (all trains)

    Args:
        data (dict): The flota data
    """
    if data is None:
        return

    # Perform analysis
    analysis = analyze_flota_data(data)
    line_summary = ', '.join([f"{code}:{count}" for code, count in sorted(analysis['line_counts'].items())])
    general_logger.info(f"Total trains: {analysis['total_trains']} | Lines: {line_summary}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = OUTPUT_DIR / f"general-prenfe_{timestamp}.json"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        general_logger.debug(f"Data saved to {filename}")

        # Upload to Cloud Storage
        upload_to_cloud_storage(filename, "general-prenfe")
    except IOError as e:
        general_logger.error(f"Failed to save data: {e}")


def process_cat_flow(data):
    """
    Process data for prenfe-cat flow (Regional trains R1, R14, R15, R16, etc.)

    Args:
        data (dict): The flota data
    """
    if data is None:
        return

    # Filter for regional trains
    filtered_data = filter_cat_trains(data)

    if not filtered_data or len(filtered_data) == 0:
        cat_logger.warning("No regional trains (R*) found in current data")
        return

    # Perform analysis on filtered data
    analysis = analyze_flota_data(filtered_data)
    line_summary = ', '.join([f"{code}:{count}" for code, count in sorted(analysis['line_counts'].items())])
    cat_logger.info(f"Regional trains filtered: {analysis['total_trains']} trains | {line_summary}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = OUTPUT_DIR / f"prenfe-cat_{timestamp}.json"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)
        cat_logger.debug(f"CAT data saved to {filename}")

        # Upload to Cloud Storage
        upload_to_cloud_storage(filename, "prenfe-cat")
    except IOError as e:
        cat_logger.error(f"Failed to save CAT data: {e}")


def upload_to_cloud_storage(local_file_path, file_type):
    """
    Upload a file to Google Cloud Storage.

    Args:
        local_file_path (Path): Path to the local file
        file_type (str): Type of file ('general' or 'cat')
    """
    if not GCS_ENABLED or gcs_client is None:
        return

    try:
        bucket = gcs_client.bucket(GCS_BUCKET_NAME)
        blob_name = f"{GCS_FOLDER_NAME}/{local_file_path.name}"
        blob = bucket.blob(blob_name)

        blob.upload_from_filename(str(local_file_path))
        general_logger.debug(f"Uploaded {file_type} file to gs://{GCS_BUCKET_NAME}/{blob_name}")
    except Exception as e:
        general_logger.error(f"Failed to upload {file_type} file to Cloud Storage: {e}")


def cleanup_old_logs():
    """
    Clean up log files older than 2.5 hours
    """
    now = datetime.now()
    cutoff_time = now - timedelta(seconds=LOG_RETENTION_SECONDS)
    
    for log_file in LOGS_DIR.glob("*.log"):
        try:
            file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
            if file_time < cutoff_time:
                log_file.unlink()
                general_logger.debug(f"Deleted old log file: {log_file.name}")
        except Exception as e:
            general_logger.error(f"Failed to delete log file {log_file.name}: {e}")


def save_flota_data(data):
    """
    Save flota data to both flows
    
    Args:
        data (dict): The flota data to save
    """
    if data is None:
        return
    
    # Process general flow
    process_general_flow(data)
    
    # Process CAT flow
    process_cat_flow(data)
    
    # Cleanup old logs periodically
    cleanup_old_logs()


def run_fetch_cycle():
    """Execute a single fetch/process cycle triggered by Cloud Scheduler HTTP request."""
    try:
        data = fetch_flota_data()
        if data:
            save_flota_data(data)
            return True
        return False
    except Exception as e:
        general_logger.error(f"Error during fetch cycle: {e}", exc_info=True)
        return False


# Create Flask app for Cloud Run
app = Flask(__name__)


@app.route('/', methods=['POST'])
def trigger():
    """HTTP endpoint for Cloud Scheduler triggers"""
    try:
        general_logger.info("Received HTTP trigger from Cloud Scheduler")
        success = run_fetch_cycle()
        return {'status': 'success', 'message': 'Fetch cycle completed'}, 200
    except Exception as e:
        general_logger.error(f"Error handling trigger: {e}", exc_info=True)
        return {'status': 'error', 'message': str(e)}, 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return {'status': 'ok'}, 200


if __name__ == "__main__":
    # Cloud Run: start HTTP server on configured PORT
    port = int(os.getenv('PORT', 8080))
    general_logger.info(f"Starting Cloud Run HTTP server on port {port}")
    general_logger.info(f"Ready to receive Cloud Scheduler triggers")
    app.run(host='0.0.0.0', port=port, debug=False)
