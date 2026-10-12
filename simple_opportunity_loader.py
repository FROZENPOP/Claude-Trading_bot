#!/usr/bin/env python3
"""
Simple opportunity loader for Phase 4 system.
This script loads ranked opportunities by simulating what the Phase 4
opportunity generation system would produce.
"""

import sys
import os
import json
from datetime import datetime, timedelta
import random

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def load_ranked_opportunities():
    """
    Load ranked opportunities from the Phase 4 system.

    This function simulates the output of the Phase 4 opportunity generation
    workflow by creating realistic opportunities based on ranked stocks.
    """

    # Simulate loading ranked stocks from Phase 3 system
    # In a real implementation, this would come from the Phase 3 workflow output
    ranked_stocks = [
        {
            'symbol': 'AAPL',
            'research_score': 85.0,
            'recommendation': 'buy',
            'current_price': 175.23,
            'signal_strength': 0.82
        },
        {
            'symbol': 'MSFT',
            'research_score': 82.0,
            'recommendation': 'buy',
            'current_price': 382.45,
            'signal_strength': 0.78
        },
        {
            'symbol': 'GOOGL',
            'research_score': 78.0,
            'recommendation': 'buy',
            'current_price': 142.67,
            'signal_strength': 0.75
        },
        {
            'symbol': 'TSLA',
            'research_score': 75.0,
            'recommendation': 'buy',
            'current_price': 248.92,
            'signal_strength': 0.71
        },
        {
            'symbol': 'AMZN',
            'research_score': 72.0,
            'recommendation': 'buy',
            'current_price': 145.33,
            'signal_strength': 0.68
        },
        {
            'symbol': 'META',
            'research_score': 70.0,
            'recommendation': 'buy',
            'current_price': 312.45,
            'signal_strength': 0.65
        },
        {
            'symbol': 'NVDA',
            'research_score': 68.0,
            'recommendation': 'buy',
            'current_price': 875.30,
            'signal_strength': 0.62
        },
        {
            'symbol': 'JPM',
            'research_score': 65.0,
            'recommendation': 'buy',
            'current_price': 165.20,
            'signal_strength': 0.60
        }
    ]

    # Simulate market data for each stock (in a real system, this would be downloaded)
    market_data_dict = {}
    for stock in ranked_stocks:
        symbol = stock['symbol']
        base_price = stock['current_price']

        # Generate realistic market data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        # Create daily data points
        dates = []
        prices = []
        current_price = base_price

        for i in range(30):
            date = start_date + timedelta(days=i)
            dates.append(date)

            # Add some realistic price movement
            daily_change = random.uniform(-0.02, 0.02)  # ±2% daily change
            current_price *= (1 + daily_change)
            prices.append(max(current_price, 0.01))  # Ensure positive price

        market_data_dict[symbol] = {
            'dates': dates,
            'prices': prices,
            'volumes': [random.randint(1000000, 10000000) for _ in range(30)]
        }

    # Generate opportunities for each stock
    all_opportunities = []

    for stock in ranked_stocks:
        symbol = stock['symbol']
        current_price = stock['current_price']
        research_score = stock['research_score']
        signal_strength = stock['signal_strength']
        recommendation = stock['recommendation']

        # Get market data for this symbol
        market_data = market_data_dict[symbol]

        # Generate bull call spread opportunities (main strategy from Phase 4 framework)
        # In a real implementation, this would use the vertical spread strategy
        bull_opportunities = generate_bull_call_spreads(
            symbol, current_price, research_score, signal_strength, recommendation, market_data
        )

        all_opportunities.extend(bull_opportunities)

    # Filter and rank opportunities
    # Filter by minimum expected return (5%) and minimum probability (60%)
    filtered_opportunities = [
        opp for opp in all_opportunities
        if opp['expected_return'] >= 0.05 and opp['probability_of_profit'] >= 0.6
    ]

    # Sort by expected return (descending), then by probability of profit (descending)
    ranked_opportunities = sorted(
        filtered_opportunities,
        key=lambda x: (x['expected_return'], x['probability_of_profit']),
        reverse=True
    )

    # Take top 10 opportunities for Phase 5
    top_opportunities = ranked_opportunities[:10]

    # Format for StructuredOutput
    result = {
        "ranked_opportunities": [
            {
                "symbol": opp["symbol"],
                "strategy_type": opp["strategy_type"],
                "long_strike": opp["long_strike"],
                "short_strike": opp["short_strike"],
                "expiration_date": opp["expiration_date"],
                "days_to_expiry": opp["days_to_expiry"],
                "net_debit": opp["net_debit"],
                "max_profit": opp["max_profit"],
                "max_loss": opp["max_loss"],
                "expected_return": opp["expected_return"],
                "probability_of_profit": opp["probability_of_profit"],
                "underlying_price": opp["underlying_price"]
            }
            for opp in top_opportunities
        ]
    }

    return result

def generate_bull_call_spreads(symbol, current_price, research_score, signal_strength, recommendation, market_data):
    """
    Generate bull call spread opportunities for a stock.

    This simulates what the vertical spread strategy would produce.
    """
    opportunities = []

    # Only generate opportunities for stocks with bullish signals
    if recommendation not in ['buy', 'strong_buy'] or research_score < 0.6:
        return opportunities

    # Generate multiple expiration dates
    expirations = [
        datetime.now() + timedelta(days=14),  # 2 weeks
        datetime.now() + timedelta(days=30),  # 1 month
        datetime.now() + timedelta(days=45)   # ~6 weeks
    ]

    # Generate multiple strike prices around the current price
    # For bull call spreads: long strike < short strike
    base_strike = round(current_price)

    for exp_date in expirations:
        days_to_expiry = (exp_date - datetime.now()).days

        # Skip if outside preferred DTE range (7-45 days)
        if days_to_expiry < 7 or days_to_expiry > 45:
            continue

        # Generate strike pairs
        for long_offset in [-5, -2.5, 0, 2.5]:  # Long strike offsets
            for short_offset in [2.5, 5, 7.5, 10]:  # Short strike offsets (must be > long offset)
                if short_offset <= long_offset:
                    continue

                long_strike = base_strike + long_offset
                short_strike = base_strike + short_offset

                # Ensure strikes are positive and reasonable
                if long_strike <= 0 or short_strike <= 0:
                    continue

                # Calculate spread width
                width = short_strike - long_strike

                # Skip if width is too large (max 10% of stock price)
                if width > current_price * 0.1:
                    continue

                # Simulate option prices (simplified Black-Scholes approximation)
                # In a real implementation, this would use the option pricing model
                time_to_expiry = days_to_expiry / 365.0
                volatility = 0.25  # 25% assumed volatility

                # Simplified option pricing (intrinsic value + time value)
                long_intrinsic = max(current_price - long_strike, 0)
                short_intrinsic = max(current_price - short_strike, 0)

                # Time value approximation (simplified)
                long_time_value = long_strike * 0.03 * (time_to_expiry ** 0.5)
                short_time_value = short_strike * 0.03 * (time_to_expiry ** 0.5)

                long_price = long_intrinsic + long_time_value
                short_price = short_intrinsic + short_time_value

                # Ensure prices are positive
                long_price = max(long_price, 0.01)
                short_price = max(short_price, 0.01)

                # For bull call spread: we buy the long call and sell the short call
                net_debit = long_price - short_price  # We pay more for the lower strike call

                # Actually, for a bull call spread: long lower strike, short higher strike
                # So we buy the lower strike call and sell the higher strike call
                # Net debit = price of long call - price of short call
                # Since long call (lower strike) is more expensive, net_debit should be positive
                net_debit = long_price - short_price

                # If net_debit is negative, we have it backwards - swap the logic
                if net_debit < 0:
                    # This would be a credit spread, not what we want for bull call
                    continue

                # Calculate max profit and max loss
                # For bull call spread:
                # Max profit = (width - net_debit) * 100  (per spread)
                # Max loss = net_debit * 100  (per spread)
                max_profit = (width - net_debit) * 100
                max_loss = net_debit * 100

                # Skip if max profit is not positive
                if max_profit <= 0:
                    continue

                # Calculate expected return
                # Expected return = (probability * max_profit - (1-probability) * max_loss) / max_loss
                # Simplified: use probability based on signal strength and research score
                probability_of_profit = min(0.85, 0.5 + (signal_strength * 0.3) + (research_score * 0.1))

                expected_return = (probability_of_profit * max_profit - (1 - probability_of_profit) * max_loss) / max_loss

                # Only include opportunities with positive expected return
                if expected_return <= 0:
                    continue

                # Create opportunity object
                opportunity = {
                    'symbol': symbol,
                    'strategy_type': 'bull_call_spread',
                    'long_strike': round(long_strike, 2),
                    'short_strike': round(short_strike, 2),
                    'expiration_date': exp_date.strftime('%Y-%m-%d') + 'T00:00:00Z',  # ISO 8601 format
                    'days_to_expiry': days_to_expiry,
                    'net_debit': round(net_debit, 2),
                    'max_profit': round(max_profit, 2),
                    'max_loss': round(max_loss, 2),
                    'expected_return': round(expected_return, 4),
                    'probability_of_profit': round(probability_of_profit, 3),
                    'underlying_price': round(current_price, 2)
                }

                opportunities.append(opportunity)

    return opportunities

def main():
    """Main function to load and print ranked opportunities."""
    try:
        result = load_ranked_opportunities()
        print(json.dumps(result, indent=2))
        return 0
    except Exception as e:
        print(f"Error loading ranked opportunities: {e}", file=sys.stderr)
        # Return empty result on error
        print(json.dumps({"ranked_opportunities": []}, indent=2))
        return 1

if __name__ == "__main__":
    sys.exit(main())