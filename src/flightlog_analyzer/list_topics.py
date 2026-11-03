#!/usr/bin/env python3
"""
Topic Listing Utility for PX4 ULog Files

This script reads a ULog file and prints all available topics and their fields.
This is critical because topic names and availability vary between PX4 versions.

Why this exists:
- Different PX4 versions log different topics
- Topic names can change between versions
- Not all topics are present in every flight
- We need to know what's available before trying to analyze it

Usage:
    list-topics <path_to_ulg_file>

Example output:
    Topic: sensor_accel_0
      - timestamp (uint64)
      - x (float)
      - y (float)
      - z (float)
"""

import sys
from pathlib import Path
from pyulog import ULog


def list_topics(ulg_path: str) -> None:
    """
    Read a ULog file and print all topics with their fields.

    Args:
        ulg_path: Path to the .ulg file

    What it does:
    - Opens the ULog file using pyulog
    - Iterates through all logged data messages
    - For each topic, prints its name and all available fields with their types
    - Handles errors gracefully if the file can't be read
    """
    try:
        # Load the ULog file
        # pyulog.ULog parses the binary .ulg format into Python objects
        ulog = ULog(ulg_path)

        print(f"\n{'='*70}")
        print(f"ULog file: {Path(ulg_path).name}")
        print(f"{'='*70}\n")

        # ulog.data_list contains all the logged message types
        # Each entry represents one topic (message type) that was logged
        if not ulog.data_list:
            print("No data topics found in this log file.")
            return

        print(f"Found {len(ulog.data_list)} topics:\n")

        # Sort topics alphabetically for easier reading
        sorted_data = sorted(ulog.data_list, key=lambda d: d.name)

        for data in sorted_data:
            # data.name is the topic name (e.g., "sensor_accel", "vehicle_attitude")
            # data.field_data contains the actual logged data
            # data.multi_id distinguishes multiple instances (e.g., accel_0, accel_1)

            topic_name = data.name
            if data.multi_id is not None:
                topic_name += f"_{data.multi_id}"

            print(f"Topic: {topic_name}")

            # List all fields (columns) in this topic
            # field_data is a list of _FieldData objects with field_name and type_str
            for field in sorted(data.field_data, key=lambda f: f.field_name):
                # Get the field name and type
                field_name = field.field_name
                field_type = field.type_str
                print(f"   - {field_name} ({field_type})")

            print()  # Blank line between topics

        # Show some basic file info
        print(f"{'='*70}")
        print(f"Start time: {ulog.start_timestamp / 1e6:.2f} seconds")
        print(f"Duration: {(ulog.last_timestamp - ulog.start_timestamp) / 1e6:.2f} seconds")
        print(f"{'='*70}\n")

    except FileNotFoundError:
        print(f"Error: File not found: {ulg_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading ULog file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Entry point for the list-topics command."""
    if len(sys.argv) != 2:
        print("Usage: list-topics <path_to_ulg_file>")
        print("\nThis tool lists all topics and fields in a PX4 ULog file.")
        print("Use it before analysis to see what data is available.")
        sys.exit(1)

    ulg_path = sys.argv[1]

    if not Path(ulg_path).exists():
        print(f"Error: File does not exist: {ulg_path}", file=sys.stderr)
        sys.exit(1)

    if not ulg_path.endswith('.ulg'):
        print(f"Warning: File doesn't have .ulg extension: {ulg_path}")
        print("Attempting to read anyway...\n")

    list_topics(ulg_path)


if __name__ == "__main__":
    main()
