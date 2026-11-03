# flightlog-analyzer

A Python command-line tool that analyzes PX4 ULog (.ulg) files and produces detailed flight reports.

## What it does

This tool reads a PX4 ULog file from a drone flight and generates a standalone HTML report showing:
- Flight overview (duration, modes, altitude, speed)
- Vibration analysis (accelerometer data, frequency analysis)
- Battery health (voltage, current, internal resistance)
- Motor performance (actuator outputs, saturation, balance)
- Attitude tracking quality (setpoint vs actual)
- Ranked findings summary with linked evidence plots

Analyses skip unavailable topics gracefully and report when a result cannot be calculated.

## Installation

```bash
# Clone the repository
cd flightlog-analyzer

# Install in development mode
pip install -e ".[dev]"
```

## Requirements

- Python 3.11 or higher
- Dependencies: pyulog, pandas, numpy, scipy, matplotlib, PyYAML, pytest

## Usage

### List topics in a ULog file

Before analyzing, you can inspect what data is available in your log:

```bash
list-topics path/to/your_flight.ulg
```

This shows all topics and their fields, helping you understand what data was logged.

### Analyze a flight

```bash
flightlog-analyzer path/to/your_flight.ulg
```

This generates `your_flight_report.html` in the same directory as the log file. The report embeds its plots and can be opened offline. You can choose a different output path and threshold configuration:

```bash
flightlog-analyzer path/to/your_flight.ulg --output reports/flight.html
flightlog-analyzer path/to/your_flight.ulg --config config/thresholds.yaml
```

The report contains flight overview, vibration, battery, motor-output and attitude-tracking sections. Battery resistance is an approximate voltage/current estimate, and threshold findings are indicators rather than a diagnosis.

## Example Reports

*Coming soon: links to example reports from real flights*

## Limitations

- Analysis quality depends on what topics were logged during the flight
- Topic names vary between PX4 versions; missing topics are skipped gracefully
- Thresholds are tunable defaults, not industry standards
- Internal resistance estimation requires sufficient current variation
- Frequency analysis requires steady-state flight segments for best results

## How I used coding agents on this project

*To be completed after project completion*

This section will describe:
- What worked well when using AI assistance
- What required manual correction or deeper investigation
- Lessons learned about AI-assisted development

## Project Structure

```
flightlog-analyzer/
├── src/
│   └── flightlog_analyzer/
│       ├── __init__.py
│       ├── cli.py              # Main entry point
│       ├── list_topics.py      # Topic listing utility
│       ├── loader.py           # ULog data loader
│       ├── overview.py         # Flight overview module
│       ├── vibration.py        # Vibration analysis
│       ├── battery.py          # Battery analysis
│       ├── motor.py            # Motor analysis
│       ├── attitude.py         # Attitude tracking analysis
│       └── report.py           # HTML report generator
├── tests/
│   └── test_*.py               # Pytest unit tests
├── config/
│   └── thresholds.yaml         # Tunable analysis thresholds
├── pyproject.toml
└── README.md
```

## License

MIT License (or specify your chosen license)
