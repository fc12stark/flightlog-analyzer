import math
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from flightlog_analyzer.attitude import AttitudeAnalyzer
from flightlog_analyzer.battery import BatteryAnalyzer
from flightlog_analyzer.cli import main
from flightlog_analyzer.motor import MotorAnalyzer
from flightlog_analyzer.report import generate_report


class FakeLoader:
	def __init__(self, topics):
		self.topics = topics
		self.duration_s = 10.0
		self.start_time_us = 1_000_000

	def get_topic_data(self, name, instance=0):
		return self.topics.get((name, instance))

	def get_topic_list(self):
		return [(name, instance) for name, instance in self.topics]


def test_battery_calculates_energy_and_internal_resistance():
	times = np.arange(4, dtype=float)
	data = pd.DataFrame({
		"voltage_v": [12.6, 12.3, 12.0, 11.7],
		"current_a": [0.0, 2.0, 4.0, 6.0],
		"cell_count": [3, 3, 3, 3],
	}, index=times)
	results = BatteryAnalyzer(FakeLoader({("battery_status", 0): data})).analyze()
	assert results["available"] is True
	assert math.isclose(results["estimated_internal_resistance_ohm"], 0.15, rel_tol=1e-8)
	assert math.isclose(results["energy_consumed_wh"], 107.7 / 3600, rel_tol=1e-8)
	assert math.isclose(results["min_voltage_per_cell"], 3.9)


def test_battery_reports_missing_topic_gracefully():
	results = BatteryAnalyzer(FakeLoader({})).analyze()
	assert results["available"] is False
	assert "reason" in results


def test_motor_analysis_detects_saturation_and_imbalance():
	data = pd.DataFrame({
		"control[0]": [0.2, 0.98, 0.99],
		"control[1]": [0.2, 0.4, 0.5],
	}, index=[0.0, 1.0, 2.0])
	loader = FakeLoader({("actuator_motors", 0): data})
	results = MotorAnalyzer(loader).analyze()
	assert results["available"] is True
	assert results["saturation_fraction_pct"]["control[0]"] > 0
	assert results["imbalance_pct"] > 20
	assert any("saturation" in finding.lower() for finding in results["findings"])


def test_attitude_analysis_measures_yaw_tracking_error():
	times = np.array([0.0, 1.0, 2.0])
	angle = math.radians(10.0)
	actual = pd.DataFrame({
		"q[0]": [1.0] * 3, "q[1]": [0.0] * 3, "q[2]": [0.0] * 3, "q[3]": [0.0] * 3,
	}, index=times)
	desired = pd.DataFrame({
		"q_d[0]": [math.cos(angle / 2)] * 3,
		"q_d[1]": [0.0] * 3,
		"q_d[2]": [0.0] * 3,
		"q_d[3]": [math.sin(angle / 2)] * 3,
	}, index=times)
	loader = FakeLoader({("vehicle_attitude", 0): actual, ("vehicle_attitude_setpoint", 0): desired})
	results = AttitudeAnalyzer(loader).analyze()
	assert results["available"] is True
	assert math.isclose(results["rms_error_deg"]["yaw"], 10.0, abs_tol=1e-8)
	assert math.isclose(results["rms_error_deg"]["roll"], 0.0, abs_tol=1e-8)


def test_report_embeds_plots_and_escapes_html(tmp_path):
	class Analyzer:
		results = {"findings": ["WARNING: <unsafe>"], "score": 1.0}

		def plot(self, output_path):
			Path(output_path).write_bytes(b"png")
			return output_path

	output = tmp_path / "report.html"
	generate_report("test.ulg", {"Battery": Analyzer()}, str(output))
	content = output.read_text(encoding="utf-8")
	assert "data:image/png;base64,cG5n" in content
	assert "&lt;unsafe&gt;" in content
	assert "battery-plot" in content


def test_cli_wires_analyses_and_default_report_path(tmp_path):
	source = tmp_path / "flight.ulg"
	source.write_bytes(b"test")
	output = source.with_name("flight_report.html")

	class StubAnalyzer:
		def __init__(self, *args, **kwargs):
			self.results = {}

		def analyze(self, *args, **kwargs):
			return self.results

	class StubOverview:
		results = {"duration_s": 10.0}

	with patch("flightlog_analyzer.cli.LogLoader"), \
		 patch("flightlog_analyzer.cli.generate_overview", return_value=StubOverview()), \
		 patch("flightlog_analyzer.cli.VibrationAnalyzer", StubAnalyzer), \
		 patch("flightlog_analyzer.cli.BatteryAnalyzer", StubAnalyzer), \
		 patch("flightlog_analyzer.cli.MotorAnalyzer", StubAnalyzer), \
		 patch("flightlog_analyzer.cli.AttitudeAnalyzer", StubAnalyzer), \
		  patch("flightlog_analyzer.cli._load_config", return_value={}), \
		 patch("flightlog_analyzer.cli.generate_report") as report:
		assert main([str(source)]) == 0

	assert report.call_args.args[2] == str(output)
