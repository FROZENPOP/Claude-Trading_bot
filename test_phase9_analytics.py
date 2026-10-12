#!/usr/bin/env python3
"""Test script for Phase 9 performance analytics functionality."""

import sys
import os
from datetime import datetime, timedelta

# Add the trading_bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.monitoring.analytics import (
    PerformanceAnalytics, create_performance_analytics
)
from trading_bot.execution.phase8_execution_monitoring import ExecutionMonitor


def test_performance_analytics_creation():
    """Test creating PerformanceAnalytics instance."""
    print("=== Testing PerformanceAnalytics Creation ===")

    # Create a mock WebullExecution (we won't actually connect to API)
    class MockWebullExecution:
        def __init__(self):
            self.client = None

        def _is_option_symbol(self, symbol):
            # Simple mock - treat anything with C/P as option
            return 'C' in symbol or 'P' in symbol

    # Create execution monitor
    mock_webull = MockWebullExecution()
    monitor = ExecutionMonitor(
        webull_executor=mock_webull,  # Using Webull executor for testing
        check_interval=10,
        enable_auto_exit=False,
        enable_alerts=False
    )

    # Create performance analytics
    analytics = PerformanceAnalytics(monitor)

    print(f"PerformanceAnalytics created successfully")
    print(f"  Trade history length: {len(analytics.trade_history)}")
    print(f"  Daily returns length: {len(analytics.daily_returns)}")
    print(f"  Portfolio values length: {len(analytics.portfolio_values)}")
    print()


def test_trade_addition():
    """Test adding completed trades."""
    print("=== Testing Trade Addition ===")

    class MockWebullExecution:
        def __init__(self):
            self.client = None

        def _is_option_symbol(self, symbol):
            return 'C' in symbol or 'P' in symbol

    mock_webull = MockWebullExecution()
    monitor = ExecutionMonitor(
        webull_executor=mock_webull,  # Using Webull executor for testing
        check_interval=10,
        enable_auto_exit=False,
        enable_alerts=False
    )

    analytics = PerformanceAnalytics(monitor)

    # Add a winning trade
    analytics.add_completed_trade(
        symbol="AAPL261016C00190000",
        side="buy",
        quantity=2,
        entry_price=5.00,
        exit_price=6.50,  # Profit
        entry_time=datetime.now() - timedelta(days=5),
        exit_time=datetime.now() - timedelta(days=3),
        tags=["bull_call", "long_aapl"]
    )

    # Add a losing trade
    analytics.add_completed_trade(
        symbol="TSLA261016P00250000",
        side="sell",
        quantity=1,
        entry_price=3.00,
        exit_price=4.50,  # Loss (price went up against short put)
        entry_time=datetime.now() - timedelta(days=7),
        exit_time=datetime.now() - timedelta(days=2),
        tags=["cash_secured_put", "short_tsla"]
    )

    # Add another winning trade
    analytics.add_completed_trade(
        symbol="MSFT261016C00300000",
        side="buy",
        quantity=3,
        entry_price=4.00,
        exit_price=5.20,  # Profit
        entry_time=datetime.now() - timedelta(days=4),
        exit_time=datetime.now() - timedelta(days=1),
        tags=["bull_call", "long_msft"]
    )

    print(f"Added 3 trades. Trade history length: {len(analytics.trade_history)}")

    # Verify trade details
    if len(analytics.trade_history) >= 3:
        trade1 = analytics.trade_history[0]
        trade2 = analytics.trade_history[1]
        trade3 = analytics.trade_history[2]

        print(f"Trade 1: {trade1['symbol']} {trade1['side']} {trade1['quantity']} - P&L: ${trade1['pnl']:.2f} ({'WIN' if trade1['is_win'] else 'LOSS'})")
        print(f"Trade 2: {trade2['symbol']} {trade2['side']} {trade2['quantity']} - P&L: ${trade2['pnl']:.2f} ({'WIN' if trade2['is_win'] else 'LOSS'})")
        print(f"Trade 3: {trade3['symbol']} {trade3['side']} {trade3['quantity']} - P&L: ${trade3['pnl']:.2f} ({'WIN' if trade3['is_win'] else 'LOSS'})")

    print()


def test_performance_metrics():
    """Test performance metric calculations."""
    print("=== Testing Performance Metrics ===")

    class MockWebullExecution:
        def __init__(self):
            self.client = None

        def _is_option_symbol(self, symbol):
            return 'C' in symbol or 'P' in symbol

    mock_webull = MockWebullExecution()
    monitor = ExecutionMonitor(
        webull_executor=mock_webull,  # Using Webull executor for testing
        check_interval=10,
        enable_auto_exit=False,
        enable_alerts=False
    )

    analytics = PerformanceAnalytics(monitor)

    # Add test trades
    analytics.add_completed_trade(
        symbol="AAPL261016C00190000",
        side="buy",
        quantity=2,
        entry_price=5.00,
        exit_price=6.50,  # $3.00 profit per share * 2 * 100 = $600
        entry_time=datetime.now() - timedelta(days=5),
        exit_time=datetime.now() - timedelta(days=3),
        tags=["bull_call"]
    )

    analytics.add_completed_trade(
        symbol="TSLA261016P00250000",
        side="sell",
        quantity=1,
        entry_price=3.00,
        exit_price=4.50,  # $1.50 loss per share * 1 * 100 = $150 loss
        entry_time=datetime.now() - timedelta(days=7),
        exit_time=datetime.now() - timedelta(days=2),
        tags=["cash_secured_put"]
    )

    analytics.add_completed_trade(
        symbol="MSFT261016C00300000",
        side="buy",
        quantity=1,
        entry_price=4.00,
        exit_price=5.00,  # $1.00 profit per share * 1 * 100 = $100
        entry_time=datetime.now() - timedelta(days=4),
        exit_time=datetime.now() - timedelta(days=1),
        tags=["bull_call"]
    )

    # Set up portfolio values for return calculations
    analytics.portfolio_values = [
        (datetime.now() - timedelta(days=10), 95000.0),
        (datetime.now() - timedelta(days=5), 98000.0),
        (datetime.now(), 102000.0)  # Total profit of $700 from trades + any other changes
    ]
    analytics.daily_returns = [2.0, -1.0, 3.0]  # Sample daily returns

    # Test metrics
    win_rate = analytics.calculate_win_rate()
    avg_return = analytics.calculate_average_return()
    avg_win = analytics.calculate_average_win()
    avg_loss = analytics.calculate_average_loss()
    profit_factor = analytics.calculate_profit_factor()
    sharpe_ratio = analytics.calculate_sharpe_ratio()
    max_drawdown = analytics.calculate_max_drawdown()
    total_return = analytics.calculate_total_return()

    print(f"Win Rate: {win_rate:.1f}% (expected: 66.7%)")
    print(f"Average Return/Trade: {avg_return:.2f}%")
    print(f"Average Win: ${avg_win:.2f} (expected: $350.00)")
    print(f"Average Loss: ${avg_loss:.2f} (expected: $150.00)")
    print(f"Profit Factor: {profit_factor:.2f} (expected: 4.67)")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2f}%")
    print(f"Total Return: {total_return:.2f}%")

    # Verify expected values (approximately)
    assert abs(win_rate - 66.7) < 1.0, f"Win rate should be ~66.7%, got {win_rate}"
    assert abs(avg_win - 200.0) < 1.0, f"Average win should be ~$200, got ${avg_win}"
    assert abs(avg_loss - 150.0) < 1.0, f"Average loss should be ~$150, got ${avg_loss}"
    assert abs(profit_factor - 2.67) < 0.5, f"Profit factor should be ~2.67, got {profit_factor}"

    print("All performance metrics calculated correctly!")
    print()


def test_strategy_performance():
    """Test strategy-specific performance analysis."""
    print("=== Testing Strategy Performance ===")

    class MockWebullExecution:
        def __init__(self):
            self.client = None

        def _is_option_symbol(self, symbol):
            return 'C' in symbol or 'P' in symbol

    mock_webull = MockWebullExecution()
    monitor = ExecutionMonitor(
        webull_executor=mock_webull,  # Using Webull executor for testing
        check_interval=10,
        enable_auto_exit=False,
        enable_alerts=False
    )

    analytics = PerformanceAnalytics(monitor)

    # Add trades with different tags
    analytics.add_completed_trade(
        symbol="AAPL261016C00190000",
        side="buy",
        quantity=2,
        entry_price=5.00,
        exit_price=6.50,
        entry_time=datetime.now() - timedelta(days=5),
        exit_time=datetime.now() - timedelta(days=3),
        tags=["bull_call", "long_aapl"]
    )

    analytics.add_completed_trade(
        symbol="AAPL261016P00190000",
        side="sell",
        quantity=1,
        entry_price=2.00,
        exit_price=1.50,
        entry_time=datetime.now() - timedelta(days=4),
        exit_time=datetime.now() - timedelta(days=1),
        tags=["bull_put", "short_aapl"]
    )

    analytics.add_completed_trade(
        symbol="MSFT261016C00300000",
        side="buy",
        quantity=1,
        entry_price=4.00,
        exit_price=5.00,
        entry_time=datetime.now() - timedelta(days=3),
        exit_time=datetime.now(),
        tags=["bull_call", "long_msft"]
    )

    # Test strategy performance
    bull_call_perf = analytics.get_strategy_performance("bull_call")
    long_aapl_perf = analytics.get_strategy_performance("long_aapl")
    short_tsla_perf = analytics.get_strategy_performance("short_tsla")  # Should be empty

    print(f"Bull Call Strategy:")
    print(f"  Trades: {bull_call_perf['trade_count']} (expected: 2)")
    print(f"  Win Rate: {bull_call_perf['win_rate']:.1f}%")
    print(f"  Total P&L: ${bull_call_perf['total_pnl']:.2f}")
    print(f"  Average Return: {bull_call_perf['average_return']:.2f}%")

    print(f"\nLong AAPL Strategy:")
    print(f"  Trades: {long_aapl_perf['trade_count']} (expected: 1)")
    print(f"  Win Rate: {long_aapl_perf['win_rate']:.1f}% (expected: 100.0%)")
    print(f"  Total P&L: ${long_aapl_perf['total_pnl']:.2f} (expected: $300.00)")

    print(f"\nShort TSLA Strategy:")
    print(f"  Trades: {short_tsla_perf['trade_count']} (expected: 0)")

    # Verify expected values
    assert bull_call_perf['trade_count'] == 2, f"Bull call should have 2 trades, got {bull_call_perf['trade_count']}"
    assert long_aapl_perf['trade_count'] == 1, f"Long AAPL should have 1 trade, got {long_aapl_perf['trade_count']}"
    assert short_tsla_perf['trade_count'] == 0, f"Short TSLA should have 0 trades, got {short_tsla_perf['trade_count']}"
    assert abs(long_aapl_perf['total_pnl'] - 300.0) < 1.0, f"Long AAPL P&L should be $300, got ${long_aapl_perf['total_pnl']}"

    print("Strategy performance analysis working correctly!")
    print()


def test_factory_function():
    """Test the factory function."""
    print("=== Testing Factory Function ===")

    class MockWebullExecution:
        def __init__(self):
            self.client = None

        def _is_option_symbol(self, symbol):
            return 'C' in symbol or 'P' in symbol

    # Test factory function
    mock_webull = MockWebullExecution()
    monitor = ExecutionMonitor(
        webull_executor=mock_webull,  # Using Webull executor for testing
        check_interval=10,
        enable_auto_exit=False,
        enable_alerts=False
    )

    analytics = create_performance_analytics(monitor)

    print(f"Factory function created PerformanceAnalytics instance")
    print(f"  Type: {type(analytics).__name__}")
    print(f"  Has monitor: {analytics.monitor is not None}")
    print()

    print("Factory function working correctly!")
    print()


def main():
    """Run all tests."""
    print("Testing Phase 9 Performance Analytics Functionality")
    print("=" * 55)

    try:
        test_performance_analytics_creation()
        test_trade_addition()
        test_performance_metrics()
        test_strategy_performance()
        test_factory_function()

        print("All tests completed successfully!")

    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())