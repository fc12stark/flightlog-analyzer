#!/usr/bin/env python3
"""
Test script for the VibrationAnalyzer module.

This demonstrates and validates vibration analysis.
"""

import sys
from src.flightlog_analyzer.loader import LogLoader
from src.flightlog_analyzer.vibration import analyze_vibration


def test_vibration(ulg_path: str):
    """Test the VibrationAnalyzer with a real ULog file."""

    print("=" * 70)
    print("Testing VibrationAnalyzer Module")
    print("=" * 70)
    print()

    # Load the log
    print(f"Loading: {ulg_path}")
    loader = LogLoader(ulg_path)
    print(f"Duration: {loader.duration_s:.1f} seconds")
    print()

    # Run vibration analysis with custom thresholds
    config = {
        'rms_threshold_ms2': 15.0,  # Tunable default, not industry standard
        'clip_threshold_count': 10,
    }

    print("Running vibration analysis...")
    print(f"Config: RMS threshold = {config['rms_threshold_ms2']} m/s²")
    print(f"        Clip threshold = {config['clip_threshold_count']} events")
    print()

    analyzer = analyze_vibration(loader, config)

    # Display the formatted report
    print(analyzer.format_report())
    print()

    # Show raw results for inspection
    print("=" * 70)
    print("Raw Results (for debugging):")
    print("=" * 70)
    for key, value in analyzer.results.items():
        if key in ['psd_x', 'psd_y', 'psd_z', 'frequencies']:
            print(f"{key}: array with {len(value)} elements")
        else:
            print(f"{key}: {value}")
    print()

    # Generate plot
    print("Generating plot...")
    try:
        analyzer.plot("vibration_analysis.png")
        print("Plot saved to vibration_analysis.png")
    except Exception as e:
        print(f"Could not generate plot: {e}")
    print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_vibration.py <path_to_ulg_file>")
        sys.exit(1)

    test_vibration(sys.argv[1])
