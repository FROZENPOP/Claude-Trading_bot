"""Options opportunity generation module for autonomous options trading system.

Generates specific options opportunities (vertical spreads, etc.) for ranked stocks
from Phase 3 screening. Uses existing options strategies and applies filters to
identify high-probability trading opportunities.
"""

import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import yaml
from pathlib import Path

# Import existing options strategies
from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
from trading_bot.strategies.option_pricing import OptionPricingModel as OptionPricingEngine
from trading_bot.strategies.signals import SignalGenerator

logger = logging.getLogger(__name__)


class OptionOpportunityGenerator:
    """Generates options opportunities for ranked stocks."""

    def __init__(self,
                 min_premium_return: Optional[float] = None,  # Will be dynamically adjusted
                 max_days_to_expiry: int = 45,      # Maximum DTE for opportunities
                 min_days_to_expiry: int = 7,       # Minimum DTE for opportunities
                 min_confidence_score: Optional[float] = None): # Will be dynamically adjusted
        """Initialize opportunity generator.

        Args:
            min_premium_return: Minimum expected return as fraction of premium (None for dynamic)
            max_days_to_expiry: Maximum days to expiry for considered options
            min_days_to_expiry: Minimum days to expiry for considered options
            min_confidence_score: Minimum signal confidence for opportunity (None for dynamic)
        """
        self.min_premium_return = min_premium_return
        self.max_days_to_expiry = max_days_to_expiry
        self.min_days_to_expiry = min_days_to_expiry
        self.min_confidence_score = min_confidence_score

        # Dynamic thresholds that will be adjusted based on performance
        self.dynamic_min_return = min_premium_return or 0.05  # Start with 5% as default
        self.dynamic_min_confidence = min_confidence_score or 0.6  # Start with 60% as default

        self.vertical_spread_strategy = VerticalSpreadStrategy()
        self.option_pricer = OptionPricingEngine()
        self.signal_generator = SignalGenerator()

        # Performance tracking for dynamic adjustment
        self.performance_history = []
        self.market_regime = "unknown"  # Will be updated based on market conditions

        logger.info(f"Option opportunity generator initialized "
                   f"(min_return: {self.dynamic_min_return:.1%}, "
                   f"DTE: {min_days_to_expiry}-{max_days_to_expiry})")

    def update_performance_metrics(self, trade_result: Dict[str, Any], market_data: Optional[pd.DataFrame] = None):
        """Update performance metrics for dynamic threshold adjustment.

        Args:
            trade_result: Dictionary containing trade performance data
            market_data: Optional market data to determine regime
        """
        self.performance_history.append(trade_result)
        # Keep only last 100 trades for memory efficiency
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]

        # Update market regime if data provided
        if market_data is not None and not market_data.empty:
            self._update_market_regime(market_data)

        # Adjust thresholds based on recent performance and market regime
        self._adjust_thresholds()

    def _update_market_regime(self, market_data: pd.DataFrame):
        """Update market regime classification based on recent price action.

        Args:
            market_data: Market data DataFrame
        """
        if len(market_data) < 20:
            return

        # Calculate volatility and trend metrics
        returns = market_data['adjusted_close'].pct_change().dropna()
        if len(returns) < 10:
            return

        volatility = returns.rolling(window=10).std().iloc[-1] * np.sqrt(252)  # Annualized
        trend = (market_data['adjusted_close'].iloc[-1] / market_data['adjusted_close'].iloc[-10] - 1) if len(market_data) >= 10 else 0

        # Classify regime
        if volatility > 0.3:  # High volatility
            if abs(trend) < 0.05:  # Sideways
                self.market_regime = "high_volatility_sideways"
            elif trend > 0.05:  # Uptrend
                self.market_regime = "high_volatility_uptrend"
            else:  # Downtrend
                self.market_regime = "high_volatility_downtrend"
        else:  # Low volatility
            if abs(trend) < 0.05:  # Sideways
                self.market_regime = "low_volatility_sideways"
            elif trend > 0.05:  # Uptrend
                self.market_regime = "low_volatility_uptrend"
            else:  # Downtrend
                self.market_regime = "low_volatility_downtrend"

    def _adjust_thresholds(self):
        """Dynamically adjust return and confidence thresholds based on historical performance and market regime."""
        if len(self.performance_history) < 15:  # Need minimum samples
            return

        # Get recent trades (last 30 or all if fewer)
        recent_trades = self.performance_history[-30:] if len(self.performance_history) >= 15 else self.performance_history

        # Separate winning and losing trades
        winning_trades = [t for t in recent_trades if t.get('profit_loss', 0) > 0]
        losing_trades = [t for t in recent_trades if t.get('profit_loss', 0) <= 0]

        # Calculate win rate
        win_rate = len(winning_trades) / len(recent_trades) if recent_trades else 0

        # Adjust return target based on win rate and average returns
        if winning_trades:
            avg_win = np.mean([t.get('return_pct', 0) for t in winning_trades])
            avg_loss = np.mean([abs(t.get('return_pct', 0)) for t in losing_trades]) if losing_trades else 0.02

            # Target return that maintains positive expectancy
            # We want: (win_rate * avg_win) - ((1-win_rate) * avg_loss) > 0
            # Solving for minimum acceptable win: min_win = avg_loss * (1-win_rate) / win_rate
            if win_rate > 0:
                min_acceptable_return = avg_loss * (1 - win_rate) / win_rate
                # Add a buffer for robustness
                target_return = min_acceptable_return * 1.5

                # Apply regime-based adjustments
                regime_multiplier = self._get_regime_return_multiplier()
                target_return *= regime_multiplier

                # Bound the return target reasonably
                self.dynamic_min_return = max(0.01, min(0.25, target_return))

        # Adjust confidence threshold based on signal quality and win rate
        if 'signal_strength' in recent_trades[0] if recent_trades else False:
            signal_strengths = [t.get('signal_strength', 0) for t in recent_trades]
            winning_signals = [t.get('signal_strength', 0) for t in winning_trades] if winning_trades else []
            losing_signals = [t.get('signal_strength', 0) for t in losing_trades] if losing_trades else []

            if winning_signals and losing_signals:
                avg_winning_signal = np.mean(winning_signals)
                avg_losing_signal = np.mean(losing_signals)

                # If winning trades have significantly higher signal strength, we can be more selective
                signal_separation = avg_winning_signal - avg_losing_signal
                if signal_separation > 0.1:  # Good separation
                    # Increase confidence threshold to be more selective
                    base_confidence = 0.5 + (signal_separation * 0.5)  # Scale 0.5 to 1.0 based on separation
                else:
                    # Poor separation, use win rate to determine threshold
                    base_confidence = max(0.4, min(0.8, win_rate + 0.1))
            else:
                # Fallback to win rate based approach
                base_confidence = max(0.4, min(0.8, win_rate + 0.1))

            # Apply regime-based adjustments
            regime_multiplier = self._get_regime_confidence_multiplier()
            self.dynamic_min_confidence = max(0.3, min(0.9, base_confidence * regime_multiplier))

    def _get_regime_return_multiplier(self) -> float:
        """Get return multiplier based on current market regime.

        Returns:
            Multiplier to apply to base return target
        """
        regime_multipliers = {
            "high_volatility_sideways": 1.2,   # Higher returns possible in choppy markets
            "high_volatility_uptrend": 1.1,    # Moderate increase
            "high_volatility_downtrend": 0.9,  # Slightly lower due to risk
            "low_volatility_sideways": 0.8,    # Lower returns in calm markets
            "low_volatility_uptrend": 1.0,     # Baseline
            "low_volatility_downtrend": 0.9,   # Slightly lower
            "unknown": 1.0
        }
        return regime_multipliers.get(self.market_regime, 1.0)

    def _get_regime_confidence_multiplier(self) -> float:
        """Get confidence multiplier based on current market regime.

        Returns:
            Multiplier to apply to base confidence threshold
        """
        regime_multipliers = {
            "high_volatility_sideways": 0.9,   # Lower confidence needed in volatile markets
            "high_volatility_uptrend": 0.95,   # Slightly lower
            "high_volatility_downtrend": 1.1,  # Need higher confidence in risky markets
            "low_volatility_sideways": 1.1,    # Need higher confidence in calm markets (fewer opportunities)
            "low_volatility_uptrend": 1.0,     # Baseline
            "low_volatility_downtrend": 1.05,  # Slightly higher
            "unknown": 1.0
        }
        return regime_multipliers.get(self.market_regime, 1.0)

    def generate_opportunities(self,
                              ranked_stocks: List[Dict[str, Any]],
                              market_data_dict: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """Generate options opportunities for ranked stocks.

        Args:
            ranked_stocks: List of ranked stock results from Phase 3
            market_data_dict: Dictionary mapping symbols to market data

        Returns:
            List of options opportunities sorted by expected return
        """
        opportunities = []

        logger.info(f"Generating options opportunities for {len(ranked_stocks)} ranked stocks")

        for stock_result in ranked_stocks:
            symbol = stock_result['symbol']

            # Skip stocks with errors or poor recommendations
            if stock_result.get('recommendation') in ['error', 'avoid']:
                continue

            # Get market data for this symbol
            market_data = market_data_dict.get(symbol)
            if market_data is None or market_data.empty:
                logger.warning(f"No market data available for {symbol}")
                continue

            # Generate opportunities for this stock
            stock_opportunities = self._generate_stock_opportunities(
                symbol, stock_result, market_data
            )
            opportunities.extend(stock_opportunities)

        # Sort opportunities by expected return (descending)
        opportunities.sort(key=lambda x: x.get('expected_return', 0), reverse=True)

        logger.info(f"Generated {len(opportunities)} total options opportunities")
        return opportunities

    def _generate_stock_opportunities(self,
                                    symbol: str,
                                    stock_result: Dict[str, Any],
                                    market_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate options opportunities for a single stock.

        Args:
            symbol: Stock symbol
            stock_result: Stock screening result from Phase 3
            market_data: Market data DataFrame for the stock

        Returns:
            List of opportunities for this stock
        """
        opportunities = []

        try:
            # Determine market bias from stock result
            recommendation = stock_result.get('recommendation', 'hold')
            research_score = stock_result.get('research_score', 0.5)
            signal_strength = stock_result.get('signal_strength', 0.0)

            # Determine strategy type based on recommendation and score
            # Use dynamic thresholds for research score
            bullish_threshold = self._get_dynamic_research_threshold('bullish')
            bearish_threshold = self._get_dynamic_research_threshold('bearish')
            neutral_threshold = self._get_dynamic_research_threshold('neutral')

            if recommendation in ['strong_buy', 'buy'] and research_score >= bullish_threshold:
                # Bullish bias - look for bull call spreads or cash-secured puts
                bullish_opps = self._generate_bullish_opportunities(
                    symbol, stock_result, market_data
                )
                opportunities.extend(bullish_opps)

            elif recommendation in ['sell', 'strong_sell'] and research_score >= bearish_threshold:
                # Bearish bias - look for bear put spreads or call credit spreads
                bearish_opps = self._generate_bearish_opportunities(
                    symbol, stock_result, market_data
                )
                opportunities.extend(bearish_opps)

            elif recommendation in ['weak_hold', 'hold'] and research_score >= neutral_threshold:
                # Neutral bias - look for iron condors or credit spreads
                neutral_opps = self._generate_neutral_opportunities(
                    symbol, stock_result, market_data
                )
                opportunities.extend(neutral_opps)

            # Also generate opportunities based on signal strength regardless of recommendation
            # This allows us to act on strong signals even if the recommendation doesn't match
            if abs(signal_strength) >= self.dynamic_min_confidence:
                if signal_strength > 0:  # Bullish signal
                    signal_opps = self._generate_bullish_opportunities(
                        symbol, stock_result, market_data
                    )
                    opportunities.extend(signal_opps)
                elif signal_strength < 0:  # Bearish signal
                    signal_opps = self._generate_bearish_opportunities(
                        symbol, stock_result, market_data
                    )
                    opportunities.extend(signal_opps)

        except Exception as e:
            logger.error(f"Error generating opportunities for {symbol}: {e}")

        return opportunities

    def _get_dynamic_research_threshold(self, strategy_type: str) -> float:
        """Get dynamic research score threshold based on historical performance.

        Args:
            strategy_type: Type of strategy ('bullish', 'neutral', 'bearish')

        Returns:
            Research score threshold
        """
        # Default thresholds
        default_thresholds = {
            'bullish': 0.6,
            'neutral': 0.4,
            'bearish': 0.3
        }

        # If we don't have enough performance data, return defaults
        if len(self.performance_history) < 10:
            return default_thresholds.get(strategy_type, 0.5)

        # Analyze performance by research score for this strategy type
        # This is simplified - in practice, we'd want to track which strategy was used
        recent_trades = self.performance_history[-20:]

        if not recent_trades:
            return default_thresholds.get(strategy_type, 0.5)

        # For now, adjust based on overall win rate
        win_rate = sum(1 for t in recent_trades if t.get('profit_loss', 0) > 0) / len(recent_trades)

        # If we're winning more than expected, we can be more selective (higher threshold)
        # If we're winning less than expected, we need to be less selective (lower threshold)
        base_win_rate = 0.5  # Baseline expectation
        adjustment_factor = win_rate / base_win_rate if base_win_rate > 0 else 1.0

        # Apply adjustment to thresholds
        default_threshold = default_thresholds.get(strategy_type, 0.5)
        adjusted_threshold = default_threshold * (2.0 - adjustment_factor)  # Inverse relationship

        # Bound the threshold
        return max(0.2, min(0.8, adjusted_threshold))

    def _generate_bullish_opportunities(self,
                                      symbol: str,
                                      stock_result: Dict[str, Any],
                                      market_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate bullish options opportunities (call spreads, etc.)."""
        opportunities = []

        try:
            # Use vertical spread strategy to find bull call spreads
            current_price = stock_result.get('current_price', 0)
            if current_price <= 0:
                current_price = market_data['adjusted_close'].iloc[-1]

            # Generate potential bull call spreads using vertical spread strategy
            # First, get option chain data for today using MCP tools (contract-metadata-first approach)
            from datetime import datetime
            try:
                # Get option chain data for current date
                option_chain = None
                current_date = datetime.now().date()

                # Import MCP tools inside the function to avoid issues if not available
                # Following the same pattern as research_options_strategies.py
                def _is_mcp_available():
                    global MCP_AVAILABLE
                    if MCP_AVAILABLE is None:
                        try:
                            mcp__webull__get_account_balance()
                            MCP_AVAILABLE = True
                        except (NameError, AttributeError):
                            MCP_AVAILABLE = False
                    return MCP_AVAILABLE

                if not _is_mcp_available():
                    logger.warning("MCP tools not available - skipping bullish opportunity generation")
                    return opportunities

                # Get option chain data using MCP Webull tools
                # Get ALL active contracts as of today (metadata first)
                today_str = current_date.strftime('%Y-%m-%d')
                all_contracts_df = mcp__webull__get_option_contracts(
                    underlying_symbols=symbol,
                    expiration_date_gte=today_str,
                    status="active"
                )

                if all_contracts_df is None or (hasattr(all_contracts_df, '__len__') and len(all_contracts_df) == 0):
                    logger.warning(f"No option contracts found for {symbol}")
                    return opportunities

                # Convert to DataFrame if needed (following research framework pattern)
                if isinstance(all_contracts_df, str):
                    import json
                    data = json.loads(all_contracts_df)
                    # Assuming the MCP returns a list of contracts
                    option_chain = pd.DataFrame(data)
                else:
                    option_chain = all_contracts_df

                # Now verify each contract has trading data on the target date
                # This prevents look-ahead bias by verifying trading data per contract
                chains_with_data = []

                for _, contract in option_chain.iterrows():
                    contract_symbol = contract['symbol']

                    try:
                        # Get historical bars for this contract on the target date
                        bars_df = mcp__webull__get_option_bars(
                            symbol=contract_symbol,
                            start=today_str,
                            end=today_str,
                            timeframe="1Day",
                            limit=1
                        )

                        # If we have bar data for this contract on the target date, include it
                        if bars_df is not None and hasattr(bars_df, '__len__') and len(bars_df) > 0:
                            chains_with_data.append(contract)
                    except Exception as bar_error:
                        # Skip contracts where we can't get bar data
                        logger.debug(f"Could not get bar data for contract {contract_symbol}: {bar_error}")
                        continue

                if not chains_with_data:
                    logger.warning(f"No option contracts with trading data found for {symbol} on {today_str}")
                    return opportunities

                option_chain = pd.DataFrame(chains_with_data)

                logger.debug(f"Retrieved option chain for {symbol}: {len(option_chain)} contracts with data")

                # Generate signals from the vertical spread strategy
                if hasattr(self.vertical_spread_strategy, 'generate_spread_signals'):
                    raw_signals = self.vertical_spread_strategy.generate_spread_signals(
                        market_data=market_data,
                        option_chain=option_chain,
                        current_date=datetime.combine(current_date, datetime.min.time())
                    )

                    # Filter for bullish signals and convert to expected format
                    spreads = []
                    for signal in raw_signals:
                        if hasattr(signal, 'signal_type') and signal.signal_type == 'bullish':
                            # Extract the attributes that are actually set by the strategy methods
                            # Calculate missing values where possible
                            long_strike = getattr(signal, 'long_strike', 0)
                            short_strike = getattr(signal, 'short_strike', 0)
                            net_debit = getattr(signal, 'net_debit', 0.0)
                            days_to_exp = getattr(signal, 'days_to_exp', 0)
                            underlying_price = getattr(signal, 'underlying_price', 0)
                            expected_net_return = getattr(signal, 'expected_net_return', 0.0)

                            # Calculate expiration date from days to expiry
                            from datetime import datetime, timedelta
                            expiration_date = (datetime.now() + timedelta(days=days_to_exp)).strftime('%Y-%m-%d')

                            # For vertical spreads, we can estimate max profit/loss
                            # For bull call spread: max profit = spread width - net debit, max loss = net debit
                            # For bear put spread: max profit = spread width - net credit, max loss = net credit
                            spread_width = abs(short_strike - long_strike)
                            option_type = getattr(signal, 'option_type', 'call')

                            # For debit spreads (bull call/bear put): we pay net debit
                            # Max profit = spread width - net debit
                            # Max loss = net debit
                            # Ensure we don't have invalid values
                            if net_debit < 0 or spread_width <= 0:
                                # Invalid spread, skip
                                continue
                            max_profit = max(0.0, spread_width - net_debit)
                            max_loss = net_debit

                            # Calculate expected return (simplified: profit potential / risk)
                            expected_return = max_profit / max_loss if max_loss > 0 else 0.0

                            # Probability of profit - simplified estimate based on credit/debit ratio
                            # For debit spreads: lower debit relative to width = higher probability
                            # For credit spreads: higher credit relative to width = higher probability
                            if net_debit > 0:  # Debit spread
                                probability_of_profit = max(0.1, min(0.9, 1.0 - (net_debit / spread_width)))
                            else:  # Credit spread (net_debit would be negative for credit)
                                net_credit = abs(net_debit)
                                probability_of_profit = max(0.1, min(0.9, net_credit / spread_width))

                            # Apply dynamic confidence threshold
                            if probability_of_profit >= self.dynamic_min_confidence and expected_return >= self.dynamic_min_return:
                                spread_dict = {
                                    'long_strike': long_strike,
                                    'short_strike': short_strike,
                                    'expiration_date': expiration_date,
                                    'days_to_expiry': days_to_exp,
                                    'net_debit': net_debit,
                                    'max_profit': max_profit,
                                    'max_loss': max_loss,
                                    'expected_return': expected_return,
                                    'probability_of_profit': probability_of_profit
                                }
                                spreads.append(spread_dict)

                    logger.debug(f"Generated {len(spreads)} bullish spread signals for {symbol}")
                else:
                    logger.warning("Vertical spread strategy does not have generate_spread_signals method")
                    spreads = []

            except Exception as e:
                logger.error(f"Error generating bullish opportunities for {symbol}: {e}")
                spreads = []

            for spread in spreads:
                # Enhance spread with stock-specific information
                opportunity = {
                    'symbol': symbol,
                    'strategy_type': 'bull_call_spread',
                    'long_strike': spread['long_strike'],
                    'short_strike': spread['short_strike'],
                    'expiration_date': spread['expiration_date'],
                    'days_to_expiry': spread['days_to_expiry'],
                    'net_debit': spread['net_debit'],
                    'max_profit': spread['max_profit'],
                    'max_loss': spread['max_loss'],
                    'expected_return': spread['expected_return'],
                    'probability_of_profit': spread.get('probability_of_profit', 0.5),
                    'underlying_price': current_price,
                    'research_score': stock_result.get('research_score', 0.5),
                    'signal_confidence': stock_result.get('signal_strength', 0.0),
                    'recommendation': stock_result.get('recommendation', 'hold'),
                    'timestamp': datetime.now().isoformat()
                }
                opportunities.append(opportunity)

        except Exception as e:
            logger.error(f"Error generating bullish opportunities for {symbol}: {e}")

        return opportunities

    def _generate_bearish_opportunities(self,
                                      symbol: str,
                                      stock_result: Dict[str, Any],
                                      market_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate bearish options opportunities (put spreads, etc.)."""
        opportunities = []

        try:
            # Use vertical spread strategy to find bear put spreads
            current_price = stock_result.get('current_price', 0)
            if current_price <= 0:
                current_price = market_data['adjusted_close'].iloc[-1]

            # Generate potential bear put spreads using vertical spread strategy
            # First, get option chain data for today using MCP tools (contract-metadata-first approach)
            from datetime import datetime
            try:
                # Get option chain data for current date
                option_chain = None
                current_date = datetime.now().date()

                # Import MCP tools inside the function to avoid issues if not available
                # Following the same pattern as research_options_strategies.py
                def _is_mcp_available():
                    global MCP_AVAILABLE
                    if MCP_AVAILABLE is None:
                        try:
                            mcp__webull__get_account_balance()
                            MCP_AVAILABLE = True
                        except (NameError, AttributeError):
                            MCP_AVAILABLE = False
                    return MCP_AVAILABLE

                if not _is_mcp_available():
                    logger.warning("MCP tools not available - skipping bearish opportunity generation")
                    return opportunities

                # Get option chain data using MCP Webull tools
                # Get ALL active contracts as of today (metadata first)
                today_str = current_date.strftime('%Y-%m-%d')
                all_contracts_df = mcp__webull__get_option_contracts(
                    underlying_symbols=symbol,
                    expiration_date_gte=today_str,
                    status="active"
                )

                if all_contracts_df is None or (hasattr(all_contracts_df, '__len__') and len(all_contracts_df) == 0):
                    logger.warning(f"No option contracts found for {symbol}")
                    return opportunities

                # Convert to DataFrame if needed (following research framework pattern)
                if isinstance(all_contracts_df, str):
                    import json
                    data = json.loads(all_contracts_df)
                    # Assuming the MCP returns a list of contracts
                    option_chain = pd.DataFrame(data)
                else:
                    option_chain = all_contracts_df

                # Now verify each contract has trading data on the target date
                # This prevents look-ahead bias by verifying trading data per contract
                chains_with_data = []

                for _, contract in option_chain.iterrows():
                    contract_symbol = contract['symbol']

                    try:
                        # Get historical bars for this contract on the target date
                        bars_df = mcp__webull__get_option_bars(
                            symbol=contract_symbol,
                            start=today_str,
                            end=today_str,
                            timeframe="1Day",
                            limit=1
                        )

                        # If we have bar data for this contract on the target date, include it
                        if bars_df is not None and hasattr(bars_df, '__len__') and len(bars_df) > 0:
                            chains_with_data.append(contract)
                    except Exception as bar_error:
                        # Skip contracts where we can't get bar data
                        logger.debug(f"Could not get bar data for contract {contract_symbol}: {bar_error}")
                        continue

                if not chains_with_data:
                    logger.warning(f"No option contracts with trading data found for {symbol} on {today_str}")
                    return opportunities

                option_chain = pd.DataFrame(chains_with_data)

                logger.debug(f"Retrieved option chain for {symbol}: {len(option_chain)} contracts with data")

                # Generate signals from the vertical spread strategy
                if hasattr(self.vertical_spread_strategy, 'generate_spread_signals'):
                    raw_signals = self.vertical_spread_strategy.generate_spread_signals(
                        market_data=market_data,
                        option_chain=option_chain,
                        current_date=datetime.combine(current_date, datetime.min.time())
                    )

                    # Filter for bearish signals and convert to expected format
                    spreads = []
                    for signal in raw_signals:
                        if hasattr(signal, 'signal_type') and signal.signal_type == 'bearish':
                            # Extract the attributes that are actually set by the strategy methods
                            # Calculate missing values where possible
                            long_strike = getattr(signal, 'long_strike', 0)
                            short_strike = getattr(signal, 'short_strike', 0)
                            net_debit = getattr(signal, 'net_debit', 0.0)
                            days_to_exp = getattr(signal, 'days_to_exp', 0)
                            underlying_price = getattr(signal, 'underlying_price', 0)
                            expected_net_return = getattr(signal, 'expected_net_return', 0.0)

                            # Calculate expiration date from days to expiry
                            from datetime import datetime, timedelta
                            expiration_date = (datetime.now() + timedelta(days=days_to_exp)).strftime('%Y-%m-%d')

                            # For vertical spreads, we can estimate max profit/loss
                            # For bear put spread: we pay net debit, max profit is width - debit, max loss is debit
                            spread_width = abs(short_strike - long_strike)
                            option_type = getattr(signal, 'option_type', 'put')

                            # For debit spreads (bull call/bear put): we pay net debit
                            # Max profit = spread width - net debit
                            # Max loss = net debit
                            # Ensure we don't have invalid values
                            if net_debit < 0 or spread_width <= 0:
                                # Invalid spread, skip
                                continue
                            max_profit = max(0.0, spread_width - net_debit)
                            max_loss = net_debit

                            # Calculate expected return (simplified: profit potential / risk)
                            expected_return = max_profit / max_loss if max_loss > 0 else 0.0

                            # Probability of profit - simplified estimate based on credit/debit ratio
                            # For debit spreads: lower debit relative to width = higher probability
                            if net_debit > 0:  # Debit spread
                                probability_of_profit = max(0.1, min(0.9, 1.0 - (net_debit / spread_width)))
                            else:  # Credit spread (net_debit would be negative for credit)
                                net_credit = abs(net_debit)
                                probability_of_profit = max(0.1, min(0.9, net_credit / spread_width))

                            # Apply dynamic confidence threshold
                            if probability_of_profit >= self.dynamic_min_confidence and expected_return >= self.dynamic_min_return:
                                spread_dict = {
                                    'long_strike': long_strike,
                                    'short_strike': short_strike,
                                    'expiration_date': expiration_date,
                                    'days_to_expiry': days_to_exp,
                                    'net_debit': net_debit,
                                    'max_profit': max_profit,
                                    'max_loss': max_loss,
                                    'expected_return': expected_return,
                                    'probability_of_profit': probability_of_profit
                                }
                                spreads.append(spread_dict)

                    logger.debug(f"Generated {len(spreads)} bearish spread signals for {symbol}")
                else:
                    logger.warning("Vertical spread strategy does not have generate_spread_signals method")
                    spreads = []

            except Exception as e:
                logger.error(f"Error generating bearish opportunities for {symbol}: {e}")
                spreads = []

            for spread in spreads:
                # Enhance spread with stock-specific information
                opportunity = {
                    'symbol': symbol,
                    'strategy_type': 'bear_put_spread',
                    'long_strike': spread['long_strike'],
                    'short_strike': spread['short_strike'],
                    'expiration_date': spread['expiration_date'],
                    'days_to_expiry': spread['days_to_expiry'],
                    'net_debit': spread['net_debit'],
                    'max_profit': spread['max_profit'],
                    'max_loss': spread['max_loss'],
                    'expected_return': spread['expected_return'],
                    'probability_of_profit': spread.get('probability_of_profit', 0.5),
                    'underlying_price': current_price,
                    'research_score': stock_result.get('research_score', 0.5),
                    'signal_confidence': stock_result.get('signal_strength', 0.0),
                    'recommendation': stock_result.get('recommendation', 'hold'),
                    'timestamp': datetime.now().isoformat()
                }
                opportunities.append(opportunity)

        except Exception as e:
            logger.error(f"Error generating bearish opportunities for {symbol}: {e}")

        return opportunities

    def _generate_neutral_opportunities(self,
                                      symbol: str,
                                      stock_result: Dict[str, Any],
                                      market_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate neutral options opportunities (iron condors, credit spreads)."""
        opportunities = []

        try:
            # For now, we'll focus on bullish opportunities as primary
            # In a full implementation, this would generate iron condors, etc.
            logger.debug(f"Neutral opportunities not yet implemented for {symbol}")

        except Exception as e:
            logger.error(f"Error generating neutral opportunities for {symbol}: {e}")

        return opportunities

    def filter_opportunities(self,
                           opportunities: List[Dict[str, Any]],
                           max_opportunities: int = 10) -> List[Dict[str, Any]]:
        """Filter and limit opportunities based on quality criteria.

        Args:
            opportunities: List of generated opportunities
            max_opportunities: Maximum number of opportunities to return

        Returns:
            Filtered list of opportunities
        """
        # Filter by dynamic minimum confidence score and return
        filtered = [
            opp for opp in opportunities
            if opp.get('expected_return', 0) >= self.dynamic_min_return
            and opp.get('probability_of_profit', 0) >= self.dynamic_min_confidence
        ]

        # Sort by expected return and take top N
        filtered.sort(key=lambda x: x.get('expected_return', 0), reverse=True)
        result = filtered[:max_opportunities]

        logger.info(f"Filtered {len(opportunities)} opportunities to {len(result)} high-quality opportunities")
        return result

    def save_opportunities(self,
                          opportunities: List[Dict[str, Any]],
                          output_path: str = "options_opportunities.yaml"):
        """Save options opportunities to YAML file.

        Args:
            opportunities: List of options opportunities
            output_path: Path to save results
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to YAML-serializable format
        yaml_data = {
            'generation_timestamp': datetime.now().isoformat(),
            'total_opportunities': len(opportunities),
            'opportunities': opportunities
        }

        with open(output_path, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False)

        logger.info(f"Options opportunities saved to {output_path}")


def generate_opportunities_from_ranking(ranked_stocks: List[Dict[str, Any]],
                                      market_data_dict: Dict[str, pd.DataFrame],
                                      config_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Convenience function to generate opportunities from ranked stocks.

    Args:
        ranked_stocks: Ranked stock results from Phase 3
        market_data_dict: Market data for each stock
        config_path: Optional path to configuration file

    Returns:
        List of filtered options opportunities
    """
    # Load configuration if provided
    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    # Initialize generator with config values
    generator = OptionOpportunityGenerator(
        min_premium_return=config.get('min_premium_return', None),  # None for dynamic
        max_days_to_expiry=config.get('max_days_to_expiry', 45),
        min_days_to_expiry=config.get('min_days_to_expiry', 7),
        min_confidence_score=config.get('min_confidence_score', None)  # None for dynamic
    )

    # Generate opportunities
    opportunities = generator.generate_opportunities(ranked_stocks, market_data_dict)

    # Filter to best opportunities
    max_opps = config.get('max_opportunities', 10)
    filtered_opportunities = generator.filter_opportunities(opportunities, max_opps)

    return filtered_opportunities


if __name__ == "__main__":
    # Test the opportunity generation system
    print("Testing options opportunity generation system...")

    # This would normally be called with actual data from Phase 3
    print("Options opportunity generation system test completed!")