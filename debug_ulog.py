#!/usr/bin/env python3
"""Debug script to understand pyulog structure."""

from pyulog import ULog
import sys

ulg = ULog(sys.argv[1])

print("Checking structure of ulog.data_list...")
print(f"Number of data items: {len(ulg.data_list)}")

if len(ulg.data_list) > 0:
    first_data = ulg.data_list[0]
    print(f"\nFirst data item:")
    print(f"  name: {first_data.name}")
    print(f"  multi_id: {first_data.multi_id}")
    print(f"  field_data type: {type(first_data.field_data)}")
    print(f"  field_data length: {len(first_data.field_data)}")

    print(f"\nFirst field:")
    first_field = first_data.field_data[0]
    print(f"  type: {type(first_field)}")
    print(f"  attributes: {dir(first_field)}")

    # Check if it has name and data attributes
    if hasattr(first_field, 'field_name'):
        print(f"  field_name: {first_field.field_name}")
    if hasattr(first_field, 'data'):
        print(f"  data type: {type(first_field.data)}")
        print(f"  data dtype: {first_field.data.dtype if hasattr(first_field.data, 'dtype') else 'N/A'}")
