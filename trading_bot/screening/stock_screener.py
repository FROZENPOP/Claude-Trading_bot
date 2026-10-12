"""Stock screening module for autonomous options trading system.

Provides stock screening and ranking capabilities using a multi-factor model
with enhanced filtering and signal confirmation for discovered stocks.
"""

import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import yaml

# Import existing signal generation technology
from trading_bot.strategies.signals import SignalGenerator, Signal
from trading_bot.strategies.composite_score import CompositeTrendScore

# Global flag to track if MCP tools are available
MCP_AVAILABLE = None  # Will be set on first call to _is_mcp_available()

logger = logging.getLogger(__name__)


class MultiFactorModel:
    """Calculates multi-factor scores for stocks."""

    def __init__(self):
        """Initialize multi-factor model."""
        self.composite_scorer = CompositeTrendScore()
        self.signal_generator = SignalGenerator()
        logger.info("Multi-factor model initialized")

    def calculate_technical_score(self, data: pd.DataFrame) -> float:
        """Calculate technical score based on price trends and momentum.

        Args:
            data: DataFrame with historical market data

        Returns:
            Technical score (0-1)
        """
        try:
            # Use existing composite score as technical foundation
            prices = data['adjusted_close']
            composite_scores = self.composite_scorer.calculate_composite_score(prices)
            latest_composite = composite_scores.iloc[-1] if len(composite_scores) > 0 else 0.0

            # Normalize from [-1, 1] to [0, 1]
            technical_score = (float(latest_composite) + 1) / 2

            # Add momentum confirmation
            if len(prices) >= 20:
                # 20-day momentum
                momentum_20d = (prices.iloc[-1] / prices.iloc[-20]) - 1
                momentum_score = np.tanh(momentum_20d * 5)  # Normalize to [-1, 1] then to [0, 1]
                momentum_score = (momentum_score + 1) / 2

                # Combine with technical score (70% composite, 30% momentum)
                technical_score = 0.7 * technical_score + 0.3 * momentum_score

            # Ensure valid score
            if pd.isna(technical_score) or not np.isfinite(technical_score):
                technical_score = 0.5

            return max(0.0, min(1.0, technical_score))

        except Exception as e:
            logger.warning(f"Error calculating technical score: {e}")
            return 0.5

    def calculate_fundamental_score(self, data: pd.DataFrame, symbol: str) -> float:
        """Calculate fundamental score based on financial health proxies.

        Args:
            data: DataFrame with historical market data
            symbol: Stock symbol

        Returns:
            Fundamental score (0-1)
        """
        try:
            # Use price stability and volume consistency as fundamental proxies
            prices = data['adjusted_close']
            volumes = data.get('volume', pd.Series([0] * len(data)))

            if len(prices) < 20:
                return 0.5

            # Price volatility (lower volatility = higher fundamental score)
            returns = prices.pct_change().dropna()
            if len(returns) > 0:
                volatility = returns.std()
                # Convert volatility to score (0-1, where lower vol = higher score)
                vol_score = 1 / (1 + volatility * 100)  # Scale factor
            else:
                vol_score = 0.5

            # Volume consistency (consistent volume = healthy trading)
            if len(volumes) > 0 and volumes.mean() > 0:
                vol_cv = volumes.std() / volumes.mean()  # Coefficient of variation
                vol_consistency_score = 1 / (1 + vol_cv)  # Lower CV = higher score
            else:
                vol_consistency_score = 0.5

            # Price trend consistency (higher = better fundamentals)
            # Count days price closed above moving average
            ma_20 = prices.rolling(20).mean()
            days_above_ma = (prices > ma_20).sum()
            trend_consistency = days_above_ma / len(prices) if len(prices) > 0 else 0.5

            # Combine fundamental factors
            fundamental_score = (
                0.4 * vol_score +
                0.3 * vol_consistency_score +
                0.3 * trend_consistency
            )

            # Ensure valid score
            if pd.isna(fundamental_score) or not np.isfinite(fundamental_score):
                fundamental_score = 0.5

            return max(0.0, min(1.0, fundamental_score))

        except Exception as e:
            logger.warning(f"Error calculating fundamental score for {symbol}: {e}")
            return 0.5

    def calculate_quality_score(self, data: pd.DataFrame) -> float:
        """Calculate quality score based on financial strength proxies.

        Args:
            data: DataFrame with historical market data

        Returns:
            Quality score (0-1)
        """
        try:
            prices = data['adjusted_close']

            if len(prices) < 10:
                return 0.5

            # Price recovery ability (quality stocks bounce off support)
            # Look for higher lows in downtrends
            rolling_min = prices.rolling(10).min()
            higher_lows = 0
            total_comparisons = 0

            for i in range(10, len(prices)):
                if prices.iloc[i] > rolling_min.iloc[i-1]:
                    higher_lows += 1
                total_comparisons += 1

            recovery_score = higher_lows / max(total_comparisons, 1)

            # Price consistency (less extreme moves = higher quality)
            returns = prices.pct_change().dropna()
            if len(returns) > 0:
                # Count extreme moves (>2 standard deviations)
                return_std = returns.std()
                extreme_moves = ((returns.abs() > 2 * return_std)).sum()
                consistency_score = 1 - (extreme_moves / len(returns))
            else:
                consistency_score = 0.5

            # Combine quality factors
            quality_score = 0.6 * recovery_score + 0.4 * consistency_score

            # Ensure valid score
            if pd.isna(quality_score) or not np.isfinite(quality_score):
                quality_score = 0.5

            return max(0.0, min(1.0, quality_score))

        except Exception as e:
            logger.warning(f"Error calculating quality score: {e}")
            return 0.5

    def calculate_sentiment_score(self, data: pd.DataFrame) -> float:
        """Calculate sentiment score based on price action and volume patterns.

        Args:
            data: DataFrame with historical market data

        Returns:
            Sentiment score (0-1)
        """
        try:
            prices = data['adjusted_close']
            volumes = data.get('volume', pd.Series([0] * len(data)))

            if len(prices) < 5:
                return 0.5

            # Price-volume relationship (bullish = price up on volume)
            returns = prices.pct_change().dropna()
            vol_changes = volumes.pct_change().dropna()

            # Align the series
            min_len = min(len(returns), len(vol_changes))
            if min_len > 0:
                returns_aligned = returns.iloc[-min_len:]
                vol_changes_aligned = vol_changes.iloc[-min_len:]

                # Calculate correlation (positive = bullish sentiment)
                if len(returns_aligned) > 1 and len(vol_changes_aligned) > 1:
                    correlation = np.corrcoef(returns_aligned, vol_changes_aligned)[0,1]
                    if np.isnan(correlation):
                        sentiment_score = 0.5
                    else:
                        # Convert from [-1,1] to [0,1]
                        sentiment_score = (correlation + 1) / 2
                else:
                    sentiment_score = 0.5
            else:
                sentiment_score = 0.5

            # Recent price trend (uptrend = positive sentiment)
            if len(prices) >= 5:
                recent_trend = (prices.iloc[-1] / prices.iloc[-5]) - 1
                trend_score = np.tanh(recent_trend * 3)  # Normalize
                trend_score = (trend_score + 1) / 2  # To [0,1]

                # Combine with volume-price relationship
                sentiment_score = 0.7 * sentiment_score + 0.3 * trend_score

            # Ensure valid score
            if pd.isna(sentiment_score) or not np.isfinite(sentiment_score):
                sentiment_score = 0.5

            return max(0.0, min(1.0, sentiment_score))

        except Exception as e:
            logger.warning(f"Error calculating sentiment score: {e}")
            return 0.5

    def calculate_volume_liquidity_score(self, data: pd.DataFrame) -> float:
        """Calculate volume/liquidity score based on trading activity.

        Args:
            data: DataFrame with historical market data

        Returns:
            Volume/liquidity score (0-1)
        """
        try:
            volumes = data.get('volume', pd.Series([0] * len(data)))
            prices = data['adjusted_close']

            if len(volumes) == 0 or volumes.sum() == 0:
                return 0.5

            # Average daily volume (higher = better liquidity)
            avg_volume = volumes.mean()
            # Normalize volume score (assuming 1M shares is good liquidity)
            volume_score = min(1.0, avg_volume / 1000000)

            # Volume consistency (consistent volume = reliable liquidity)
            if len(volumes) > 0 and volumes.mean() > 0:
                vol_cv = volumes.std() / volumes.mean()
                consistency_score = 1 / (1 + vol_cv)
            else:
                consistency_score = 0.5

            # Price impact approximation (lower impact = better liquidity)
            # Calculate typical price change per volume unit
            if len(prices) > 1 and len(volumes) > 1:
                returns = prices.pct_change().dropna()
                vol_changes = volumes.pct_change().dropna()

                # Avoid division by zero
                valid_idx = (vol_changes != 0) & ~(vol_changes.isna()) & ~(returns.isna())
                if valid_idx.sum() > 0:
                    price_impact = abs(returns[valid_idx] / vol_changes[valid_idx]).mean()
                    # Lower price impact = higher liquidity score
                    impact_score = 1 / (1 + price_impact * 100)  # Scale factor
                else:
                    impact_score = 0.5
            else:
                impact_score = 0.5

            # Combine volume/liquidity factors
            volume_liquidity_score = (
                0.4 * volume_score +
                0.3 * consistency_score +
                0.3 * impact_score
            )

            # Ensure valid score
            if pd.isna(volume_liquidity_score) or not np.isfinite(volume_liquidity_score):
                volume_liquidity_score = 0.5

            return max(0.0, min(1.0, volume_liquidity_score))

        except Exception as e:
            logger.warning(f"Error calculating volume/liquidity score: {e}")
            return 0.5

    def calculate_options_score(self, data: pd.DataFrame, symbol: str) -> float:
        """Calculate options-specific score based on options chain data.

        Args:
            data: DataFrame with historical market data
            symbol: Stock symbol

        Returns:
            Options score (0-1)
        """
        try:
            # Use contract-metadata-first approach to prevent look-ahead bias
            # Similar to approach in opportunity_generator.py

            # Check if MCP tools are available
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
                logger.warning("MCP tools not available - using neutral options score")
                return 0.5

            from datetime import datetime, timedelta

            # Get today's date for contract metadata
            current_date = datetime.now().date()
            today_str = current_date.strftime('%Y-%m-%d')

            # Get option chain data for current date (metadata first)
            option_chain_df = mcp__webull__get_option_contracts(
                underlying_symbols=symbol,
                expiration_date_gte=today_str,
                status="active"
            )

            # Handle case where we get no data or unexpected format
            if option_chain_df is None:
                logger.warning(f"No option chain data returned for {symbol}")
                return 0.5

            # Convert to DataFrame if needed (following research framework pattern)
            if isinstance(option_chain_df, str):
                import json
                try:
                    data_dict = json.loads(option_chain_df)
                    if isinstance(data_dict, dict) and 'data' in data_dict and isinstance(data_dict['data'], dict):
                        if 'option_contracts' in data_dict['data']:
                            option_chain_df = pd.DataFrame(data_dict['data']['option_contracts'])
                        else:
                            logger.warning(f"Unexpected option chain data format for {symbol}")
                            return 0.5
                    else:
                        logger.warning(f"Unexpected option chain data format for {symbol}")
                        return 0.5
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse option chain data for {symbol}")
                    return 0.5
            elif not isinstance(option_chain_df, pd.DataFrame):
                logger.warning(f"Unexpected option chain data type for {symbol}: {type(option_chain_df)}")
                return 0.5

            # Check if we have valid data
            if option_chain_df.empty:
                logger.warning(f"Empty option chain data for {symbol}")
                return 0.5

            # Ensure required columns exist
            required_columns = ['symbol', 'option_type', 'volume', 'open_interest']
            missing_columns = [col for col in required_columns if col not in option_chain_df.columns]
            if missing_columns:
                logger.warning(f"Missing columns in option chain data for {symbol}: {missing_columns}")
                return 0.5

            # Separate puts and calls
            puts_df = option_chain_df[option_chain_df['option_type'] == 'put'].copy()
            calls_df = option_chain_df[option_chain_df['option_type'] == 'call'].copy()

            # Calculate Put/Call Ratio based on volume (avoiding division by zero)
            put_volume = puts_df['volume'].sum() if 'volume' in puts_df.columns and not puts_df.empty else 0
            call_volume = calls_df['volume'].sum() if 'volume' in calls_df.columns and not calls_df.empty else 0
            total_volume = put_volume + call_volume

            if total_volume > 0:
                put_call_ratio = put_volume / call_volume if call_volume > 0 else float('inf')
                # Normalize put/call ratio to 0-1 scale
                # Typical range is 0.5 to 2.0, with 1.0 being neutral
                # We'll map: <0.5 -> 0.0 (extremely bearish), 0.5-2.0 -> 0.0-1.0, >2.0 -> 1.0 (extremely bullish)
                if put_call_ratio <= 0.5:
                    pc_ratio_score = 0.0  # Extremely bearish sentiment
                elif put_call_ratio >= 2.0:
                    pc_ratio_score = 1.0  # Extremely bullish sentiment (contrarian interpretation)
                else:
                    # Linear mapping from [0.5, 2.0] to [0.0, 1.0]
                    pc_ratio_score = (put_call_ratio - 0.5) / (2.0 - 0.5)
            else:
                pc_ratio_score = 0.5  # Neutral if no volume data

            # Calculate options activity level (total volume normalized)
            # We'll use a heuristic: assume 100k volume is moderate activity
            activity_score = min(1.0, total_volume / 100000)

            # Calculate open interest level (proxy for market depth)
            total_oi = 0
            if 'open_interest' in option_chain_df.columns:
                total_oi = option_chain_df['open_interest'].sum()
            oi_score = min(1.0, total_oi / 50000)  # Assume 50k OI is good depth

            # Combine options factors
            # Weight: 40% put/call ratio (sentiment), 30% activity, 30% open interest (liquidity)
            options_score = (
                0.4 * pc_ratio_score +
                0.3 * activity_score +
                0.3 * oi_score
            )

            # Ensure valid score
            if pd.isna(options_score) or not np.isfinite(options_score):
                options_score = 0.5

            return max(0.0, min(1.0, options_score))

        except Exception as e:
            logger.warning(f"Error calculating options score for {symbol}: {e}")
            return 0.5


class StockResearchScore:
    """Calculates research scores for stocks using multi-factor model with enhanced filtering."""

    def __init__(self,
                 lookback_days: int = 100,
                 entry_threshold: float = 0.5,
                 exit_threshold: float = -0.3,
                 min_price: float = 5.0,
                 max_price: float = 1000.0,
                 min_avg_volume: int = 500000):
        """Initialize stock research scorer.

        Args:
            lookback_days: Number of days of historical data to analyze
            entry_threshold: Minimum composite score for bullish signal
            exit_threshold: Maximum composite score for bearish signal
            min_price: Minimum stock price to consider (filters out penny stocks)
            max_price: Maximum stock price to consider (filters out extremely expensive stocks)
            min_avg_volume: Minimum average daily volume for liquidity
        """
        self.lookback_days = lookback_days
        self.min_price = min_price
        self.max_price = max_price
        self.min_avg_volume = min_avg_volume
        self.multi_factor_model = MultiFactorModel()
        signal_generator = SignalGenerator()
        self.composite_scorer = CompositeTrendScore(
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold
        )
        logger.info(f"Stock research scorer initialized (lookback: {lookback_days} days, "
                   f"price range: ${min_price}-${max_price}, min volume: {min_avg_volume:,})")

    def _apply_pre_screening_filters(self, symbol: str, market_data: pd.DataFrame) -> Tuple[bool, str]:
        """Apply pre-screening filters to eliminate unsuitable stocks early.

        Args:
            symbol: Stock symbol to check
            market_data: DataFrame with historical market data

        Returns:
            Tuple of (passes_filters, reason_if_failed)
        """
        try:
            # Check if we have sufficient data
            if market_data is None or market_data.empty:
                return False, "No market data"

            # Check for required columns
            required_columns = ['date', 'adjusted_close']
            missing_columns = [col for col in required_columns if col not in market_data.columns]
            if missing_columns:
                return False, f"Missing columns: {missing_columns}"

            # Check data sufficiency
            if len(market_data) < 20:
                return False, f"Insufficient data: {len(market_data)} days"

            # Price filters
            current_price = market_data['adjusted_close'].iloc[-1]
            if current_price < self.min_price:
                return False, f"Price below minimum (${current_price:.2f} < ${self.min_price})"

            if current_price > self.max_price:
                return False, f"Price above maximum (${current_price:.2f} > ${self.max_price})"

            # Liquidity filter
            if 'volume' in market_data.columns:
                avg_volume = market_data['volume'].mean()
                if avg_volume < self.min_avg_volume:
                    return False, f"Insufficient liquidity ({avg_volume:,.0f} < {self.min_avg_volume:,} avg volume)"
            else:
                return False, "No volume data available"

            # Check for excessive volatility or gaps that might indicate problems
            prices = market_data['adjusted_close']
            if len(prices) >= 2:
                # Check for extreme single-day changes (>50%)
                daily_returns = prices.pct_change().abs()
                max_daily_change = daily_returns.max()
                if max_daily_change > 0.5:  # 50% single-day change
                    return False, f"Excessive volatility detected ({max_daily_change*100:.1f}% max daily change)"

            return True, "Passes all pre-screening filters"

        except Exception as e:
            logger.warning(f"Error applying pre-screening filters to {symbol}: {e}")
            return False, f"Filter error: {str(e)}"

    def screen_stock(self, symbol: str, market_data: pd.DataFrame) -> Dict[str, Any]:
        """Screen a single stock and calculate its research score using multi-factor model.

        Args:
            symbol: Stock symbol to screen
            market_data: DataFrame with historical market data

        Returns:
            Dictionary containing screening results and research score
        """
        try:
            # Apply pre-screening filters first
            passes_filters, filter_reason = self._apply_pre_screening_filters(symbol, market_data)
            if not passes_filters:
                return self._create_filtered_out_result(symbol, filter_reason)

            # Prepare data for analysis
            data = market_data.copy()
            data['date'] = pd.to_datetime(data['date'])

            # Filter to lookback period
            cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
            data = data[data['date'] >= cutoff_date].copy()

            # Final data sufficiency check after filtering
            if len(data) < 20:
                return self._create_error_result(symbol, f"Insufficient data after lookback filtering: {len(data)} days")

            # Sort by date ascending
            data = data.sort_values('date').reset_index(drop=True)

            # Calculate multi-factor scores
            technical_score = self.multi_factor_model.calculate_technical_score(data)
            fundamental_score = self.multi_factor_model.calculate_fundamental_score(data, symbol)
            quality_score = self.multi_factor_model.calculate_quality_score(data)
            sentiment_score = self.multi_factor_model.calculate_sentiment_score(data)
            volume_liquidity_score = self.multi_factor_model.calculate_volume_liquidity_score(data)
            options_score = self.multi_factor_model.calculate_options_score(data, symbol)

            # Calculate composite research score using weighted factors
            research_score = (
                0.25 * technical_score +
                0.25 * fundamental_score +
                0.15 * quality_score +
                0.15 * sentiment_score +
                0.10 * volume_liquidity_score +
                0.10 * options_score
            )

            # Get legacy signals for backward compatibility
            prices = data['adjusted_close']
            composite_scores = self.composite_scorer.calculate_composite_score(prices)
            latest_composite_score = composite_scores.iloc[-1] if len(composite_scores) > 0 else 0.0

            # Handle NaN composite score
            if pd.isna(latest_composite_score):
                latest_composite_score = 0.0

            # Generate trading signal using existing technology
            signal_generator = SignalGenerator()
            signal = signal_generator.get_signal(data, data['date'].iloc[-1])

            # Determine signal strength and type
            if signal is not None:
                signal_strength = signal.signal_strength
                signal_type = signal.signal_type
                signal_details = signal.metadata.get('details', 'No details')

                # Handle NaN signal strength
                if pd.isna(signal_strength):
                    signal_strength = 0.0
            else:
                signal_strength = 0.0
                signal_type = 'neutral'
                signal_details = 'No signal generated'

            # Apply signal confirmation logic - require alignment between factors and signal
            confirmed_signal = self._confirm_signal(
                technical_score, fundamental_score, quality_score,
                sentiment_score, volume_liquidity_score, options_score,
                signal_strength, signal_type
            )

            # Adjust research score based on signal confirmation
            if confirmed_signal:
                # Boost score if signals align with factors
                research_score = min(1.0, research_score * 1.1)
                confirmation_status = "confirmed"
            else:
                # Reduce score if signals conflict with factors
                research_score = max(0.0, research_score * 0.9)
                confirmation_status = "conflicted"

            # Final validation
            if pd.isna(research_score) or not np.isfinite(research_score):
                research_score = 0.5  # Default neutral score

            # Determine overall recommendation based on research score
            if research_score >= 0.8:
                recommendation = 'strong_buy'
            elif research_score >= 0.7:
                recommendation = 'buy'
            elif research_score >= 0.6:
                recommendation = 'moderate_buy'
            elif research_score >= 0.4:
                recommendation = 'hold'
            elif research_score >= 0.3:
                recommendation = 'weak_hold'
            else:
                recommendation = 'avoid'

            # Calculate additional metrics
            current_price = prices.iloc[-1]
            price_change_1d = ((prices.iloc[-1] / prices.iloc[-2]) - 1) * 100 if len(prices) >= 2 else 0
            price_change_5d = ((prices.iloc[-1] / prices.iloc[-6]) - 1) * 100 if len(prices) >= 6 else 0
            price_change_20d = ((prices.iloc[-1] / prices.iloc[-21]) - 1) * 100 if len(prices) >= 21 else 0

            # Calculate volatility (annualized)
            returns = prices.pct_change().dropna()
            if len(returns) > 0:
                volatility = returns.std() * np.sqrt(252) * 100
            else:
                volatility = 0

            # Handle any remaining NaN values in metrics
            metrics = {
                'current_price': float(current_price) if not pd.isna(current_price) else 0.0,
                'price_change_1d': float(price_change_1d) if not pd.isna(price_change_1d) else 0.0,
                'price_change_5d': float(price_change_5d) if not pd.isna(price_change_5d) else 0.0,
                'price_change_20d': float(price_change_20d) if not pd.isna(price_change_20d) else 0.0,
                'volatility': float(volatility) if not pd.isna(volatility) else 0.0
            }

            result = {
                'symbol': symbol,
                'research_score': float(research_score),
                'composite_score': float(latest_composite_score),
                'signal_strength': float(signal_strength),
                'signal_type': signal_type,
                'signal_details': signal_details,
                'signal_confirmation': confirmation_status,
                'recommendation': recommendation,
                'data_points': int(len(data)),
                'lookback_days': int(self.lookback_days),
                'timestamp': datetime.now().isoformat(),
                # Factor breakdown for analysis
                'factor_scores': {
                    'technical': float(technical_score),
                    'fundamental': float(fundamental_score),
                    'quality': float(quality_score),
                    'sentiment': float(sentiment_score),
                    'volume_liquidity': float(volume_liquidity_score),
                    'options': float(options_score)
                }
            }

            # Add metrics to result
            result.update(metrics)

            logger.debug(f"Screened {symbol}: score={research_score:.3f}, "
                        f"recommendation={recommendation}, confirmation={confirmation_status}")
            return result

        except Exception as e:
            logger.error(f"Error screening stock {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._create_error_result(symbol, f"Screening error: {str(e)}")

    def _confirm_signal(self, technical: float, fundamental: float, quality: float,
                       sentiment: float, volume_liquidity: float, options_score: float,
                       signal_strength: float, signal_type: str) -> bool:
        """Confirm signal alignment with multi-factor scores.

        Args:
            technical, fundamental, quality, sentiment, volume_liquidity, options_score: Factor scores (0-1)
            signal_strength: Signal strength (-1 to 1, where positive = bullish)
            signal_type: Signal type ('bullish', 'bearish', 'neutral')

        Returns:
            True if signal is confirmed by factors, False if conflicted
        """
        try:
            # Calculate overall factor alignment (0-1 scale)
            factor_alignment = (
                0.25 * technical +
                0.25 * fundamental +
                0.15 * quality +
                0.15 * sentiment +
                0.10 * volume_liquidity +
                0.10 * options_score
            )

            # Convert signal strength to 0-1 scale (0 = bearish, 0.5 = neutral, 1 = bullish)
            signal_normalized = (signal_strength + 1) / 2

            # Calculate alignment between factors and signal
            # Perfect alignment = 1.0, perfect misalignment = 0.0
            alignment = 1.0 - abs(factor_alignment - signal_normalized)

            # Require at least 60% alignment for confirmation
            return alignment >= 0.6

        except Exception as e:
            logger.warning(f"Error in signal confirmation: {e}")
            return False  # Default to not confirmed on error

    def _create_filtered_out_result(self, symbol: str, reason: str) -> Dict[str, Any]:
        """Create a filtered out result for a stock that failed pre-screening.

        Args:
            symbol: Stock symbol
            reason: Reason for filtering out

        Returns:
            Filtered out result dictionary
        """
        return {
            'symbol': symbol,
            'research_score': 0.0,
            'composite_score': 0.0,
            'signal_strength': 0.0,
            'signal_type': 'filtered',
            'signal_details': reason,
            'signal_confirmation': 'filtered',
            'recommendation': 'filtered',
            'current_price': 0.0,
            'price_change_1d': 0.0,
            'price_change_5d': 0.0,
            'price_change_20d': 0.0,
            'volatility': 0.0,
            'data_points': 0,
            'lookback_days': self.lookback_days,
            'timestamp': datetime.now().isoformat(),
            'filtered': True,
            'filter_reason': reason
        }

    def _create_error_result(self, symbol: str, error_message: str) -> Dict[str, Any]:
        """Create an error result for a stock that failed screening.

        Args:
            symbol: Stock symbol
            error_message: Error description

        Returns:
            Error result dictionary
        """
        return {
            'symbol': symbol,
            'research_score': 0.0,
            'composite_score': 0.0,
            'signal_strength': 0.0,
            'signal_type': 'error',
            'signal_details': error_message,
            'signal_confirmation': 'error',
            'recommendation': 'error',
            'current_price': 0.0,
            'price_change_1d': 0.0,
            'price_change_5d': 0.0,
            'price_change_20d': 0.0,
            'volatility': 0.0,
            'data_points': 0,
            'lookback_days': self.lookback_days,
            'timestamp': datetime.now().isoformat(),
            'error': True
        }


def screen_stocks_batch(symbols: List[str],
                       market_data_dict: Dict[str, pd.DataFrame],
                       lookback_days: int = 100,
                       min_price: float = 5.0,
                       max_price: float = 1000.0,
                       min_avg_volume: int = 500000) -> List[Dict[str, Any]]:
    """Screen a batch of stocks and return ranked results.

    Args:
        symbols: List of stock symbols to screen
        market_data_dict: Dictionary mapping symbols to their market data
        lookback_days: Number of days of historical data to analyze
        min_price: Minimum stock price to consider
        max_price: Maximum stock price to consider
        min_avg_volume: Minimum average daily volume for liquidity

    Returns:
        List of screening results sorted by research score (descending)
    """
    screener = StockResearchScore(
        lookback_days=lookback_days,
        min_price=min_price,
        max_price=max_price,
        min_avg_volume=min_avg_volume
    )
    results = []

    for symbol in symbols:
        # Get market data for this symbol
        market_data = market_data_dict.get(symbol)

        if market_data is None:
            logger.warning(f"No market data found for {symbol}")
            result = screener._create_error_result(symbol, "No market data available")
        else:
            result = screener.screen_stock(symbol, market_data)

        results.append(result)

    # Separate filtered out stocks from regular results for better reporting
    filtered_results = [r for r in results if r.get('filtered', False)]
    error_results = [r for r in results if r.get('error', False)]
    valid_results = [r for r in results if not r.get('filtered', False) and not r.get('error', False)]

    # Sort valid results by research score descending (highest first)
    valid_results.sort(key=lambda x: x['research_score'], reverse=True)

    # Combine results: valid first, then filtered, then errors
    results = valid_results + filtered_results + error_results

    logger.info(f"Screened {len(results)} stocks: "
                f"{len(valid_results)} valid, {len(filtered_results)} filtered, "
                f"{len(error_results)} errors")
    return results


def get_top_stocks(screening_results: List[Dict[str, Any]],
                   top_n: int = 20,
                   min_score: float = 0.0) -> List[Dict[str, Any]]:
    """Get top N stocks from screening results.

    Args:
        screening_results: List of screening results (should be sorted by score)
        top_n: Maximum number of stocks to return
        min_score: Minimum research score threshold

    Returns:
        List of top stocks meeting criteria
    """
    # Filter by minimum score and exclude errors and filtered out stocks
    filtered_results = [r for r in screening_results
                       if r['research_score'] >= min_score
                       and r.get('recommendation') not in ['error', 'filtered']
                       and not pd.isna(r['research_score'])
                       and np.isfinite(r['research_score'])]

    # Return top N
    top_stocks = filtered_results[:top_n]

    logger.info(f"Selected {len(top_stocks)} top stocks from {len(screening_results)} screened")
    return top_stocks


def save_screening_results(results: List[Dict[str, Any]],
                          output_path: str = "screening_results.yaml"):
    """Save screening results to YAML file.

    Args:
        results: List of screening results
        output_path: Path to save results
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to YAML-serializable format
    yaml_data = {
        'screening_timestamp': datetime.now().isoformat(),
        'total_stocks_screened': len(results),
        'results': results
    }

    with open(output_path, 'w') as f:
        yaml.dump(yaml_data, f, default_flow_style=False)

    logger.info(f"Screening results saved to {output_path}")


if __name__ == "__main__":
    # Test the screening system
    print("Testing stock screening system...")

    # Create test data
    test_dates = [datetime.now() - timedelta(days=i) for i in range(30, 0, -1)]
    test_prices = [100 + i * 0.3 + np.random.normal(0, 1) for i in range(30)]

    test_data = pd.DataFrame({
        'date': test_dates,
        'adjusted_close': test_prices,
        'volume': [1000000 + np.random.normal(0, 50000) for _ in range(30)]
    })

    # Test screening
    screener = StockResearchScore()
    result = screener.screen_stock("TEST", test_data)

    print(f"Test result for TEST: {result['recommendation']} (score: {result['research_score']:.3f})")
    print(f"Signal confirmation: {result.get('signal_confirmation', 'N/A')}")
    print("Factor breakdown:")
    for factor, score in result['factor_scores'].items():
        print(f"  {factor}: {score:.3f}")
    print("Stock screening system test completed!")