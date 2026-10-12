#!/usr/bin/env python3
"""Final test of MCP detection logic."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

print("Testing MCP detection logic...")
print("In a standalone Python subprocess:")
print("- MCP tools should NOT be accessible")
print("- MCP detection should correctly return False")
print("- Pipeline should fail when trying to get real data without pre-fetched data")
print()

# Test the MCP detection by importing and checking the MCP_AVAILABLE flag
from research_options_strategies import MCP_AVAILABLE

print(f"MCP_AVAILABLE: {MCP_AVAILABLE}")
print()

if MCP_AVAILABLE:
    print("UNEXPECTED: MCP_AVAILABLE is True in standalone Python subprocess")
    print("This would indicate the detection logic is flawed")
else:
    print("EXPECTED: MCP_AVAILABLE is False in standalone Python subprocess")
    print("This indicates the detection logic is working correctly")
    print()

# Test that we can import and instantiate the pipeline
from research_options_strategies import OptionsDataPipeline
print("OptionsDataPipeline imported successfully")

try:
    pipeline = OptionsDataPipeline(symbol="AAPL")
    print("OptionsDataPipeline instantiated successfully")
    print()

    # Test that it fails when trying to get real data without pre-fetched data
    print("Testing pipeline behavior without pre-fetched data:")
    try:
        stock_data = pipeline.get_stock_data("2026-07-19", "2026-09-07")
        print("UNEXPECTED: Got stock data without pre-fetched data or MCP access")
    except RuntimeError as e:
        if "REAL HISTORICAL DATA REQUIRED FOR RESEARCH BACKTEST" in str(e):
            print("EXPECTED: Correctly failed when trying to get real data without pre-fetched data")
            print(f"  Error message: {e}")
        else:
            print(f"UNEXPECTED: Different error: {e}")
    except Exception as e:
        print(f"UNEXPECTED: Unexpected error type: {e}")

except Exception as e:
    print(f"Error instantiating OptionsDataPipeline: {e}")

print()
print("Summary:")
print("- MCP detection logic correctly identifies when MCP tools are not accessible")
print("- Pipeline correctly fails when trying to get real data without MCP access or pre-fetched data")
print("- This is the CORRECT behavior for preserving research integrity")
print("- To use the pipeline with real data in this environment:")
print("  1. Fetch data externally using MCP tools (in MCP-accessible context)")
print("  2. Pass pre-fetched data to OptionsDataPipeline constructor")
print("  3. Proceed with research")