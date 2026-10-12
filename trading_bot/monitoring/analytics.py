"""Performance analytics and reporting for autonomous options trading system.

This module provides:
- Performance metrics calculation (win rate, average return, Sharpe ratio, etc.)
- Position performance analysis
- Strategy-specific performance tracking
- Report generation and visualization
- Integration with ExecutionMonitor from Phase 8
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import math
import statistics

from trading_bot.execution.phase8_execution_monitoring import ExecutionMonitor, PositionInfo


class PerformanceAnalytics:
    """Calculate and track performance metrics for the trading system."""

    def __init__(self, execution_monitor: ExecutionMonitor):
        """Initialize performance analytics.

        Args:
            execution_monitor: Initialized ExecutionMonitor instance
        """
        self.monitor = execution_monitor
        self.trade_history: List[Dict] = []  # Completed trades with P&L
        self.daily_returns: List[float] = []  # Daily percentage returns
        self.portfolio_values: List[Tuple[datetime, float]] = []  # Portfolio value over time

        logger = logging.getLogger(__name__)
        self.logger = logger

    def add_completed_trade(self, symbol: str, side: str, quantity: int,
                          entry_price: float, exit_price: float,
                          entry_time: datetime, exit_time: datetime,
                          tags: Optional[List[str]] = None):
        """Add a completed trade to the history for performance analysis.

        Args:
            symbol: Stock or option symbol
            side: 'buy' or 'sell'
            quantity: Number of contracts/shares
            entry_price: Entry price per share/contract
            exit_price: Exit price per share/contract
            entry_time: When position was opened
            exit_time: When position was closed
            tags: Optional tags for strategy identification
        """
        # Calculate P&L
        multiplier = 100 if self._is_option_symbol(symbol) else 1
        if side.lower() == 'buy':
            pnl = (exit_price - entry_price) * quantity * multiplier
        else:  # sell
            pnl = (entry_price - exit_price) * quantity * multiplier

        # Calculate return percentage
        if side.lower() == 'buy':
            return_pct = ((exit_price - entry_price) / entry_price) * 100
        else:
            return_pct = ((entry_price - exit_price) / entry_price) * 100

        trade_record = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'hold_time': exit_time - entry_time,
            'pnl': pnl,
            'return_pct': return_pct,
            'tags': tags or [],
            'is_win': pnl > 0
        }

        self.trade_history.append(trade_record)
        self.logger.info(f"Added completed trade: {symbol} {side} {quantity} - P&L: ${pnl:.2f}")

    def _is_option_symbol(self, symbol: str) -> bool:
        """Check if a symbol represents an option contract."""
        # Option symbol format: {UNDERLYING}{YY}{MM}{DD}{C/P}{STRIKE*1000}
        import re
        option_pattern = r'^[A-Z]+\d{6}[CP]\d{8}$'
        return bool(re.match(option_pattern, symbol))

    def update_daily_performance(self):
        """Update daily performance metrics based on current positions."""
        try:
            # Get current portfolio value from Webull
            balance_result = mcp__webull__get_account_balance()
            portfolio_value = balance_result.get('net_liquidation', 0.0)
            timestamp = datetime.now()

            self.portfolio_values.append((timestamp, portfolio_value))

            # Calculate daily return if we have previous day's data
            if len(self.portfolio_values) >= 2:
                yesterday_value = self.portfolio_values[-2][1]
                today_value = self.portfolio_values[-1][1]
                if yesterday_value > 0:
                    daily_return = ((today_value - yesterday_value) / yesterday_value) * 100
                    self.daily_returns.append(daily_return)

        except Exception as e:
            self.logger.warning(f"Could not update daily performance: {e}")

    def calculate_win_rate(self) -> float:
        """Calculate win rate percentage.

        Returns:
            Win rate as percentage (0-100)
        """
        if not self.trade_history:
            return 0.0

        wins = sum(1 for trade in self.trade_history if trade['is_win'])
        return (wins / len(self.trade_history)) * 100

    def calculate_average_return(self) -> float:
        """Calculate average return per trade.

        Returns:
            Average return percentage
        """
        if not self.trade_history:
            return 0.0

        returns = [trade['return_pct'] for trade in self.trade_history]
        return statistics.mean(returns)

    def calculate_average_win(self) -> float:
        """Calculate average win amount.

        Returns:
            Average win in dollars
        """
        wins = [trade['pnl'] for trade in self.trade_history if trade['is_win']]
        if not wins:
            return 0.0
        return statistics.mean(wins)

    def calculate_average_loss(self) -> float:
        """Calculate average loss amount.

        Returns:
            Average loss in dollars (positive value)
        """
        losses = [abs(trade['pnl']) for trade in self.trade_history if not trade['is_win']]
        if not losses:
            return 0.0
        return statistics.mean(losses)

    def calculate_profit_factor(self) -> float:
        """Calculate profit factor (gross wins / gross losses).

        Returns:
            Profit factor
        """
        wins = [trade['pnl'] for trade in self.trade_history if trade['is_win']]
        losses = [abs(trade['pnl']) for trade in self.trade_history if not trade['is_win']]

        gross_wins = sum(wins) if wins else 0
        gross_losses = sum(losses) if losses else 0

        if gross_losses == 0:
            return float('inf') if gross_wins > 0 else 0.0

        return gross_wins / gross_losses

    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio based on daily returns.

        Args:
            risk_free_rate: Annual risk-free rate as percentage (default 0%)

        Returns:
            Sharpe ratio
        """
        if len(self.daily_returns) < 2:
            return 0.0

        # Convert annual risk-free rate to daily
        daily_risk_free = risk_free_rate / 252  # Assuming 252 trading days per year

        # Calculate excess returns
        excess_returns = [r - daily_risk_free for r in self.daily_returns]

        if len(excess_returns) < 2:
            return 0.0

        mean_excess = statistics.mean(excess_returns)
        std_excess = statistics.stdev(excess_returns)

        if std_excess == 0:
            return 0.0

        # Annualize Sharpe ratio (multiply by sqrt of trading days per year)
        sharpe = (mean_excess / std_excess) * math.sqrt(252)
        return sharpe

    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown percentage.

        Returns:
            Maximum drawdown as percentage (0-100)
        """
        if len(self.portfolio_values) < 2:
            return 0.0

        # Calculate running maximum and drawdown
        peak = self.portfolio_values[0][1]
        max_drawdown = 0.0

        for _, value in self.portfolio_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak * 100 if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    def calculate_total_return(self) -> float:
        """Calculate total return percentage.

        Returns:
            Total return percentage
        """
        if len(self.portfolio_values) < 2:
            return 0.0

        start_value = self.portfolio_values[0][1]
        end_value = self.portfolio_values[-1][1]

        if start_value == 0:
            return 0.0

        return ((end_value - start_value) / start_value) * 100

    def get_strategy_performance(self, tag: str) -> Dict:
        """Get performance metrics for a specific strategy tag.

        Args:
            tag: Strategy tag to analyze

        Returns:
            Dictionary with performance metrics for the strategy
        """
        # Filter trades by tag
        strategy_trades = [
            trade for trade in self.trade_history
            if tag in trade['tags']
        ]

        if not strategy_trades:
            return {
                'tag': tag,
                'trade_count': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'average_return': 0.0,
                'average_win': 0.0,
                'average_loss': 0.0,
                'profit_factor': 0.0
            }

        wins = [t for t in strategy_trades if t['is_win']]
        losses = [t for t in strategy_trades if not t['is_win']]

        total_pnl = sum(t['pnl'] for t in strategy_trades)
        win_rate = (len(wins) / len(strategy_trades)) * 100 if strategy_trades else 0.0
        avg_return = statistics.mean([t['return_pct'] for t in strategy_trades]) if strategy_trades else 0.0
        avg_win = statistics.mean([t['pnl'] for t in wins]) if wins else 0.0
        avg_loss = statistics.mean([abs(t['pnl']) for t in losses]) if losses else 0.0
        gross_wins = sum(t['pnl'] for t in wins)
        gross_losses = sum(abs(t['pnl']) for t in losses)
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else float('inf') if gross_wins > 0 else 0.0

        return {
            'tag': tag,
            'trade_count': len(strategy_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'average_return': avg_return,
            'average_win': avg_win,
            'average_loss': avg_loss,
            'profit_factor': profit_factor
        }

    def generate_performance_report(self) -> Dict:
        """Generate a comprehensive performance report.

        Returns:
            Dictionary containing all performance metrics
        """
        # Update daily performance before generating report
        self.update_daily_performance()

        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_trades': len(self.trade_history),
                'win_rate': self.calculate_win_rate(),
                'total_pnl': sum(t['pnl'] for t in self.trade_history),
                'total_return_pct': self.calculate_total_return(),
                'average_return_per_trade': self.calculate_average_return(),
                'average_win': self.calculate_average_win(),
                'average_loss': self.calculate_average_loss(),
                'profit_factor': self.calculate_profit_factor(),
                'sharpe_ratio': self.calculate_sharpe_ratio(),
                'max_drawdown': self.calculate_max_drawdown()
            },
            'recent_trades': self.trade_history[-10:] if self.trade_history else [],  # Last 10 trades
            'strategies': {}
        }

        # Add performance for each unique tag
        all_tags = set()
        for trade in self.trade_history:
            all_tags.update(trade['tags'])

        for tag in all_tags:
            report['strategies'][tag] = self.get_strategy_performance(tag)

        return report

    def print_performance_summary(self):
        """Print a formatted performance summary to console."""
        report = self.generate_performance_report()
        summary = report['summary']

        print("\n" + "="*60)
        print("PERFORMANCE ANALYTICS REPORT")
        print("="*60)
        print(f"Timestamp: {report['timestamp']}")
        print(f"Total Trades: {summary['total_trades']}")
        print(f"Win Rate: {summary['win_rate']:.1f}%")
        print(f"Total P&L: ${summary['total_pnl']:.2f}")
        print(f"Total Return: {summary['total_return_pct']:.2f}%")
        print(f"Average Return/Trade: {summary['average_return_per_trade']:.2f}%")
        print(f"Average Win: ${summary['average_win']:.2f}")
        print(f"Average Loss: ${summary['average_loss']:.2f}")
        print(f"Profit Factor: {summary['profit_factor']:.2f}")
        print(f"Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {summary['max_drawdown']:.2f}%")

        if report['strategies']:
            print("\nSTRATEGY PERFORMANCE:")
            print("-"*60)
            for tag, perf in report['strategies'].items():
                print(f"{tag}:")
                print(f"  Trades: {perf['trade_count']}")
                print(f"  Win Rate: {perf['win_rate']:.1f}%")
                print(f"  Total P&L: ${perf['total_pnl']:.2f}")
                print(f"  Profit Factor: {perf['profit_factor']:.2f}")
                print()


def create_performance_analytics(execution_monitor: ExecutionMonitor) -> PerformanceAnalytics:
    """Factory function to create a PerformanceAnalytics instance.

    Args:
        execution_monitor: Initialized ExecutionMonitor instance

    Returns:
        Configured PerformanceAnalytics instance
    """
    return PerformanceAnalytics(execution_monitor)


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

    # For demonstration, we'll show how the PerformanceAnalytics would work with WebullExecution
    # In practice, you would initialize WebullExecution with real credentials
    print("Note: This is a demonstration. For actual trading, initialize WebullExecution with real credentials.")

    # We'll create a mock monitor for demonstration purposes
    class MockExecutionMonitor:
        def get_position_summary(self):
            return {
                'positions': [],
                'total_unrealized_pnl': 0.0
            }

        def add_alert_callback(self, callback):
            pass  # Mock implementation

    monitor = MockExecutionMonitor()

    # Create performance analytics
    analytics = create_performance_analytics(monitor)

    # Add some demo trades
    from datetime import datetime, timedelta

    # Winning trade
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

    # Losing trade
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

    # Another winning trade
    analytics.add_completed_trade(
        symbol="MSFT261016C00300000",
        side="buy",
        quantity=3,
        entry_price=4.00,
        exit_price=5.20,
        entry_time=datetime.now() - timedelta(days=4),
        exit_time=datetime.now() - timedelta(days=1),
        tags=["bull_call", "long_msft"]
    )

    # Update portfolio values for return calculation
    analytics.portfolio_values = [
        (datetime.now() - timedelta(days=10), 95000.0),
        (datetime.now() - timedelta(days=5), 98000.0),
        (datetime.now(), 102000.0)
    ]
    analytics.daily_returns = [3.2, -1.5, 4.1]  # Sample daily returns

    # Generate and print report
    analytics.print_performance_summary()

    print("\nPerformanceAnalytics module loaded successfully")
    print("Use create_performance_analytics(monitor) to create an instance")