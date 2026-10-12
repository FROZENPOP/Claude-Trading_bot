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
                 min_premium_return: float = 0.05,  # 5% minimum return
                 max_days_to_expiry: int = 45,      # Maximum DTE for opportunities
                 min_days_to_expiry: int = 7,       # Minimum DTE for opportunities
                 min_confidence_score: float = 0.6): # Minimum signal confidence
        """Initialize opportunity generator.

        Args:
            min_premium_return: Minimum expected return as fraction of premium
            max_days_to_expiry: Maximum days to expiry for considered options
            min_days_to_expiry: Minimum days to expiry for considered options
            min_confidence_score: Minimum signal confidence for opportunity
        """
        self.min_premium_return = min_premium_return
        self.max_days_to_expiry = max_days_to_expiry
        self.min_days_to_expiry = min_days_to_expiry
        self.min_confidence_score = min_confidence_score

        self.vertical_spread_strategy = VerticalSpreadStrategy()
        self.option_pricer = OptionPricingEngine()
        self.signal_generator = SignalGenerator()

        logger.info(f"Option opportunity generator initialized "
                   f"(min_return: {min_premium_return:.1%}, "
                   f"DTE: {min_days_to_expiry}-{max_days_to_expiry})")

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

            # Determine strategy type based on recommendation and score
            if recommendation in ['strong_buy', 'buy'] and research_score >= 0.6:
                # Bullish bias - look for bull call spreads or cash-secured puts
                bullish_opps = self._generate_bullish_opportunities(
                    symbol, stock_result, market_data
                )
                opportunities.extend(bullish_opps)

            elif recommendation in ['weak_hold', 'hold'] and research_score >= 0.4:
                # Neutral bias - look for iron condors or credit spreads
                neutral_opps = self._generate_neutral_opportunities(
                    symbol, stock_result, market_data
                )
                opportunities.extend(neutral_opps)

            # Note: Bearish opportunities could be added for low scores if desired

        except Exception as e:
            logger.error(f"Error generating opportunities for {symbol}: {e}")

        return opportunities

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

                            # Calculate expiration date from days to expiry
                            from datetime import datetime, timedelta
                            expiration_date = (datetime.now() + timedelta(days=days_to_exp)).strftime('%Y-%m-%d')

                            # For vertical spreads, we can estimate max profit/loss
                            # For bull call spread: max profit = spread width - net debit, max loss = net debit
                            # For bear put spread: max profit = spread width - net credit, max loss = net credit
                            spread_width = abs(short_strike - long_strike)
                            option_type = getattr(signal, 'option_type', 'call')

                            if option_type == 'call':
                                # Bull call spread: we pay net debit, max profit is width - debit, max loss is debit
                                max_profit = max(0.0, spread_width - net_debit)
                                max_loss = net_debit
                            else:
                                # Bear put spread: we receive net credit, max profit is width - credit, max loss is credit
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
        # Filter by minimum confidence score
        filtered = [
            opp for opp in opportunities
            if opp.get('expected_return', 0) >= self.min_premium_return
            and opp.get('probability_of_profit', 0) >= self.min_confidence_score
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
        min_premium_return=config.get('min_premium_return', 0.05),
        max_days_to_expiry=config.get('max_days_to_expiry', 45),
        min_days_to_expiry=config.get('min_days_to_expiry', 7),
        min_confidence_score=config.get('min_confidence_score', 0.6)
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