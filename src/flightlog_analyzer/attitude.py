"""Attitude setpoint tracking analysis for PX4 ULog data."""

import re
from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .loader import LogLoader


class AttitudeAnalyzer:
	"""Compare desired and estimated attitude using PX4 quaternions."""

	AXES = ("roll", "pitch", "yaw")

	def __init__(self, loader: LogLoader, config: Optional[Dict[str, Any]] = None):
		self.loader = loader
		self.config = config or {}
		self.results: Dict[str, Any] = {}
		self._comparison: Optional[pd.DataFrame] = None

	def analyze(self, instance: int = 0) -> Dict[str, Any]:
		actual = self.loader.get_topic_data("vehicle_attitude", instance)
		desired = self.loader.get_topic_data("vehicle_attitude_setpoint", instance)
		results: Dict[str, Any] = {"available": False, "findings": []}
		if actual is None or desired is None:
			missing = []
			if actual is None:
				missing.append(f"vehicle_attitude_{instance}")
			if desired is None:
				missing.append(f"vehicle_attitude_setpoint_{instance}")
			results["reason"] = "Missing required topic(s): " + ", ".join(missing)
			self.results = results
			return results

		try:
			actual_euler = self._quaternion_to_euler(actual, "q")
			desired_euler = self._quaternion_to_euler(desired, "q_d")
		except ValueError as error:
			results["error"] = str(error)
			results["findings"] = ["WARNING: Attitude quaternion fields are unavailable"]
			self.results = results
			return results

		desired_times = desired.index.to_numpy(dtype=float)
		actual_times = actual.index.to_numpy(dtype=float)
		valid = np.isfinite(actual_times) & np.isfinite(actual_euler).all(axis=1)
		if valid.sum() < 2 or len(desired_times) < 2:
			results["error"] = "Not enough valid attitude samples for tracking analysis"
			self.results = results
			return results

		actual_times = actual_times[valid]
		actual_euler = actual_euler[valid]
		desired_valid = np.isfinite(desired_times) & np.isfinite(desired_euler).all(axis=1)
		desired_times = desired_times[desired_valid]
		desired_euler = desired_euler[desired_valid]
		if len(desired_times) < 2:
			results["error"] = "Not enough valid setpoint samples for tracking analysis"
			self.results = results
			return results

		order = np.argsort(desired_times)
		desired_times, desired_euler = desired_times[order], desired_euler[order]
		order = np.argsort(actual_times)
		actual_times, actual_euler = actual_times[order], actual_euler[order]
		in_range = (actual_times >= desired_times[0]) & (actual_times <= desired_times[-1])
		actual_times, actual_euler = actual_times[in_range], actual_euler[in_range]
		if len(actual_times) < 2:
			results["error"] = "Attitude and setpoint time ranges do not overlap"
			self.results = results
			return results

		desired_aligned = np.column_stack([
			np.interp(actual_times, desired_times, desired_euler[:, axis]) for axis in range(3)
		])
		errors = np.arctan2(np.sin(desired_aligned - actual_euler), np.cos(desired_aligned - actual_euler))
		errors_deg = np.rad2deg(errors)
		comparison = pd.DataFrame(index=actual_times)
		for axis, name in enumerate(self.AXES):
			comparison[f"{name}_actual_deg"] = np.rad2deg(actual_euler[:, axis])
			comparison[f"{name}_setpoint_deg"] = np.rad2deg(desired_aligned[:, axis])
			comparison[f"{name}_error_deg"] = errors_deg[:, axis]

		results["available"] = True
		results["num_samples"] = len(comparison)
		results["duration_s"] = float(actual_times[-1] - actual_times[0])
		results["rms_error_deg"] = {}
		results["max_error_deg"] = {}
		for axis in self.AXES:
			error_values = comparison[f"{axis}_error_deg"].to_numpy()
			results["rms_error_deg"][axis] = float(np.sqrt(np.mean(error_values ** 2)))
			results["max_error_deg"][axis] = float(np.max(np.abs(error_values)))
		results["findings"] = self._generate_findings(results)
		self._comparison = comparison
		self.results = results
		return results

	@staticmethod
	def _quaternion_to_euler(data: pd.DataFrame, prefix: str) -> np.ndarray:
		fields = [f"{prefix}[{index}]" for index in range(4)]
		if not all(field in data.columns for field in fields):
			raise ValueError(f"Missing quaternion fields: {', '.join(fields)}")
		quaternion = data[fields].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
		norms = np.linalg.norm(quaternion, axis=1)
		valid = np.isfinite(norms) & (norms > 1e-12)
		normalized = np.full_like(quaternion, np.nan)
		normalized[valid] = quaternion[valid] / norms[valid, None]
		w, x, y, z = normalized.T
		roll = np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
		pitch_arg = np.clip(2 * (w * y - z * x), -1.0, 1.0)
		pitch = np.arcsin(pitch_arg)
		yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
		return np.column_stack((roll, pitch, yaw))

	def _generate_findings(self, results: Dict[str, Any]) -> list[str]:
		rms_threshold = float(self.config.get("rms_error_threshold_deg", 5.0))
		max_threshold = float(self.config.get("max_error_threshold_deg", 15.0))
		findings = []
		for axis in self.AXES:
			rms = results["rms_error_deg"][axis]
			maximum = results["max_error_deg"][axis]
			if rms > rms_threshold:
				findings.append(f"WARNING: {axis.title()} RMS tracking error is {rms:.1f}°")
			if maximum > max_threshold:
				findings.append(f"WARNING: {axis.title()} maximum tracking error is {maximum:.1f}°")
		if not findings:
			findings.append("OK: Attitude tracking errors are within configured thresholds")
		return findings

	def plot(self, output_path: str) -> Optional[str]:
		if self._comparison is None:
			return None
		fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
		for axis, name in zip(axes, self.AXES):
			axis.plot(self._comparison.index, self._comparison[f"{name}_actual_deg"], label="Actual")
			axis.plot(self._comparison.index, self._comparison[f"{name}_setpoint_deg"], label="Setpoint", alpha=0.75)
			axis.set_ylabel(f"{name.title()} (°)")
			axis.grid(True, alpha=0.25)
			axis.legend(loc="upper right")
		axes[-1].set_xlabel("Time (s)")
		fig.tight_layout()
		fig.savefig(output_path, dpi=120)
		plt.close(fig)
		return output_path


def analyze_attitude(loader: LogLoader, config: Optional[Dict[str, Any]] = None) -> AttitudeAnalyzer:
	analyzer = AttitudeAnalyzer(loader, config)
	analyzer.analyze()
	return analyzer
