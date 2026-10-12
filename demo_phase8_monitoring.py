#!/usr/bin/env python3
"""Demo script showing Phase 8 execution monitoring functionality.

This demonstrates how to use the ExecutionMonitor to:
1. Track positions and monitor for exit conditions
2. Set up stop losses and take profits
3. Monitor position P&L
4. Generate alerts for position events
"""

import sys
import os
from datetime import datetime, timedelta

# Add the trading_bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.execution.phase8_execution_monitoring import (
    ExecutionMonitor, create_execution_monitor
)
from trading_bot.execution.webull_execution import WebullExecution
from trading_bot.execution.webull import OrderSide


def demo_basic_monitoring():
    """Demonstrate basic position monitoring functionality."""
    print("=== Phase 8 Execution Monitoring Demo ===\n")

    # Create a mock WebullExecution for demonstration (no real API calls)
    class DemoWebullExecution:
        def __init__(self):
            self.client = None

        def _is_option_symbol(self, symbol):
            # Simple mock - treat anything with C/P as option
            return 'C' in symbol or 'P' in symbol

    # Create execution monitor with demo executor
    demo_webull = DemoWebullExecution()
    monitor = ExecutionMonitor(
        webull_executor=demo_webull,  # Using Webull executor for demo
        check_interval=5,  # Check every 5 seconds for demo
        enable_auto_exit=False,  # Manual exit for demo
        enable_alerts=True
    )

    # Add alert callback to see alerts in console
    def demo_alert(message):
        print(f"[ALERT] {message}")

    monitor.add_alert_callback(demo_alert)

    print("1. Adding positions to monitor...")

    # Add a bull call spread position (buy lower strike, sell higher strike)
    monitor.add_position(
        symbol="AAPL261016C00190000",  # Buy AAPL 190 call
        qty=2,
        side=OrderSide.BUY,
        entry_price=5.50,
        stop_loss=4.00,    # Stop loss at $4.00
        take_profit=8.00,  # Take profit at $8.00
        max_hold_time=timedelta(days=30),
        tags=["bull_call_spread", "long_aapl"]
    )

    monitor.add_position(
        symbol="AAPL261016C00200000",  # Sell AAPL 200 call
        qty=2,
        side=OrderSide.SELL,
        entry_price=3.00,
        stop_loss=5.00,    # Stop loss at $5.00 (if price goes against us)
        take_profit=1.50,  # Take profit at $1.50
        max_hold_time=timedelta(days=30),
        tags=["bull_call_spread", "short_aapl"]
    )

    print(f"   Added {len(monitor.positions)} positions to monitor\n")

    print("2. Setting up position prices for demonstration...")

    # Simulate current market prices
    if "AAPL261016C00190000" in monitor.positions:
        monitor.positions["AAPL261016C00190000"].current_price = 6.00  # Up $0.50
    if "AAPL261016C00200000" in monitor.positions:
        monitor.positions["AAPL261016C00200000"].current_price = 2.50  # Down $0.50

    print("   Simulated market prices:")
    print("   - AAPL 190 Call: $6.00 (entry: $5.50)")
    print("   - AAPL 200 Call: $2.50 (entry: $3.00)\n")

    print("3. Checking position summary...")

    summary = monitor.get_position_summary()
    print(f"   Open positions: {summary['open_positions_count']}")
    print(f"   Total unrealized P&L: ${summary['total_unrealized_pnl']:.2f}")
    print(f"   Total realized P&L: ${summary['total_realized_pnl']:.2f}")
    print(f"   Total P&L: ${summary['total_pnl']:.2f}\n")

    print("4. Checking for exit conditions...")

    exit_signals = monitor.check_exit_conditions()
    print(f"   Exit signals detected: {len(exit_signals)}")

    for signal in exit_signals:
        pos = monitor.positions[signal.position_symbol]
        print(f"   - {signal.position_symbol}: {signal.exit_reason} @ ${signal.exit_price:.2f}")
        print(f"     Position: {pos.side.value} {pos.qty} @ ${pos.entry_price:.2f}")
        print(f"     Current: ${pos.current_price:.2f}")

    print()

    print("5. Demonstrating position updates...")

    # Simulate price movement that triggers exit
    print("   Simulating price move to trigger stop loss on short position...")
    if "AAPL261016C00200000" in monitor.positions:
        monitor.positions["AAPL261016C00200000"].current_price = 5.20  # Above stop loss of $5.00

    exit_signals = monitor.check_exit_conditions()
    if exit_signals:
        signal = exit_signals[0]
        print(f"   EXIT SIGNAL: {signal.exit_reason} for {signal.position_symbol}")
        print(f"   Reason: Price ${signal.exit_price:.2f} triggered {signal.exit_reason}")

    print()

    print("6. Showing position history capabilities...")

    # Show that we can track closed positions
    print(f"   Currently tracking {len(monitor.positions)} open positions")
    print(f"   Position history tracking: {len(monitor.closed_positions)} closed positions")

    print("\n=== Demo Complete ===")
    print("The ExecutionMonitor successfully:")
    print("  * Tracks open positions with entry/exit prices")
    print("  * Monitors for stop loss, take profit, and time-based exits")
    print("  * Calculates unrealized and realized P&L")
    print("  * Generates alerts for position events")
    print("  * Maintains history of closed positions")
    print("\nIn a live system, this would:")
    print("  • Connect to Webull API for real position data")
    print("  • Automatically submit exit orders when signals are triggered")
    print("  • Provide real-time P&L tracking and risk management")


def demo_factory_function():
    """Demonstrate using the factory function."""
    print("\n=== Factory Function Demo ===")

    # This shows how you would create a monitor for live trading
    # (Commented out to prevent actual API calls in demo)
    """
    monitor = create_execution_monitor(
        paper=True,  # Use paper trading
        check_interval=30,  # Check every 30 seconds
        max_daily_loss=0.05,  # 5% max daily loss
        max_position_size=0.10,  # 10% max position size
        max_daily_trades=10  # Max 10 trades per day
    )

    # Add your alert handler
    def my_alert_handler(message):
        # Send email, Slack notification, etc.
        print(f"[TRADING ALERT] {message}")

    monitor.add_alert_handler(my_alert_handler)

    # Start monitoring
    monitor.start()

    # ... let it run ...

    # Stop when done
    # monitor.stop()
    """

    print("Factory function create_execution_monitor() available for live trading")
    print("Returns configured ExecutionMonitor with Webull executor")


if __name__ == "__main__":
    demo_basic_monitoring()
    demo_factory_function()