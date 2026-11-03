"""
Log Loader Module

This module loads PX4 ULog data into pandas DataFrames with a common time axis.

Key design decisions:
1. Common time axis - All data resampled to seconds since log start
2. Graceful handling - Missing topics don't crash, just return None
3. No hardcoded topics - Caller specifies what they need
4. Memory efficient - Only load requested topics

Why pandas DataFrames:
- Easy time-based alignment and resampling
- Built-in interpolation for different sample rates
- Compatible with scipy, numpy, matplotlib
- Familiar API for data analysis
"""

from typing import Dict, Optional, List
import numpy as np
import pandas as pd
from pyulog import ULog


class LogLoader:
    """
    Loads and manages ULog data as pandas DataFrames.

    The main challenge: different topics log at different rates.
    - IMU sensors: ~1000 Hz
    - Attitude estimates: ~100 Hz
    - Battery status: ~1 Hz

    Solution: Create a common time axis in seconds and resample/interpolate.
    """

    def __init__(self, ulg_path: str):
        """
        Initialize the loader with a ULog file.

        Args:
            ulg_path: Path to the .ulg file

        What happens:
        - Opens the ULog file using pyulog
        - Stores the ULog object for later topic access
        - Does NOT load all data yet (memory efficient)
        """
        self.ulog = ULog(ulg_path)
        self.ulg_path = ulg_path

        # Calculate time reference
        # ULog timestamps are in microseconds
        # We'll convert everything to seconds since log start
        self.start_time_us = self.ulog.start_timestamp
        self.duration_s = (self.ulog.last_timestamp - self.ulog.start_timestamp) / 1e6

    def get_topic_data(
        self,
        topic_name: str,
        multi_id: int = 0
    ) -> Optional[pd.DataFrame]:
        """
        Load a single topic as a pandas DataFrame.

        Args:
            topic_name: Name of the topic (e.g., "sensor_accel")
            multi_id: Instance ID for multi-instance topics (default 0)

        Returns:
            DataFrame with time_s column and all fields, or None if topic not found

        How it works:
        1. Search for the topic in ulog.data_list
        2. Extract the data dict (timestamp + fields)
        3. Convert timestamp from microseconds to seconds since start
        4. Build a DataFrame with time_s as index
        5. Return None gracefully if topic doesn't exist

        Why this approach:
        - Topic availability varies between PX4 versions
        - Better to return None than crash
        - Caller can check and skip analysis if needed
        """
        # Find the topic in the log
        topic_data = None
        for data in self.ulog.data_list:
            if data.name == topic_name and data.multi_id == multi_id:
                topic_data = data
                break

        if topic_data is None:
            # Topic not found - this is OK, just return None
            return None

        # Extract the data dictionary
        # Keys are field names (timestamp, x, y, z, etc.)
        # Values are numpy arrays
        data_dict = topic_data.data

        # Convert timestamp from microseconds to seconds since start
        timestamp_us = data_dict['timestamp']
        time_s = (timestamp_us - self.start_time_us) / 1e6

        # Build the DataFrame
        # Start with time as a column
        df_data = {'time_s': time_s}

        # Add all other fields
        for field_name, field_data in data_dict.items():
            if field_name != 'timestamp':  # Skip the original timestamp
                df_data[field_name] = field_data

        df = pd.DataFrame(df_data)

        # Set time_s as the index for easy time-based operations
        df.set_index('time_s', inplace=True)

        return df

    def get_multiple_topics(
        self,
        topic_specs: List[tuple]
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Load multiple topics at once.

        Args:
            topic_specs: List of (topic_name, multi_id) tuples

        Returns:
            Dictionary mapping topic_name to DataFrame (or None)

        Example:
            specs = [
                ("sensor_accel", 0),
                ("battery_status", 0),
                ("vehicle_attitude", 0)
            ]
            data = loader.get_multiple_topics(specs)

            if data["sensor_accel"] is not None:
                # Analyze accelerometer data
                pass
        """
        result = {}
        for topic_name, multi_id in topic_specs:
            key = f"{topic_name}_{multi_id}"
            result[key] = self.get_topic_data(topic_name, multi_id)
        return result

    def get_topic_list(self) -> List[tuple]:
        """
        Get a list of all available topics.

        Returns:
            List of (topic_name, multi_id) tuples

        Useful for:
        - Checking what's available before requesting
        - Building dynamic analysis based on available data
        """
        topics = []
        for data in self.ulog.data_list:
            topics.append((data.name, data.multi_id))
        return topics
