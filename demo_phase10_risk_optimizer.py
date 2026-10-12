#!/usr/bin/env python3
"""
Demonstration of Phase 10: Risk Management and Optimization
Shows how to use the RiskOptimizer with ExecutionMonitor and PerformanceAnalytics
"""

import sys
import os
from datetime import datetime, timedelta

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from trading_bot.monitoring.risk_optimizer import create_risk_optimizer
from trading_bot.execution.phase8_execution_monitoring import ExecutionMonitor
from trading_bot.monitoring.analytics import PerformanceAnalytics


def demo_alert(message: str):
    """Simple alert function for demonstration."""
    print(f"[ALERT] {message}")


def main():
    """Run the Phase 10 risk optimizer demonstration."""
    print("=== Autonomous Trading System - Phase 10 Demo ===\n")
    print("Risk Management and Optimization\n")

    # Create mock Webull execution component (simulating Phase 7)
    class MockWebullExecution:
        def __init__(self):
            self.client = MockWebullClient()

        def _is_option_symbol(self, symbol):
            import re
            # Simple option symbol pattern: e.g., AAPL261016C00190000
            option_pattern = r'^[A-Z]+\d{6}[CP]\d{8}$'
            return bool(re.match(option_pattern, symbol))

    class MockWebullClient:
        def get_account(self):
            class MockAccount:
                portfolio_value = 100000.0  # $100k starting portfolio
            return MockAccount()

    # Set up ExecutionMonitor (from Phase 8)
    mock_webull = MockWebullExecution()
    monitor = ExecutionMonitor(
        webull_executor=mock_webull,  # Using Webull executor for demo
        check_interval=30,
        enable_auto_exit=False,
        enable_alerts=False  # We'll use our demo_alert instead
    )

    # Override the alert function to use our demo version
    monitor.send_alert = demo_alert

    # Set up PerformanceAnalytics (from Phase 9)
    analytics = PerformanceAnalytics(monitor)

    # Create RiskOptimizer (Phase 10)
    risk_optimizer = create_risk_optimizer(monitor, analytics)

    print("1. System Components Initialized")
    print(f"   - ExecutionMonitor: {type(monitor).__name__}")
    print(f"   - PerformanceAnalytics: {type(analytics).__name__}")
    print(f"   - RiskOptimizer: {type(risk_optimizer).__name__}\n")

    # Add some sample trades to demonstrate functionality
    print("2. Adding Sample Trade History")

    # Add winning trades
    analytics.add_completed_trade(
        symbol="AAPL261016C00190000",
        side="buy",
        quantity=2,
        entry_price=5.00,
        exit_price=6.50,
        entry_time=datetime.now() - timedelta(days=5),
        exit_time=datetime.now() - timedelta(days=3),
        tags=["bull_call", "long_aapl", "tech"]
    )

    analytics.add_completed_trade(
        symbol="MSFT261016C00300000",
        side="buy",
        quantity=3,
        entry_price=4.00,
        exit_price=5.50,
        entry_time=datetime.now() - timedelta(days=4),
        exit_time=datetime.now() - timedelta(days=1),
        tags=["bull_call", "long_msft", "tech"]
    )

    # Add losing trades
    analytics.add_completed_trade(
        symbol="TSLA261016P00250000",
        side="sell",
        quantity=1,
        entry_price=3.00,
        exit_price=2.00,
        entry_time=datetime.now() - timedelta(days=7),
        exit_time=datetime.now() - timedelta(days=2),
        tags=["bear_put", "short_tsla", "volatile"]
    )

    analytics.add_completed_trade(
        symbol="GOOGL261016C00120000",
        side="buy",
        quantity=1,
        entry_price=8.00,
        exit_price=7.00,
        entry_time=datetime.now() - timedelta(days=6),
        exit_time=datetime.now() - timedelta(days=4),
        tags=["bull_call", "long_googl", "tech"]
    )

    # Set up portfolio values for return calculation
    analytics.portfolio_values = [
        (datetime.now() - timedelta(days=15), 95000.0),
        (datetime.now() - timedelta(days=10), 97000.0),
        (datetime.now() - timedelta(days=5), 99000.0),
        (datetime.now(), 102000.0)  # Overall profit
    ]
    analytics.daily_returns = [2.1, 1.8, -0.5, 3.2]

    print(f"   - Added {len(analytics.trade_history)} sample trades\n")

    # Demonstrate risk optimizer functionality
    print("3. Risk Parameter Updates")
    risk_optimizer.update_risk_parameters()
    print(f"   - Max Position Size: {risk_optimizer.max_position_size:.2%}")
    print(f"   - Max Daily Loss: {risk_optimizer.max_daily_loss:.2%}")
    print(f"   - Max Portfolio Risk: {risk_optimizer.max_portfolio_risk:.2%}\n")

    # Demonstrate position sizing
    print("4. Optimal Position Sizing Examples")

    # Stock position sizing
    stock_qty = risk_optimizer.calculate_optimal_position_size(
        symbol="AAPL",
        entry_price=150.00,
        stop_loss=140.00,
        strategy_tags=["long_aapl"]
    )
    print(f"   - AAPL stock position: {stock_qty} shares")
    print(f"     (Entry: $150.00, Stop: $140.00, Risk: $10.00/share)")

    # Option position sizing
    option_qty = risk_optimizer.calculate_optimal_position_size(
        symbol="AAPL261016C00190000",
        entry_price=6.00,
        stop_loss=5.00,
        strategy_tags=["bull_call", "long_aapl"]
    )
    print(f"   - AAPL call option position: {option_qty} contracts")
    print(f"     (Entry: $6.00, Stop: $5.00, Risk: $1.00/contract)")
    print(f"     (Actual risk: ${option_qty * 1.00 * 100:.2f} for {option_qty} contracts)\n")

    # Demonstrate volatility-adjusted stop loss
    print("5. Volatility-Adjusted Stop Loss Examples")

    # Long position stop loss
    long_adj_stop = risk_optimizer.get_risk_adjusted_stop_loss(
        symbol="AAPL261016C00190000",
        entry_price=6.00,
        initial_stop_loss=5.00,
        is_long=True
    )
    print(f"   - Long AAPL call: ${5.00} -> ${long_adj_stop:.2f}")

    # Short position stop loss
    short_adj_stop = risk_optimizer.get_risk_adjusted_stop_loss(
        symbol="TSLA261016P00250000",
        entry_price=3.00,
        initial_stop_loss=4.00,
        is_long=False
    )
    print(f"   - Short TSLA put: ${4.00} -> ${short_adj_stop:.2f}\n")

    # Demonstrate portfolio risk calculation
    print("6. Portfolio Risk Metrics")
    risk_metrics = risk_optimizer.calculate_portfolio_risk()

    if 'error' not in risk_metrics:
        print(f"   - Portfolio Value: ${risk_metrics['portfolio_value']:,.2f}")
        print(f"   - Total Exposure: ${risk_metrics['total_exposure']:,.2f}")
        print(f"   - Portfolio Risk: {risk_metrics['portfolio_risk_pct']:.2f}%")
        print(f"   - Daily P&L: {risk_metrics['daily_pnl_pct']:.2f}%")
        print(f"   - Risk Utilization:")
        for key, value in risk_metrics['risk_utilization'].items():
            print(f"     * {key}: {value:.2%}")
    else:
        print(f"   - Error calculating risk: {risk_metrics['error']}")
    print()

    # Demonstrate risk recommendations
    print("7. Risk Management Recommendations")
    recommendations = risk_optimizer.generate_risk_recommendations()

    for i, rec in enumerate(recommendations, 1):
        print(f"   {i}. [{rec['type'].upper()}] {rec['component']}")
        print(f"      {rec['message']}")
        print(f"      → {rec['suggestion']}\n")

    # Demonstrate system status
    print("8. System Status")
    status = risk_optimizer.get_risk_optimization_status()
    print(f"   - Trades Processed: {status['performance_trades_count']}")
    print(f"   - Recommendations Generated: {status['recommendations_count']}")
    print(f"   - Volatility Estimates Tracked: {len(status['volatility_estimates'])} symbols")
    print(f"   - Strategy Weights Tracked: {len(status['strategy_weights'])} strategies")

    if status['volatility_estimates']:
        print("   - Sample Volatility Estimates:")
        for symbol, vol in list(status['volatility_estimates'].items())[:3]:
            print(f"     * {symbol}: {vol:.2%} annualized")

    if status['strategy_weights']:
        print("   - Sample Strategy Weights:")
        for strategy, weight in list(status['strategy_weights'].items())[:3]:
            print(f"     * {strategy}: {weight:.2f}x")
    print()

    print("=== Phase 10 Demonstration Complete ===")
    print("\nKey Features Demonstrated:")
    print("✓ Dynamic position sizing based on performance and volatility")
    print("✓ Strategy allocation optimization based on historical performance")
    print("✓ Volatility-based risk adjustment")
    print("✓ Portfolio risk calculation and monitoring")
    print("✓ Automated risk management recommendations")
    print("✓ Integration with ExecutionMonitor (Phase 8) and PerformanceAnalytics (Phase 9)")
    print("\nThe RiskOptimizer provides advanced risk management capabilities that")
    print("build upon the foundation laid in previous phases to optimize")
    print("system performance while preserving capital.")


if __name__ == "__main__":
    main()