"""Battery health and energy analysis for PX4 ULog data."""

from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .loader import LogLoader


class BatteryAnalyzer:
	"""Analyze battery voltage, current, energy use, and voltage sag."""

	def __init__(self, loader: LogLoader, config: Optional[Dict[str, Any]] = None):
		self.loader = loader
		self.config = config or {}
		self.results: Dict[str, Any] = {}
		self._data: Optional[pd.DataFrame] = None

	def analyze(self, battery_id: int = 0) -> Dict[str, Any]:
		data = self.loader.get_topic_data("battery_status", battery_id)
		results: Dict[str, Any] = {"available": data is not None, "findings": []}
		self._data = data
		if data is None:
			results["reason"] = f"battery_status_{battery_id} not found in log"
			self.results = results
			return results

		results["battery_id"] = battery_id
		voltage = self._numeric_column(data, "voltage_v")
		current = self._numeric_column(data, "current_a")
		cell_count = self._numeric_column(data, "cell_count")

		if voltage is None:
			results["error"] = "battery_status is missing voltage_v"
			results["findings"] = ["WARNING: Battery voltage data is unavailable"]
			self.results = results
			return results

		results["min_voltage_v"] = float(voltage.min())
		results["max_voltage_v"] = float(voltage.max())
		results["mean_voltage_v"] = float(voltage.mean())
		cells = int(round(cell_count.median())) if cell_count is not None else 0
		results["cell_count"] = cells or None
		if cells > 0:
			results["min_voltage_per_cell"] = float(voltage.min() / cells)
			results["mean_voltage_per_cell"] = float(voltage.mean() / cells)

		if current is not None:
			valid = voltage.notna() & current.notna()
			times = data.index.to_numpy(dtype=float)[valid.to_numpy()]
			volts = voltage[valid].to_numpy(dtype=float)
			amps = current[valid].to_numpy(dtype=float)
			if len(amps) >= 2:
				order = np.argsort(times)
				times, volts, amps = times[order], volts[order], amps[order]
				watts = np.maximum(amps, 0) * volts
				integrate = getattr(np, "trapezoid", None) or np.trapz
				results["energy_consumed_wh"] = float(integrate(watts, times) / 3600.0)
				results["current_mean_a"] = float(np.mean(amps))
				results["current_max_a"] = float(np.max(amps))
				results["voltage_sag_v"] = float(np.max(volts) - np.min(volts))
				if np.ptp(amps) >= float(self.config.get("min_current_variation_a", 1.0)):
					slope = float(np.polyfit(amps, volts, 1)[0])
					resistance = max(0.0, -slope)
					results["estimated_internal_resistance_ohm"] = resistance
				else:
					results["estimated_internal_resistance_ohm"] = None
			else:
				results["estimated_internal_resistance_ohm"] = None
		else:
			results["estimated_internal_resistance_ohm"] = None

		results["findings"] = self._generate_findings(results)
		self.results = results
		return results

	@staticmethod
	def _numeric_column(data: pd.DataFrame, column: str) -> Optional[pd.Series]:
		if column not in data.columns:
			return None
		values = pd.to_numeric(data[column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
		return values if not values.empty else None

	def _generate_findings(self, results: Dict[str, Any]) -> list[str]:
		findings = []
		per_cell = results.get("min_voltage_per_cell")
		threshold = float(self.config.get("min_voltage_per_cell", 3.5))
		if per_cell is not None and per_cell < threshold:
			findings.append(f"HIGH: Minimum cell voltage {per_cell:.2f} V is below {threshold:.2f} V")
		sag = results.get("voltage_sag_v")
		max_sag = float(self.config.get("max_voltage_sag", 0.5))
		if sag is not None and sag > max_sag:
			findings.append(f"WARNING: Voltage varied by {sag:.2f} V during the log")
		if results.get("estimated_internal_resistance_ohm") is not None:
			findings.append("INFO: Internal resistance is a rough voltage-current estimate")
		if not findings:
			findings.append("OK: No battery warning thresholds were exceeded")
		return findings

	def plot(self, output_path: str) -> Optional[str]:
		if self._data is None:
			return None
		voltage = self._numeric_column(self._data, "voltage_v")
		current = self._numeric_column(self._data, "current_a")
		if voltage is None:
			return None
		fig, axis = plt.subplots(figsize=(10, 4))
		axis.plot(voltage.index, voltage, color="#2563eb", label="Voltage (V)")
		axis.set_xlabel("Time (s)")
		axis.set_ylabel("Voltage (V)")
		if current is not None:
			current_axis = axis.twinx()
			current_axis.plot(current.index, current, color="#dc2626", alpha=0.7, label="Current (A)")
			current_axis.set_ylabel("Current (A)")
		axis.grid(True, alpha=0.25)
		fig.tight_layout()
		fig.savefig(output_path, dpi=120)
		plt.close(fig)
		return output_path


def analyze_battery(loader: LogLoader, config: Optional[Dict[str, Any]] = None) -> BatteryAnalyzer:
	analyzer = BatteryAnalyzer(loader, config)
	analyzer.analyze()
	return analyzer
