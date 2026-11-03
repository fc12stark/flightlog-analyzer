# Step 2 Complete: Log Loader Module

## What was created

### loader.py - The LogLoader class

A module that loads PX4 ULog data into pandas DataFrames with proper time alignment.

## Key concepts explained

### The time alignment problem

Different sensors log at different rates:
- **IMU (accelerometer/gyro)**: ~1000 Hz in flight (but only ~1 Hz in our sample - likely a downsampled log)
- **Attitude estimates**: ~20-100 Hz
- **Battery status**: ~5 Hz
- **GPS**: ~1-10 Hz

**Solution**: Convert all timestamps to "seconds since log start" and use pandas time-indexed DataFrames.

### How LogLoader works

**1. Initialization (`__init__`)**
```python
loader = LogLoader("flight.ulg")
```
- Opens the ULog file with pyulog
- Calculates `start_time_us` (log start in microseconds)
- Calculates `duration_s` (total log duration in seconds)
- Does NOT load all data yet (memory efficient)

**2. Loading a single topic (`get_topic_data`)**
```python
accel_df = loader.get_topic_data("sensor_accel", 0)
```
- Searches for the topic in `ulog.data_list`
- Returns `None` if topic doesn't exist (graceful handling)
- Extracts the data dictionary from pyulog
- Converts timestamps: `time_s = (timestamp_us - start_time_us) / 1e6`
- Builds a pandas DataFrame with `time_s` as the index
- All fields except timestamp become columns

**3. Loading multiple topics (`get_multiple_topics`)**
```python
data = loader.get_multiple_topics([
    ("sensor_accel", 0),
    ("battery_status", 0),
    ("vehicle_attitude", 0)
])
```
- Batch loads several topics
- Returns a dict: `{topic_name: DataFrame or None}`
- Efficient for analysis modules that need several topics

**4. Getting available topics (`get_topic_list`)**
```python
topics = loader.get_topic_list()  # [(name, multi_id), ...]
```
- Lists all available topics in the log
- Useful for checking what exists before requesting

## Test results from sample log

✅ **Successfully loaded:**
- `sensor_accel_0`: 79 samples at ~1.0 Hz
- `battery_status_0`: 398 samples at ~5.0 Hz  
- `vehicle_attitude_0`: 1589 samples at ~19.9 Hz
- Total topics available: 149

✅ **Graceful handling verified:**
- Requesting non-existent topic returns `None` (doesn't crash)

## What could go wrong

### 1. **File not found or corrupted**
- pyulog will raise an exception
- Caller should catch and handle

### 2. **Topic doesn't exist**
- `get_topic_data` returns `None`
- Analysis modules check for `None` before proceeding
- Report says "skipped - topic not found"

### 3. **Memory issues with huge logs**
- Current design loads entire topics into memory
- For multi-hour logs, this could be GBs
- Future optimization: support chunked reading

### 4. **Different sample rates**
- DataFrames have different lengths
- Time indices won't align exactly
- Solution (for later steps): resample or interpolate

### 5. **Time jumps or gaps**
- If the drone restarted mid-log, timestamps might jump
- Current implementation doesn't detect this
- Analysis modules should be robust to gaps

## Design decisions explained

### Why pandas DataFrames?
- Time-indexed for easy alignment
- Built-in interpolation and resampling
- Compatible with scipy, numpy, matplotlib
- `.resample()`, `.rolling()`, `.interpolate()` methods

### Why time_s as index?
- Easier than keeping timestamp as a column
- Enables `df.loc[start:end]` time-based slicing
- Natural for plotting: `plt.plot(df.index, df['x'])`

### Why return None instead of raising exceptions?
- Topic availability varies between PX4 versions
- Better to gracefully skip analysis than crash entire tool
- Caller decides how to handle missing data

### Why not load everything upfront?
- Memory efficient - only load what you need
- Faster startup
- Some logs have 100+ topics, most unused

## Example usage in analysis modules

```python
from loader import LogLoader

loader = LogLoader("flight.ulg")

# Load accelerometer data
accel = loader.get_topic_data("sensor_accel", 0)

if accel is None:
    print("Vibration analysis skipped - no accelerometer data")
    return None

# Analyze the data
rms_x = accel['x'].std()
rms_y = accel['y'].std()
rms_z = accel['z'].std()

print(f"Vibration RMS: X={rms_x:.3f}, Y={rms_y:.3f}, Z={rms_z:.3f} m/s²")
```

## Next steps (Step 3)

Build the **overview module**:
- Load flight duration from loader
- Extract flight modes over time (if available)
- Calculate max altitude and speed (if available)
- Display basic flight statistics

This will be our first real analysis module using the loader!

## Questions before proceeding to Step 3?

1. Does the time conversion make sense? (microseconds → seconds since start)
2. Is the None-handling approach clear?
3. Any concerns about the DataFrame structure?
4. Ready to build the first analysis module?
