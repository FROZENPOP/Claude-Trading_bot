#!/usr/bin/env python3
"""Test script to check if imports work correctly."""

import os
import sys

print("Initial sys.path:")
for i, p in enumerate(sys.path[:5]):  # Show first 5 entries
    print(f"  {i}: {p}")

# Try to import from our local webull module
try:
    # Add the project root to path
    project_root = os.path.join(os.path.dirname(__file__), '..', '..')
    if project_root not in sys.path:
        sys.path.append(project_root)

    from trading_bot.execution.webull import WebullExecution
    print(f"Successfully imported WebullExecution from local module")
except Exception as e:
    print(f"Failed to import WebullExecution from local module: {e}")
    import traceback
    traceback.print_exc()

# Try to import from phase7 webull executor
try:
    from trading_bot.execution.phase7_webull_execution import Phase7WebullExecutor
    print(f"Successfully imported Phase7WebullExecutor from local module")
except Exception as e:
    print(f"Failed to import Phase7WebullExecutor from local module: {e}")
    import traceback
    traceback.print_exc()