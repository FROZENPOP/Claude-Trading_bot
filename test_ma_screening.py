#!/usr/bin/env python3
"""
Test MA-based stock screening.
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime

def screen_stock_ma(symbol="AAPL", lookback_days=50):
    """
    Screen a stock based on moving average analysis and calculate research score.

    Args:
        symbol: Stock symbol to analyze
        lookback_days: Number of days of historical data to use

    Returns:
        Dictionary with research score and metrics in the requested format
    """
    try:
        # Get stock data using Alpaca MCP tool
        print(f"Fetching {lookback_days} days of data for {symbol}...")
        raw_result = mcp__alpaca__get_stock_bars(
            symbols=symbol,
            timeframe="1Day",
            days=lookback_days
        )

        # Extract the bars data
        bars_data = raw_result['data']['bars'][symbol]

        # Convert to DataFrame
        df = pd.DataFrame(bars_data)

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['t'])
        df = df.set_index('timestamp')

        # Ensure we have the data we need
        if df.empty or len(df) < 20:
            return {
                "symbol": symbol,
                "research_score": 0.0,
                "composite_score": 0.0,
                "signal_strength": 0.0,
                "signal_type": "error",
                "recommendation": "error",
                "current_price": 0.0,
                "data_points": 0,
                "timestamp": datetime.now().isoformat()
            }

        # Sort by date (oldest first)
        df = df.sort_index()

        # Extract close prices
        close_prices = df['c']

        # Calculate moving averages
        # Short-term: 20-day MA
        ma_20 = close_prices.rolling(window=20).mean()
        # Medium-term: 50-day MA
        ma_50 = close_prices.rolling(window=50).mean()
        # Long-term: 200-day MA (use available data if less than 200 days)
        ma_200_window = min(200, len(close_prices))
        ma_200 = close_prices.rolling(window=ma_200_window).mean()

        # Get latest values
        latest_price = close_prices.iloc[-1]
        latest_ma_20 = ma_20.iloc[-1] if not pd.isna(ma_20.iloc[-1]) else latest_price
        latest_ma_50 = ma_50.iloc[-1] if not pd.isna(ma_50.iloc[-1]) else latest_price
        latest_ma_200 = ma_200.iloc[-1] if not pd.isna(ma_200.iloc[-1]) else latest_price

        # Calculate price relative to MAs (as percentages)
        price_vs_ma20 = (latest_price - latest_ma_20) / latest_ma_20 if latest_ma_20 != 0 else 0
        price_vs_ma50 = (latest_price - latest_ma_50) / latest_ma_50 if latest_ma_50 != 0 else 0
        price_vs_ma200 = (latest_price - latest_ma_200) / latest_ma_200 if latest_ma_200 != 0 else 0

        # Calculate MA relationships (trend strength)
        ma20_vs_ma50 = (latest_ma_20 - latest_ma_50) / latest_ma_50 if latest_ma_50 != 0 else 0
        ma50_vs_ma200 = (latest_ma_50 - latest_ma_200) / latest_ma_200 if latest_ma_200 != 0 else 0

        # Calculate momentum (rate of change)
        price_change_5d = (close_prices.iloc[-1] / close_prices.iloc[-6] - 1) if len(close_prices) >= 6 else 0
        price_change_20d = (close_prices.iloc[-1] / close_prices.iloc[-21] - 1) if len(close_prices) >= 21 else 0

        # Generate research score based on MA analysis
        # Score components:
        # 1. Price above MAs (bullish if price > MA)
        # 2. MA alignment (bullish if MA20 > MA50 > MA200)
        # 3. Recent momentum

        # Component 1: Price position relative to MAs (0-1 scale)
        price_score = 0
        if latest_price > latest_ma_20:
            price_score += 0.3
        if latest_price > latest_ma_50:
            price_score += 0.3
        if latest_price > latest_ma_200:
            price_score += 0.4

        # Component 2: MA alignment/trend (0-1 scale)
        trend_score = 0
        if latest_ma_20 > latest_ma_50:
            trend_score += 0.4
        if latest_ma_50 > latest_ma_200:
            trend_score += 0.4
        # Add strength of trend based on separation
        ma_separation = abs(ma20_vs_ma50) + abs(ma50_vs_ma200)
        trend_strength = min(0.2, ma_separation * 10)  # Cap at 0.2
        trend_score += trend_strength

        # Component 3: Momentum (0-1 scale)
        momentum_score = 0
        if price_change_5d > 0:
            momentum_score += 0.3 * min(1, price_change_5d * 10)  # Scale factor
        if price_change_20d > 0:
            momentum_score += 0.4 * min(1, price_change_20d * 5)   # Scale factor
        # Add penalty for negative momentum
        if price_change_5d < 0:
            momentum_score -= 0.2 * min(1, abs(price_change_5d) * 10)
        if price_change_20d < 0:
            momentum_score -= 0.3 * min(1, abs(price_change_20d) * 5)
        momentum_score = max(0, min(1, momentum_score))  # Clamp to 0-1

        # Combine scores (weighted average)
        research_score = (price_score * 0.4) + (trend_score * 0.4) + (momentum_score * 0.2)

        # Ensure score is in 0-1 range
        research_score = max(0, min(1, research_score))

        # Determine recommendation based on score
        if research_score >= 0.8:
            recommendation = "strong_buy"
        elif research_score >= 0.6:
            recommendation = "buy"
        elif research_score >= 0.4:
            recommendation = "hold"
        elif research_score >= 0.2:
            recommendation = "weak_hold"
        else:
            recommendation = "avoid"

        # Calculate additional metrics
        # Volatility (annualized)
        if len(close_prices) > 1:
            returns = close_prices.pct_change().dropna()
            volatility = returns.std() * np.sqrt(252) * 100  # Annualized volatility %
        else:
            volatility = 0.0

        # Return result in the requested format
        result = {
            "symbol": symbol,
            "research_score": round(float(research_score), 3),
            "composite_score": round(float(research_score), 3),
            "signal_strength": round(float(research_score), 3),
            "signal_type": recommendation,
            "recommendation": recommendation,
            "current_price": round(float(latest_price), 2),
            "data_points": int(len(df)),
            "timestamp": datetime.now().isoformat()
        }

        return result

    except Exception as e:
        print(f"Error processing {symbol}: {str(e)}")
        return {
            "symbol": symbol,
            "research_score": 0.0,
            "composite_score": 0.0,
            "signal_strength": 0.0,
            "signal_type": "error",
            "recommendation": "error",
            "current_price": 0.0,
            "data_points": 0,
            "timestamp": datetime.now().isoformat()
        }

def main():
    """Main function to test the MA screening."""
    # Test with a few symbols
    symbols = ["AAPL", "MSFT", "GOOGL"]

    print("Testing MA-based stock screening...")
    print("=" * 50)

    for symbol in symbols:
        print(f"\nAnalyzing {symbol}...")
        result = screen_stock_ma(symbol, lookback_days=50)

        # Print key results
        print(f"  Research Score: {result['research_score']:.3f}")
        print(f"  Recommendation: {result['recommendation']}")
        print(f"  Current Price: ${result['current_price']:.2f}")
        print(f"  Data Points: {result['data_points']}")

        # If we want to see the full JSON output for one symbol
        if symbol == "AAPL":
            print(f"\nFull JSON output for {symbol}:")
            print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()