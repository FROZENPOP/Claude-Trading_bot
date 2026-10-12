#!/usr/bin/env python3
"""Test script to generate ranked opportunities using the fixed opportunity generator."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_bot.opportunities.option_generator import OptionOpportunityGenerator
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_market_data(symbol, base_price=None, days=30):
    """Create mock market data for a symbol."""
    if base_price is None:
        base_price = np.random.uniform(50, 150)

    dates = []
    prices = []

    # Generate trending price data
    for i in range(days):
        date = datetime.now() - timedelta(days=days-i-1)
        dates.append(date)

        # Add some trend and noise
        trend = i * 0.1  # Slow upward trend
        noise = np.random.normal(0, base_price * 0.02)  # 2% noise
        price = base_price + trend + noise
        prices.append(max(price, 0.01))  # Ensure positive price

    # Create DataFrame
    df = pd.DataFrame({
        'date': dates,
        'open': [p * np.random.uniform(0.99, 1.01) for p in prices],
        'high': [p * np.random.uniform(1.01, 1.03) for p in prices],
        'low': [p * np.random.uniform(0.97, 0.99) for p in prices],
        'close': prices,
        'volume': [np.random.randint(500000, 5000000) for _ in prices],
        'adjusted_close': prices  # For simplicity, same as close
    })

    return df

def main():
    print("Testing opportunity generation with fixed import...")

    # Create ranked stocks (simulating Phase 3 output)
    ranked_stocks = [
        {'symbol': 'AAPL', 'research_score': 85.0, 'recommendation': 'buy', 'current_price': 175.0, 'signal_strength': 0.8},
        {'symbol': 'MSFT', 'research_score': 82.0, 'recommendation': 'buy', 'current_price': 380.0, 'signal_strength': 0.75},
        {'symbol': 'GOOGL', 'research_score': 78.0, 'recommendation': 'buy', 'current_price': 140.0, 'signal_strength': 0.7},
        {'symbol': 'TSLA', 'research_score': 75.0, 'recommendation': 'buy', 'current_price': 250.0, 'signal_strength': 0.65},
        {'symbol': 'AMZN', 'research_score': 72.0, 'recommendation': 'buy', 'current_price': 145.0, 'signal_strength': 0.6}
    ]

    # Create market data for each stock
    market_data_dict = {}
    for stock in ranked_stocks:
        market_data_dict[stock['symbol']] = create_market_data(
            stock['symbol'],
            base_price=stock['current_price']
        )

    # Initialize the opportunity generator
    generator = OptionOpportunityGenerator(
        min_premium_return=0.05,    # 5% minimum return
        max_days_to_expiry=45,      # Maximum 45 days to expiry
        min_days_to_expiry=7,       # Minimum 7 days to expiry
        min_confidence_score=0.6    # Minimum 60% confidence
    )

    # Generate opportunities
    opportunities = generator.generate_opportunities(ranked_stocks, market_data_dict)

    print(f"Generated {len(opportunities)} raw opportunities")

    # Filter to best opportunities
    filtered_opportunities = generator.filter_opportunities(opportunities, 10)  # Top 10

    print(f"Filtered to {len(filtered_opportunities)} high-quality opportunities")

    # Print the opportunities
    for i, opp in enumerate(filtered_opportunities):
        print(f"\nOpportunity {i+1}:")
        print(f"  Symbol: {opp['symbol']}")
        print(f"  Strategy: {opp['strategy_type']}")
        print(f"  Long Strike: {opp['long_strike']}")
        print(f"  Short Strike: {opp['short_strike']}")
        print(f"  Expiration: {opp['expiration_date']}")
        print(f"  Days to Expiry: {opp['days_to_expiry']}")
        print(f"  Net Debit: ${opp['net_debit']:.2f}")
        print(f"  Max Profit: ${opp['max_profit']:.2f}")
        print(f"  Max Loss: ${opp['max_loss']:.2f}")
        print(f"  Expected Return: {opp['expected_return']:.2%}")
        print(f"  Probability of Profit: {opp['probability_of_profit']:.2%}")
        print(f"  Underlying Price: ${opp['underlying_price']:.2f}")

    # Return the opportunities in the format expected by StructuredOutput
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
            for opp in filtered_opportunities
        ]
    }

    import json
    print("\nJSON output for StructuredOutput:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()