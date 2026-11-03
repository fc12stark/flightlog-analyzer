"""Motor output balance and saturation analysis for PX4 ULog data."""

import re
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .loader import LogLoader


class MotorAnalyzer:
	"""Analyze actuator motor commands and output saturation."""

	def __init__(self, loader: LogLoader, config: Optional[Dict[str, Any]] = None):
		self.loader = loader
		self.config = config or {}
		self.results: Dict[str, Any] = {}
		self._data: Optional[pd.DataFrame] = None

	def analyze(self) -> Dict[str, Any]:
		topic_name, data = self._find_topic()
		results: Dict[str, Any] = {"available": data is not None, "findings": []}
		self._data = data
		if data is None or topic_name is None:
			results["reason"] = "No actuator_motors or actuator_outputs topic found"
			self.results = results
			return results

		field_prefix = "control" if topic_name == "actuator_motors" else "output"
		fields = sorted(
			(column for column in data.columns if re.fullmatch(rf"{field_prefix}\[\d+\]", column)),
			key=lambda column: int(re.search(r"\d+", column).group()),
		)
		if not fields:
			results["error"] = f"{topic_name} contains no {field_prefix}[n] motor fields"
			results["findings"] = ["WARNING: Motor output fields are unavailable"]
			self.results = results
			return results

		outputs = {}
		source_max = max(float(pd.to_numeric(data[field], errors="coerce").max()) for field in fields)
		for field in fields:
			values = pd.to_numeric(data[field], errors="coerce").replace([np.inf, -np.inf], np.nan)
			outputs[field] = self._to_percentage(values, topic_name, source_max)
		output_frame = pd.DataFrame(outputs, index=data.index).dropna(how="all")
		results["available"] = True
		results["topic"] = topic_name
		results["num_motors"] = len(fields)
		threshold = float(self.config.get("saturation_threshold_pct", 95.0))
		imbalance_threshold = float(self.config.get("imbalance_threshold_pct", 20.0))
		results["saturation_threshold_pct"] = threshold
		results["motor_mean_pct"] = {
			name: float(values.mean()) for name, values in output_frame.items() if values.notna().any()
		}
		results["motor_max_pct"] = {
			name: float(values.max()) for name, values in output_frame.items() if values.notna().any()
		}
		active = output_frame.where(output_frame > 1.0)
		results["saturation_fraction_pct"] = {
			name: float((values >= threshold).mean() * 100.0)
			for name, values in output_frame.items() if values.notna().any()
		}
		active_means = active.mean().dropna()
		if len(active_means) >= 2:
			results["imbalance_pct"] = float(
				(active_means.max() - active_means.min()) / max(active_means.mean(), 1e-9) * 100.0
			)
		else:
			results["imbalance_pct"] = None
		results["findings"] = self._generate_findings(results, imbalance_threshold)
		self._output_frame = output_frame
		self.results = results
		return results

	def _find_topic(self) -> tuple[Optional[str], Optional[pd.DataFrame]]:
		available = self.loader.get_topic_list()
		for name in ("actuator_motors", "actuator_outputs"):
			instances = [multi_id for topic, multi_id in available if topic == name]
			if instances:
				instance = min(instances, key=lambda value: -1 if value is None else value)
				return name, self.loader.get_topic_data(name, instance)
		return None, None

	@staticmethod
	def _to_percentage(values: pd.Series, topic_name: str, source_max: float) -> pd.Series:
		if topic_name == "actuator_outputs" and source_max > 100.0:
			return ((values - 1000.0) / 1000.0 * 100.0).clip(0.0, 100.0)
		if source_max <= 1.0:
			return (values.clip(lower=0.0) * 100.0).clip(0.0, 100.0)
		return values.clip(0.0, 100.0)

	def _generate_findings(self, results: Dict[str, Any], imbalance_threshold: float) -> List[str]:
		findings = []
		for name, fraction in results.get("saturation_fraction_pct", {}).items():
			if fraction > 0:
				findings.append(f"WARNING: {name} was at or above saturation threshold for {fraction:.1f}% of samples")
		imbalance = results.get("imbalance_pct")
		if imbalance is not None and imbalance > imbalance_threshold:
			findings.append(f"WARNING: Motor output imbalance is {imbalance:.1f}%")
		if not findings:
			findings.append("OK: No sustained motor saturation or significant output imbalance detected")
		return findings

	def plot(self, output_path: str) -> Optional[str]:
		if self._data is None:
			return None
		if not hasattr(self, "_output_frame"):
			self.analyze()
		frame = getattr(self, "_output_frame", None)
		if frame is None or frame.empty:
			return None
		fig, axis = plt.subplots(figsize=(10, 4))
		for name, values in frame.items():
			axis.plot(frame.index, values, label=name)
		axis.set_xlabel("Time (s)")
		axis.set_ylabel("Output (%)")
		axis.set_ylim(0, 105)
		axis.grid(True, alpha=0.25)
		axis.legend(ncol=4, fontsize="small")
		fig.tight_layout()
		fig.savefig(output_path, dpi=120)
		plt.close(fig)
		return output_path


def analyze_motors(loader: LogLoader, config: Optional[Dict[str, Any]] = None) -> MotorAnalyzer:
	analyzer = MotorAnalyzer(loader, config)
	analyzer.analyze()
	return analyzer
