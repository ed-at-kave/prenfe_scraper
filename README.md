# RENFE Real-time Train Scraper

This project scrapes real-time train fleet data from RENFE (Spanish National Railway Company).

## Overview

The scraper fetches the `flota.json` payload from https://tiempo-real.renfe.com/ every minute and saves the data locally with timestamps.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python scraper.py
```

The script will:
- Fetch `/flota.json` from the RENFE website every 60 seconds
- Save each response to `data/flota_YYYYMMDD_HHMMSS.json`
- Log all activities to `renfe_scraper.log`
- Display logs in the console

## Features

- ✅ Automatic periodic scraping (every 1 minute)
- ✅ JSON response parsing and storage
- ✅ Timestamped file naming for versioning
- ✅ Comprehensive logging
- ✅ Error handling and retry logic
- ✅ Connection pooling for efficiency
- ✅ Graceful shutdown (Ctrl+C)

## Output

Data is saved in the `data/` directory with naming pattern:
```
flota_20260217_093045.json
flota_20260217_093105.json
...
```

Logs are written to `renfe_scraper.log` and displayed on stdout.

## API Endpoint

- **Base URL**: https://tiempo-real.renfe.com
- **Endpoint**: /flota.json
- **Method**: GET
- **Response**: JSON array with train fleet information

## Notes

- The script uses connection pooling for efficiency
- Respects standard request timeouts (10 seconds)
- Follows HTTP best practices with proper User-Agent headers
