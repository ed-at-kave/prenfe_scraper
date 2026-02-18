#!/usr/bin/env python3
"""
Test suite for RENFE scraper
Tests core functionality without making actual API calls
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import requests
import os

# Import scraper functions
import scraper


class TestFilterCatTrains:
    """Tests for filter_cat_trains function"""

    def test_filter_list_with_rg1_trains(self):
        """Should filter list data to only include RG1 trains"""
        data = [
            {'linea': 'rg1', 'nombre': 'Train 1'},
            {'linea': 'r11', 'nombre': 'Train 2'},
            {'linea': 'other', 'nombre': 'Train 3'},
        ]
        result = scraper.filter_cat_trains(data)
        assert len(result) == 2
        assert all(item['linea'].upper() in ('RG1', 'R11') for item in result)

    def test_filter_dict_with_r11_trains(self):
        """Should filter dict data to only include R11 trains"""
        data = {
            'train1': {'linea': 'RG1', 'nombre': 'Train 1'},
            'train2': {'linea': 'R11', 'nombre': 'Train 2'},
            'train3': {'linea': 'AVE', 'nombre': 'Train 3'},
        }
        result = scraper.filter_cat_trains(data)
        assert len(result) == 2
        assert all(v['linea'].upper() in ('RG1', 'R11') for v in result.values())

    def test_filter_returns_none_for_none_input(self):
        """Should return None if input is None"""
        result = scraper.filter_cat_trains(None)
        assert result is None

    def test_filter_returns_empty_list_when_no_matches(self):
        """Should return empty list when no RG1/R11 trains found"""
        data = [
            {'linea': 'AVE', 'nombre': 'Train 1'},
            {'linea': 'AVANT', 'nombre': 'Train 2'},
        ]
        result = scraper.filter_cat_trains(data)
        assert result == []

    def test_filter_case_insensitive(self):
        """Should filter case-insensitively"""
        data = [
            {'linea': 'rg1', 'nombre': 'Train 1'},
            {'linea': 'Rg1', 'nombre': 'Train 2'},
            {'linea': 'RG1', 'nombre': 'Train 3'},
        ]
        result = scraper.filter_cat_trains(data)
        assert len(result) == 3


class TestAnalyzeFiotaData:
    """Tests for analyze_flota_data function"""

    def test_analyze_list_data(self):
        """Should analyze list of train data correctly"""
        data = [
            {'linea': 'RG1', 'nombre': 'Train 1'},
            {'linea': 'R11', 'nombre': 'Train 2'},
            {'linea': 'R11', 'nombre': 'Train 3'},
            {'linea': 'AVE', 'nombre': 'Train 4'},
        ]
        result = scraper.analyze_flota_data(data)
        assert result['total_lines'] == 4
        assert result['rg1_trains'] == 1
        assert result['r11_trains'] == 2

    def test_analyze_dict_data(self):
        """Should analyze dict of train data correctly"""
        data = {
            'train1': {'linea': 'RG1'},
            'train2': {'linea': 'R11'},
            'train3': {'linea': 'R11'},
        }
        result = scraper.analyze_flota_data(data)
        assert result['total_lines'] == 3
        assert result['rg1_trains'] == 1
        assert result['r11_trains'] == 2

    def test_analyze_returns_zeros_for_none(self):
        """Should return zeros when data is None"""
        result = scraper.analyze_flota_data(None)
        assert result['total_lines'] == 0
        assert result['rg1_trains'] == 0
        assert result['r11_trains'] == 0

    def test_analyze_missing_linea_field(self):
        """Should handle data missing linea field"""
        data = [
            {'nombre': 'Train 1'},  # No linea field
            {'linea': 'RG1', 'nombre': 'Train 2'},
        ]
        result = scraper.analyze_flota_data(data)
        assert result['total_lines'] == 2
        assert result['rg1_trains'] == 1


class TestProcessGeneralFlow:
    """Tests for process_general_flow function"""

    def test_process_general_flow_saves_file(self):
        """Should save data to JSON file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            data = [
                {'linea': 'RG1', 'nombre': 'Train 1'},
                {'linea': 'AVE', 'nombre': 'Train 2'},
            ]

            # Patch OUTPUT_DIR
            with patch.object(scraper, 'OUTPUT_DIR', output_dir):
                scraper.process_general_flow(data)

                # Check that file was created
                files = list(output_dir.glob('general-prenfe_*.json'))
                assert len(files) == 1

                # Check file contents
                with open(files[0]) as f:
                    saved_data = json.load(f)
                assert saved_data == data

    def test_process_general_flow_handles_none(self):
        """Should handle None data gracefully"""
        # Should not raise exception
        scraper.process_general_flow(None)


class TestProcessCatFlow:
    """Tests for process_cat_flow function"""

    def test_process_cat_flow_filters_and_saves(self):
        """Should filter and save only RG1/R11 trains"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            data = [
                {'linea': 'RG1', 'nombre': 'Train 1'},
                {'linea': 'AVE', 'nombre': 'Train 2'},
                {'linea': 'R11', 'nombre': 'Train 3'},
            ]

            with patch.object(scraper, 'OUTPUT_DIR', output_dir):
                scraper.process_cat_flow(data)

                files = list(output_dir.glob('prenfe-cat_*.json'))
                assert len(files) == 1

                with open(files[0]) as f:
                    saved_data = json.load(f)
                assert len(saved_data) == 2
                assert all(item['linea'] in ('RG1', 'R11') for item in saved_data)

    def test_process_cat_flow_handles_none(self):
        """Should handle None data gracefully"""
        scraper.process_cat_flow(None)

    def test_process_cat_flow_handles_no_matches(self):
        """Should not save file when no RG1/R11 trains found"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            data = [
                {'linea': 'AVE', 'nombre': 'Train 1'},
                {'linea': 'AVANT', 'nombre': 'Train 2'},
            ]

            with patch.object(scraper, 'OUTPUT_DIR', output_dir):
                scraper.process_cat_flow(data)

                files = list(output_dir.glob('prenfe-cat_*.json'))
                assert len(files) == 0


class TestCleanupOldLogs:
    """Tests for cleanup_old_logs function"""

    def test_cleanup_removes_old_files(self):
        """Should remove log files older than retention period"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)

            # Create old log file (older than retention period)
            old_file = logs_dir / 'old.log'
            old_file.touch()
            old_time = (datetime.now() - timedelta(hours=3)).timestamp()
            os.utime(old_file, (old_time, old_time))

            # Create new log file (within retention period)
            new_file = logs_dir / 'new.log'
            new_file.touch()

            with patch.object(scraper, 'LOGS_DIR', logs_dir):
                scraper.cleanup_old_logs()

                # Check that old file was removed
                assert not old_file.exists()
                assert new_file.exists()


class TestFetchFlotaData:
    """Tests for fetch_flota_data function"""

    @patch('scraper.session.get')
    def test_fetch_successful(self, mock_get):
        """Should return data on successful fetch"""
        mock_response = Mock()
        mock_response.json.return_value = [
            {'linea': 'RG1', 'nombre': 'Train 1'},
            {'linea': 'AVE', 'nombre': 'Train 2'},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = scraper.fetch_flota_data()

        assert result is not None
        assert len(result) == 2
        assert result[0]['linea'] == 'RG1'
        mock_get.assert_called_once()

    @patch('scraper.session.get')
    def test_fetch_handles_http_error(self, mock_get):
        """Should return None on HTTP error"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        result = scraper.fetch_flota_data()

        assert result is None

    @patch('scraper.session.get')
    def test_fetch_handles_json_error(self, mock_get):
        """Should return None on JSON parse error"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response

        result = scraper.fetch_flota_data()

        assert result is None


class TestIntegration:
    """Integration tests combining multiple functions"""

    def test_full_data_processing_pipeline(self):
        """Should correctly process data through full pipeline"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            data = [
                {'linea': 'RG1', 'nombre': 'Train 1', 'id': 1},
                {'linea': 'R11', 'nombre': 'Train 2', 'id': 2},
                {'linea': 'AVE', 'nombre': 'Train 3', 'id': 3},
                {'linea': 'RG1', 'nombre': 'Train 4', 'id': 4},
            ]

            with patch.object(scraper, 'OUTPUT_DIR', output_dir):
                # Process both flows
                scraper.process_general_flow(data)
                scraper.process_cat_flow(data)

                # Check general flow file
                general_files = list(output_dir.glob('general-prenfe_*.json'))
                assert len(general_files) == 1
                with open(general_files[0]) as f:
                    general_data = json.load(f)
                assert len(general_data) == 4

                # Check cat flow file
                cat_files = list(output_dir.glob('prenfe-cat_*.json'))
                assert len(cat_files) == 1
                with open(cat_files[0]) as f:
                    cat_data = json.load(f)
                assert len(cat_data) == 3  # Only RG1 and R11


class TestScheduling:
    """Tests for dynamic scheduling logic with night hours exclusion"""

    def test_interval_during_morning_peak(self):
        """Should return 60 seconds during morning peak (05:50-09:30)"""
        with patch('scraper.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 2, 17, 7, 0, 0)
            interval = scraper.get_interval_for_time()
            assert interval == 60

    def test_interval_during_evening_peak(self):
        """Should return 60 seconds during evening peak (16:00-18:30)"""
        with patch('scraper.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 2, 17, 17, 15, 0)
            interval = scraper.get_interval_for_time()
            assert interval == 60

    def test_interval_during_off_peak(self):
        """Should return 600 seconds during off-peak hours"""
        with patch('scraper.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 2, 17, 12, 0, 0)
            interval = scraper.get_interval_for_time()
            assert interval == 600

    def test_interval_during_night_hours(self):
        """Should return None during night hours (00:00-05:50) to skip queries"""
        with patch('scraper.datetime') as mock_datetime:
            # Test at 00:00 (midnight)
            mock_datetime.now.return_value = datetime(2026, 2, 17, 0, 0, 0)
            assert scraper.get_interval_for_time() is None

            # Test at 03:00 (middle of night)
            mock_datetime.now.return_value = datetime(2026, 2, 17, 3, 0, 0)
            assert scraper.get_interval_for_time() is None

            # Test at 05:49 (just before morning peak)
            mock_datetime.now.return_value = datetime(2026, 2, 17, 5, 49, 0)
            assert scraper.get_interval_for_time() is None

    def test_interval_at_boundaries(self):
        """Should correctly handle peak hour boundaries"""
        with patch('scraper.datetime') as mock_datetime:
            # At 05:50 (start of morning peak - should start querying)
            mock_datetime.now.return_value = datetime(2026, 2, 17, 5, 50, 0)
            assert scraper.get_interval_for_time() == 60

            # At 09:30 (end of morning peak)
            mock_datetime.now.return_value = datetime(2026, 2, 17, 9, 30, 0)
            assert scraper.get_interval_for_time() == 60

            # At 16:00 (start of evening peak)
            mock_datetime.now.return_value = datetime(2026, 2, 17, 16, 0, 0)
            assert scraper.get_interval_for_time() == 60

            # At 18:30 (end of evening peak)
            mock_datetime.now.return_value = datetime(2026, 2, 17, 18, 30, 0)
            assert scraper.get_interval_for_time() == 60

    def test_interval_evening_to_night_transition(self):
        """Should return 10min after 18:30 until night"""
        with patch('scraper.datetime') as mock_datetime:
            # At 19:00 (after evening peak, before night)
            mock_datetime.now.return_value = datetime(2026, 2, 17, 19, 0, 0)
            assert scraper.get_interval_for_time() == 600

            # At 23:59 (last minute before night)
            mock_datetime.now.return_value = datetime(2026, 2, 17, 23, 59, 0)
            assert scraper.get_interval_for_time() == 600


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
