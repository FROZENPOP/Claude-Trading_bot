#!/usr/bin/env python3
"""Test script for Phase 8 execution monitoring functionality."""

import sys
import os
from datetime import datetime, timedelta

# Add the trading_bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.execution.phase8_execution_monitoring import (
    ExecutionMonitor, PositionInfo, ExitSignal, OrderSide
)
from trading_bot.execution.webull_execution import WebullExecution


def test_position_info_creation():
    """Test creating PositionInfo objects."""
    print("=== Testing PositionInfo Creation ===")

    pos = PositionInfo(
        symbol="AAPL261016C00190000",
        qty=2,
        side=OrderSide.BUY,
        entry_price=5.50,
        current_price=6.00,
        unrealized_pnl=0.0,
        realized_pnl=0.0,
        entry_time=datetime.now(),
        stop_loss=4.50,
        take_profit=7.50,
        max_hold_time=timedelta(days=7),
        tags=["test", "bull_call"]
    )

    print(f"Created position: {pos.symbol} {pos.side.value} {pos.qty} @ ${pos.entry_price:.2f}")
    print(f"Current price: ${pos.current_price:.2f}")
    print(f"Stop loss: ${pos.stop_loss:.2f}")
    print(f"Take profit: ${pos.take_profit:.2f}")
    print()


def test_exit_signal_creation():
    """Test creating ExitSignal objects."""
    print("=== Testing ExitSignal Creation ===")

    signal = ExitSignal(
        position_symbol="AAPL261016C00190000",
        exit_reason="take_profit",
        exit_price=7.50,
        qty_to_exit=2,
        timestamp=datetime.now()
    )

    print(f"Exit signal: {signal.exit_reason} for {signal.position_symbol}")
    print(f"Quantity: {signal.qty_to_exit} @ ${signal.exit_price:.2f}")
    print(f"Timestamp: {signal.timestamp}")
    print()


def test_execution_monitor_creation():
    """Test creating ExecutionMonitor instance."""
    print("=== Testing ExecutionMonitor Creation ===")

    # Create a mock WebullExecution (we won't actually connect to API)
    class MockWebullExecution:
        def __init__(self):
            self.client = None

        def _is_option_symbol(self, symbol):
            # Simple mock - treat anything with C/P as option
            return 'C' in symbol or 'P' in symbol

    mock_webull = MockWebullExecution()
    monitor = ExecutionMonitor(
        webull_executor=mock_webull,
        check_interval=10,
        enable_auto_exit=False,
        enable_alerts=True
    )

    print(f"ExecutionMonitor created:")
    print(f"  Check interval: {monitor.check_interval}s")
    print(f"  Auto exit enabled: {monitor.enable_auto_exit}")
    print(f"  Alerts enabled: {monitor.enable_alerts}")
    print(f"  Open positions: {len(monitor.positions)}")
    print()


def test_position_management():
    """Test adding and managing positions."""
    print("=== Testing Position Management ===")

    class MockWebullExecution:
        def __init__(self):
            self.client = None

        def _is_option_symbol(self, symbol):
            return 'C' in symbol or 'P' in symbol

    mock_webull = MockWebullExecution()
    monitor = ExecutionMonitor(
        webull_executor=mock_webull,
        check_interval=10,
        enable_auto_exit=False,
        enable_alerts=False
    )

    # Add a position
    monitor.add_position(
        symbol="AAPL261016C00190000",
        qty=1,
        side=OrderSide.BUY,
        entry_price=5.00,
        stop_loss=4.00,
        take_profit=7.00,
        tags=["test"]
    )

    print(f"Added position. Open positions: {len(monitor.positions)}")

    # Check position details
    if "AAPL261016C00190000" in monitor.positions:
        pos = monitor.positions["AAPL261016C00190000"]
        print(f"Position details:")
        print(f"  Symbol: {pos.symbol}")
        print(f"  Side: {pos.side.value}")
        print(f"  Qty: {pos.qty}")
        print(f"  Entry price: ${pos.entry_price:.2f}")
        print(f"  Current price: ${pos.current_price:.2f}")
        print(f"  Tags: {pos.tags}")

    # Test adding same position again (should update)
    monitor.add_position(
        symbol="AAPL261016C00190000",
        qty=2,  # Different quantity
        side=OrderSide.BUY,
        entry_price=5.50,  # Different price
        stop_loss=4.50,
        take_profit=7.50,
        tags=["updated"]
    )

    print(f"After update. Open positions: {len(monitor.positions)}")
    if "AAPL261016C00190000" in monitor.positions:
        pos = monitor.positions["AAPL261016C00190000"]
        print(f"Updated position: {pos.qty} contracts @ ${pos.entry_price:.2f}")
        print(f"Tags: {pos.tags}")

    print()


def test_exit_conditions():
    """Test exit condition checking."""
    print("=== Testing Exit Condition Checking ===")

    class MockWebullExecution:
        def __init__(self):
            self.client = None

        def _is_option_symbol(self, symbol):
            return 'C' in symbol or 'P' in symbol

    mock_webull = MockWebullExecution()
    monitor = ExecutionMonitor(
        webull_executor=mock_webull,
        check_interval=10,
        enable_auto_exit=False,
        enable_alerts=False
    )

    # Add a position with stop loss and take profit
    monitor.add_position(
        symbol="AAPL261016C00190000",
        qty=1,
        side=OrderSide.BUY,
        entry_price=5.00,
        stop_loss=4.00,
        take_profit=7.00,
        tags=["exit_test"]
    )

    # Manually set current price to test exit conditions
    pos = monitor.positions["AAPL261016C00190000"]

    # Test 1: Price in range - no exit
    pos.current_price = 5.50
    exit_signals = monitor.check_exit_conditions()
    print(f"Price $5.50: {len(exit_signals)} exit signals (expected: 0)")

    # Test 2: Price at stop loss - should trigger exit
    pos.current_price = 4.00
    exit_signals = monitor.check_exit_conditions()
    print(f"Price $4.00 (stop loss): {len(exit_signals)} exit signals (expected: 1)")
    if exit_signals:
        signal = exit_signals[0]
        print(f"  Reason: {signal.exit_reason}")
        print(f"  Price: ${signal.exit_price:.2f}")

    # Reset and test take profit
    pos.current_price = 5.00
    exit_signals = monitor.check_exit_conditions()
    print(f"Price $5.00 (reset): {len(exit_signals)} exit signals (expected: 0)")

    # Test 3: Price at take profit - should trigger exit
    pos.current_price = 7.00
    exit_signals = monitor.check_exit_conditions()
    print(f"Price $7.00 (take profit): {len(exit_signals)} exit signals (expected: 1)")
    if exit_signals:
        signal = exit_signals[0]
        print(f"  Reason: {signal.exit_reason}")
        print(f"  Price: ${signal.exit_price:.2f}")

    print()


def test_position_summary():
    """Test position summary generation."""
    print("=== Testing Position Summary ===")

    class MockWebullExecution:
        def __init__(self):
            self.client = None

        def _is_option_symbol(self, symbol):
            return 'C' in symbol or 'P' in symbol

    mock_webull = MockWebullExecution()
    monitor = ExecutionMonitor(
        webull_executor=mock_webull,
        check_interval=10,
        enable_auto_exit=False,
        enable_alerts=False
    )

    # Add a couple positions
    monitor.add_position(
        symbol="AAPL261016C00190000",
        qty=1,
        side=OrderSide.BUY,
        entry_price=5.00,
        tags=["test1"]
    )

    monitor.add_position(
        symbol="MSFT261016P00300000",
        qty=2,
        side=OrderSide.SELL,
        entry_price=3.00,
        tags=["test2"]
    )

    # Manually set current prices for testing (in real usage, this would come from market data)
    if "AAPL261016C00190000" in monitor.positions:
        monitor.positions["AAPL261016C00190000"].current_price = 5.50
    if "MSFT261016P00300000" in monitor.positions:
        monitor.positions["MSFT261016P00300000"].current_price = 2.50

    # Get summary
    summary = monitor.get_position_summary()

    print(f"Position Summary:")
    print(f"  Timestamp: {summary['timestamp']}")
    print(f"  Open positions: {summary['open_positions_count']}")
    print(f"  Total unrealized P&L: ${summary['total_unrealized_pnl']:.2f}")
    print(f"  Total realized P&L: ${summary['total_realized_pnl']:.2f}")
    print(f"  Total P&L: ${summary['total_pnl']:.2f}")
    print(f"  Positions:")

    for pos in summary['positions']:
        print(f"    {pos['symbol']} {pos['side']} {pos['qty']} @ ${pos['entry_price']:.2f}")
        print(f"      Current: ${pos['current_price']:.2f}")
        print(f"      Unrealized P&L: ${pos['unrealized_pnl']:.2f}")
        print(f"      Total P&L: ${pos['total_pnl']:.2f}")

    print()


def main():
    """Run all tests."""
    print("Testing Phase 8 Execution Monitoring Functionality")
    print("=" * 50)

    try:
        test_position_info_creation()
        test_exit_signal_creation()
        test_execution_monitor_creation()
        test_position_management()
        test_exit_conditions()
        test_position_summary()

        print("All tests completed successfully!")

    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())