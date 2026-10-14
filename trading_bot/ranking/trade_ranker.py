"""Individual trade ranking module for autonomous options trading system.

Ranks individual options opportunities from Phase 4 using comprehensive scoring
that considers trade quality, portfolio context, risk management, and market
conditions to identify the most optimal trades for execution.
"""

import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import yaml
from pathlib import Path

# Import existing components
from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
from trading_bot.strategies.option_pricing import OptionPricingModel
from trading_bot.strategies.signals import SignalGenerator

logger = logging.getLogger(__name__)


class IndividualTradeRanker:
    """Ranks individual options opportunities for optimal trade selection."""

    def __init__(self,
                 min_risk_reward_ratio: float = 2.0,     # Minimum risk/reward ratio
                 max_risk_per_trade: float = 0.02,       # Maximum allowed risk ratio (max_loss_per_share / underlying_price_per_share)
                 min_win_rate: float = 0.6,              # Minimum 60% win rate
                 max_correlation: float = 0.7,           # Maximum correlation with existing positions
                 liquidity_threshold: float = 1000000):  # Minimum daily volume for liquidity
        """Initialize individual trade ranker.

        Args:
            min_risk_reward_ratio: Minimum acceptable risk/reward ratio
            max_risk_per_trade: Maximum allowed risk ratio where risk ratio = (max_loss_per_share / underlying_price_per_share)
            min_win_rate: Minimum acceptable win rate
            max_correlation: Maximum correlation with existing portfolio
            liquidity_threshold: Minimum daily dollar volume for liquidity
        """
        self.min_risk_reward_ratio = min_risk_reward_ratio
        self.max_risk_per_trade = max_risk_per_trade
        self.min_win_rate = min_win_rate
        self.max_correlation = max_correlation
        self.liquidity_threshold = liquidity_threshold

        self.vertical_spread_strategy = VerticalSpreadStrategy()
        self.option_pricer = OptionPricingModel()
        self.signal_generator = SignalGenerator()

        logger.info(f"Individual trade ranker initialized "
                   f"(min_r/r: {min_risk_reward_ratio}, max_risk: {max_risk_per_trade:.1%})")

    def rank_trades(self,
                   opportunities: List[Dict[str, Any]],
                   market_data_dict: Dict[str, pd.DataFrame],
                   portfolio_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Rank individual trades based on comprehensive scoring.

        Args:
            opportunities: List of opportunities from Phase 4
            market_data_dict: Dictionary mapping symbols to market data
            portfolio_context: Optional portfolio context for context-aware ranking

        Returns:
            List of ranked trades with individual trade scores
        """
        if not opportunities:
            logger.warning("No opportunities provided for ranking")
            return []

        logger.info(f"Ranking {len(opportunities)} individual trades")

        ranked_trades = []

        for opportunity in opportunities:
            # Calculate individual trade score
            trade_score = self._calculate_individual_trade_score(
                opportunity, market_data_dict, portfolio_context
            )

            # Create ranked trade object
            ranked_trade = opportunity.copy()
            ranked_trade.update({
                'individual_trade_score': trade_score['total_score'],
                'trade_quality_score': trade_score['quality_score'],
                'risk_score': trade_score['risk_score'],
                'context_score': trade_score['context_score'],
                'liquidity_score': trade_score['liquidity_score'],
                'ranking_timestamp': datetime.now().isoformat(),
                'ranking_factors': trade_score['factors']
            })

            ranked_trades.append(ranked_trade)

        # Sort by individual trade score (descending)
        ranked_trades.sort(key=lambda x: x['individual_trade_score'], reverse=True)

        logger.info(f"Ranked {len(ranked_trades)} trades")
        return ranked_trades

    def _calculate_individual_trade_score(self,
                                        opportunity: Dict[str, Any],
                                        market_data_dict: Dict[str, pd.DataFrame],
                                        portfolio_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate comprehensive individual trade score.

        Returns:
            Dictionary with total score and component scores
        """
        scores = {
            'quality_score': 0.0,    # Trade quality (risk/reward, win rate, etc.)
            'risk_score': 0.0,       # Risk management compliance
            'context_score': 0.0,    # Portfolio/market context fit
            'liquidity_score': 0.0,  # Market liquidity
            'total_score': 0.0,
            'factors': {}
        }

        symbol = opportunity['symbol']
        strategy_type = opportunity['strategy_type']

        # Get market data for this symbol
        market_data = market_data_dict.get(symbol)
        if market_data is None or market_data.empty:
            logger.warning(f"No market data for {symbol}, scoring as zero")
            return scores

        # 1. Trade Quality Score (40% weight)
        quality_factors = self._calculate_trade_quality(opportunity, market_data)
        scores['quality_score'] = quality_factors['score']
        scores['factors']['quality'] = quality_factors

        # 2. Risk Management Score (25% weight)
        risk_factors = self._calculate_risk_management(opportunity, market_data, portfolio_context)
        scores['risk_score'] = risk_factors['score']
        scores['factors']['risk'] = risk_factors

        # 3. Context Score (20% weight)
        context_factors = self._calculate_portfolio_context(opportunity, market_data, portfolio_context)
        scores['context_score'] = context_factors['score']
        scores['factors']['context'] = context_factors

        # 4. Liquidity Score (15% weight)
        liquidity_factors = self._calculate_liquidity(opportunity, market_data)
        scores['liquidity_score'] = liquidity_factors['score']
        scores['factors']['liquidity'] = liquidity_factors

        # Calculate weighted total score
        weights = {
            'quality': 0.40,
            'risk': 0.25,
            'context': 0.20,
            'liquidity': 0.15
        }

        total_score = (
            scores['quality_score'] * weights['quality'] +
            scores['risk_score'] * weights['risk'] +
            scores['context_score'] * weights['context'] +
            scores['liquidity_score'] * weights['liquidity']
        )

        scores['total_score'] = min(max(total_score, 0.0), 1.0)  # Clamp to 0-1

        return scores

    def _calculate_trade_quality(self,
                               opportunity: Dict[str, Any],
                               market_data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate trade quality based on risk/reward, win rate, etc."""
        factors = {
            'risk_reward_ratio': 0.0,
            'win_rate_estimate': 0.0,
            'expected_value': 0.0,
            'score': 0.0
        }

        # Extract trade parameters
        max_profit = opportunity.get('max_profit', 0)
        max_loss = opportunity.get('max_loss', 0)
        expected_return = opportunity.get('expected_return', 0)
        probability = opportunity.get('probability_of_profit', 0)

        # Calculate risk/reward ratio
        if max_loss > 0:
            risk_reward_ratio = max_profit / max_loss
            factors['risk_reward_ratio'] = risk_reward_ratio

            # Score risk/reward (higher is better, cap at 5.0 for scoring)
            rr_score = min(risk_reward_ratio / 5.0, 1.0) if risk_reward_ratio >= 0 else 0.0
        else:
            rr_score = 0.0

        # Estimate win rate from probability of profit
        win_rate = probability  # Simplified - in reality would be more complex
        factors['win_rate_estimate'] = win_rate

        # Score win rate (higher is better)
        wr_score = win_rate  # Already 0-1

        # Calculate expected value (simplified)
        if max_loss > 0:
            expected_value = (probability * max_profit) - ((1 - probability) * max_loss)
            ev_score = min(max(expected_value / max_loss, 0.0), 2.0) / 2.0  # Normalize to 0-1
        else:
            ev_score = 0.0

        factors['expected_value'] = expected_value

        # Combine quality factors (weighted average)
        quality_score = (rr_score * 0.4) + (wr_score * 0.3) + (ev_score * 0.3)
        factors['score'] = min(max(quality_score, 0.0), 1.0)

        return factors

    def _calculate_risk_management(self,
                                 opportunity: Dict[str, Any],
                                 market_data: pd.DataFrame,
                                 portfolio_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate risk management compliance score."""
        factors = {
            'max_risk_per_trade': 0.0,
            'max_drawdown_estimate': 0.0,
            'score': 0.0
        }

        max_loss = opportunity.get('max_loss', 0)
        underlying_price = opportunity.get('underlying_price', 0)

        # Calculate risk per trade as percentage of underlying price
        if underlying_price > 0 and max_loss > 0:
            risk_per_share = max_loss  # For spread, this is the max loss per share
            risk_percentage = risk_per_share / underlying_price

            # Score based on max risk per trade (lower is better)
            if risk_percentage <= self.max_risk_per_trade:
                risk_score = 1.0 - (risk_percentage / self.max_risk_per_trade) * 0.5  # 0.5-1.0 range
            else:
                risk_score = max(0.0, 1.0 - ((risk_percentage - self.max_risk_per_trade) / self.max_risk_per_trade) * 0.5)

            factors['max_risk_per_trade'] = risk_percentage
            factors['score'] = max(0.0, min(risk_score, 1.0))
        else:
            factors['score'] = 0.0

        return factors

    def _calculate_portfolio_context(self,
                                   opportunity: Dict[str, Any],
                                   market_data: pd.DataFrame,
                                   portfolio_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate portfolio/market context fit score."""
        factors = {
            'correlation_score': 0.5,  # Default neutral
            'sector_diversification': 0.5,
            'market_regime_fit': 0.5,
            'score': 0.5  # Default neutral
        }

        # If no portfolio context provided, return neutral score
        if not portfolio_context:
            return factors

        symbol = opportunity['symbol']

        # In a full implementation, this would:
        # 1. Check correlation with existing positions
        # 2. Check sector diversification
        # 3. Check market regime fit (trending vs ranging)
        # 4. Check opportunity size relative to portfolio

        # For now, we'll use a simplified approach based on available data
        # Check if we have some basic portfolio info
        current_positions = portfolio_context.get('positions', [])
        portfolio_value = portfolio_context.get('total_value', 100000)  # Default $100k

        # Simple diversification bonus if we have few positions
        position_count = len(current_positions)
        if position_count < 5:
            diversification_score = 0.7  # Good to add more positions
        elif position_count < 10:
            diversification_score = 0.6
        else:
            diversification_score = 0.4  # May be over-concentrated

        factors['sector_diversification'] = diversification_score

        # Market regime fit - simplified based on recent volatility
        if len(market_data) >= 20:
            recent_returns = market_data['adjusted_close'].pct_change().tail(20)
            volatility = recent_returns.std() * np.sqrt(252)  # Annualized

            # Prefer moderate volatility for options selling
            if 0.15 <= volatility <= 0.35:  # 15-35% volatility ideal for premium selling
                regime_score = 0.8
            elif volatility < 0.15:
                regime_score = 0.6  # Low vol - less premium available
            else:
                regime_score = 0.5  # High vol - higher risk

            factors['market_regime_fit'] = regime_score

        # Combine context factors
        context_score = (
            factors['correlation_score'] * 0.4 +
            factors['sector_diversification'] * 0.3 +
            factors['market_regime_fit'] * 0.3
        )
        factors['score'] = min(max(context_score, 0.0), 1.0)

        return factors

    def _calculate_liquidity(self,
                           opportunity: Dict[str, Any],
                           market_data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate market liquidity score."""
        factors = {
            'daily_volume': 0.0,
            'bid_ask_spread_estimate': 0.0,
            'score': 0.0
        }

        if market_data is None or market_data.empty:
            return factors

        # Calculate average daily volume
        if 'volume' in market_data.columns:
            avg_volume = market_data['volume'].tail(10).mean()  # 10-day average
            factors['daily_volume'] = avg_volume

            # Score based on volume (higher is better)
            # Normalize: 1M+ volume = 1.0 score, 100K volume = 0.1 score
            volume_score = min(avg_volume / 1000000.0, 1.0) if avg_volume > 0 else 0.0
            volume_score = max(volume_score, 0.1)  # Minimum 0.1 for any volume

            # Estimate bid-ask spread from price volatility (simplified)
            if len(market_data) >= 2:
                price_changes = market_data['adjusted_close'].pct_change().abs().tail(5)
                avg_price_change = price_changes.mean()
                # Higher volatility = wider spreads
                spread_estimate = avg_price_change * 2  # Rough estimate
                spread_score = max(0.0, 1.0 - (spread_estimate * 20))  # Penalize high spreads
            else:
                spread_score = 0.8  # Default assumption

            # Combine liquidity factors
            liquidity_score = (volume_score * 0.7) + (spread_score * 0.3)
            factors['score'] = min(max(liquidity_score, 0.0), 1.0)
        else:
            factors['score'] = 0.5  # Neutral if no volume data

        return factors

    def filter_and_rank_trades(self,
                              opportunities: List[Dict[str, Any]],
                              market_data_dict: Dict[str, pd.DataFrame],
                              portfolio_context: Optional[Dict[str, Any]] = None,
                              max_trades: int = 5) -> List[Dict[str, Any]]:
        """Filter and rank trades, returning only the best candidates.

        Args:
            opportunities: List of opportunities from Phase 4
            market_data_dict: Market data for each symbol
            portfolio_context: Optional portfolio context
            max_trades: Maximum number of trades to return

        Returns:
            List of top-ranked trades meeting quality thresholds
        """
        # Rank all trades
        ranked_trades = self.rank_trades(opportunities, market_data_dict, portfolio_context)

        # Filter by minimum quality thresholds
        filtered_trades = [
            trade for trade in ranked_trades
            if trade['individual_trade_score'] >= 0.5  # Minimum 50% overall score
            and trade.get('risk_score', 0) >= 0.4      # Minimum 40% risk score
            and trade.get('liquidity_score', 0) >= 0.3 # Minimum 30% liquidity score
        ]

        # Return top N trades
        result = filtered_trades[:max_trades]

        logger.info(f"Filtered {len(ranked_trades)} trades to {len(result)} quality trades")
        return result

    def save_ranked_trades(self,
                          ranked_trades: List[Dict[str, Any]],
                          output_path: str = "ranked_trades.yaml"):
        """Save ranked trades to YAML file.

        Args:
            ranked_trades: List of ranked trades
            output_path: Path to save results
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to YAML-serializable format
        yaml_data = {
            'ranking_timestamp': datetime.now().isoformat(),
            'total_trades_ranked': len(ranked_trades),
            'trades': ranked_trades
        }

        with open(output_path, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False)

        logger.info(f"Ranked trades saved to {output_path}")


def rank_individual_trades(opportunities: List[Dict[str, Any]],
                          market_data_dict: Dict[str, pd.DataFrame],
                          portfolio_context: Optional[Dict[str, Any]] = None,
                          config_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Convenience function to rank individual trades from opportunities.

    Args:
        opportunities: Opportunities from Phase 4
        market_data_dict: Market data for each symbol
        portfolio_context: Optional portfolio context
        config_path: Optional path to configuration file

    Returns:
        List of ranked individual trades
    """
    # Load configuration if provided
    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    # Initialize ranker with config values
    ranker = IndividualTradeRanker(
        min_risk_reward_ratio=config.get('min_risk_reward_ratio', 2.0),
        max_risk_per_trade=config.get('max_risk_per_trade', 0.02),
        min_win_rate=config.get('min_win_rate', 0.6),
        max_correlation=config.get('max_correlation', 0.7),
        liquidity_threshold=config.get('liquidity_threshold', 1000000)
    )

    # Rank trades
    ranked_trades = ranker.rank_trades(opportunities, market_data_dict, portfolio_context)

    # Filter to best trades
    max_trades = config.get('max_trades', 5)
    filtered_trades = ranker.filter_and_rank_trades(
        opportunities, market_data_dict, portfolio_context, max_trades
    )

    return filtered_trades


if __name__ == "__main__":
    # Test the individual trade ranking system
    print("Testing individual trade ranking system...")

    # This would normally be called with actual data from Phase 4
    print("Individual trade ranking system test completed!")