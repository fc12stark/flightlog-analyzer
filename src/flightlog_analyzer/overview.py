"""
Flight Overview Module

Generates basic flight statistics:
- Duration
- Flight modes over time
- Maximum altitude and speed
- Distance traveled

Why this module:
- Provides context for all other analyses
- Quick sanity check of the log
- First thing a pilot wants to know: "What happened?"
"""

from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from .loader import LogLoader


# Flight mode names for nav_state field
# These are the standard PX4 navigation states
# Source: PX4 vehicle_status.msg definition
NAV_STATE_NAMES = {
    0: "Manual",
    1: "Altitude Control",
    2: "Position Control",
    3: "Auto Mission",
    4: "Auto Loiter",
    5: "Auto RTL (Return to Launch)",
    6: "RC Recovery",
    7: "Auto RTL (GPS Failure)",
    8: "Auto Land (Engine Failure)",
    9: "Auto Land (GPS Failure)",
    10: "Acro",
    11: "Unused",
    12: "Descend",
    13: "Termination",
    14: "Offboard",
    15: "Stabilized",
    16: "Auto Takeoff",
    17: "Auto Land",
    18: "Auto Follow Target",
    19: "Auto Precland",
    20: "Orbit",
    21: "Auto VTOL Takeoff",
}


class FlightOverview:
    """
    Analyzes basic flight characteristics.

    What it needs:
    - vehicle_local_position: for altitude, speed, distance
    - vehicle_status: for flight modes and arming state

    What it handles gracefully:
    - Missing topics (returns None for those stats)
    - Invalid data (filters out bad values)
    """

    def __init__(self, loader: LogLoader):
        """
        Initialize with a LogLoader.

        Args:
            loader: LogLoader instance with an opened ULog file
        """
        self.loader = loader
        self.results = {}

    def analyze(self) -> Dict[str, Any]:
        """
        Run the full overview analysis.

        Returns:
            Dictionary with overview statistics

        What it computes:
        - duration_s: Total log duration
        - armed_duration_s: Time motors were armed
        - max_altitude_m: Highest point above takeoff
        - max_speed_ms: Fastest horizontal speed
        - distance_traveled_m: Total horizontal distance
        - flight_modes: List of (mode_name, duration_s) tuples
        """
        results = {}

        # Basic duration (always available)
        results['duration_s'] = self.loader.duration_s
        results['start_time_s'] = self.loader.start_time_us / 1e6

        # Load vehicle status for flight modes and arming
        vehicle_status = self.loader.get_topic_data("vehicle_status", 0)
        if vehicle_status is not None:
            results['armed_duration_s'] = self._analyze_armed_time(vehicle_status)
            results['flight_modes'] = self._analyze_flight_modes(vehicle_status)
        else:
            results['armed_duration_s'] = None
            results['flight_modes'] = None

        # Load vehicle position for altitude and speed
        vehicle_pos = self.loader.get_topic_data("vehicle_local_position", 0)
        if vehicle_pos is not None:
            results['max_altitude_m'] = self._analyze_altitude(vehicle_pos)
            results['max_speed_ms'] = self._analyze_speed(vehicle_pos)
            results['distance_traveled_m'] = self._analyze_distance(vehicle_pos)
        else:
            results['max_altitude_m'] = None
            results['max_speed_ms'] = None
            results['distance_traveled_m'] = None

        self.results = results
        return results

    def _analyze_armed_time(self, vehicle_status: pd.DataFrame) -> Optional[float]:
        """
        Calculate how long the motors were armed.

        Args:
            vehicle_status: DataFrame with arming_state field

        Returns:
            Armed duration in seconds, or None if data unavailable

        How it works:
        - arming_state field: 1 = standby, 2 = armed
        - Count time samples where arming_state == 2
        - Multiply by average sample interval

        What could go wrong:
        - Corrupt timestamps (very large or negative values)
        - Solution: filter out unrealistic timestamps
        """
        if 'arming_state' not in vehicle_status.columns:
            return None

        # Filter out corrupt timestamps
        # Valid timestamps should be between 0 and log duration
        time_index = vehicle_status.index.values
        valid_time_mask = (time_index >= 0) & (time_index <= self.loader.duration_s * 1.1)

        if not valid_time_mask.any():
            return None

        # Apply the filter
        filtered_status = vehicle_status[valid_time_mask]

        if len(filtered_status) < 2:
            return None

        # Find armed periods (arming_state == 2)
        armed_mask = filtered_status['arming_state'] == 2

        if not armed_mask.any():
            return 0.0

        # Calculate time deltas between samples
        time_index = filtered_status.index.values

        # Approximate: count armed samples * average sample interval
        armed_samples = armed_mask.sum()
        avg_interval = (time_index[-1] - time_index[0]) / len(time_index)
        armed_duration = armed_samples * avg_interval

        return float(armed_duration)

    def _analyze_flight_modes(self, vehicle_status: pd.DataFrame) -> Optional[list]:
        """
        Extract flight modes and their durations.

        Args:
            vehicle_status: DataFrame with nav_state field

        Returns:
            List of (mode_name, duration_s, percentage) tuples

        How it works:
        - nav_state field encodes the flight mode (0-21)
        - Group by mode and sum time in each
        - Map numeric codes to human-readable names
        """
        if 'nav_state' not in vehicle_status.columns:
            return None

        # Filter out corrupt timestamps
        time_index = vehicle_status.index.values
        valid_time_mask = (time_index >= 0) & (time_index <= self.loader.duration_s * 1.1)

        if not valid_time_mask.any():
            return None

        filtered_status = vehicle_status[valid_time_mask]

        # Get mode transitions
        nav_states = filtered_status['nav_state'].values
        time_index = filtered_status.index.values

        if len(nav_states) < 2:
            return None

        # Calculate time in each mode
        mode_durations = {}

        for i in range(len(nav_states) - 1):
            mode = int(nav_states[i])
            duration = time_index[i+1] - time_index[i]

            # Skip negative or unrealistic durations
            if duration < 0 or duration > self.loader.duration_s:
                continue

            if mode not in mode_durations:
                mode_durations[mode] = 0.0
            mode_durations[mode] += duration

        if not mode_durations:
            return None

        # Convert to list with percentages
        total_time = sum(mode_durations.values())
        mode_list = []

        for mode_num, duration in sorted(mode_durations.items(), key=lambda x: x[1], reverse=True):
            mode_name = NAV_STATE_NAMES.get(mode_num, f"Unknown ({mode_num})")
            percentage = (duration / total_time) * 100 if total_time > 0 else 0
            mode_list.append((mode_name, float(duration), float(percentage)))

        return mode_list

    def _analyze_altitude(self, vehicle_pos: pd.DataFrame) -> Optional[float]:
        """
        Find maximum altitude above takeoff.

        Args:
            vehicle_pos: DataFrame with z field

        Returns:
            Maximum altitude in meters (negative because NED frame)

        What is z in PX4:
        - PX4 uses NED (North-East-Down) frame
        - z is positive DOWN
        - So altitude = -z
        - Takeoff point is z = 0 (approximately)
        """
        if 'z' not in vehicle_pos.columns:
            return None

        # Filter valid data
        if 'z_valid' in vehicle_pos.columns:
            z_valid_mask = vehicle_pos['z_valid'].astype(bool)
            z_data = vehicle_pos.loc[z_valid_mask, 'z']
        else:
            z_data = vehicle_pos['z']

        if len(z_data) == 0:
            return None

        # Maximum altitude = most negative z value (NED frame)
        # Return as positive altitude
        max_altitude = -z_data.min()

        return float(max_altitude)

    def _analyze_speed(self, vehicle_pos: pd.DataFrame) -> Optional[float]:
        """
        Find maximum horizontal speed.

        Args:
            vehicle_pos: DataFrame with vx, vy fields

        Returns:
            Maximum horizontal speed in m/s

        How it's calculated:
        - vx = velocity North (m/s)
        - vy = velocity East (m/s)
        - horizontal_speed = sqrt(vx^2 + vy^2)
        """
        if 'vx' not in vehicle_pos.columns or 'vy' not in vehicle_pos.columns:
            return None

        # Filter valid velocity data
        if 'v_xy_valid' in vehicle_pos.columns:
            v_valid_mask = vehicle_pos['v_xy_valid'].astype(bool)
            valid_data = vehicle_pos[v_valid_mask]
        else:
            valid_data = vehicle_pos

        if len(valid_data) == 0:
            return None

        # Calculate horizontal speed magnitude
        vx = valid_data['vx'].values
        vy = valid_data['vy'].values
        horizontal_speed = np.sqrt(vx**2 + vy**2)

        max_speed = np.max(horizontal_speed)

        return float(max_speed)

    def _analyze_distance(self, vehicle_pos: pd.DataFrame) -> Optional[float]:
        """
        Calculate total distance traveled (approximate).

        Args:
            vehicle_pos: DataFrame with x, y fields

        Returns:
            Total horizontal distance in meters

        How it's calculated:
        - x, y are position in NED frame (meters)
        - Sum up distances between consecutive points
        - This is approximate (straight lines between samples)
        """
        if 'x' not in vehicle_pos.columns or 'y' not in vehicle_pos.columns:
            return None

        # Filter valid position data
        if 'xy_valid' in vehicle_pos.columns:
            xy_valid_mask = vehicle_pos['xy_valid'].astype(bool)
            valid_data = vehicle_pos[xy_valid_mask]
        else:
            valid_data = vehicle_pos

        if len(valid_data) < 2:
            return None

        x = valid_data['x'].values
        y = valid_data['y'].values

        # Calculate distance between consecutive points
        dx = np.diff(x)
        dy = np.diff(y)
        distances = np.sqrt(dx**2 + dy**2)

        total_distance = np.sum(distances)

        return float(total_distance)

    def format_report(self) -> str:
        """
        Format the overview results as a human-readable report.

        Returns:
            Multi-line string report
        """
        if not self.results:
            return "No analysis results available. Run analyze() first."

        lines = []
        lines.append("=" * 70)
        lines.append("FLIGHT OVERVIEW")
        lines.append("=" * 70)
        lines.append("")

        # Duration
        duration = self.results['duration_s']
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        lines.append(f"Total Duration: {minutes}m {seconds}s ({duration:.1f}s)")

        # Armed time
        armed = self.results.get('armed_duration_s')
        if armed is not None:
            armed_min = int(armed // 60)
            armed_sec = int(armed % 60)
            armed_pct = (armed / duration) * 100 if duration > 0 else 0
            lines.append(f"Armed Time: {armed_min}m {armed_sec}s ({armed_pct:.1f}%)")
        else:
            lines.append("Armed Time: N/A (vehicle_status not available)")

        lines.append("")

        # Altitude
        max_alt = self.results.get('max_altitude_m')
        if max_alt is not None:
            lines.append(f"Maximum Altitude: {max_alt:.1f} m")
        else:
            lines.append("Maximum Altitude: N/A (position data not available)")

        # Speed
        max_speed = self.results.get('max_speed_ms')
        if max_speed is not None:
            lines.append(f"Maximum Speed: {max_speed:.1f} m/s ({max_speed * 3.6:.1f} km/h)")
        else:
            lines.append("Maximum Speed: N/A (velocity data not available)")

        # Distance
        distance = self.results.get('distance_traveled_m')
        if distance is not None:
            lines.append(f"Distance Traveled: {distance:.1f} m ({distance/1000:.2f} km)")
        else:
            lines.append("Distance Traveled: N/A (position data not available)")

        lines.append("")

        # Flight modes
        modes = self.results.get('flight_modes')
        if modes is not None and len(modes) > 0:
            lines.append("Flight Modes:")
            for mode_name, duration, percentage in modes:
                mode_min = int(duration // 60)
                mode_sec = int(duration % 60)
                lines.append(f"  - {mode_name}: {mode_min}m {mode_sec}s ({percentage:.1f}%)")
        else:
            lines.append("Flight Modes: N/A (vehicle_status not available)")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)


def generate_overview(loader: LogLoader) -> FlightOverview:
    """
    Convenience function to generate a flight overview.

    Args:
        loader: LogLoader instance

    Returns:
        FlightOverview instance with results

    Example:
        loader = LogLoader("flight.ulg")
        overview = generate_overview(loader)
        print(overview.format_report())
    """
    overview = FlightOverview(loader)
    overview.analyze()
    return overview
