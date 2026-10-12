#!/usr/bin/env python3
"""Test the MCP detection logic."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

# Test the MCP detection by importing and checking the MCP_AVAILABLE flag
from research_options_strategies import MCP_AVAILABLE

print(f"MCP_AVAILABLE: {MCP_AVAILABLE}")

# Also test that we can import the pipeline
from research_options_strategies import OptionsDataPipeline
print("OptionsDataPipeline imported successfully")

# Test instantiation
try:
    pipeline = OptionsDataPipeline(symbol="AAPL")
    print("OptionsDataPipeline instantiated successfully")
except Exception as e:
    print(f"Error instantiating OptionsDataPipeline: {e}")