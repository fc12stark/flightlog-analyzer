"""Self-contained HTML flight report generation."""

import base64
import html
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import numpy as np


_SEVERITY_ORDER = {"HIGH": 0, "CRITICAL": 0, "WARNING": 1, "INFO": 2, "OK": 3}


class ReportGenerator:
	"""Render analyzer results and available plots into a standalone HTML file."""

	def __init__(self, source: str, analyses: Mapping[str, Any], title: Optional[str] = None):
		self.source = source
		self.analyses = analyses
		self.title = title or f"Flight report — {Path(source).name}"

	def generate(self, output_path: str) -> str:
		output = Path(output_path)
		output.parent.mkdir(parents=True, exist_ok=True)
		sections = []
		findings = []
		with tempfile.TemporaryDirectory() as temporary_directory:
			for name, analyzer in self.analyses.items():
				results = getattr(analyzer, "results", analyzer)
				if not isinstance(results, dict):
					results = {"result": results}
				section_id = self._section_id(name)
				plot_data = self._make_plot(analyzer, Path(temporary_directory) / f"{section_id}.png")
				for finding in results.get("findings", []):
					text = str(finding)
					severity = self._severity(text)
					findings.append((severity, name, section_id, text, plot_data is not None))
				sections.append(self._render_section(name, section_id, results, plot_data))

			findings.sort(key=lambda item: (_SEVERITY_ORDER.get(item[0], 2), item[1]))
			summary = self._render_findings(findings)
			document = self._document(summary, "\n".join(sections))
			output.write_text(document, encoding="utf-8")
		return str(output)

	@staticmethod
	def _section_id(name: str) -> str:
		slug = "".join(char.lower() if char.isalnum() else "-" for char in name).strip("-")
		return slug or "analysis"

	@staticmethod
	def _severity(finding: str) -> str:
		prefix = finding.split(":", 1)[0].strip().upper()
		return prefix if prefix in _SEVERITY_ORDER else "INFO"

	@staticmethod
	def _make_plot(analyzer: Any, image_path: Path) -> Optional[str]:
		plot = getattr(analyzer, "plot", None)
		if not callable(plot):
			return None
		try:
			plot(str(image_path))
			if image_path.exists():
				encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
				return f"data:image/png;base64,{encoded}"
		except (OSError, ValueError, RuntimeError):
			return None
		return None

	@classmethod
	def _render_findings(cls, findings: list[tuple]) -> str:
		if not findings:
			return "<p>No hay hallazgos disponibles.</p>"
		items = []
		for severity, name, section_id, text, has_plot in findings:
			link = f" <a href=\"#{section_id}-plot\">Ver gráfica</a>" if has_plot else f" <a href=\"#{section_id}\">Ver análisis</a>"
			detail = text.split(":", 1)[1].strip() if ":" in text else text
			items.append(
				f"<li class=\"severity-{severity.lower()}\"><strong>{html.escape(severity)}</strong> "
				f"<span>{html.escape(name)}: {html.escape(detail)}</span>{link}</li>"
			)
		return "<ol class=\"findings\">" + "".join(items) + "</ol>"

	@classmethod
	def _render_section(cls, name: str, section_id: str, results: Dict[str, Any], plot_data: Optional[str]) -> str:
		rows = []
		for key, value in results.items():
			if key == "findings" or isinstance(value, np.ndarray):
				continue
			rendered = cls._format_value(value)
			if rendered is not None:
				rows.append(
					f"<tr><th>{html.escape(str(key.replace('_', ' ').title()))}</th>"
					f"<td>{html.escape(rendered)}</td></tr>"
				)
		table = "<table><tbody>" + "".join(rows) + "</tbody></table>" if rows else "<p>No hay métricas disponibles.</p>"
		findings = results.get("findings", [])
		finding_list = "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in findings) + "</ul>" if findings else ""
		plot = ""
		if plot_data:
			plot = f"<figure id=\"{section_id}-plot\"><img src=\"{plot_data}\" alt=\"Gráfica de {html.escape(name)}\"><figcaption>Gráfica de {html.escape(name)}</figcaption></figure>"
		return (
			f"<details open id=\"{section_id}\"><summary>{html.escape(name)}</summary>"
			f"{table}{finding_list}{plot}</details>"
		)

	@staticmethod
	def _format_value(value: Any) -> Optional[str]:
		if value is None:
			return "No disponible"
		if isinstance(value, (str, bool, int)):
			return str(value)
		if isinstance(value, float):
			return f"{value:.3f}" if np.isfinite(value) else "No disponible"
		if isinstance(value, np.generic):
			return ReportGenerator._format_value(value.item())
		if isinstance(value, dict):
			return "; ".join(f"{key}: {ReportGenerator._format_value(item)}" for key, item in value.items())
		if isinstance(value, (list, tuple)):
			if len(value) > 20:
				return f"{len(value)} elementos"
			return ", ".join(str(item) for item in value)
		return str(value)

	def _document(self, summary: str, sections: str) -> str:
		title = html.escape(self.title)
		source = html.escape(self.source)
		return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, sans-serif; background: #f3f4f6; color: #172033; }}
body {{ max-width: 1100px; margin: 2rem auto; padding: 0 1rem; }}
header, section, details {{ background: white; border-radius: .6rem; padding: 1.2rem; margin: 1rem 0; box-shadow: 0 1px 5px #0001; }}
h1, h2 {{ margin-top: 0; }}
details summary {{ font-size: 1.2rem; font-weight: 650; cursor: pointer; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ text-align: left; padding: .5rem; border-bottom: 1px solid #e5e7eb; }}
th {{ width: 35%; }}
figure {{ margin: 1rem 0 0; }}
figure img {{ width: 100%; height: auto; }}
figcaption, .source {{ color: #596579; }}
.findings {{ padding-left: 1.5rem; }}
.findings li {{ margin: .55rem 0; }}
.severity-high, .severity-critical {{ color: #b91c1c; }}
.severity-warning {{ color: #a16207; }}
a {{ margin-left: .4rem; }}
</style>
</head>
<body>
<header><h1>{title}</h1><p class="source">Registro: {source}</p></header>
<section><h2>Hallazgos</h2>{summary}</section>
{sections}
</body>
</html>
"""


def generate_report(source: str, analyses: Mapping[str, Any], output_path: str, title: Optional[str] = None) -> str:
	return ReportGenerator(source, analyses, title).generate(output_path)
