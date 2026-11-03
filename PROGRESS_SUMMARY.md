# flightlog-analyzer: Progress Summary

**Project:** Python CLI tool to analyze PX4 ULog flight logs  
**Purpose:** Portfolio project for drone/defense-tech working student application  
**Date:** 2026-11-03  
**Status:** Steps 1-4 complete (40% done)

---

## Project Overview

A command-line tool that reads PX4 ULog (.ulg) files and produces detailed flight reports with:
- Flight overview statistics
- Vibration analysis with frequency content
- Battery health assessment (coming)
- Motor performance analysis (coming)
- Attitude tracking quality (coming)
- HTML report with ranked findings (coming)

**Key design principle:** Graceful handling of missing data - different PX4 versions log different topics.

---

## What We've Built (Steps 1-4)

### Step 1: Project Setup ✅

**Files created:**
- `pyproject.toml` - Modern Python packaging
- `README.md` - Complete documentation skeleton
- `src/flightlog_analyzer/__init__.py` - Package init
- `src/flightlog_analyzer/list_topics.py` - **Topic listing utility**

**What list_topics does:**
- Lists all topics and fields in a ULog file
- Critical because topic names vary between PX4 versions
- Must check what's available before analyzing

**Key learning:**
- Never hardcode topic names from memory
- Always inspect actual log files first
- Real logs have different topics than expected

**Test result:**
```
Sample log has 149 topics including:
- sensor_accel_0, sensor_gyro_0
- vehicle_local_position_0
- vehicle_status_0
- battery_status_0
- actuator_motors_0, actuator_outputs_1
```

---

### Step 2: Log Loader Module ✅

**Files created:**
- `src/flightlog_analyzer/loader.py` - **LogLoader class**

**What it does:**
- Loads ULog topics into pandas DataFrames
- Converts timestamps to "seconds since log start"
- Returns `None` for missing topics (graceful)
- Memory efficient - only loads requested topics

**Key concepts:**

**Time alignment problem:**
Different sensors log at different rates:
- IMU: ~1000 Hz (or ~1 Hz in downsampled logs)
- Attitude: ~20-100 Hz
- Battery: ~5 Hz

**Solution:**
- Convert all timestamps: `time_s = (timestamp_us - start_time_us) / 1e6`
- Use pandas DataFrames with `time_s` as index
- Each topic becomes separate DataFrame

**Methods:**
```python
loader = LogLoader("flight.ulg")

# Load single topic
df = loader.get_topic_data("sensor_accel", 0)

# Load multiple topics
data = loader.get_multiple_topics([
    ("sensor_accel", 0),
    ("battery_status", 0),
])

# Check what's available
topics = loader.get_topic_list()
```

**Test result:**
- Loaded sensor_accel_0: 79 samples at ~1 Hz
- Loaded battery_status_0: 398 samples at ~5 Hz
- Loaded vehicle_attitude_0: 1589 samples at ~20 Hz
- Gracefully returns None for non-existent topics ✓

**Key learning:**
- Different sample rates are normal
- Pandas time-indexed DataFrames handle this elegantly
- Returning None is better than crashing

---

### Step 3: Flight Overview Module ✅

**Files created:**
- `src/flightlog_analyzer/overview.py` - **FlightOverview class**

**What it analyzes:**
1. **Duration**: Total time, armed time, % armed
2. **Altitude**: Maximum altitude above takeoff
3. **Speed**: Maximum horizontal speed
4. **Distance**: Total distance traveled (approximate)
5. **Flight modes**: Which modes used, duration, percentage

**Key concepts:**

**NED coordinate frame:**
```
PX4 uses North-East-Down:
- x = North (positive = north)
- y = East (positive = east)
- z = Down (positive = DOWN)

Therefore:
- Altitude = -z (negate because down is positive)
- Max altitude = most negative z value
```

**Speed calculation:**
```python
vx = velocity North (m/s)
vy = velocity East (m/s)
horizontal_speed = sqrt(vx² + vy²)
```

**Distance calculation:**
```python
# Sum straight-line distances between consecutive points
for each point pair:
    dx = x[i+1] - x[i]
    dy = y[i+1] - y[i]
    distance += sqrt(dx² + dy²)
```

**Flight mode mapping:**
```
nav_state (numeric) -> human-readable name
0 -> "Manual"
2 -> "Position Control"
14 -> "Offboard"
17 -> "Auto Land"
... (21 modes total)
```

**Test result:**
```
Flight Overview:
- Duration: 1m 19s (79.7s)
- Armed Time: 1m 17s (97.6%)
- Max Altitude: 3.1 m
- Max Speed: 2.7 m/s (9.7 km/h)
- Distance: 101.4 m

Flight Modes:
- Offboard: 84.6%
- Auto Follow Target: 11.4%
- Auto Land: 3.3%
```

**Key learning - Corrupt timestamps:**
- Real logs can have bad timestamps (e.g., 1.8e13 seconds!)
- Solution: Filter timestamps to [0, duration * 1.1]
- Without filtering, got huge negative values
- **Lesson:** Always validate real-world data

**Key learning - Boolean mask indexing:**
- Can't use boolean array as DataFrame column selector
- Must use `.loc[mask, column]` syntax
- Pandas quirk that AI initially got wrong

---

### Step 4: Vibration Analysis Module ✅

**Files created:**
- `src/flightlog_analyzer/vibration.py` - **VibrationAnalyzer class**
- `config/thresholds.yaml` - **Threshold configuration with explanations**

**What it analyzes:**
1. **RMS vibration** per axis (m/s²)
2. **Power Spectral Density** (frequency analysis)
3. **Dominant frequency peaks** (identify vibration sources)
4. **Clipping events** (sensor saturation)
5. **Plots**: Time-domain and frequency-domain

**Key concepts:**

**RMS (Root Mean Square):**
```
RMS = sqrt(mean(x²))

- Measures overall vibration magnitude
- Units: m/s² (same as acceleration)
- Higher = more vibration energy
```

**PSD (Power Spectral Density):**
```
- Shows vibration power at each frequency
- Units: (m/s²)² / Hz
- Calculated using Welch's method (scipy.signal.welch)
- Welch = FFT with averaging over segments (reduces noise)
```

**Why Welch's method:**
- Raw FFT is noisy
- Welch divides signal into overlapping segments
- Computes FFT for each, then averages
- Result: Smoother, more robust PSD estimate

**Frequency peak interpretation:**
- Motor frequency: RPM / 60 Hz
- Propeller frequency: (RPM × blades) / 60
- Structural resonance: 50-150 Hz typical
- Single strong peak → specific mechanical issue
- Broadband noise → general roughness

**Sample rate limitation (Nyquist):**
```
Can only detect frequencies up to sample_rate / 2

Our sample log: 1 Hz → max 0.5 Hz detectable
Typical motors: 50-200 Hz
Conclusion: This log too downsampled for frequency analysis

Typical logs: 500-1000 Hz → can see 0-250 or 0-500 Hz ✓
```

**Test result:**
```
Vibration Analysis:
- Sample Rate: 1.0 Hz (downsampled)
- RMS X: 10.24 m/s² (Good)
- RMS Y: 20.44 m/s² (HIGH - exceeds 15 m/s²)
- RMS Z: 12.21 m/s² (Good)
- Clipping: 0 events (Excellent)
- Frequency Analysis: Skipped (1 Hz too low, need >= 10 Hz)
- Plot: vibration_analysis.png (209KB) ✓
```

**Threshold configuration approach:**
- All thresholds in `config/thresholds.yaml`
- Each threshold documented with:
  - Default value
  - Rationale for choosing it
  - What to adjust based on
  - Clearly labeled "tunable defaults, NOT industry standards"

**Example threshold:**
```yaml
rms_threshold_ms2: 15.0
# Rationale: Based on typical consumer multirotor performance
#   < 10 m/s²: Excellent
#   10-15 m/s²: Good
#   15-25 m/s²: Elevated
#   > 25 m/s²: High (likely problem)
# Adjust based on:
#   - Drone size
#   - Motor/prop configuration
#   - Frame stiffness
```

**Key learning:**
- Signal processing requires physics understanding
- Can't blindly run FFT - check sample rate first
- Gracefully skip analysis when data inadequate
- Document threshold rationale, don't claim standards

---

## Architecture & Design Patterns

### 1. Graceful Degradation
```python
# Every analysis module checks for required topics
accel = loader.get_topic_data("sensor_accel", 0)
if accel is None:
    results['available'] = False
    results['reason'] = "sensor_accel not found"
    return results

# Report shows what's available vs missing
# Tool never crashes on partial data
```

### 2. No Hardcoded Topic Names
```python
# WRONG (Step 1 rule):
def analyze():
    accel = ulog.get_topic("sensor_accel_0")  # Assumes name

# RIGHT:
def analyze():
    accel = loader.get_topic_data("sensor_accel", 0)
    if accel is None:
        return "Skipped - topic not found"
```

### 3. Configuration Over Magic Numbers
```python
# WRONG:
if rms > 15.0:  # Magic number, why 15?

# RIGHT:
threshold = config.get('rms_threshold_ms2', 15.0)  # Documented in YAML
if rms > threshold:
```

### 4. Robust to Real-World Data Corruption
```python
# Filter corrupt timestamps
valid_mask = (time >= 0) & (time <= duration * 1.1)
filtered_data = data[valid_mask]

# Estimate sample rate with median (robust to outliers)
sample_rate = 1.0 / np.median(np.diff(timestamps))
```

### 5. Separation of Concerns
```
loader.py        - Data loading only
overview.py      - Flight statistics
vibration.py     - Vibration analysis
(battery.py)     - Battery analysis (coming)
(report.py)      - HTML generation (coming)

Each module independent, testable
```

---

## Testing Strategy

**Current approach:**
- Manual test scripts for each module
- Test with real ULog file (sample_logs/)
- Verify outputs manually

**Example test script:**
```python
# test_overview.py
loader = LogLoader("sample.ulg")
overview = generate_overview(loader)
print(overview.format_report())
print(overview.results)  # Raw data for debugging
```

**Coming in Step 9:**
- pytest unit tests
- Synthetic signals with known answers
- Example: sine wave at 50 Hz → PSD should peak at 50 Hz
- Example: known resistor model → should recover resistance value

---

## Project Structure (Current)

```
flightlog-analyzer/
├── src/
│   └── flightlog_analyzer/
│       ├── __init__.py
│       ├── list_topics.py    ✅ Topic listing utility
│       ├── loader.py          ✅ ULog → pandas DataFrames
│       ├── overview.py        ✅ Flight statistics
│       ├── vibration.py       ✅ Vibration analysis
│       ├── cli.py             (placeholder)
│       ├── battery.py         (Step 5 - coming)
│       ├── motor.py           (Step 6 - coming)
│       ├── attitude.py        (Step 7 - coming)
│       └── report.py          (Step 8 - coming)
├── tests/
│   └── (Step 9 - coming)
├── config/
│   └── thresholds.yaml        ✅ Threshold configuration
├── sample_logs/
│   └── 385c5c92...ulg         ✅ Real PX4 flight log (3.8MB)
├── test_loader.py             ✅ Loader test script
├── test_overview.py           ✅ Overview test script
├── test_vibration.py          ✅ Vibration test script
├── pyproject.toml             ✅ Python packaging
├── README.md                  ✅ Documentation
├── STEP1_COMPLETE.md          ✅ Step 1 summary
├── STEP2_COMPLETE.md          ✅ Step 2 summary
├── STEP3_COMPLETE.md          ✅ Step 3 summary
└── STEP4_COMPLETE.md          ✅ Step 4 summary
```

---

## What's Left (Steps 5-10)

### Step 5: Battery Module (Next)
- Load battery_status topic
- Plot voltage and current vs time
- Calculate minimum voltage
- Calculate energy consumed (integrate current)
- Estimate internal resistance from V-I relationship
- Detect voltage sag under load
- Flag low voltage events

**Key concepts:** Ohm's law, battery discharge curves, internal resistance modeling

### Step 6: Motor Module
- Load actuator_motors or actuator_outputs
- Calculate time near saturation (>95%)
- Detect motor imbalance (different output levels)
- Flag control authority issues
- Plot motor outputs over time

**Key concepts:** Control saturation, motor mixing, thrust-to-weight

### Step 7: Attitude Tracking Module
- Load vehicle_attitude and vehicle_attitude_setpoint
- Calculate tracking error per axis (setpoint - actual)
- RMS error and max error
- Plot setpoint vs actual over time
- Flag poor tracking (PID tuning issues)

**Key concepts:** Control loops, PID tuning, tracking performance

### Step 8: Report Generator
- Generate HTML report with all analyses
- Ranked "findings" summary at top
- Each finding links to evidence plot
- Collapsible sections for each analysis
- Export plots as embedded images

**Key concepts:** HTML generation, report structure, data visualization

### Step 9: Testing with pytest
- Unit tests for each module
- Synthetic signals with known answers
- Example: sine at 50 Hz → PSD peaks at 50 Hz
- Example: known R model → recovers R
- Test graceful handling of missing data

**Key concepts:** Test-driven validation, synthetic data, edge cases

### Step 10: Final Documentation
- Update README with:
  - Example reports on 3 different logs
  - Limitations section
  - "How I used coding agents" section
- Installation and usage guide
- Screenshots of example reports

---

## Key Learnings So Far

### What AI Did Well:
1. Generated correct pandas/numpy/scipy code
2. Understood domain concepts (NED frame, FFT, PSD)
3. Good code structure and documentation
4. Proper error handling patterns

### What Required Manual Fixes:
1. **Boolean mask indexing** - Pandas quirk with `.loc[mask, col]`
2. **Corrupt timestamp handling** - Real logs have bad data
3. **Sample rate validation** - Must check before FFT
4. **Threshold philosophy** - Not claiming industry standards

### What You Learned:
1. **pyulog structure** - `.data_list`, `.field_data`, time conversion
2. **pandas time indexing** - Using time_s as index
3. **NED coordinate frame** - Why altitude = -z
4. **RMS vs PSD** - Time domain vs frequency domain
5. **Welch's method** - Why not raw FFT
6. **Nyquist theorem** - Sample rate limitations
7. **Real-world data** - Corruption, missing topics, edge cases

### Project Management:
- **Small steps** - One module at a time, test before continuing
- **Explain everything** - Every calculation, every design decision
- **Real data first** - Test with actual logs, not synthetic
- **Document rationale** - Why each threshold, why each approach

---

## For the "How I Used Coding Agents" Section

**What to write in your README:**

> ### How I used coding agents on this project
>
> **What worked well:**
> - AI generated correct implementations of signal processing algorithms (FFT, Welch's method, RMS)
> - Understood domain-specific concepts like NED coordinate frames and PX4 log structure
> - Produced well-documented code with clear comments
> - Suggested appropriate Python libraries (pandas, scipy, matplotlib)
>
> **What I had to correct:**
> - Boolean mask indexing in pandas (`.loc` syntax)
> - Handling of corrupt timestamps in real flight logs
> - Sample rate validation before running FFT
> - Threshold documentation approach (tunable defaults vs claimed standards)
>
> **Workflow:**
> 1. Worked in small steps (one module per session)
> 2. Required AI to explain every line and design decision
> 3. Tested each module with real flight data immediately
> 4. Debugged issues by reading actual error messages and data
> 5. Learned the "why" behind each algorithm, not just the "how"
>
> **Key insight:**
> AI is excellent at generating correct code for well-defined problems, but real-world drone logs have edge cases (corrupt timestamps, downsampled data, missing topics) that only appear when testing with actual data. The combination of AI code generation + human validation with real data was highly effective.

---

## Next Session Plan

When you're ready to continue:

1. **Step 5: Battery Module**
   - Voltage/current curves
   - Internal resistance estimation
   - Energy calculation
   - ~1-2 hours

2. **Step 6: Motor Module**
   - Saturation detection
   - Imbalance analysis
   - ~1 hour

3. **Step 7: Attitude Module**
   - Tracking error analysis
   - ~1 hour

4. **Step 8: HTML Report Generator**
   - Combine all analyses
   - ~1-2 hours

5. **Step 9: pytest Tests**
   - Synthetic signal tests
   - ~1 hour

6. **Step 10: Final Documentation**
   - README completion
   - Example reports
   - ~30 minutes

**Estimated remaining time: 5-7 hours**

---

## Questions or Concerns?

Before continuing, review:
1. Do all the concepts (RMS, PSD, NED, etc.) make sense?
2. Any parts of the code unclear?
3. Ready to continue, or need more explanation?
4. Want to adjust the remaining plan?

**The foundation is solid. Steps 5-10 build on what we've created.**
