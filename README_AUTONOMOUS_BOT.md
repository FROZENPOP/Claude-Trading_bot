# Autonomous Options Trading Bot

This is the main entry point for the Autonomous Options Trading System that automatically starts during premarket/market open and stops/closes when finished for the day.

## Features

- **Market-Hours Aware**: Automatically detects when market is open/closed and adjusts behavior accordingly
- **Phase 11 Integration**: Fully integrates all Phase 11 components:
  - Smart Order Routing (VWAP, TWAP, POV algorithms)
  - Advanced Order Types (Iceberg, Pegged orders)
  - Execution Analysis (slippage measurement, market impact)
  - Adaptive Execution (market condition detection, volatility-based algorithm selection)
  - Execution Monitoring (performance tracking, alerting)
- **Premarket/Postmarket Support**: Recognizes and can trade during PRE_MARKET and POST_MARKET conditions
- **Automatic Start/Stop**: No external scheduler needed - the bot manages its own lifecycle based on market hours
- **Graceful Shutdown**: Handles shutdown signals properly for clean exit

## Usage

### Basic Usage (Paper Trading)
```bash
python run_trading_bot.py
```

### With Custom Symbols
```bash
python run_trading_bot.py --symbols AAPL MSFT GOOGL TSLA
```

### With Custom Check Interval
```bash
python run_trading_bot.py --interval 60  # Check every 60 seconds
```

### Live Trading (Use with Extreme Caution)
```bash
python run_trading_bot.py --live --api-key YOUR_API_KEY --secret-key YOUR_SECRET_KEY
```

### Disabling Specific Components
```bash
python run_trading_bot.py --disable-smart-routing --disable-advanced-orders
```

## How It Works

1. **Market Detection**: The bot checks market status on each loop iteration
2. **Trading Hours**: When market is open (including PRE_MARKET and POST_MARKET), it executes trading cycles
3. **Trading Cycle**: For each symbol, it:
   - Gets current market data
   - Analyzes market conditions using Phase 11 adaptive execution
   - Creates execution plans using the Phase 11 coordinator
   - Executes trades based on the plans
4. **Market Close**: After market closes (16:00 ET), it performs end-of-day tasks:
   - Gets performance summary from Phase 11 components
   - Logs daily statistics
5. **Continuous Operation**: The bot runs continuously, checking market status at the configured interval

## Market Conditions Detected

The bot uses the Phase 11 AdaptiveExecutionEngine to detect:
- `PRE_MARKET`: Before regular market hours
- `OPEN`: Regular market hours (9:30 AM - 4:00 PM ET)
- `POST_MARKET`: After regular market hours
- Other conditions as detected by the adaptive execution engine

## Requirements

- All Phase 11 components must be properly installed and importable
- Alpaca API credentials (for live trading) or paper trading enabled
- Python 3.7+

## Safety Features

- Defaults to paper trading mode
- Comprehensive error handling and logging
- Graceful shutdown on interrupt signals (Ctrl+C)
- Integration with alerting system for error notifications
- Simulation mode for execution (can be modified for live trading)

## Notes

- This bot is designed to run continuously until manually stopped
- For production use, consider running it as a service or using process supervision
- Always test thoroughly in paper trading mode before considering live trading
- The bot makes trading decisions based on the Phase 11 coordinator - in a live system,
  you would want to connect this to actual strategy signals rather than the default 'buy' side