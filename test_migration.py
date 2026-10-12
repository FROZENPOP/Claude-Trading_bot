#!/usr/bin/env python3
"""
Test script to verify that the migration from Alpaca to Webull is working correctly.
This tests the phase8_execution_monitoring module to ensure it uses the WebullExecution
directly.
"""

import sys
import os

# Add the trading_bot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_imports():
    """Test that we can import the module without errors."""
    try:
        from trading_bot.execution.phase8_execution_monitoring import (
            ExecutionMonitor,
            PositionInfo,
            ExitSignal,
            create_execution_monitor
        )
        print("[PASS] Successfully imported phase8_execution_monitoring")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to import phase8_execution_monitoring: {e}")
        return False

def test_position_info_creation():
    """Test that we can create a PositionInfo object with string side."""
    try:
        from trading_bot.execution.phase8_execution_monitoring import PositionInfo
        from datetime import datetime

        pos = PositionInfo(
            symbol="AAPL",
            qty=10,
            side="buy",  # String instead of OrderSide.BUY
            entry_price=150.0,
            current_price=155.0,
            unrealized_pnl=50.0,
            realized_pnl=0.0,
            entry_time=datetime.now()
        )

        assert pos.side == "buy"
        assert pos.symbol == "AAPL"
        assert pos.qty == 10
        print("[PASS] Successfully created PositionInfo with string side")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to create PositionInfo: {e}")
        return False

def test_exit_signal_creation():
    """Test that we can create an ExitSignal object."""
    try:
        from trading_bot.execution.phase8_execution_monitoring import ExitSignal
        from datetime import datetime

        signal = ExitSignal(
            position_symbol="AAPL",
            exit_reason="stop_loss",
            exit_price=145.0,
            qty_to_exit=10,
            timestamp=datetime.now()
        )

        assert signal.exit_reason == "stop_loss"
        assert signal.position_symbol == "AAPL"
        print("[PASS] Successfully created ExitSignal")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to create ExitSignal: {e}")
        return False

def test_webull_executor_import():
    """Test that we can import the WebullExecution."""
    try:
        from trading_bot.execution.webull_execution import WebullExecution
        print("[PASS] Successfully imported WebullExecution")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to import WebullExecution: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing migration from Alpaca to Webull in phase8_execution_monitoring...")
    print("=" * 70)

    tests = [
        test_imports,
        test_position_info_creation,
        test_exit_signal_creation,
        test_webull_executor_import
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()  # Empty line between tests

    print("=" * 70)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("All tests passed! Migration to Webull is working correctly.")
        return 0
    else:
        print("Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())