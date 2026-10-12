"""Risk management and optimization for autonomous options trading system.

This module provides:
- Dynamic position sizing based on performance and volatility
- Strategy allocation optimization
- Volatility-based risk adjustment
- Correlation analysis and diversification
- Adaptive risk limits based on drawdown
- Portfolio rebalancing recommendations
- Integration with ExecutionMonitor and PerformanceAnalytics from Phases 8-9
"""

import os
import sys
import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

from trading_bot.execution.phase8_execution_monitoring import ExecutionMonitor, PositionInfo
from trading_bot.monitoring.analytics import PerformanceAnalytics


class RiskOptimizer:
    """Manage and optimize risk for the trading system."""

    def __init__(self, execution_monitor: ExecutionMonitor,
                 performance_analytics: PerformanceAnalytics):
        """Initialize risk optimizer.

        Args:
            execution_monitor: Initialized ExecutionMonitor instance
            performance_analytics: Initialized PerformanceAnalytics instance
        """
        self.monitor = execution_monitor
        self.analytics = performance_analytics

        # Risk parameters (can be adjusted over time)
        self.base_max_position_size = 0.10  # 10% of portfolio per position
        self.base_max_daily_loss = 0.05     # 5% max daily loss
        self.base_max_portfolio_risk = 0.20  # 20% max portfolio at risk

        # Current adjusted parameters
        self.max_position_size = self.base_max_position_size
        self.max_daily_loss = self.base_max_daily_loss
        self.max_portfolio_risk = self.base_max_portfolio_risk

        # Performance tracking for optimization
        self.performance_history: List[Dict] = []
        self.volatility_estimates: Dict[str, float] = {}  # symbol -> volatility estimate
        self.strategy_weights: Dict[str, float] = defaultdict(lambda: 1.0)  # strategy -> weight

        logger = logging.getLogger(__name__)
        self.logger = logger

    def update_risk_parameters(self):
        """Update risk parameters based on recent performance and market conditions."""
        try:
            # Update volatility estimates
            self._update_volatility_estimates()

            # Adjust position sizing based on recent performance
            self._adjust_position_sizing()

            # Adjust strategy allocations
            self._adjust_strategy_allocations()

            # Update volatility-based risk limits
            self._adjust_volatility_based_limits()

            self.logger.info("Risk parameters updated")

        except Exception as e:
            self.logger.error(f"Error updating risk parameters: {e}")

    def _update_volatility_estimates(self):
        """Estimate volatility for symbols based on price history."""
        # In a real implementation, this would use historical price data
        # For now, we'll use a simplified approach based on recent P&L volatility

        # Get recent trades
        recent_trades = self.analytics.trade_history[-20:] if self.analytics.trade_history else []

        # Group trades by symbol
        symbol_returns = defaultdict(list)
        for trade in recent_trades:
            symbol = trade['symbol']
            symbol_returns[symbol].append(trade['return_pct'])

        # Calculate volatility (standard deviation of returns) for each symbol
        for symbol, returns in symbol_returns.items():
            if len(returns) >= 2:
                volatility = statistics.stdev(returns)
                # Convert to annualized volatility (approx)
                self.volatility_estimates[symbol] = volatility * math.sqrt(252)  # 252 trading days
            else:
                # Default volatility if insufficient data
                self.volatility_estimates[symbol] = 0.30  # 30% default annual volatility

    def _adjust_position_sizing(self):
        """Adjust maximum position size based on recent performance."""
        if not self.analytics.trade_history:
            return

        # Calculate recent performance metrics
        recent_trades = self.analytics.trade_history[-10:] if len(self.analytics.trade_history) >= 10 else self.analytics.trade_history

        if not recent_trades:
            return

        # Calculate win rate and average return
        wins = [t for t in recent_trades if t['is_win']]
        win_rate = len(wins) / len(recent_trades) if recent_trades else 0
        avg_return = statistics.mean([t['return_pct'] for t in recent_trades]) if recent_trades else 0

        # Adjust position size based on performance
        # Good performance -> increase position size (up to a limit)
        # Poor performance -> decrease position size
        performance_factor = 1.0

        if win_rate > 0.6 and avg_return > 0:  # Good performance
            performance_factor = min(1.5, 1.0 + (win_rate - 0.5) * 2)  # Up to 1.5x
        elif win_rate < 0.4 or avg_return < -1:  # Poor performance
            performance_factor = max(0.5, win_rate * 1.5)  # Down to 0.5x

        # Apply adjustment with bounds
        new_max_position_size = self.base_max_position_size * performance_factor
        self.max_position_size = max(0.02, min(0.25, new_max_position_size))  # Between 2% and 25%

        self.logger.info(f"Adjusted max position size: {self.max_position_size:.2%} "
                        f"(base: {self.base_max_position_size:.2%}, factor: {performance_factor:.2f})")

    def _adjust_strategy_allocations(self):
        """Adjust strategy weights based on recent performance."""
        if not self.analytics.trade_history:
            return

        # Calculate performance by strategy
        strategy_performance = {}
        for trade in self.analytics.trade_history[-30:]:  # Last 30 trades
            for tag in trade['tags']:
                if tag not in strategy_performance:
                    strategy_performance[tag] = {'returns': [], 'trades': 0}
                strategy_performance[tag]['returns'].append(trade['return_pct'])
                strategy_performance[tag]['trades'] += 1

        # Update weights based on performance
        for strategy, perf in strategy_performance.items():
            if perf['trades'] >= 3:  # Only adjust if we have enough data
                avg_return = statistics.mean(perf['returns'])
                # Convert return to weight adjustment (better performance -> higher weight)
                # Use a sigmoid-like function to bound adjustments
                if avg_return > 0:
                    weight_factor = 1.0 + math.tanh(avg_return / 10)  # Tanh bounds to [-1,1]
                else:
                    weight_factor = 1.0 + math.tanh(avg_return / 10)  # Will be < 1 for negative returns

                # Apply gradual adjustment (don't change weights too quickly)
                current_weight = self.strategy_weights[strategy]
                new_weight = current_weight * 0.7 + weight_factor * 0.3  # 70% old, 30% new
                self.strategy_weights[strategy] = max(0.1, min(3.0, new_weight))  # Bound between 0.1 and 3.0

    def _adjust_volatility_based_limits(self):
        """Adjust risk limits based on overall market volatility."""
        if not self.volatility_estimates:
            return

        # Calculate average volatility
        volatilities = list(self.volatility_estimates.values())
        if not volatilities:
            return

        avg_volatility = statistics.mean(volatilities)

        # Adjust daily loss limit based on volatility
        # Higher volatility -> lower daily loss limit to prevent large drawdowns
        vol_factor = 1.0
        if avg_volatility > 0.4:  # High volatility (>40% annualized)
            vol_factor = max(0.5, 1.0 - (avg_volatility - 0.4))  # Reduce limit
        elif avg_volatility < 0.2:  # Low volatility (<20% annualized)
            vol_factor = min(1.5, 1.0 + (0.2 - avg_volatility))  # Increase limit slightly

        new_max_daily_loss = self.base_max_daily_loss * vol_factor
        self.max_daily_loss = max(0.01, min(0.15, new_max_daily_loss))  # Between 1% and 15%

        self.logger.info(f"Adjusted max daily loss: {self.max_daily_loss:.2%} "
                        f"(base: {self.base_max_daily_loss:.2%}, vol factor: {vol_factor:.2f})")

    def calculate_optimal_position_size(self, symbol: str, entry_price: float,
                                      stop_loss: Optional[float] = None,
                                      strategy_tags: Optional[List[str]] = None) -> int:
        """Calculate optimal position size for a new trade.

        Args:
            symbol: Stock or option symbol
            entry_price: Entry price per share/contract
            stop_loss: Stop loss price (optional)
            strategy_tags: Strategy tags for this trade (optional)

        Returns:
            Optimal quantity (number of contracts/shares)
        """
        try:
            # Get account info for portfolio value from Webull
            balance_result = mcp__webull__get_account_balance()
            portfolio_value = balance_result.get('net_liquidation', 0.0)

            # Calculate base position size based on portfolio percentage
            base_position_value = portfolio_value * self.max_position_size

            # Adjust for symbol volatility
            volatility = self.volatility_estimates.get(symbol, 0.30)  # Default 30%
            vol_adjustment = max(0.5, min(2.0, 0.30 / volatility))  # Inverse vol adjustment

            # Adjust for strategy weights
            strategy_weight = 1.0
            if strategy_tags:
                # Use average weight of all tags
                weights = [self.strategy_weights.get(tag, 1.0) for tag in strategy_tags]
                strategy_weight = statistics.mean(weights) if weights else 1.0

            # Calculate volatility-adjusted position value
            adj_position_value = base_position_value * vol_adjustment * strategy_weight

            # If we have a stop loss, calculate size based on risk per share
            if stop_loss is not None and entry_price > 0:
                risk_per_share = abs(entry_price - stop_loss)
                if risk_per_share > 0:
                    # For options, remember to multiply by 100 for contract size
                    multiplier = 100 if self._is_option_symbol(symbol) else 1
                    max_risk_amount = adj_position_value
                    quantity_by_risk = int(max_risk_amount / (risk_per_share * multiplier))

                    # Also calculate quantity based on position value
                    quantity_by_value = int(adj_position_value / (entry_price * multiplier))

                    # Use the more conservative of the two
                    quantity = min(quantity_by_risk, quantity_by_value)
                else:
                    # Fallback to position value method if stop loss too close
                    multiplier = 100 if self._is_option_symbol(symbol) else 1
                    quantity = int(adj_position_value / (entry_price * multiplier))
            else:
                # No stop loss, use position value method
                multiplier = 100 if self._is_option_symbol(symbol) else 1
                quantity = int(adj_position_value / (entry_price * multiplier))

            # Ensure minimum of 1 if the calculation allows it
            quantity = max(0, quantity)

            self.logger.info(f"Calculated position size for {symbol}: {quantity} contracts "
                           f"(PV: ${adj_position_value:.0f}, Vol adj: {vol_adjustment:.2f}, "
                           f"Strategy adj: {strategy_weight:.2f})")

            return quantity

        except Exception as e:
            self.logger.error(f"Error calculating optimal position size: {e}")
            return 0  # Return 0 to indicate error

    def _is_option_symbol(self, symbol: str) -> bool:
        """Check if a symbol represents an option contract.

        Option symbol format: {UNDERLYING}{YY}{MM}{DD}{C/P}{STRIKE*1000}
        Example: AAPL261016C00190000 (AAPL, Oct 16, 2026, Call, $190 strike)
        """
        import re
        # Option symbol format: letters + 6 digits + C/P + 8 digits
        option_pattern = r'^[A-Z]+\d{6}[CP]\d{8}$'
        return bool(re.match(option_symbol, symbol))

    def get_risk_adjusted_stop_loss(self, symbol: str, entry_price: float,
                                   initial_stop_loss: float,
                                   is_long: bool = True) -> float:
        """Adjust stop loss based on volatility and recent performance.

        Args:
            symbol: Stock or option symbol
            entry_price: Entry price per share/contract
            initial_stop_loss: Initial stop loss price
            is_long: True for long position, False for short

        Returns:
            Volatility-adjusted stop loss price
        """
        try:
            # Get volatility for symbol
            volatility = self.volatility_estimates.get(symbol, 0.30)  # Default 30%

            # Calculate average true range (ATR) estimate
            # Simplified: ATR ≈ price * volatility / sqrt(252) * sqrt(trading days)
            # For daily scaling, we can use: daily volatility ≈ annual volatility / sqrt(252)
            daily_vol = volatility / math.sqrt(252)

            # Adjust stop loss based on volatility
            # Higher volatility -> wider stop loss to avoid being stopped out by noise
            volatility_multiplier = 1.0 + (volatility - 0.30)  # Adjust based on 30% baseline

            if is_long:
                # For long positions, stop loss is below entry
                price_risk = entry_price - initial_stop_loss
                if price_risk > 0:
                    adjusted_risk = price_risk * volatility_multiplier
                    adjusted_stop = entry_price - adjusted_risk
                else:
                    adjusted_stop = initial_stop_loss
            else:
                # For short positions, stop loss is above entry
                price_risk = initial_stop_loss - entry_price
                if price_risk > 0:
                    adjusted_risk = price_risk * volatility_multiplier
                    adjusted_stop = entry_price + adjusted_risk
                else:
                    adjusted_stop = initial_stop_loss

            self.logger.info(f"Adjusted stop loss for {symbol}: {initial_stop_loss:.2f} -> {adjusted_stop:.2f} "
                           f"(vol: {volatility:.2%}, multiplier: {volatility_multiplier:.2f})")

            return adjusted_stop

        except Exception as e:
            self.logger.error(f"Error adjusting stop loss: {e}")
            return initial_stop_loss  # Return original if error

    def calculate_portfolio_risk(self) -> Dict[str, Any]:
        """Calculate current portfolio risk metrics.

        Returns:
            Dictionary with portfolio risk metrics
        """
        try:
            # Get current positions
            positions_summary = self.monitor.get_position_summary()

            # Calculate total exposure
            total_exposure = 0.0
            total_market_value = 0.0
            strategy_exposure = defaultdict(float)

            for position in positions_summary['positions']:
                symbol = position['symbol']
                qty = position['qty']
                market_value = position['current_price'] * qty

                # For options, remember multiplier
                if self._is_option_symbol(symbol):
                    market_value *= 100

                total_market_value += abs(market_value)
                total_exposure += abs(market_value)  # Simplified exposure calculation

                # Assign to strategies (simplified - assign to first tag)
                # In reality, we'd need to track which strategy opened each position
                # For now, we'll skip strategy breakdown or use a default

            # Calculate portfolio risk percentage from Webull
            balance_result = mcp__webull__get_account_balance()
            portfolio_value = balance_result.get('net_liquidation', 0.0)
            portfolio_risk_pct = (total_exposure / portfolio_value) * 100 if portfolio_value > 0 else 0

            # Calculate current daily P&L
            # This would ideally come from tracking daily changes
            # For now, we'll use unrealized P&L as a proxy
            daily_pnl_pct = (positions_summary['total_unrealized_pnl'] / portfolio_value) * 100 if portfolio_value > 0 else 0

            risk_metrics = {
                'timestamp': datetime.now().isoformat(),
                'portfolio_value': portfolio_value,
                'total_exposure': total_exposure,
                'total_market_value': total_market_value,
                'portfolio_risk_pct': portfolio_risk_pct,
                'daily_pnl_pct': daily_pnl_pct,
                'max_position_size': self.max_position_size,
                'max_daily_loss': self.max_daily_loss,
                'max_portfolio_risk': self.max_portfolio_risk,
                'risk_utilization': {
                    'position_size': (total_exposure / portfolio_value) / self.max_position_size if portfolio_value > 0 else 0,
                    'daily_loss': abs(daily_pnl_pct) / self.max_daily_loss if self.max_daily_loss > 0 else 0,
                    'portfolio_risk': (total_exposure / portfolio_value) / self.max_portfolio_risk if portfolio_value > 0 and self.max_portfolio_risk > 0 else 0
                }
            }

            return risk_metrics

        except Exception as e:
            self.logger.error(f"Error calculating portfolio risk: {e}")
            return {'error': str(e)}

    def generate_risk_recommendations(self) -> List[Dict[str, Any]]:
        """Generate risk management recommendations.

        Returns:
            List of recommendation dictionaries
        """
        recommendations = []

        try:
            # Get current risk metrics
            risk_metrics = self.calculate_portfolio_risk()

            if 'error' in risk_metrics:
                return [{'type': 'error', 'message': f"Could not calculate risk metrics: {risk_metrics['error']}"}]

            # Check position sizing utilization
            pos_util = risk_metrics['risk_utilization']['position_size']
            if pos_util > 0.9:
                recommendations.append({
                    'type': 'warning',
                    'component': 'position_sizing',
                    'message': f"Position size utilization high: {pos_util:.1%} of maximum",
                    'suggestion': 'Consider reducing position sizes or taking profits'
                })
            elif pos_util < 0.3:
                recommendations.append({
                    'type': 'info',
                    'component': 'position_sizing',
                    'message': f"Position size utilization low: {pos_util:.1%} of maximum",
                    'suggestion': 'Capacity available for new positions if opportunities arise'
                })

            # Check daily loss utilization
            daily_util = risk_metrics['risk_utilization']['daily_loss']
            if daily_util > 0.9:
                recommendations.append({
                    'type': 'warning',
                    'component': 'daily_loss',
                    'message': f"Daily loss utilization high: {daily_util:.1%} of maximum",
                    'suggestion': 'Consider reducing risk or pausing new trades'
                })

            # Check portfolio risk utilization
            port_util = risk_metrics['risk_utilization']['portfolio_risk']
            if port_util > 0.9:
                recommendations.append({
                    'type': 'warning',
                    'component': 'portfolio_risk',
                    'message': f"Portfolio risk utilization high: {port_util:.1%} of maximum",
                    'suggestion': 'Consider reducing overall exposure or hedging'
                })

            # Check volatility-adjusted parameters
            if hasattr(self, 'volatility_estimates') and self.volatility_estimates:
                avg_vol = statistics.mean(self.volatility_estimates.values()) if self.volatility_estimates else 0
                if avg_vol > 0.4:
                    recommendations.append({
                        'type': 'info',
                        'component': 'volatility',
                        'message': f"High market volatility detected: {avg_vol:.1%} annualized",
                        'suggestion': 'Consider wider stop losses and smaller position sizes'
                    })

            # Check strategy performance for allocation suggestions
            if self.analytics.trade_history:
                # Find best and worst performing strategies
                strategy_perf = {}
                for trade in self.analytics.trade_history[-20:]:  # Last 20 trades
                    for tag in trade['tags']:
                        if tag not in strategy_perf:
                            strategy_perf[tag] = {'pnl': 0.0, 'trades': 0}
                        strategy_perf[tag]['pnl'] += trade['pnl']
                        strategy_perf[tag]['trades'] += 1

                if strategy_perf:
                    # Find best performing strategy (minimum 3 trades)
                    best_strategy = None
                    best_avg_pnl = -float('inf')
                    worst_strategy = None
                    worst_avg_pnl = float('inf')

                    for strategy, perf in strategy_perf.items():
                        if perf['trades'] >= 3:
                            avg_pnl = perf['pnl'] / perf['trades']
                            if avg_pnl > best_avg_pnl:
                                best_avg_pnl = avg_pnl
                                best_strategy = strategy
                            if avg_pnl < worst_avg_pnl:
                                worst_avg_pnl = avg_pnl
                                worst_strategy = strategy

                    if best_strategy and worst_strategy:
                        recommendations.append({
                            'type': 'suggestion',
                            'component': 'strategy_allocation',
                            'message': f"Strategy performance divergence: {best_strategy} (+${best_avg_pnl:.2f avg}) vs {worst_strategy} (${worst_avg_pnl:.2f avg})",
                            'suggestion': f'Consider increasing allocation to {best_strategy}, decreasing to {worst_strategy}'
                        })

            # Add general health check if no issues
            if not recommendations:
                recommendations.append({
                    'type': 'info',
                    'component': 'system_health',
                    'message': 'All risk metrics within acceptable ranges',
                    'suggestion': 'Continue monitoring for changes'
                })

        except Exception as e:
            self.logger.error(f"Error generating risk recommendations: {e}")
            recommendations.append({
                'type': 'error',
                'component': 'system',
                'message': f"Error generating recommendations: {e}"
            })

        return recommendations

    def get_risk_optimization_status(self) -> Dict[str, Any]:
        """Get current status of risk optimization system.

        Returns:
            Dictionary with system status
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'risk_parameters': {
                'max_position_size': self.max_position_size,
                'max_daily_loss': self.max_daily_loss,
                'max_portfolio_risk': self.max_portfolio_risk,
                'base_max_position_size': self.base_max_position_size,
                'base_max_daily_loss': self.base_max_daily_loss,
                'base_max_portfolio_risk': self.base_max_portfolio_risk
            },
            'volatility_estimates': dict(list(self.volatility_estimates.items())[:5]) if self.volatility_estimates else {},  # Top 5
            'strategy_weights': dict(list(self.strategy_weights.items())[:5]) if self.strategy_weights else {},  # Top 5
            'performance_trades_count': len(self.analytics.trade_history),
            'recommendations_count': len(self.generate_risk_recommendations())
        }


def create_risk_optimizer(execution_monitor: ExecutionMonitor,
                         performance_analytics: PerformanceAnalytics) -> RiskOptimizer:
    """Factory function to create a RiskOptimizer instance.

    Args:
        execution_monitor: Initialized ExecutionMonitor instance
        performance_analytics: Initialized PerformanceAnalytics instance

    Returns:
        Configured RiskOptimizer instance
    """
    return RiskOptimizer(execution_monitor, performance_analytics)


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def demo_alert(message: str):
        print(f"[ALERT] {message}")

    # For demonstration, we'll show how the RiskOptimizer would work with WebullExecution
    # In practice, you would initialize WebullExecution with real credentials
    print("Note: This is a demonstration. For actual trading, initialize WebullExecution with real credentials.")

    # Set up performance analytics (from Phase 9) - this doesn't depend on the executor type
    from trading_bot.monitoring.analytics import create_performance_analytics

    # We'll create a mock monitor for demonstration purposes
    class MockExecutionMonitor:
        def get_position_summary(self):
            return {
                'positions': [],
                'total_unrealized_pnl': 0.0
            }

    monitor = MockExecutionMonitor()

    # Set up performance analytics (from Phase 9)
    from trading_bot.monitoring.analytics import create_performance_analytics
    analytics = create_performance_analytics(monitor)

    # Create risk optimizer
    risk_optimizer = create_risk_optimizer(monitor, analytics)

    # Add some demo trades to performance analytics for testing
    from datetime import datetime, timedelta

    # Add some sample trades
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
        symbol="TSLA261016P00250000",
        side="sell",
        quantity=1,
        entry_price=3.00,
        exit_price=4.50,
        entry_time=datetime.now() - timedelta(days=7),
        exit_time=datetime.now() - timedelta(days=2),
        tags=["cash_secured_put", "short_tsla"]
    )

    # Update portfolio values for return calculation
    analytics.portfolio_values = [
        (datetime.now() - timedelta(days=10), 95000.0),
        (datetime.now() - timedelta(days=5), 98000.0),
        (datetime.now(), 102000.0)
    ]
    analytics.daily_returns = [3.2, -1.5, 4.1]

    # Test risk optimizer functionality
    print("=== Risk Optimizer Demo ===\n")

    # Update risk parameters
    risk_optimizer.update_risk_parameters()

    # Calculate optimal position size
    optimal_qty = risk_optimizer.calculate_optimal_position_size(
        symbol="AAPL261016C00190000",
        entry_price=6.00,
        stop_loss=5.00,
        strategy_tags=["bull_call", "long_aapl"]
    )
    print(f"Optimal position size for AAPL call: {optimal_qty} contracts")

    # Get risk adjusted stop loss
    adj_stop = risk_optimizer.get_risk_adjusted_stop_loss(
        symbol="AAPL261016C00190000",
        entry_price=6.00,
        initial_stop_loss=5.00,
        is_long=True
    )
    print(f"Risk-adjusted stop loss: ${adj_stop:.2f}")

    # Calculate portfolio risk
    risk_metrics = risk_optimizer.calculate_portfolio_risk()
    if 'error' not in risk_metrics:
        print(f"Portfolio risk: {risk_metrics['portfolio_risk_pct']:.2f}%")
        print(f"Daily P&L: {risk_metrics['daily_pnl_pct']:.2f}%")

    # Generate recommendations
    recommendations = risk_optimizer.generate_risk_recommendations()
    print(f"\nGenerated {len(recommendations)} risk recommendations:")
    for rec in recommendations[:3]:  # Show first 3
        print(f"  [{rec['type'].upper()}] {rec['component']}: {rec['message']}")

    # Get system status
    status = risk_optimizer.get_risk_optimization_status()
    print(f"\nSystem status: {status['performance_trades_count']} trades processed")

    print("\nRiskOptimizer module loaded successfully")
    print("Use create_risk_optimizer(monitor, analytics) to create an instance")