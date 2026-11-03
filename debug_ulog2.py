#!/usr/bin/env python3
"""Debug script to understand pyulog structure."""

from pyulog import ULog
import sys

ulg = ULog(sys.argv[1])

first_data = ulg.data_list[0]
print(f"Topic: {first_data.name}_{first_data.multi_id}")
print(f"Number of fields: {len(first_data.field_data)}")

for field in first_data.field_data:
    print(f"  - {field.field_name} ({field.type_str})")

# Also check if the data object has the actual values
print(f"\nChecking data object:")
print(f"  data type: {type(first_data.data)}")
print(f"  data keys: {first_data.data.keys()}")
print(f"  timestamp shape: {first_data.data['timestamp'].shape}")
print(f"  timestamp dtype: {first_data.data['timestamp'].dtype}")
