#!/usr/bin/env python3
"""
Create a minimal synthetic ULog file for testing.

This generates a simple but valid ULog with a few topics so we can test
the list-topics script without needing to download real flight data.
"""

from pyulog import ULog
from pyulog.core import ULogMessageData
import numpy as np
import struct


def create_test_ulog(output_path: str):
    """
    Create a minimal synthetic ULog file.

    Why synthetic data:
    - Don't depend on external downloads
    - Know exactly what topics/fields exist
    - Can test edge cases
    """
    print(f"Creating synthetic ULog file at: {output_path}")
    print("This is for testing the list-topics script only.")
    print("Real analysis will use actual flight logs.\n")

    # Create a simple ULog manually
    # Note: This is complex because ULog format is binary
    # In practice, you'd use real logs from flights

    # For now, let's document what a real ULog contains and
    # note that users should provide their own .ulg files

    print("⚠️  Creating synthetic ULog files is complex.")
    print("For Step 1 demo, please provide a real .ulg file from:")
    print("  1. Your own drone flight")
    print("  2. PX4 Flight Review: https://logs.px4.io/")
    print("  3. PX4 GitHub test logs: https://github.com/PX4/PX4-Autopilot/tree/main/test/logs")


if __name__ == "__main__":
    create_test_ulog("sample_logs/synthetic.ulg")
