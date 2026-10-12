"""Performance metrics calculation for backtesting."""

import pandas as pd
import numpy as np
from typing import Optional


class PerformanceMetrics:
    """Calculate performance metrics for trading strategies."""

    TRADING_DAYS_PER_YEAR = 252

    def __init__(self, risk_free_rate: float = 0.0):
        """Initialize performance metrics calculator.

        Args:
            risk_free_rate: Annual risk-free rate (default 0%)
        """
        self.risk_free_rate = risk_free_rate

    def calculate_all_metrics(
        self,
        portfolio_values: pd.Series,
        benchmark_values: Optional[pd.Series] = None
    ) -> dict:
        """Calculate all performance metrics.

        Args:
            portfolio_values: Series of portfolio values
            benchmark_values: Optional benchmark values for comparison

        Returns:
            Dictionary of performance metrics
        """
        returns = self._calculate_returns(portfolio_values)

        metrics = {
            # Return metrics
            'total_return': self.total_return(portfolio_values),
            'annualized_return': self.annualized_return(portfolio_values),
            'average_daily_return': returns.mean(),

            # Risk metrics
            'annualized_volatility': self.annualized_volatility(returns),
            'daily_volatility': returns.std(),

            # Risk-adjusted return metrics
            'sharpe_ratio': self.sharpe_ratio(returns),
            'sortino_ratio': self.sortino_ratio(returns),

            # Drawdown metrics
            'max_drawdown': self.max_drawdown(portfolio_values),
            'max_drawdown_date': self.max_drawdown_date(portfolio_values),
            'avg_drawdown': self.average_drawdown(portfolio_values),

            # Trade frequency
            'num_trading_days': len(portfolio_values),

            # Benchmark comparison if provided
            'information_ratio': self.information_ratio(
                returns, benchmark_values
            ) if benchmark_values is not None else None,
            'beta': self.beta(returns, benchmark_values) if benchmark_values is not None else None,
        }

        return metrics

    def _calculate_returns(self, values: pd.Series) -> pd.Series:
        """Calculate daily returns from portfolio values."""
        return values.pct_change().dropna()

    def total_return(self, portfolio_values: pd.Series) -> float:
        """Calculate total return.

        Args:
            portfolio_values: Series of portfolio values

        Returns:
            Total return as decimal (e.g., 0.5 = 50%)
        """
        if len(portfolio_values) < 2:
            return 0
        return (portfolio_values.iloc[-1] - portfolio_values.iloc[0]) / portfolio_values.iloc[0]

    def annualized_return(self, portfolio_values: pd.Series) -> float:
        """Calculate annualized return.

        Args:
            portfolio_values: Series of portfolio values

        Returns:
            Annualized return as decimal
        """
        if len(portfolio_values) < 2:
            return 0

        total_return = self.total_return(portfolio_values)
        num_years = len(portfolio_values) / self.TRADING_DAYS_PER_YEAR
        return (1 + total_return) ** (1 / num_years) - 1 if num_years > 0 else 0

    def annualized_volatility(self, returns: pd.Series) -> float:
        """Calculate annualized volatility.

        Args:
            returns: Series of daily returns

        Returns:
            Annualized volatility as decimal
        """
        if len(returns) < 2:
            return 0
        return returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)

    def sharpe_ratio(self, returns: pd.Series) -> float:
        """Calculate Sharpe ratio.

        Args:
            returns: Series of daily returns

        Returns:
            Sharpe ratio (risk-adjusted return)
        """
        if len(returns) < 2 or returns.std() == 0:
            return 0

        annualized_ret = self.annualized_return_from_returns(returns)
        annualized_vol = self.annualized_volatility(returns)

        return (annualized_ret - self.risk_free_rate) / annualized_vol if annualized_vol > 0 else 0

    def sortino_ratio(self, returns: pd.Series) -> float:
        """Calculate Sortino ratio (uses downside deviation).

        Args:
            returns: Series of daily returns

        Returns:
            Sortino ratio
        """
        if len(returns) < 2:
            return 0

        annualized_ret = self.annualized_return_from_returns(returns)

        # Downside deviation: std of returns below threshold (0)
        negative_returns = returns[returns < 0]
        if len(negative_returns) < 2:
            return 0

        downside_std = negative_returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)

        return (annualized_ret - self.risk_free_rate) / downside_std if downside_std > 0 else 0

    def max_drawdown(self, portfolio_values: pd.Series) -> float:
        """Calculate maximum drawdown.

        Args:
            portfolio_values: Series of portfolio values

        Returns:
            Maximum drawdown as decimal (positive value)
        """
        if len(portfolio_values) < 2:
            return 0

        # Running maximum
        running_max = portfolio_values.expanding().max()

        # Drawdown
        drawdown = (running_max - portfolio_values) / running_max

        return drawdown.max()

    def max_drawdown_date(self, portfolio_values: pd.Series) -> pd.Timestamp:
        """Get date of maximum drawdown.

        Args:
            portfolio_values: Series of portfolio values

        Returns:
            Date of maximum drawdown
        """
        if len(portfolio_values) < 2:
            return portfolio_values.index[0]

        running_max = portfolio_values.expanding().max()
        drawdown = (running_max - portfolio_values) / running_max

        return drawdown.idxmax()

    def average_drawdown(self, portfolio_values: pd.Series) -> float:
        """Calculate average drawdown.

        Args:
            portfolio_values: Series of portfolio values

        Returns:
            Average drawdown as decimal
        """
        if len(portfolio_values) < 2:
            return 0

        running_max = portfolio_values.expanding().max()
        drawdown = (running_max - portfolio_values) / running_max

        return drawdown.mean()

    def annualized_return_from_returns(self, returns: pd.Series) -> float:
        """Calculate annualized return from daily returns.

        Args:
            returns: Series of daily returns

        Returns:
            Annualized return as decimal
        """
        if len(returns) < 2:
            return 0

        avg_daily_return = returns.mean()
        return (1 + avg_daily_return) ** self.TRADING_DAYS_PER_YEAR - 1

    def information_ratio(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> float:
        """Calculate information ratio.

        Args:
            returns: Series of strategy returns
            benchmark_returns: Series of benchmark returns

        Returns:
            Information ratio
        """
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 0

        # Excess returns
        excess_returns = returns - benchmark_returns

        # Annualized excess return
        annualized_excess = excess_returns.mean() * self.TRADING_DAYS_PER_YEAR

        # Annualized tracking error
        tracking_error = excess_returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)

        return annualized_excess / tracking_error if tracking_error > 0 else 0

    def beta(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> float:
        """Calculate beta.

        Args:
            returns: Series of strategy returns
            benchmark_returns: Series of benchmark returns

        Returns:
            Beta coefficient
        """
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 1.0

        # Calculate covariance and variance
        covariance = returns.cov(benchmark_returns)
        benchmark_variance = benchmark_returns.var()

        return covariance / benchmark_variance if benchmark_variance > 0 else 1.0

    def win_rate(self, trades: list) -> float:
        """Calculate win rate from trades.

        Args:
            trades: List of Trade objects

        Returns:
            Win rate as decimal (0 to 1)
        """
        if not trades:
            return 0

        # Count wins (sells that resulted in profit)
        wins = 0
        total_sells = 0

        # Track cost basis per symbol
        cost_basis = {}

        for trade in trades:
            if trade.side == 'buy':
                # Update cost basis
                if trade.symbol not in cost_basis:
                    cost_basis[trade.symbol] = {'total_cost': 0, 'quantity': 0}
                cost_basis[trade.symbol]['total_cost'] += trade.price * trade.quantity
                cost_basis[trade.symbol]['quantity'] += trade.quantity
            elif trade.side == 'sell':
                total_sells += 1
                if trade.symbol in cost_basis:
                    avg_cost = cost_basis[trade.symbol]['total_cost'] / cost_basis[trade.symbol]['quantity']
                    if trade.price > avg_cost:
                        wins += 1
                    # Reduce quantity
                    cost_basis[trade.symbol]['quantity'] -= trade.quantity
                    if cost_basis[trade.symbol]['quantity'] <= 0:
                        del cost_basis[trade.symbol]

        return wins / total_sells if total_sells > 0 else 0

    def profit_factor(self, trades: list) -> float:
        """Calculate profit factor (gross profits / gross losses).

        Args:
            trades: List of Trade objects

        Returns:
            Profit factor
        """
        if not trades:
            return 0

        gross_profits = 0
        gross_losses = 0

        # Track positions
        positions = {}

        for trade in trades:
            if trade.side == 'buy':
                if trade.symbol not in positions:
                    positions[trade.symbol] = 0
                positions[trade.symbol] += trade.price * trade.quantity
            elif trade.side == 'sell':
                if trade.symbol in positions:
                    gross_profits += max(0, (trade.price - positions[trade.symbol]) * trade.quantity)
                    gross_losses += min(0, (trade.price - positions[trade.symbol]) * trade.quantity)
                    del positions[trade.symbol]

        return gross_profits / abs(gross_losses) if gross_losses < 0 else float('inf') if gross_profits > 0 else 0


def compare_to_benchmark(
    strategy_values: pd.Series,
    benchmark_values: pd.Series
) -> dict:
    """Compare strategy performance to benchmark.

    Args:
        strategy_values: Series of strategy portfolio values
        benchmark_values: Series of benchmark values

    Returns:
        Dictionary comparing strategy to benchmark
    """
    metrics = PerformanceMetrics()

    strategy_returns = metrics._calculate_returns(strategy_values)
    benchmark_returns = metrics._calculate_returns(benchmark_values)

    comparison = {
        'strategy_total_return': metrics.total_return(strategy_values),
        'strategy_annualized_return': metrics.annualized_return(strategy_values),
        'benchmark_total_return': metrics.total_return(benchmark_values),
        'benchmark_annualized_return': metrics.annualized_return(benchmark_values),
        'excess_return': metrics.total_return(strategy_values) - metrics.total_return(benchmark_values),
        'information_ratio': metrics.information_ratio(strategy_returns, benchmark_returns),
        'beta': metrics.beta(strategy_returns, benchmark_returns),
    }

    return comparison
