#!/usr/bin/env python3
"""
Test suite for Phase 10: Risk Management and Optimization
Tests the RiskOptimizer class and its integration with ExecutionMonitor and PerformanceAnalytics
"""

import sys
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from trading_bot.monitoring.risk_optimizer import RiskOptimizer, create_risk_optimizer
from trading_bot.execution.phase8_execution_monitoring import ExecutionMonitor
from trading_bot.monitoring.analytics import PerformanceAnalytics


class TestRiskOptimizer(unittest.TestCase):
    """Test cases for the RiskOptimizer class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create mock Webull execution component
        self.mock_webull_execution = Mock()
        self.mock_webull_execution._is_option_symbol = Mock(return_value=False)

        # Create mock Webull client
        self.mock_webull_client = Mock()
        mock_account = Mock()
        mock_account.portfolio_value = 100000.0  # $100k portfolio
        self.mock_webull_client.get_account.return_value = mock_account
        self.mock_webull_execution.client = self.mock_webull_client

        # Create ExecutionMonitor (Phase 8)
        self.execution_monitor = ExecutionMonitor(
            webull_executor=self.mock_webull_execution,
            check_interval=30,
            enable_auto_exit=False,
            enable_alerts=False
        )

        # Create PerformanceAnalytics (Phase 9)
        self.performance_analytics = PerformanceAnalytics(self.execution_monitor)

        # Create RiskOptimizer
        self.risk_optimizer = RiskOptimizer(self.execution_monitor, self.performance_analytics)

        # Add some sample trades for testing
        self._add_sample_trades()

    def _add_sample_trades(self):
        """Add sample trades to performance analytics for testing."""
        # Add some winning trades
        self.performance_analytics.add_completed_trade(
            symbol="AAPL261016C00190000",
            side="buy",
            quantity=2,
            entry_price=5.00,
            exit_price=6.50,
            entry_time=datetime.now() - timedelta(days=5),
            exit_time=datetime.now() - timedelta(days=3),
            tags=["bull_call", "long_aapl"]
        )

        # Add some losing trades
        self.performance_analytics.add_completed_trade(
            symbol="TSLA261016P00250000",
            side="sell",
            quantity=1,
            entry_price=3.00,
            exit_price=2.00,
            entry_time=datetime.now() - timedelta(days=7),
            exit_time=datetime.now() - timedelta(days=2),
            tags=["bear_put", "short_tsla"]
        )

        # Add another winning trade
        self.performance_analytics.add_completed_trade(
            symbol="MSFT261016C00300000",
            side="buy",
            quantity=3,
            entry_price=4.00,
            exit_price=5.50,
            entry_time=datetime.now() - timedelta(days=4),
            exit_time=datetime.now() - timedelta(days=1),
            tags=["bull_call", "long_msft"]
        )

        # Set up portfolio values for return calculation
        self.performance_analytics.portfolio_values = [
            (datetime.now() - timedelta(days=10), 95000.0),
            (datetime.now() - timedelta(days=5), 98000.0),
            (datetime.now(), 102000.0)
        ]
        self.performance_analytics.daily_returns = [3.2, -1.5, 4.1]

    def test_risk_optimizer_creation(self):
        """Test that RiskOptimizer can be created successfully."""
        self.assertIsInstance(self.risk_optimizer, RiskOptimizer)
        self.assertEqual(self.risk_optimizer.monitor, self.execution_monitor)
        self.assertEqual(self.risk_optimizer.analytics, self.performance_analytics)

        # Check default risk parameters
        self.assertEqual(self.risk_optimizer.base_max_position_size, 0.10)
        self.assertEqual(self.risk_optimizer.base_max_daily_loss, 0.05)
        self.assertEqual(self.risk_optimizer.base_max_portfolio_risk, 0.20)

    def test_update_risk_parameters(self):
        """Test updating risk parameters based on performance."""
        # Store original values
        original_max_position = self.risk_optimizer.max_position_size
        original_max_daily = self.risk_optimizer.max_daily_loss

        # Update parameters
        self.risk_optimizer.update_risk_parameters()

        # Parameters should still be valid (not necessarily changed)
        self.assertGreaterEqual(self.risk_optimizer.max_position_size, 0.0)
        self.assertLessEqual(self.risk_optimizer.max_position_size, 1.0)
        self.assertGreaterEqual(self.risk_optimizer.max_daily_loss, 0.0)
        self.assertLessEqual(self.risk_optimizer.max_daily_loss, 1.0)

    def test_calculate_optimal_position_size(self):
        """Test calculating optimal position size."""
        # Test with a stock symbol
        quantity = self.risk_optimizer.calculate_optimal_position_size(
            symbol="AAPL",
            entry_price=150.00,
            stop_loss=140.00,
            strategy_tags=["long_aapl"]
        )

        # Should return a reasonable quantity
        self.assertIsInstance(quantity, int)
        self.assertGreaterEqual(quantity, 0)

        # Test with an option symbol (mock to return True)
        self.mock_webull_execution._is_option_symbol = Mock(return_value=True)
        quantity = self.risk_optimizer.calculate_optimal_position_size(
            symbol="AAPL261016C00190000",
            entry_price=6.00,
            stop_loss=5.00,
            strategy_tags=["bull_call"]
        )
        self.mock_webull_execution._is_option_symbol = Mock(return_value=False)  # Reset

        self.assertIsInstance(quantity, int)
        self.assertGreaterEqual(quantity, 0)

    def test_calculate_optimal_position_size_zero_price(self):
        """Test position size calculation with zero or invalid prices."""
        # Test with zero entry price
        quantity = self.risk_optimizer.calculate_optimal_position_size(
            symbol="AAPL",
            entry_price=0.00,
            stop_loss=10.00
        )
        self.assertEqual(quantity, 0)

        # Test with negative entry price
        quantity = self.risk_optimizer.calculate_optimal_position_size(
            symbol="AAPL",
            entry_price=-5.00,
            stop_loss=10.00
        )
        self.assertEqual(quantity, 0)

    def test_get_risk_adjusted_stop_loss(self):
        """Test volatility-adjusted stop loss calculation."""
        # Test long position
        adj_stop = self.risk_optimizer.get_risk_adjusted_stop_loss(
            symbol="AAPL",
            entry_price=100.00,
            initial_stop_loss=90.00,
            is_long=True
        )

        # For a long position, adjusted stop should be <= original stop (more conservative)
        # or >= original stop if volatility adjustment makes it wider
        self.assertIsInstance(adj_stop, float)
        self.assertGreaterEqual(adj_stop, 0.0)

        # Test short position
        adj_stop = self.risk_optimizer.get_risk_adjusted_stop_loss(
            symbol="AAPL",
            entry_price=100.00,
            initial_stop_loss=110.00,
            is_long=False
        )

        self.assertIsInstance(adj_stop, float)
        self.assertGreaterEqual(adj_stop, 0.0)

    def test_calculate_portfolio_risk(self):
        """Test portfolio risk calculation."""
        risk_metrics = self.risk_optimizer.calculate_portfolio_risk()

        # Should return a dictionary with expected keys
        self.assertIsInstance(risk_metrics, dict)
        expected_keys = [
            'timestamp', 'portfolio_value', 'total_exposure',
            'total_market_value', 'portfolio_risk_pct', 'daily_pnl_pct',
            'max_position_size', 'max_daily_loss', 'max_portfolio_risk',
            'risk_utilization'
        ]

        for key in expected_keys:
            self.assertIn(key, risk_metrics)

        # Values should be reasonable
        self.assertGreaterEqual(risk_metrics['portfolio_value'], 0)
        self.assertGreaterEqual(risk_metrics['total_exposure'], 0)
        self.assertGreaterEqual(risk_metrics['total_market_value'], 0)
        self.assertGreaterEqual(risk_metrics['portfolio_risk_pct'], 0)
        self.assertGreaterEqual(risk_metrics['daily_pnl_pct'], -100)  # Can't lose more than 100%

    def test_generate_risk_recommendations(self):
        """Test generating risk management recommendations."""
        recommendations = self.risk_optimizer.generate_risk_recommendations()

        # Should return a list
        self.assertIsInstance(recommendations, list)

        # Each recommendation should have expected structure
        for rec in recommendations:
            self.assertIsInstance(rec, dict)
            self.assertIn('type', rec)
            self.assertIn('component', rec)
            self.assertIn('message', rec)
            self.assertIn('suggestion', rec)

            # Type should be one of expected values
            self.assertIn(rec['type'], ['info', 'warning', 'suggestion', 'error'])

    def test_get_risk_optimization_status(self):
        """Test getting risk optimization system status."""
        status = self.risk_optimizer.get_risk_optimization_status()

        self.assertIsInstance(status, dict)
        self.assertIn('timestamp', status)
        self.assertIn('risk_parameters', status)
        self.assertIn('volatility_estimates', status)
        self.assertIn('strategy_weights', status)
        self.assertIn('performance_trades_count', status)
        self.assertIn('recommendations_count', status)

        # Check risk parameters structure
        risk_params = status['risk_parameters']
        self.assertIn('max_position_size', risk_params)
        self.assertIn('max_daily_loss', risk_params)
        self.assertIn('max_portfolio_risk', risk_params)

    def test_create_risk_optimizer_factory(self):
        """Test the factory function for creating RiskOptimizer."""
        optimizer = create_risk_optimizer(self.execution_monitor, self.performance_analytics)

        self.assertIsInstance(optimizer, RiskOptimizer)
        self.assertEqual(optimizer.monitor, self.execution_monitor)
        self.assertEqual(optimizer.analytics, self.performance_analytics)


class TestRiskOptimizerIntegration(unittest.TestCase):
    """Test integration between RiskOptimizer and other system components."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock components
        self.mock_webull_execution = Mock()
        self.mock_webull_execution._is_option_symbol = Mock(return_value=False)

        self.mock_webull_client = Mock()
        mock_account = Mock()
        mock_account.portfolio_value = 50000.0  # $50k portfolio
        self.mock_webull_client.get_account.return_value = mock_account
        self.mock_webull_execution.client = self.mock_webull_client

        # Create real instances
        self.execution_monitor = ExecutionMonitor(
            webull_executor=self.mock_webull_execution,
            check_interval=30,
            enable_auto_exit=False,
            enable_alerts=False
        )

        self.performance_analytics = PerformanceAnalytics(self.execution_monitor)
        self.risk_optimizer = RiskOptimizer(self.execution_monitor, self.performance_analytics)

    def test_end_to_end_risk_workflow(self):
        """Test a complete workflow: add trades -> update risk -> get recommendations."""
        # Add several trades with different outcomes
        trades_data = [
            # Winning trades
            ("AAPL261016C00190000", "buy", 2, 5.00, 7.00, ["bull_call", "long_aapl"]),
            ("MSFT261016C00300000", "buy", 3, 4.00, 5.50, ["bull_call", "long_msft"]),
            # Losing trades
            ("TSLA261016P00250000", "sell", 1, 3.00, 2.00, ["bear_put", "short_tsla"]),
            ("GOOGL261016C00120000", "buy", 1, 8.00, 6.50, ["bull_call", "long_googl"]),
        ]

        base_time = datetime.now() - timedelta(days=10)

        for i, (symbol, side, qty, entry, exit_price, tags) in enumerate(trades_data):
            self.performance_analytics.add_completed_trade(
                symbol=symbol,
                side=side,
                quantity=qty,
                entry_price=entry,
                exit_price=exit_price,
                entry_time=base_time + timedelta(days=i*2),
                exit_time=base_time + timedelta(days=i*2 + 3),
                tags=tags
            )

        # Update portfolio values to reflect the trades
        self.performance_analytics.portfolio_values = [
            (datetime.now() - timedelta(days=15), 48000.0),
            (datetime.now() - timedelta(days=10), 49000.0),
            (datetime.now() - timedelta(days=5), 51000.0),
            (datetime.now(), 52500.0)  # Overall profit
        ]
        self.performance_analytics.daily_returns = [2.1, -0.5, 3.2, 2.9]

        # Update risk parameters based on performance
        original_max_position = self.risk_optimizer.max_position_size
        self.risk_optimizer.update_risk_parameters()

        # Calculate optimal position size for a new trade
        quantity = self.risk_optimizer.calculate_optimal_position_size(
            symbol="NVDA261016C00400000",
            entry_price=12.00,
            stop_loss=10.00,
            strategy_tags=["bull_call", "long_nvda"]
        )

        # Should return a reasonable quantity
        self.assertIsInstance(quantity, int)
        self.assertGreaterEqual(quantity, 0)

        # Get risk adjusted stop loss
        adj_stop = self.risk_optimizer.get_risk_adjusted_stop_loss(
            symbol="NVDA261016C00400000",
            entry_price=12.00,
            initial_stop_loss=10.00,
            is_long=True
        )

        self.assertIsInstance(adj_stop, float)

        # Calculate portfolio risk
        risk_metrics = self.risk_optimizer.calculate_portfolio_risk()
        self.assertIsInstance(risk_metrics, dict)
        self.assertIn('portfolio_risk_pct', risk_metrics)

        # Generate recommendations
        recommendations = self.risk_optimizer.generate_risk_recommendations()
        self.assertIsInstance(recommendations, list)

        # Get system status
        status = self.risk_optimizer.get_risk_optimization_status()
        self.assertIsInstance(status, dict)
        self.assertGreaterEqual(status['performance_trades_count'], len(trades_data))


def run_tests():
    """Run all tests for Phase 10 risk optimizer."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRiskOptimizer))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskOptimizerIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    # Configure basic logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)  # Reduce noise during tests

    exit_code = run_tests()
    sys.exit(exit_code)