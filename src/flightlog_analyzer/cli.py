#!/usr/bin/env python3
"""Command-line entry point for full PX4 flight-log analysis."""

import argparse
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Sequence

from .attitude import AttitudeAnalyzer
from .battery import BatteryAnalyzer
from .loader import LogLoader
from .motor import MotorAnalyzer
from .overview import generate_overview
from .report import generate_report
from .vibration import VibrationAnalyzer


def _load_config(config_path: Optional[Path]) -> Dict[str, Any]:
    use_default_config = config_path is None
    if config_path is None:
        candidate = Path(__file__).resolve().parents[2] / "config" / "thresholds.yaml"
        config_path = candidate if candidate.is_file() else None
    if config_path is None:
        return {}
    try:
        import yaml
    except ImportError as error:
        if use_default_config:
            return {}
        raise RuntimeError("PyYAML is required to load threshold configuration") from error
    with config_path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}
    if not isinstance(config, dict):
        raise ValueError("Threshold configuration must contain a YAML mapping")
    return config


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze a PX4 ULog and generate an HTML flight report.")
    parser.add_argument("ulg_file", type=Path, help="Path to the PX4 .ulg flight log")
    parser.add_argument("-o", "--output", type=Path, help="HTML report path (defaults beside the log)")
    parser.add_argument("--config", type=Path, help="YAML threshold configuration file")
    parser.add_argument("--sensor-id", type=int, default=0, help="Accelerometer instance to analyze (default: 0)")
    args = parser.parse_args(argv)

    if not args.ulg_file.is_file():
        parser.error(f"ULog file does not exist: {args.ulg_file}")
    if args.ulg_file.suffix.lower() != ".ulg":
        parser.error("input file must have a .ulg extension")

    output = args.output or args.ulg_file.with_name(f"{args.ulg_file.stem}_report.html")
    try:
        config = _load_config(args.config)
        loader = LogLoader(str(args.ulg_file))
        analyses = {
            "Flight overview": generate_overview(loader),
            "Vibration": VibrationAnalyzer(loader, config.get("vibration", {})),
            "Battery": BatteryAnalyzer(loader, config.get("battery", {})),
            "Motors": MotorAnalyzer(loader, config.get("motor", {})),
            "Attitude tracking": AttitudeAnalyzer(loader, config.get("attitude", {})),
        }
        analyses["Vibration"].analyze(args.sensor_id)
        analyses["Battery"].analyze()
        analyses["Motors"].analyze()
        analyses["Attitude tracking"].analyze()
        generate_report(str(args.ulg_file), analyses, str(output))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Flight report saved to: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
