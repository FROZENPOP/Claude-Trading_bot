#!/usr/bin/env python3
"""
Screen stock based on moving average (MA) for research score.
This script gets stock data, calculates MAs, and generates a research score.
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
import sys

def calculate_research_score_from_ma(symbol="AAPL", lookback_days=100):
    """
    Calculate research score based on moving average analysis.

    Args:
        symbol: Stock symbol to analyze
        lookback_days: Number of days of historical data to use

    Returns:
        Dictionary with research score and related metrics
    """
    try:
        # Get stock data using Alpaca MCP tool
        print(f"Fetching {lookback_days} days of data for {symbol}...")
        result = mcp__alpaca__get_stock_bars(
            symbols=symbol,
            timeframe="1Day",
            days=lookback_days
        )

        # Extract the bars data
        bars_data = result['data']['bars'][symbol]

        # Convert to DataFrame
        df = pd.DataFrame(bars_data)

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['t'])
        df = df.set_index('timestamp')

        # Ensure we have the data we need
        if df.empty or len(df) < 20:
            return {
                "symbol": symbol,
                "error": "Insufficient data",
                "research_score": 0.0,
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
        # Long-term: 200-day MA (or as much as we have)
        ma_200 = close_prices.rolling(window=min(200, len(close_prices))).mean()

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
        volatility = close_prices.pct_change().std() * np.sqrt(252) * 100  # Annualized volatility %

        result = {
            "symbol": symbol,
            "research_score": round(float(research_score), 3),
            "current_price": round(float(latest_price), 2),
            "ma_20": round(float(latest_ma_20), 2),
            "ma_50": round(float(latest_ma_50), 2),
            "ma_200": round(float(latest_ma_200), 2),
            "price_vs_ma20_pct": round(float(price_vs_ma20 * 100), 2),
            "price_vs_ma50_pct": round(float(price_vs_ma50 * 100), 2),
            "price_vs_ma200_pct": round(float(price_vs_ma200 * 100), 2),
            "ma20_vs_ma50_pct": round(float(ma20_vs_ma50 * 100), 2),
            "ma50_vs_ma200_pct": round(float(ma50_vs_ma200 * 100), 2),
            "price_change_5d_pct": round(float(price_change_5d * 100), 2),
            "price_change_20d_pct": round(float(price_change_20d * 100), 2),
            "volatility_pct": round(float(volatility), 2),
            "signal_strength": round(float(research_score), 3),  # Using research score as signal strength
            "signal_type": recommendation,
            "data_points": int(len(df)),
            "lookback_days": lookback_days,
            "timestamp": datetime.now().isoformat()
        }

        return result

    except Exception as e:
        print(f"Error processing {symbol}: {str(e)}")
        return {
            "symbol": symbol,
            "error": str(e),
            "research_score": 0.0,
            "recommendation": "error",
            "current_price": 0.0,
            "data_points": 0,
            "timestamp": datetime.now().isoformat()
        }

def main():
    """Main function to run the stock screening."""
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
    else:
        symbol = "AAPL"  # Default symbol

    print(f"Screening {symbol} based on Moving Average analysis...")
    result = calculate_research_score_from_ma(symbol)

    # Print results in a readable format
    print("\n" + "="*50)
    print(f"STOCK MA RESEARCH SCORE FOR {symbol}")
    print("="*50)
    print(f"Research Score: {result['research_score']:.3f}")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Current Price: ${result['current_price']:.2f}")
    print(f"Data Points: {result['data_points']}")
    print("-"*30)
    print("Moving Averages:")
    print(f"  MA20: ${result['ma_20']:.2f}")
    print(f"  MA50: ${result['ma_50']:.2f}")
    print(f"  MA200: ${result['ma_200']:.2f}")
    print("-"*30)
    print("Price vs MAs:")
    print(f"  vs MA20: {result['price_vs_ma20_pct']:+.2f}%")
    print(f"  vs MA50: {result['price_vs_ma50_pct']:+.2f}%")
    print(f"  vs MA200: {result['price_vs_ma200_pct']:+.2f}%")
    print("-"*30)
    print("MA Relationships:")
    print(f"  MA20 vs MA50: {result['ma20_vs_ma50_pct']:+.2f}%")
    print(f"  MA50 vs MA200: {result['ma50_vs_ma200_pct']:+.2f}%")
    print("-"*30)
    print("Momentum:")
    print(f"  5-day change: {result['price_change_5d_pct']:+.2f}%")
    print(f"  20-day change: {result['price_change_20d_pct']:+.2f}%")
    print(f"  Volatility: {result['volatility_pct']:.2f}%")
    print("="*50)

    # Also output as JSON for easy parsing
    print("\nJSON Output:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()