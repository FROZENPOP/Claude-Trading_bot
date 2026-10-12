#!/usr/bin/env python3
"""
Analyze stock data for MA-based research score.
This script processes stock data and calculates a research score based on MA analysis.
"""

import json
import sys
import pandas as pd
import numpy as np
from datetime import datetime

def analyze_stock_ma(data_json, symbol):
    """
    Analyze stock data and calculate MA-based research score.

    Args:
        data_json: JSON string containing stock data from MCP tool
        symbol: Stock symbol being analyzed

    Returns:
        Dictionary with research score and metrics
    """
    try:
        # Parse the JSON data
        data = json.loads(data_json)

        # Extract bars data
        bars_data = data['data']['bars'][symbol]

        # Convert to DataFrame
        df = pd.DataFrame(bars_data)

        # Convert timestamp to datetime and set as index
        df['timestamp'] = pd.to_datetime(df['t'])
        df = df.set_index('timestamp')

        # Sort by date (oldest first)
        df = df.sort_index()

        # Extract close prices
        close_prices = df['c']

        # Check if we have sufficient data
        if len(close_prices) < 20:
            return {
                "symbol": symbol,
                "error": "Insufficient data for MA calculation (need at least 20 days)",
                "research_score": 0.0,
                "recommendation": "error",
                "current_price": 0.0,
                "data_points": len(close_prices),
                "timestamp": datetime.now().isoformat()
            }

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

        result = {
            "symbol": symbol,
            "research_score": round(float(research_score), 3),
            "composite_score": round(float(research_score), 3),  # Using research score as composite
            "signal_strength": round(float(research_score), 3),
            "signal_type": recommendation,
            "recommendation": recommendation,
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
            "data_points": int(len(df)),
            "lookback_days": int(len(df)),
            "timestamp": datetime.now().isoformat()
        }

        return result

    except Exception as e:
        return {
            "symbol": symbol,
            "error": str(e),
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
    """Main function to process command line arguments."""
    if len(sys.argv) < 3:
        print("Usage: python analyze_ma.py '<json_data>' <symbol>")
        sys.exit(1)

    json_data = sys.argv[1]
    symbol = sys.argv[2]

    result = analyze_stock_ma(json_data, symbol)

    # Output as JSON
    print(json.dumps(result))

if __name__ == "__main__":
    main()