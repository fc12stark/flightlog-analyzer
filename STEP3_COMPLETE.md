# Step 3 Complete: Flight Overview Module

## What was created

### overview.py - The FlightOverview class

A module that analyzes basic flight characteristics and generates summary statistics.

## Test results from sample log

✅ **Flight Overview:**
- Total Duration: 1m 19s (79.7s)
- Armed Time: 1m 17s (97.6% of flight)
- Maximum Altitude: 3.1 m
- Maximum Speed: 2.7 m/s (9.7 km/h)
- Distance Traveled: 101.4 m (0.10 km)

✅ **Flight Modes:**
- Offboard: 1m 6s (84.6%)
- Auto Follow Target: 0m 8s (11.4%)
- Auto Land: 0m 2s (3.3%)
- Position Control: 0m 0s (0.7%)

## Key concepts explained

### What the overview module computes

**1. Duration statistics:**
- Total log duration (from LogLoader)
- Armed time (motors spinning)
- Percentage of time armed

**2. Altitude and speed:**
- Maximum altitude above takeoff
- Maximum horizontal speed
- Both calculated from vehicle_local_position topic

**3. Distance traveled:**
- Total horizontal distance
- Calculated by summing distances between consecutive position samples
- Approximate (assumes straight lines between samples)

**4. Flight modes:**
- Which modes were used during the flight
- Duration and percentage for each mode
- Maps numeric nav_state codes to human-readable names

### How it works

**Altitude calculation:**
```
PX4 uses NED (North-East-Down) frame:
- N = North direction (positive = north)
- E = East direction (positive = east)
- D = Down direction (positive = DOWN)

Therefore:
- z field is positive downward
- Altitude above takeoff = -z
- Maximum altitude = most negative z value
```

**Speed calculation:**
```
vx = velocity North (m/s)
vy = velocity East (m/s)
horizontal_speed = sqrt(vx^2 + vy^2)
max_speed = maximum of all horizontal speeds
```

**Distance calculation:**
```
For each consecutive pair of position samples:
  dx = x[i+1] - x[i]
  dy = y[i+1] - y[i]
  distance = sqrt(dx^2 + dy^2)

total_distance = sum of all distances
```

**Armed time calculation:**
```
arming_state values:
- 1 = standby (motors off)
- 2 = armed (motors on)

Count samples where arming_state == 2
Multiply by average sample interval
```

**Flight mode mapping:**
```
nav_state -> human-readable name
0 -> "Manual"
2 -> "Position Control"
14 -> "Offboard"
17 -> "Auto Land"
... (21 total modes)
```

## What could go wrong

### 1. Corrupt timestamps (FIXED)
Problem: Some logs have invalid timestamps (e.g., 1.8e13 seconds)
Solution: Filter out timestamps outside valid range [0, duration * 1.1]
Impact: Without filtering, calculations give huge negative values

### 2. Missing topics
Problem: vehicle_status or vehicle_local_position not in log
Solution: Return None for those metrics, display N/A in report
Impact: Gracefully degrades, shows what's available

### 3. Invalid data flags
Problem: Position/velocity may be invalid (GPS loss, etc.)
Solution: Check z_valid, v_xy_valid, xy_valid flags
Impact: Only use valid data for calculations

### 4. Downsampled logs
Problem: Our sample log has IMU at ~1 Hz (usually ~1000 Hz)
Solution: Algorithms work at any sample rate
Impact: Lower sample rate = less accurate distance calculation

### 5. Distance is approximate
Problem: Assumes straight lines between samples
Impact: Underestimates actual path if drone curves between samples
Better would be: Use higher-rate position data if available

## Design decisions explained

### Why filter timestamps?
Real-world logs can have corruption:
- Dropouts or resets
- Clock synchronization issues
- Buffer overflows during high CPU load

Better to filter outliers than crash or return nonsense.

### Why return None for missing data?
Different PX4 versions and configurations log different topics:
- Some don't log position (indoor flights without GPS)
- Some don't log certain status fields
- Hardware variations (no barometer, etc.)

Returning None allows:
- Caller decides how to handle
- Report shows what's available vs missing
- Tool doesn't crash on partial data

### Why percentage for flight modes?
- Easier to spot anomalies ("90% in Manual? That's unusual")
- Independent of log duration
- Useful for comparing different flights

### Why map nav_state numbers?
- Nav_state is encoded as 0-21 in the log
- Numbers are meaningless to humans
- Mapping makes reports readable
- Source: PX4 vehicle_status.msg definition

## Example usage

```python
from loader import LogLoader
from overview import generate_overview

# Load log
loader = LogLoader("flight.ulg")

# Generate overview
overview = generate_overview(loader)

# Display report
print(overview.format_report())
```

## What I learned (for the AI assistance section)

**What worked:**
- AI generated correct pandas filtering logic
- Understood NED coordinate frame
- Proper error handling structure

**What I had to fix:**
- Boolean mask indexing issue (can't use True/False array as column name)
- Corrupt timestamp handling (AI didn't anticipate real-world data corruption)
- Both required reading actual error messages and understanding pandas behavior

**Key lesson:**
Real-world drone logs have edge cases that synthetic examples don't show. Always test with actual flight data.

## Next steps (Step 4)

Build the vibration module:
- Load sensor_accel data
- Calculate RMS vibration per axis
- Perform FFT/PSD (power spectral density) analysis
- Detect strong frequency peaks
- Plot time-domain and frequency-domain
- Flag excessive vibration

This will be more mathematically complex (FFT, signal processing).

## Questions before proceeding to Step 4?

1. Does the NED coordinate frame explanation make sense?
2. Is the corrupt timestamp handling clear?
3. Any concerns about the distance calculation approximation?
4. Ready for signal processing (FFT, PSD)?
