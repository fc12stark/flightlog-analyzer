#!/usr/bin/env python3
"""
Test script for the FlightOverview module.

This demonstrates and validates the overview analysis.
"""

import sys
from src.flightlog_analyzer.loader import LogLoader
from src.flightlog_analyzer.overview import generate_overview


def test_overview(ulg_path: str):
    """Test the FlightOverview with a real ULog file."""

    print("=" * 70)
    print("Testing FlightOverview Module")
    print("=" * 70)
    print()

    # Load the log
    print(f"Loading: {ulg_path}")
    loader = LogLoader(ulg_path)
    print(f"Duration: {loader.duration_s:.1f} seconds")
    print()

    # Generate overview
    print("Running overview analysis...")
    overview = generate_overview(loader)
    print()

    # Display the formatted report
    print(overview.format_report())
    print()

    # Show raw results for inspection
    print("=" * 70)
    print("Raw Results (for debugging):")
    print("=" * 70)
    for key, value in overview.results.items():
        if key == 'flight_modes' and value is not None:
            print(f"{key}:")
            for mode_name, duration, pct in value:
                print(f"  {mode_name}: {duration:.1f}s ({pct:.1f}%)")
        else:
            print(f"{key}: {value}")
    print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_overview.py <path_to_ulg_file>")
        sys.exit(1)

    test_overview(sys.argv[1])
