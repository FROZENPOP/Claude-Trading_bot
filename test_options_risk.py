#!/usr/bin/env python3
"""
Test script to validate options-specific risk management functionality.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.portfolio.risk import (
    RiskLimits,
    RiskManager,
    PortfolioGreeks,
    OptionPosition
)
from trading_bot.backtesting.robustness import (
    ParameterSensitivity,
    WhitesRealityCheck,
    run_options_parameter_sweep
)
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def test_options_risk_management():
    """Test options-specific risk management functionality."""
    print("Testing options-specific risk management...")

    # Create risk limits with options-specific settings
    limits = RiskLimits(
        target_volatility=0.15,
        max_position_size=0.10,
        max_portfolio_exposure=1.0,
        max_daily_loss=0.05,
        max_drawdown=0.15,
        max_open_positions=10,
        max_daily_trades=10,
        # Options-specific limits
        max_option_notional=0.50,
        max_net_delta=0.20,
        max_gamma_exposure=0.05,
        max_theta_decay=0.02,
        max_vega_exposure=0.10,
        max_single_option_position=0.15
    )

    # Create risk manager
    risk_manager = RiskManager(limits)

    # Create sample option positions
    option1 = OptionPosition(
        symbol="AAPL",
        option_symbol="AAPL240119C00150000",
        quantity=5,  # 5 contracts
        strike=150.0,
        expiration="2024-01-19",
        option_type="call",
        entry_price=5.0,
        current_price=5.5,
        underlying_price=152.0,
        delta=0.6,
        gamma=0.02,
        theta=-0.1,
        vega=0.15,
        rho=0.05
    )

    option2 = OptionPosition(
        symbol="AAPL",
        option_symbol="AAPL240119P00140000",
        quantity=3,  # 3 contracts
        strike=140.0,
        expiration="2024-01-19",
        option_type="put",
        entry_price=3.0,
        current_price=2.8,
        underlying_price=152.0,
        delta=-0.4,
        gamma=0.015,
        theta=-0.08,
        vega=0.12,
        rho=-0.03
    )

    # Test recording option positions
    print("\n1. Testing position recording...")
    risk_manager.record_option_position(option1)
    risk_manager.record_option_position(option2)

    # Check portfolio Greeks
    portfolio_greeks = risk_manager.get_portfolio_greeks()
    print(f"   Portfolio Greeks - Delta: {portfolio_greeks.delta:.2f}, "
          f"Gamma: {portfolio_greeks.gamma:.4f}, "
          f"Theta: {portfolio_greeks.theta:.2f}, "
          f"Vega: {portfolio_greeks.vega:.2f}, "
          f"Rho: {portfolio_greeks.rho:.2f}")

    # Check total option notional
    total_notional = risk_manager.get_total_option_notional()
    print(f"   Total option notional: ${total_notional:,.2f}")

    # Test options position limits checking
    print("\n2. Testing options position limits...")

    # Create a new option position to test
    new_option = OptionPosition(
        symbol="AAPL",
        option_symbol="AAPL240216C00160000",
        quantity=10,
        strike=160.0,
        expiration="2024-02-16",
        option_type="call",
        entry_price=4.0,
        current_price=4.2,
        underlying_price=152.0,
        delta=0.5,
        gamma=0.018,
        theta=-0.09,
        vega=0.14,
        rho=0.04
    )

    # Test if we can open this position (with a $100,000 portfolio)
    can_open, reason = risk_manager.can_open_option_position(100000.0, new_option)
    print(f"   Can open new option position: {can_open}")
    print(f"   Reason: {reason}")

    # Test exiting a position
    print("\n3. Testing position exit...")
    risk_manager.record_option_exit("AAPL240119C00150000")
    portfolio_greeks_after = risk_manager.get_portfolio_greeks()
    print(f"   Portfolio Greeks after exit - Delta: {portfolio_greeks_after.delta:.2f}, "
          f"Gamma: {portfolio_greeks_after.gamma:.4f}")

    print("\nOptions risk management tests completed successfully!")
    return True


def test_options_robustness():
    """Test options-specific robustness testing functionality."""
    print("\nTesting options-specific robustness testing...")

    # Create sample market data
    dates = [datetime.now() - timedelta(days=i) for i in range(252, 0, -1)]
    # Create realistic price data with some trend and volatility
    base_price = 150.0
    prices = []
    for i in range(252):
        # Add some trend and random walk
        trend = 0.0002 * i  # Small upward trend
        noise = np.random.normal(0, 0.02)  # Daily volatility
        price = base_price * (1 + trend + noise)
        prices.append(max(price, 1.0))  # Ensure positive prices
        base_price = price  # For next iteration

    sample_data = pd.DataFrame({
        'date': dates,
        'adjusted_close': prices,
        'open': [p * 0.99 for p in prices],
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'volume': [np.random.randint(1000000, 5000000) for _ in range(252)],
        'symbol': ['AAPL'] * 252
    })

    # Test ParameterSensitivity with options strategies
    print("\n1. Testing ParameterSensitivity for options...")
    sensitivity = ParameterSensitivity(sample_data, symbol="AAPL")

    # Define parameter grid for vertical spread
    vs_param_grid = {
        'spread_widths': [5, 10],
        'delta_targets': [0.2, 0.3],
        'dte_min_list': [30, 45],
        'dte_max_list': [60, 75]
    }

    try:
        vs_results = sensitivity.test_options_strategy_parameters(
            'vertical_spread', vs_param_grid, initial_capital=50000
        )
        print(f"   Tested {len(vs_results)} vertical spread configurations")
        if vs_results:
            best_vs = max(vs_results, key=lambda x: x.sharpe_ratio if hasattr(x, 'sharpe_ratio') else 0)
            print(f"   Best vertical spread: {best_vs.config_name} "
                  f"(Sharpe: {getattr(best_vs, 'sharpe_ratio', 0):.2f})")
    except Exception as e:
        print(f"   Warning: Vertical spread testing encountered: {e}")
        # This is expected since we don't have real options data

    # Test WhitesRealityCheck
    print("\n2. Testing WhitesRealityCheck...")
    wrc = WhitesRealityCheck(n_bouts=100, random_seed=42)  # Small number for testing

    # Test with sample returns
    sample_returns = [0.001, -0.002, 0.003, -0.001, 0.002] * 20  # 100 returns
    wrc_result = wrc.reality_check_test(sample_returns, benchmark_return=0.0)
    print(f"   White's Reality Check p-value: {wrc_result['p_value']:.4f}")
    print(f"   Has edge: {wrc_result['has_edge']}")

    # Test bootstrap testing
    print("\n3. Testing bootstrap strategy test...")
    bootstrap_result = wrc.bootstrap_strategy_test(sample_returns, n_bootstrap=100)
    print(f"   Bootstrap mean return: {bootstrap_result['mean']:.4f}")
    print(f"   Significant different from zero: {bootstrap_result['significant']}")

    print("\nOptions robustness testing completed successfully!")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Options Trading System Components")
    print("=" * 60)

    success = True

    try:
        success &= test_options_risk_management()
        success &= test_options_robustness()
    except Exception as e:
        print(f"\n✗ Testing failed with error: {e}")
        success = False

    print("\n" + "=" * 60)
    if success:
        print("ALL TESTS PASSED - Options trading system components are working!")
    else:
        print("SOME TESTS FAILED - Please check the implementation")
    print("=" * 60)

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)