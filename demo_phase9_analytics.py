#!/usr/bin/env python3
"""Demo script showing Phase 9 performance analytics functionality.

This demonstrates how to use the PerformanceAnalytics to:
1. Track completed trades
2. Calculate performance metrics (win rate, average return, Sharpe ratio, etc.)
3. Analyze strategy-specific performance
4. Generate comprehensive performance reports
"""

import sys
import os
from datetime import datetime, timedelta

# Add the trading_bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.monitoring.analytics import create_performance_analytics
from trading_bot.execution.phase8_execution_monitoring import ExecutionMonitor


def demo_performance_analytics():
    """Demonstrate performance analytics functionality."""
    print("=== Phase 9 Performance Analytics Demo ===\n")

    # Create mock components for demonstration
    class MockWebullExecution:
        def __init__(self):
            self.client = None

        def _is_option_symbol(self, symbol):
            # Simple mock - treat anything with C/P as option
            import re
            option_pattern = r'^[A-Z]+\d{6}[CP]\d{8}$'
            return bool(re.match(option_pattern, symbol))

    class MockWebullClient:
        def get_account(self):
            class MockAccount:
                portfolio_value = 100000.0  # $100k starting portfolio
            return MockAccount()

    # Set up execution monitor
    mock_webull = MockWebullExecution()
    mock_webull.client = MockWebullClient()

    monitor = ExecutionMonitor(
        webull_executor=mock_webull,  # Using Webull executor for demo
        check_interval=30,
        enable_auto_exit=False,
        enable_alerts=False
    )

    # Create performance analytics
    analytics = create_performance_analytics(monitor)

    print("1. Adding sample trades to performance history...")

    # Add some sample trades
    trades_data = [
        # Winning bull call spread (long call)
        {
            "symbol": "AAPL261016C00190000",
            "side": "buy",
            "quantity": 2,
            "entry_price": 5.50,
            "exit_price": 7.00,  # $1.50 profit per share
            "days_ago_entry": 10,
            "days_ago_exit": 5,
            "tags": ["bull_call", "long_aapl", "tech"]
        },
        # Losing trade (short put that went against us)
        {
            "symbol": "TSLA261016P00250000",
            "side": "sell",
            "quantity": 1,
            "entry_price": 3.00,
            "exit_price": 4.20,  # $1.20 loss per share (short put)
            "days_ago_entry": 8,
            "days_ago_exit": 3,
            "tags": ["cash_secured_put", "short_tsla"]
        },
        # Winning long call
        {
            "symbol": "MSFT261016C00300000",
            "side": "buy",
            "quantity": 3,
            "entry_price": 4.00,
            "exit_price": 5.20,  # $1.20 profit per share
            "days_ago_entry": 7,
            "days_ago_exit": 2,
            "tags": ["bull_call", "long_msft", "tech"]
        },
        # Winning covered call
        {
            "symbol": "AMZN261016C00350000",
            "side": "sell",
            "quantity": 1,
            "entry_price": 2.50,
            "exit_price": 0.80,  # $1.70 profit per share (time decay)
            "days_ago_entry": 6,
            "days_ago_exit": 1,
            "tags": ["covered_call", "short_amzn"]
        },
        # Losing trade (long call that didn't move enough)
        {
            "symbol": "GOOGL261016C00180000",
            "side": "buy",
            "quantity": 1,
            "entry_price": 6.00,
            "exit_price": 5.50,  # $0.50 loss per share
            "days_ago_entry": 5,
            "days_ago_exit": 0,  # Just closed today
            "tags": ["long_call", "speculative"]
        }
    ]

    for trade_data in trades_data:
        analytics.add_completed_trade(
            symbol=trade_data["symbol"],
            side=trade_data["side"],
            quantity=trade_data["quantity"],
            entry_price=trade_data["entry_price"],
            exit_price=trade_data["exit_price"],
            entry_time=datetime.now() - timedelta(days=trade_data["days_ago_entry"]),
            exit_time=datetime.now() - timedelta(days=trade_data["days_ago_exit"]),
            tags=trade_data["tags"]
        )

        print(f"   Added: {trade_data['symbol']} {trade_data['side']} {trade_data['quantity']} "
              f"@ ${trade_data['entry_price']:.2f} -> ${trade_data['exit_price']:.2f}")

    print(f"\n   Total trades added: {len(trades_data)}\n")

    print("2. Updating portfolio performance data...")

    # Simulate portfolio value over time for return calculations
    analytics.portfolio_values = [
        (datetime.now() - timedelta(days=15), 98000.0),  # Starting value
        (datetime.now() - timedelta(days=10), 99500.0),
        (datetime.now() - timedelta(days=5),  101000.0),
        (datetime.now(), 103500.0)  # Current value
    ]

    # Simulate daily returns
    analytics.daily_returns = [1.2, -0.8, 2.1, 1.5, -0.5, 3.2]  # Sample daily returns

    print("   Portfolio values and daily returns updated\n")

    print("3. Generating performance report...")

    # Generate and display performance report
    report = analytics.generate_performance_report()
    summary = report['summary']

    print("   PERFORMANCE SUMMARY")
    print("   " + "-" * 40)
    print(f"   Period: {report['timestamp']}")
    print(f"   Total Trades: {summary['total_trades']}")
    print(f"   Win Rate: {summary['win_rate']:.1f}%")
    print(f"   Total P&L: ${summary['total_pnl']:.2f}")
    print(f"   Total Return: {summary['total_return_pct']:.2f}%")
    print(f"   Average Return/Trade: {summary['average_return_per_trade']:.2f}%")
    print(f"   Average Win: ${summary['average_win']:.2f}")
    print(f"   Average Loss: ${summary['average_loss']:.2f}")
    print(f"   Profit Factor: {summary['profit_factor']:.2f}")
    print(f"   Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
    print(f"   Max Drawdown: {summary['max_drawdown']:.2f}%")

    print("\n4. Strategy-specific performance...")

    if report['strategies']:
        print("   " + "-" * 40)
        print("   STRATEGY BREAKDOWN")
        for tag, perf in report['strategies'].items():
            print(f"   {tag.upper()}:")
            print(f"     Trades: {perf['trade_count']}")
            print(f"     Win Rate: {perf['win_rate']:.1f}%")
            print(f"     Total P&L: ${perf['total_pnl']:.2f}")
            print(f"     Average Return: {perf['average_return']:.2f}%")
            print(f"     Profit Factor: {perf['profit_factor']:.2f}")

    print("\n5. Recent trades...")

    print("   " + "-" * 40)
    print("   RECENT TRADES (Last 5)")
    for i, trade in enumerate(report['recent_trades'][-5:], 1):
        pnl_str = f"+${trade['pnl']:.2f}" if trade['pnl'] >= 0 else f"-${abs(trade['pnl']):.2f}"
        print(f"   {i}. {trade['symbol']} {trade['side'].upper()} {trade['quantity']} "
              f"@{trade['entry_price']:.2f}->{trade['exit_price']:.2f} ({pnl_str})")

    print("\n" + "=" * 50)
    print("DEMO COMPLETE")
    print("=" * 50)
    print("The PerformanceAnalytics system successfully:")
    print("  • Tracks completed trades with detailed P&L calculation")
    print("  • Calculates key performance metrics (win rate, return, Sharpe, etc.)")
    print("  • Provides strategy-specific performance analysis")
    print("  • Generates comprehensive performance reports")
    print("  • Integrates with ExecutionMonitor from Phase 8")
    print("\nIn a live system, this would:")
    print("  • Continuously update with new completed trades")
    print("  • Provide real-time performance dashboards")
    print("  • Enable data-driven strategy optimization")
    print("  • Support risk-adjusted return analysis")


def demo_factory_function():
    """Demonstrate using the factory function."""
    print("\n=== Factory Function Demo ===")

    # This shows how you would create analytics for live trading
    # (Commented out to prevent actual API calls in demo)
    """
    # Set up live execution monitor (would need real API keys)
    # monitor = create_execution_monitor(paper=True, check_interval=30)

    # Create performance analytics using factory function
    # analytics = create_performance_analytics(monitor)
    #
    # # Add your alert handler for performance alerts
    # def performance_alert(message):
    #     # Send email, Slack notification, etc. when significant events occur
    #     print(f"[PERFORMANCE ALERT] {message}")
    #
    # analytics.add_alert_callback(performance_alert)
    #
    # # Generate reports periodically
    # # report = analytics.generate_performance_report()
    # """

    print("Factory function create_performance_analytics() available")
    print("Returns configured PerformanceAnalytics with ExecutionMonitor")


if __name__ == "__main__":
    demo_performance_analytics()
    demo_factory_function()