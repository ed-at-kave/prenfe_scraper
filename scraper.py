#!/usr/bin/env python3
"""
RENFE Real-time Train Scraper
Scrapes train fleet data from flota.json every minute
Supports multiple flows: general-prenfe (all trains) and prenfe-cat (RG1/R11 only)
"""

import requests
import json
import time
import os
from datetime import datetime, timedelta
import logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from google.cloud import storage
from flask import Flask, request
import functools

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
    Filter data to only include regional trains (R1, R14, R15, R16, etc.)

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
            if isinstance(item, dict) and item.get('codLinea', '').upper() in ('R1', 'R11', 'R14', 'R15', 'R16', 'R2', 'R2N', 'R2S', 'R4')
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


def get_interval_for_time():
    """
    Get the fetch interval based on current time.

    Schedule:
    - 05:50-09:30: Every 1 minute (peak morning)
    - 16:00-18:30: Every 1 minute (peak evening)
    - 09:30-16:00: Every 10 minutes (daytime off-peak)
    - 18:30-05:50: Every 10 minutes (evening/night)
    - 00:00-05:50: Do NOT fetch (night hours - return None to skip)

    Returns:
        int: Interval in seconds, or None to skip fetching during night
    """
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    current_minutes = hour * 60 + minute

    # Night hours: 00:00-05:50 (0-350 minutes) - skip queries
    night_start = 0 * 60           # 0 minutes (00:00)
    night_end = 5 * 60 + 50        # 350 minutes (05:50)

    # Peak hours: 05:50-09:30 (350-570 minutes) and 16:00-18:30 (960-1110 minutes)
    morning_start = 5 * 60 + 50    # 350 minutes (05:50)
    morning_end = 9 * 60 + 30      # 570 minutes (09:30)
    evening_start = 16 * 60        # 960 minutes (16:00)
    evening_end = 18 * 60 + 30     # 1110 minutes (18:30)

    # Skip queries during night hours
    if night_start <= current_minutes < night_end:
        return None  # Do not fetch

    # Peak hours: 1 minute interval
    if (morning_start <= current_minutes <= morning_end or
        evening_start <= current_minutes <= evening_end):
        return 60  # 1 minute during peak hours

    # Off-peak hours: 10 minutes interval
    return 600  # 10 minutes during off-peak hours


def run_fetch_cycle():
    """Execute a single fetch/process cycle. Used by both CLI and HTTP server."""
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


def main():
    """
    Main scraper loop - runs with dynamic intervals based on time:
    - Peak hours (05:30-09:30, 16:00-18:30): Every 1 minute
    - Off-peak: Every 10 minutes
    - Sleep: 00:00-05:30
    Two flows:
    - general-prenfe: All trains
    - prenfe-cat: Regional trains (R1, R11, R15, R16, R2, R2N, R2S, R4)
    Logs retained for 2.5 hours
    """
    general_logger.info(f"Starting RENFE scraper with dynamic scheduling")
    general_logger.info(f"Peak hours (1min): 05:30-09:30, 16:00-18:30")
    general_logger.info(f"Off-peak (10min): 09:30-16:00, 18:30-00:00")
    general_logger.info(f"Sleep: 00:00-05:30")
    general_logger.info(f"Endpoint: {FULL_URL}")
    general_logger.info(f"Log retention: {LOG_RETENTION_SECONDS / 3600} hours")
    cat_logger.info(f"Starting prenfe-cat flow - filtering regional trains (R1, R11, R15, R16, R2, R2N, R2S, R4)")

    iteration = 0
    last_interval = None

    try:
        while True:
            # Get current interval
            interval = get_interval_for_time()

            # Log interval change
            if interval != last_interval:
                if interval is None:
                    interval_label = "SLEEPING (night hours 00:00-05:30)"
                elif interval == 60:
                    interval_label = "1min (peak hours)"
                else:
                    interval_label = "10min (off-peak)"
                general_logger.info(f"Schedule switched to {interval_label}")
                cat_logger.info(f"Schedule switched to {interval_label}")
                last_interval = interval

            # Skip fetching during night hours (00:00-05:30)
            if interval is None:
                general_logger.debug("Night hours: sleeping for 5 minutes before checking again")
                time.sleep(300)  # Sleep 5 minutes during night, then check if we can resume
                continue

            # Fetch during active hours
            iteration += 1
            general_logger.info(f"--- Iteration {iteration} ---")
            cat_logger.info(f"--- Iteration {iteration} ---")

            # Run single fetch cycle
            run_fetch_cycle()

            # Wait for next iteration with dynamic interval
            general_logger.debug(f"Waiting {interval} seconds until next fetch...")
            time.sleep(interval)

    except KeyboardInterrupt:
        general_logger.info("Scraper stopped by user")
        cat_logger.info("Scraper stopped by user")
    except Exception as e:
        general_logger.error(f"Unexpected error: {e}", exc_info=True)
        cat_logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        session.close()
        general_logger.info("Session closed")
        cat_logger.info("Session closed")


if __name__ == "__main__":
    # Check if running on Cloud Run (PORT env var indicates HTTP server mode)
    port = os.getenv('PORT')
    if port:
        # Cloud Run: start HTTP server
        port = int(port)
        general_logger.info(f"Starting Cloud Run HTTP server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # Local development: run CLI with dynamic scheduling
        main()
