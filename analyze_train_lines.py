#!/usr/bin/env python3
"""
Analysis script to identify all unique train lines from RENFE API
Helps determine which regional trains should be included in the filter
"""

import requests
import json
from collections import Counter

def fetch_and_analyze_train_lines():
    """Fetch flota data and analyze all unique train line codes"""
    try:
        url = "https://tiempo-real.renfe.com/renfe-visor/flota.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract train line codes
        trains_list = data.get('trenes', []) if isinstance(data, dict) else data
        
        if isinstance(trains_list, list):
            line_codes = []
            for item in trains_list:
                if isinstance(item, dict):
                    code = item.get('codLinea', '').upper()
                    if code:
                        line_codes.append(code)
            
            # Count occurrences of each line
            line_counts = Counter(line_codes)
            
            print("=" * 60)
            print("RENFE Train Line Analysis")
            print("=" * 60)
            print(f"\nTotal trains: {len(line_codes)}")
            print(f"Unique line codes: {len(line_counts)}")
            print("\nAll train lines (sorted by frequency):")
            print("-" * 60)
            
            for line, count in line_counts.most_common():
                print(f"  {line:8} - {count:4} trains")
            
            # Identify RG* lines
            rg_lines = [code for code in line_counts.keys() if code.startswith('RG')]
            print("\n" + "=" * 60)
            print(f"RG* Regional Lines Found: {sorted(rg_lines)}")
            print("=" * 60)
            
            return line_counts
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    fetch_and_analyze_train_lines()
