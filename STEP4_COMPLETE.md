# Step 4 Complete: Vibration Analysis Module

## What was created

### 1. vibration.py - VibrationAnalyzer class
A module that performs vibration analysis using accelerometer data with signal processing techniques.

### 2. config/thresholds.yaml
Configuration file with tunable threshold defaults and detailed explanations for why each was chosen.

## Test results from sample log

✅ **Vibration Analysis Results:**
- Sensor: sensor_accel_0
- Sample Rate: 1.0 Hz (downsampled log)
- Samples: 79 over 78 seconds

✅ **RMS Vibration:**
- X-axis: 10.24 m/s² (Good)
- Y-axis: 20.44 m/s² (HIGH - exceeds 15 m/s² threshold)
- Z-axis: 12.21 m/s² (Good)

✅ **Clipping:**
- All axes: 0 clips (Excellent)

✅ **Frequency Analysis:**
- Skipped (1 Hz sample rate too low, need >= 10 Hz for FFT)

✅ **Plot Generated:**
- vibration_analysis.png (209KB)
- Time-domain: acceleration vs time for all 3 axes
- Frequency-domain: Would show PSD if sample rate was higher

## Key concepts explained

### What is RMS vibration?

**RMS = Root Mean Square**
```
RMS = sqrt(mean(x²))
```

For vibration:
- Measures overall vibration magnitude
- Units: m/s² (same as acceleration)
- Higher RMS = more vibration energy
- Independent of frequency content

**Why RMS instead of peak or average?**
- Peak can be a single outlier
- Average of oscillating signal ≈ 0
- RMS captures actual energy content

### What is Power Spectral Density (PSD)?

**PSD shows vibration power at each frequency**
```
Units: (m/s²)² / Hz
```

**How we calculate it:**
- Use Welch's method (scipy.signal.welch)
- Divides signal into overlapping segments
- Computes FFT for each segment
- Averages results (reduces noise)

**Why Welch's method instead of raw FFT?**
- Raw FFT is noisy
- Welch averages over segments = smoother estimate
- More robust for noisy real-world data

### What do frequency peaks tell us?

**Common vibration sources:**
- **Motor frequency**: RPM / 60 Hz
  - 6000 RPM motor = 100 Hz fundamental
- **Propeller frequency**: (RPM × num_blades) / 60
  - 6000 RPM, 2-blade prop = 200 Hz
- **Structural resonances**: Frame natural frequencies
  - Typically 50-150 Hz for multirotors
- **Bearing defects**: Specific frequencies based on geometry

**What to look for:**
- Single strong peak → specific mechanical issue
- Broadband noise → general roughness
- Multiple harmonics → motor/prop imbalance

### Sample rate limitations

**Nyquist theorem:** Can only detect frequencies up to sample_rate / 2

Our sample log:
- 1 Hz sample rate → can only see up to 0.5 Hz
- Typical motor vibrations: 50-200 Hz
- **Conclusion:** This log is too downsampled for frequency analysis

Typical flight logs:
- IMU: 500-1000 Hz
- Can see: 0-250 Hz or 0-500 Hz
- Covers motor/prop frequencies ✓

## What could go wrong

### 1. Low sample rate (handled gracefully)
**Problem:** Sample rate < 10 Hz
**Solution:** Skip frequency analysis, only report RMS
**Impact:** Can't identify specific vibration sources, but overall level is still useful

### 2. Corrupt or missing data
**Problem:** sensor_accel topic not in log
**Solution:** Return available=False with reason
**Impact:** Analysis skipped, report shows why

### 3. Timestamp issues
**Problem:** Non-uniform sampling or corrupt timestamps
**Solution:** Estimate sample rate using median interval
**Impact:** Robust to outliers

### 4. Clipping detection
**Problem:** Sensor saturates (vibration exceeds ±16g or ±8g range)
**Solution:** Check clip_counter fields if available
**Impact:** Know when data is unreliable

### 5. Threshold interpretation
**Problem:** Thresholds vary by platform
**Solution:** Config file with explanations, clearly labeled as tunable defaults
**Impact:** Users can adjust for their specific drone

## Design decisions explained

### Why skip frequency analysis below 10 Hz?

- FFT needs enough samples per cycle
- At 1 Hz sampling, we have ~80 samples total
- Can only resolve down to ~0.01 Hz resolution
- Motor vibrations are 50-200 Hz = completely aliased
- Better to say "not available" than show garbage

### Why Welch's method with nperseg=256?

**nperseg (segment length) tradeoff:**
- Larger nperseg = better frequency resolution, more noise
- Smaller nperseg = worse frequency resolution, less noise

256 samples is a good compromise:
- At 1000 Hz: 0.256 seconds per segment
- Frequency resolution: ~4 Hz
- Good enough to separate motor harmonics

### Why find only top 3 peaks?

- Most vibration issues show 1-3 dominant frequencies
- More peaks = harder to read, likely noise
- User can look at full PSD plot if needed

### Why 10% threshold for peak detection?

- Peaks must be at least 10% of maximum PSD
- Filters out noise floor
- Focuses on significant vibration sources

### Why return findings as strings?

- Easy to display in report
- Easy to parse for automated systems
- Severity level in string: "HIGH", "WARNING", "INFO", "OK"
- Alternative: structured dict (could add later)

## Threshold configuration explained

All thresholds in `config/thresholds.yaml` are:
1. **Tunable defaults**, not industry standards
2. **Documented** with rationale for the value
3. **Context-dependent** (adjust for your platform)

**RMS threshold (15 m/s²):**
- Based on typical consumer multirotor behavior
- < 10: Excellent
- 10-15: Good
- 15-25: Elevated
- > 25: High (likely problem)

**Why this matters for the portfolio:**
Shows you understand:
- No magic numbers in code
- Document assumptions
- Make system configurable
- Explain tradeoffs

## Example usage

```python
from loader import LogLoader
from vibration import analyze_vibration

# Load log
loader = LoadLoader("flight.ulg")

# Run analysis with custom thresholds
config = {
    'rms_threshold_ms2': 20.0,  # Tunable default
    'clip_threshold_count': 5,
}

analyzer = analyze_vibration(loader, config)

# Display report
print(analyzer.format_report())

# Generate plots
analyzer.plot("vibration.png")

# Access raw results
print(f"X-axis RMS: {analyzer.results['rms_x']:.2f} m/s²")
if 'peaks_x' in analyzer.results:
    freq, power = analyzer.results['peaks_x'][0]
    print(f"Dominant frequency: {freq:.1f} Hz")
```

## What I learned (for the AI assistance section)

**What worked:**
- AI correctly implemented Welch's method using scipy
- Proper FFT frequency axis calculation
- Good error handling structure
- Clear threshold documentation approach

**What required understanding:**
- Why low sample rate breaks frequency analysis
- Nyquist theorem implications
- When to skip analysis vs. show degraded results
- Real-world threshold selection process

**Key insight:**
Signal processing requires understanding the physics. Can't just run FFT on any data - need to check if sample rate is adequate first.

## Next steps (Step 5)

Build the **battery module**:
- Voltage and current vs time
- Minimum voltage detection
- Energy consumed calculation
- Internal resistance estimation (from V vs I relationship)
- Voltage sag analysis
- Plot voltage and current curves

This involves electrical modeling (Ohm's law, battery discharge curves).

## Questions before proceeding to Step 5?

1. Does the RMS vs PSD distinction make sense?
2. Is the sample rate limitation clear?
3. Any concerns about threshold configuration approach?
4. Ready for battery electrical analysis?
