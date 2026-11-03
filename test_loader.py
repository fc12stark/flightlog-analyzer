#!/usr/bin/env python3
"""
Test script for the LogLoader module.

This demonstrates how the loader works and validates basic functionality.
"""

import sys
from src.flightlog_analyzer.loader import LogLoader

def test_loader(ulg_path: str):
    """Test the LogLoader with a real ULog file."""
    
    print("=" * 70)
    print("Testing LogLoader")
    print("=" * 70)
    
    # Initialize the loader
    print(f"\n1. Loading ULog file: {ulg_path}")
    loader = LogLoader(ulg_path)
    print(f"   Start time: {loader.start_time_us / 1e6:.2f} seconds")
    print(f"   Duration: {loader.duration_s:.2f} seconds")
    
    # Test getting topic list
    print(f"\n2. Available topics: {len(loader.get_topic_list())} total")
    
    # Test loading a single topic
    print("\n3. Loading sensor_accel_0...")
    accel_df = loader.get_topic_data("sensor_accel", 0)
    
    if accel_df is not None:
        print(f"   Success! Shape: {accel_df.shape}")
        print(f"   Columns: {list(accel_df.columns)}")
        print(f"   Time range: {accel_df.index.min():.2f} to {accel_df.index.max():.2f} seconds")
        print(f"   Sample rate: ~{len(accel_df) / loader.duration_s:.1f} Hz")
        print("\n   First few rows:")
        print(accel_df.head())
    else:
        print("   Topic not found (this is OK)")
    
    # Test loading multiple topics
    print("\n4. Loading multiple topics...")
    topics = [
        ("sensor_accel", 0),
        ("battery_status", 0),
        ("vehicle_attitude", 0),
    ]
    
    data = loader.get_multiple_topics(topics)
    
    for key, df in data.items():
        if df is not None:
            rate = len(df) / loader.duration_s
            print(f"   {key}: {df.shape} at ~{rate:.1f} Hz")
        else:
            print(f"   {key}: NOT FOUND")
    
    # Test loading a topic that doesn't exist
    print("\n5. Testing graceful handling of missing topic...")
    missing_df = loader.get_topic_data("nonexistent_topic", 0)
    if missing_df is None:
        print("   Correctly returned None for missing topic")
    
    print("\n" + "=" * 70)
    print("LogLoader tests complete!")
    print("=" * 70)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_loader.py <path_to_ulg_file>")
        sys.exit(1)
    
    test_loader(sys.argv[1])
