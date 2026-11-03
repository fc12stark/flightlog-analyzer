"""
Vibration Analysis Module

Analyzes accelerometer data to detect vibration issues:
- RMS vibration per axis
- Power spectral density (frequency analysis)
- Peak frequency detection
- Clipping detection

Why vibration matters:
- Excessive vibration degrades flight performance
- Can cause position estimate errors
- May indicate mechanical issues (loose props, bad bearings)
- Frequency content reveals the source (motor freq, prop freq, etc.)
"""

from typing import Optional, Dict, Any, Tuple
import numpy as np
import pandas as pd
from scipy import signal
from scipy.fft import rfft, rfftfreq
import matplotlib.pyplot as plt
from .loader import LogLoader


class VibrationAnalyzer:
    """
    Analyzes vibration from accelerometer data.

    What it needs:
    - sensor_accel topic with x, y, z fields

    What it computes:
    - RMS vibration per axis (m/s^2)
    - Power spectral density
    - Dominant frequency peaks
    - Clipping events (sensor saturation)
    """

    def __init__(self, loader: LogLoader, config: Optional[Dict] = None):
        """
        Initialize vibration analyzer.

        Args:
            loader: LogLoader instance
            config: Optional configuration dict with thresholds
        """
        self.loader = loader
        self.config = config or {}
        self.results = {}

    def analyze(self, sensor_id: int = 0) -> Dict[str, Any]:
        """
        Run full vibration analysis.

        Args:
            sensor_id: Which accelerometer instance to analyze (default 0)

        Returns:
            Dictionary with analysis results
        """
        results = {}

        # Load accelerometer data
        accel = self.loader.get_topic_data("sensor_accel", sensor_id)

        if accel is None:
            results['available'] = False
            results['reason'] = f"sensor_accel_{sensor_id} not found in log"
            self.results = results
            return results

        results['available'] = True
        results['sensor_id'] = sensor_id

        # Check if we have the required fields
        required_fields = ['x', 'y', 'z']
        if not all(field in accel.columns for field in required_fields):
            results['error'] = f"Missing required fields. Found: {list(accel.columns)}"
            self.results = results
            return results

        # Calculate sample rate
        time_index = accel.index.values
        if len(time_index) < 2:
            results['error'] = "Not enough samples for analysis"
            self.results = results
            return results

        sample_rate = self._estimate_sample_rate(time_index)
        results['sample_rate_hz'] = sample_rate
        results['num_samples'] = len(accel)
        results['duration_s'] = time_index[-1] - time_index[0]

        # Extract acceleration vectors
        ax = accel['x'].values
        ay = accel['y'].values
        az = accel['z'].values

        # RMS vibration analysis
        results['rms_x'] = self._calculate_rms(ax)
        results['rms_y'] = self._calculate_rms(ay)
        results['rms_z'] = self._calculate_rms(az)

        # Frequency analysis (if sample rate is high enough)
        if sample_rate >= 10:  # Need at least 10 Hz for meaningful frequency analysis
            results['psd_x'], results['frequencies'] = self._calculate_psd(ax, sample_rate)
            results['psd_y'], _ = self._calculate_psd(ay, sample_rate)
            results['psd_z'], _ = self._calculate_psd(az, sample_rate)

            # Find dominant peaks
            results['peaks_x'] = self._find_peaks(results['frequencies'], results['psd_x'])
            results['peaks_y'] = self._find_peaks(results['frequencies'], results['psd_y'])
            results['peaks_z'] = self._find_peaks(results['frequencies'], results['psd_z'])
        else:
            results['frequency_analysis'] = f"Skipped (sample rate {sample_rate:.1f} Hz too low, need >= 10 Hz)"

        # Clipping detection
        if 'clip_counter[0]' in accel.columns:
            results['clip_x'] = int(accel['clip_counter[0]'].max())
            results['clip_y'] = int(accel['clip_counter[1]'].max())
            results['clip_z'] = int(accel['clip_counter[2]'].max())
        else:
            results['clip_x'] = None
            results['clip_y'] = None
            results['clip_z'] = None

        # Threshold checks
        results['findings'] = self._generate_findings(results)

        self.results = results
        return results

    def _estimate_sample_rate(self, time_index: np.ndarray) -> float:
        """
        Estimate the sample rate from timestamps.

        Args:
            time_index: Array of timestamps in seconds

        Returns:
            Estimated sample rate in Hz

        How it works:
        - Calculate time differences between consecutive samples
        - Take the median (robust to outliers)
        - Sample rate = 1 / median_interval
        """
        intervals = np.diff(time_index)
        # Filter out unrealistic intervals (e.g., from timestamp corruption)
        valid_intervals = intervals[(intervals > 0) & (intervals < 10)]

        if len(valid_intervals) == 0:
            return 1.0  # Fallback

        median_interval = np.median(valid_intervals)
        sample_rate = 1.0 / median_interval

        return float(sample_rate)

    def _calculate_rms(self, data: np.ndarray) -> float:
        """
        Calculate Root Mean Square of a signal.

        Args:
            data: 1D array of values

        Returns:
            RMS value

        What is RMS:
        - Measure of signal magnitude
        - RMS = sqrt(mean(x^2))
        - For vibration, indicates overall vibration level
        - Units: m/s^2 (same as acceleration)
        """
        rms = np.sqrt(np.mean(data**2))
        return float(rms)

    def _calculate_psd(
        self,
        data: np.ndarray,
        sample_rate: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate Power Spectral Density using Welch's method.

        Args:
            data: 1D array of acceleration values
            sample_rate: Sample rate in Hz

        Returns:
            Tuple of (psd, frequencies)

        What is PSD:
        - Shows vibration power at each frequency
        - Units: (m/s^2)^2 / Hz
        - Peaks indicate dominant vibration frequencies

        Why Welch's method:
        - More robust than raw FFT
        - Averages over segments
        - Reduces noise in the estimate
        """
        # Use Welch's method for PSD estimation
        # nperseg: length of each segment (smaller = better freq resolution, more noise)
        nperseg = min(len(data), 256)

        frequencies, psd = signal.welch(
            data,
            fs=sample_rate,
            nperseg=nperseg,
            scaling='density'
        )

        return psd, frequencies

    def _find_peaks(
        self,
        frequencies: np.ndarray,
        psd: np.ndarray,
        num_peaks: int = 3
    ) -> list:
        """
        Find dominant frequency peaks in the PSD.

        Args:
            frequencies: Frequency array
            psd: Power spectral density array
            num_peaks: Number of top peaks to return

        Returns:
            List of (frequency, power) tuples

        How it works:
        - Use scipy.signal.find_peaks to detect peaks
        - Sort by peak height (power)
        - Return top N peaks

        What peaks indicate:
        - Motor/propeller frequencies
        - Structural resonances
        - Bearing defects
        """
        # Find peaks in the PSD
        peak_indices, properties = signal.find_peaks(
            psd,
            height=np.max(psd) * 0.1,  # Peaks must be at least 10% of max
            distance=int(len(psd) / 20)  # Minimum separation between peaks
        )

        if len(peak_indices) == 0:
            return []

        # Sort by peak height
        peak_heights = properties['peak_heights']
        sorted_indices = np.argsort(peak_heights)[::-1]

        # Return top N peaks
        peaks = []
        for i in sorted_indices[:num_peaks]:
            idx = peak_indices[i]
            freq = frequencies[idx]
            power = psd[idx]
            peaks.append((float(freq), float(power)))

        return peaks

    def _generate_findings(self, results: Dict[str, Any]) -> list:
        """
        Generate findings based on thresholds.

        Args:
            results: Analysis results dictionary

        Returns:
            List of finding strings

        Thresholds are tunable defaults, not industry standards.
        They are chosen based on typical multirotor performance.
        """
        findings = []

        # Get thresholds from config or use defaults
        # These are TUNABLE DEFAULTS, not industry standards
        rms_threshold = self.config.get('rms_threshold_ms2', 15.0)
        # Why 15 m/s^2? Typical value for consumer multirotors.
        # Higher = likely mechanical issue. Lower = smooth flight.

        clip_threshold = self.config.get('clip_threshold_count', 10)
        # Why 10? A few clips are OK (transients), many = sensor saturating

        # Check RMS levels
        rms_x = results.get('rms_x', 0)
        rms_y = results.get('rms_y', 0)
        rms_z = results.get('rms_z', 0)

        if rms_x > rms_threshold:
            findings.append(f"HIGH: X-axis RMS vibration {rms_x:.1f} m/s² exceeds threshold {rms_threshold} m/s²")

        if rms_y > rms_threshold:
            findings.append(f"HIGH: Y-axis RMS vibration {rms_y:.1f} m/s² exceeds threshold {rms_threshold} m/s²")

        if rms_z > rms_threshold:
            findings.append(f"HIGH: Z-axis RMS vibration {rms_z:.1f} m/s² exceeds threshold {rms_threshold} m/s²")

        # Check clipping
        clip_x = results.get('clip_x')
        clip_y = results.get('clip_y')
        clip_z = results.get('clip_z')

        if clip_x is not None and clip_x > clip_threshold:
            findings.append(f"WARNING: X-axis clipped {clip_x} times (sensor saturation)")

        if clip_y is not None and clip_y > clip_threshold:
            findings.append(f"WARNING: Y-axis clipped {clip_y} times (sensor saturation)")

        if clip_z is not None and clip_z > clip_threshold:
            findings.append(f"WARNING: Z-axis clipped {clip_z} times (sensor saturation)")

        # Check for strong frequency peaks
        if 'peaks_x' in results and len(results['peaks_x']) > 0:
            freq, power = results['peaks_x'][0]
            findings.append(f"INFO: Dominant X-axis frequency peak at {freq:.1f} Hz")

        if 'peaks_y' in results and len(results['peaks_y']) > 0:
            freq, power = results['peaks_y'][0]
            findings.append(f"INFO: Dominant Y-axis frequency peak at {freq:.1f} Hz")

        if 'peaks_z' in results and len(results['peaks_z']) > 0:
            freq, power = results['peaks_z'][0]
            findings.append(f"INFO: Dominant Z-axis frequency peak at {freq:.1f} Hz")

        if not findings:
            findings.append("OK: Vibration levels within normal range")

        return findings

    def format_report(self) -> str:
        """
        Format vibration analysis as a human-readable report.

        Returns:
            Multi-line string report
        """
        if not self.results:
            return "No analysis results. Run analyze() first."

        lines = []
        lines.append("=" * 70)
        lines.append("VIBRATION ANALYSIS")
        lines.append("=" * 70)
        lines.append("")

        if not self.results.get('available', False):
            lines.append(f"Analysis not available: {self.results.get('reason', 'Unknown')}")
            lines.append("=" * 70)
            return "\n".join(lines)

        if 'error' in self.results:
            lines.append(f"Error: {self.results['error']}")
            lines.append("=" * 70)
            return "\n".join(lines)

        # Basic info
        lines.append(f"Sensor: sensor_accel_{self.results['sensor_id']}")
        lines.append(f"Sample Rate: {self.results['sample_rate_hz']:.1f} Hz")
        lines.append(f"Samples: {self.results['num_samples']}")
        lines.append(f"Duration: {self.results['duration_s']:.1f} s")
        lines.append("")

        # RMS vibration
        lines.append("RMS Vibration:")
        lines.append(f"  X-axis: {self.results['rms_x']:.2f} m/s²")
        lines.append(f"  Y-axis: {self.results['rms_y']:.2f} m/s²")
        lines.append(f"  Z-axis: {self.results['rms_z']:.2f} m/s²")
        lines.append("")

        # Clipping
        if self.results.get('clip_x') is not None:
            lines.append("Clipping Events:")
            lines.append(f"  X-axis: {self.results['clip_x']} clips")
            lines.append(f"  Y-axis: {self.results['clip_y']} clips")
            lines.append(f"  Z-axis: {self.results['clip_z']} clips")
            lines.append("")

        # Frequency analysis
        if 'peaks_x' in self.results:
            lines.append("Dominant Frequency Peaks:")
            if len(self.results['peaks_x']) > 0:
                lines.append("  X-axis:")
                for freq, power in self.results['peaks_x']:
                    lines.append(f"    {freq:.1f} Hz (power: {power:.2e})")

            if len(self.results['peaks_y']) > 0:
                lines.append("  Y-axis:")
                for freq, power in self.results['peaks_y']:
                    lines.append(f"    {freq:.1f} Hz (power: {power:.2e})")

            if len(self.results['peaks_z']) > 0:
                lines.append("  Z-axis:")
                for freq, power in self.results['peaks_z']:
                    lines.append(f"    {freq:.1f} Hz (power: {power:.2e})")
            lines.append("")
        elif 'frequency_analysis' in self.results:
            lines.append(f"Frequency Analysis: {self.results['frequency_analysis']}")
            lines.append("")

        # Findings
        lines.append("Findings:")
        for finding in self.results.get('findings', []):
            lines.append(f"  - {finding}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)

    def plot(self, output_path: Optional[str] = None):
        """
        Generate vibration analysis plots.

        Args:
            output_path: Path to save plot (if None, displays instead)

        Creates:
        - Time-domain plot (acceleration vs time)
        - Frequency-domain plot (PSD vs frequency)
        """
        if not self.results or not self.results.get('available', False):
            print("No data to plot")
            return

        # Load the data again for plotting
        accel = self.loader.get_topic_data("sensor_accel", self.results['sensor_id'])
        if accel is None:
            return

        fig, axes = plt.subplots(2, 1, figsize=(12, 8))

        # Time-domain plot
        ax1 = axes[0]
        ax1.plot(accel.index, accel['x'], label='X', alpha=0.7)
        ax1.plot(accel.index, accel['y'], label='Y', alpha=0.7)
        ax1.plot(accel.index, accel['z'], label='Z', alpha=0.7)
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Acceleration (m/s²)')
        ax1.set_title('Accelerometer Data - Time Domain')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Frequency-domain plot
        if 'psd_x' in self.results:
            ax2 = axes[1]
            freqs = self.results['frequencies']
            ax2.semilogy(freqs, self.results['psd_x'], label='X', alpha=0.7)
            ax2.semilogy(freqs, self.results['psd_y'], label='Y', alpha=0.7)
            ax2.semilogy(freqs, self.results['psd_z'], label='Z', alpha=0.7)
            ax2.set_xlabel('Frequency (Hz)')
            ax2.set_ylabel('PSD ((m/s²)²/Hz)')
            ax2.set_title('Power Spectral Density - Frequency Domain')
            ax2.legend()
            ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        if output_path:
            plt.savefig(output_path, dpi=150)
            plt.close(fig)
            return output_path
        else:
            plt.show()
            plt.close(fig)


def analyze_vibration(loader: LogLoader, config: Optional[Dict] = None) -> VibrationAnalyzer:
    """
    Convenience function for vibration analysis.

    Args:
        loader: LogLoader instance
        config: Optional configuration dict

    Returns:
        VibrationAnalyzer with results

    Example:
        loader = LogLoader("flight.ulg")
        analyzer = analyze_vibration(loader)
        print(analyzer.format_report())
        analyzer.plot("vibration.png")
    """
    analyzer = VibrationAnalyzer(loader, config)
    analyzer.analyze()
    return analyzer
