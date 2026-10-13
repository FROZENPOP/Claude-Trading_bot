# Claude Trading Bot - Autonomous Options Trading System

## Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [Installation & Setup](#installation--setup)
- [Usage](#usage)
- [Configuration](#configuration)
- [Safety Features](#safety-features)
- [Development & Contributing](#development--contributing)
- [Project Status](#project-status)
- [Important Notes](#important-notes)

## Overview

This is an autonomous options trading bot that automatically detects market conditions, generates trading signals, and executes trades based on predefined strategies. The system is designed to run continuously during market hours and handle the complete trading lifecycle from signal generation to execution.

The bot integrates Phase 11 execution components including smart order routing, advanced order types, execution analysis, adaptive execution, and execution monitoring for sophisticated trade execution.

## Key Features

### Core Functionality
- **Market-Hours Aware**: Automatically detects when market is open/closed (including PRE_MARKET and POST_MARKET) and adjusts behavior accordingly
- **Autonomous Operation**: Manages its own lifecycle based on market hours - no external scheduler needed
- **Multi-Strategy Support**: Implements various options strategies including vertical spreads, covered calls, cash-secured puts, iron condors, calendar spreads, straddles, strangles, butterflies, collars, diagonal spreads, and protective puts
- **Phase 11 Integration**: Full integration of advanced execution components:
  - Smart Order Routing (VWAP, TWAP, POV algorithms)
  - Advanced Order Types (Iceberg, Pegged orders)
  - Execution Analysis (slippage measurement, market impact)
  - Adaptive Execution (market condition detection, volatility-based algorithm selection)
  - Execution Monitoring (performance tracking, alerting)

### Data Integration
- Stock data via yfinance (through MCP when available)
- Options data via Webull API (through MCP)
- Real-time market data for liquidity and volatility calculations
- Historical data for backtesting and analysis

### Paper Trading Focus
- Defaults to paper trading mode for safe testing
- Extensive safeguards to prevent unintended trading
- Simulation mode for execution testing

### Comprehensive Analytics
- Includes backtesting, walk-forward analysis, and performance reporting
- Risk management with position sizing and risk limits
- Detailed logging and audit trails
- Alert system for significant events and errors

## System Architecture

The system follows a modular, layered architecture:

```
claude-trading-bot/
├── trading_bot/                 # Main application package
│   ├── data/                    # Data handling (download, validation)
│   │   ├── downloader.py            # yfinance stock data
│   │   ├── options_downloader.py    # Webull options data
│   │   ├── validator.py             # Stock data validation
│   │   └── option_validator.py      # Options data validation
│   ├── strategies/              # Strategy implementations
│   │   ├── trend_following.py       # Main trend strategy
│   │   ├── composite_score.py       # Signal components (MA crossover, momentum, etc.)
│   │   ├── vertical_spread.py       # Bull call/bear put spreads
│   │   ├── covered_call.py          # Covered calls/cash-secured puts
│   │   ├── iron_condor.py           # Iron condor strategy
│   │   ├── calendar_spread.py       # Calendar spread strategy
│   │   ├── straddle.py              # Straddle strategy
│   │   ├── strangle.py              # Strangle strategy
│   │   ├── butterfly.py             # Butterfly strategy
│   │   ├── collar.py                # Collar strategy
│   │   ├── diagonal_spread.py       # Diagonal spread strategy
│   │   ├── protective_put.py        # Protective put strategy
│   │   └── option_pricing.py        # Black-Scholes model & Greeks
│   ├── backtesting/             # Backtesting engine
│   │   ├── engine.py                  # Core backtesting logic
│   │   ├── costs.py                   # Transaction cost modeling
│   │   ├── metrics.py                 # Performance metrics
│   │   └── robustness.py              # Robustness testing
│   ├── portfolio/               # Portfolio & risk management
│   │   ├── sizing.py                  # Position sizing
│   │   └── risk.py                    # Risk management
│   ├── execution/               # Order execution
│   │   ├── webull.py                  # Webull broker integration
│   │   ├── reconciliation.py          # Position reconciliation
│   │   ├── phase11_coordinator.py     # Phase 11 execution coordinator
│   │   ├── phase11_smart_order_routing.py  # Smart order routing (VWAP/TWAP/POV)
│   │   ├── phase11_advanced_order_types.py # Advanced order types (Iceberg/Pegged)
│   │   ├── phase11_execution_analysis.py   # Execution analysis (slippage/impact)
│   │   ├── phase11_execution_monitor.py    # Execution monitoring & alerting
│   │   ├── phase11_adaptive_execution.py   # Adaptive execution (market condition detection)
│   │   └── phase11_coordinator.py          # Main Phase 11 coordinator
│   ├── research/                # Research & analysis
│   │   ├── walk_forward.py          # Walk-forward analysis
│   │   ├── reports.py               # Report generation
│   │   └── experiments.py           # Experimental framework
│   ├── monitoring/              # Monitoring & logging
│   │   ├── logger.py                # Logging configuration
│   │   └── alerts.py                # Alert system
│   ├── opportunities/           # Opportunity generation
│   │   ├── option_generator.py          # Options opportunity generation
│   │   └── phase4_opportunity_generation_workflow.py  # Workflow for opportunity generation
│   ├── ranking/                 # Trade ranking
│   │   ├── trade_ranker.py            # Individual trade ranking
│   │   ├── phase5_individual_trade_ranking_workflow.py  # Workflow for individual trade ranking
│   │   └── phase6_portfolio_risk_management_workflow.py # Workflow for portfolio risk management
│   ├── screening/               # Stock screening
│   │   ├── phase3_stock_screening_workflow.py   # Workflow for stock screening
│   │   └── stock_screener.py          # Enhanced stock screener with options factors
│   └── __init__.py              # Package initializer
├── config/                      # Configuration files
│   ├── config.yaml                  # Main configuration
│   ├── strategy_params.yaml         # Strategy parameters
│   └── __init__.py                  # Package initializer
├── tests/                       # Test suite
│   ├── __init__.py                  # Package initializer
│   ├── unit/                        # Unit tests
│   │   └── __init__.py
│   └── integration/                 # Integration tests
│       └── __init__.py
├── research_outputs/            # Research reports and analysis
│   ├── research_report_AAPL_2026.md
│   ├── options_data_access_report.md
│   ├── options_data_validation_report.md
│   ├── final_options_strategy_research.md
│   └── zero_trade_diagnostic.md
├── run_trading_bot.py           # Main entry point (autonomous trading bot)
├── run_paper_trade.py           # Paper trading execution script
├── run_research.py              # Research execution script
├── requirements.txt             # Python dependencies
├── .gitignore                   # Git ignore rules
├── README.md                    # This file
├── CHANGES_SUMMARY.md           # Summary of recent changes
└── README_AUTONOMOUS_BOT.md     # Specifics about the autonomous bot
```

## Component Details

### Data Layer (`trading_bot/data/`)
- **downloader.py**: Downloads stock data using yfinance
- **options_downloader.py**: Retrieves options data via Webull API through MCP
- **validator.py**: Validates stock data quality and integrity
- **option_validator.py**: Validates options data quality and integrity

### Strategy Layer (`trading_bot/strategies/`)
- **trend_following.py**: Main trend-following strategy using moving average crossovers
- **composite_score.py**: Combines multiple signal components (technical, fundamental, quality, sentiment, volume/liquidity, options)
- **vertical_spread.py**: Implements bull call and bear put spread strategies
- **covered_call.py**: Implements covered call and cash-secured put strategies
- **iron_condor.py**: Implements iron condor options strategy
- **calendar_spread.py**: Implements calendar spread options strategy
- **straddle.py**: Implements straddle options strategy (long and short)
- **strangle.py**: Implements strangle options strategy (long and short)
- **butterfly.py**: Implements butterfly options strategy (long and short)
- **collar.py**: Implements collar options strategy (protective collar)
- **diagonal_spread.py**: Implements diagonal spread options strategy (bullish and bearish)
- **protective_put.py**: Implements protective put strategy (long stock + long put)
- **option_pricing.py**: Black-Scholes model for options pricing and Greeks calculation

### Backtesting Layer (`trading_bot/backtesting/`)
- **engine.py**: Core backtesting engine that simulates trades on historical data
- **costs.py**: Models transaction costs including slippage and commissions
- **metrics.py**: Calculates performance metrics (Sharpe ratio, drawdown, win rate, etc.)
- **robustness.py**: Tests strategy robustness under various market conditions

### Portfolio & Risk Management (`trading_bot/portfolio/`)
- **sizing.py**: Implements position sizing algorithms (fixed fractional, volatility-based, etc.)
- **risk.py**: Manages portfolio-level risk limits and exposure controls

### Execution Layer (`trading_bot/execution/`)
- **webull.py**: Integrates with Webull broker API for paper/live trading
- **reconciliation.py**: Ensures position synchronization between local tracking and broker
- **phase11_coordinator.py**: Main coordinator for all Phase 11 execution components
- **phase11_smart_order_routing.py**: Implements VWAP, TWAP, and POV smart routing algorithms
- **phase11_advanced_order_types.py**: Implements Iceberg and Pegged order types
- **phase11_execution_analysis.py**: Measures slippage and market impact
- **phase11_execution_monitor.py**: Tracks execution performance and generates alerts
- **phase11_adaptive_execution.py**: Detects market conditions and selects optimal execution algorithms

### Research Layer (`trading_bot/research/`)
- **walk_forward.py**: Implements walk-forward analysis for strategy validation
- **reports.py**: Generates comprehensive performance reports
- **experiments.py**: Framework for running strategy experiments

### Monitoring Layer (`trading_bot/monitoring/`)
- **logger.py**: Configures application logging with audit trails
- **alerts.py**: Manages alerting system for significant events and errors

### Opportunity Generation (`trading_bot/opportunities/`)
- **option_generator.py**: Generates specific options opportunities (vertical spreads, etc.) for ranked stocks
- **phase4_opportunity_generation_workflow.py**: Workflow orchestrating opportunity generation

### Ranking (`trading_bot/ranking/`)
- **trade_ranker.py**: Ranks individual trades based on risk-adjusted returns
- **phase5_individual_trade_ranking_workflow.py**: Workflow for individual trade ranking
- **phase6_portfolio_risk_management_workflow.py**: Workflow for portfolio risk management

### Screening (`trading_bot/screening/`)
- **phase3_stock_screening_workflow.py**: Workflow orchestrating stock screening
- **stock_screener.py**: Enhanced multi-factor stock screener with options-specific factors

## Data Flow

The system processes data through the following flow:

1. **Data Acquisition Phase**
   - Stock data collected via yfinance (through `trading_bot.data.downloader`)
   - Options data collected via Webull API (through `trading_bot.data.options_downloader`)
   - Both data sources utilize MCP (Model Context Protocol) when available for efficient data access

2. **Validation Phase**
   - Stock data validated via `trading_bot.data.validator`
   - Options data validated via `trading_bot.data.option_validator`

3. **Signal Generation Phase**
   - Market data processed through strategy components in `trading_bot.strategies`
   - Technical indicators calculated (moving averages, RSI, MACD, etc.)
   - Fundamental and quality factors assessed
   - Sentiment and volume/liquidity factors analyzed
   - **Enhanced**: Options-specific factors now included (Put/Call Ratio, options activity, market depth)
   - Combined into composite signal via `trading_bot.strategies.composite_score`

4. **Opportunity Generation Phase**
   - For options trading, specific opportunities generated via `trading_bot.opportunities.option_generator`
   - Uses contract-metadata-first approach to prevent look-ahead bias
   - Generates vertical spreads, covered calls, and other options strategies

5. **Screening & Ranking Phase**
   - Stocks screened via `trading_bot.screeing.stock_screener` (now enhanced with options factors)
   - Trades ranked via `trading_bot.ranking.trade_ranker`
   - Portfolio risk managed via `trading_bot.portfolio.phase6_portfolio_risk_management_workflow`

6. **Risk Management Phase**
   - Position sizing calculated via `trading_bot.portfolio.sizing`
   - Risk limits validated via `trading_bot.portfolio.risk`
   - Exposure checks performed before trade execution

7. **Execution Phase**
   - Orders prepared via execution modules (`trading_bot.execution.webull`)
   - Advanced execution techniques applied via Phase 11 components:
     - Market condition detection (`phase11_adaptive_execution`)
     - Smart order routing selection (`phase11_smart_order_routing`)
     - Advanced order types (`phase11_advanced_order_types`)
     - Execution analysis (`phase11_execution_analysis`)
     - Performance monitoring (`phase11_execution_monitor`)
   - Orders submitted to broker API
   - Position reconciliation via `trading_bot.execution.reconciliation`

8. **Analysis & Reporting Phase**
   - Performance tracked via monitoring components
   - Reports generated via `trading_bot.research.reports`
   - Walk-forward analysis performed via `trading_bot.research.walk_forward`

## Installation & Setup

### Prerequisites
- Python 3.8+
- Git (for version control)
- Brokerage account (Webull for live trading)

### Installation Steps
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Claude-Trading_bot
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On Unix/macOS:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   - Copy `.env.example` to `.env` (if provided) or create your own
   - Set required API keys and configuration values:
     ```
     # Webull API (for options/stock trading)
     WEBULL_APP_KEY=your_webull_app_key
     WEBULL_APP_SECRET=your_webull_app_secret
     WEBULL_ENVIRONMENT=uat  # or 'live' for production
     WEBULL_REGION_ID=us
     
     # Trading parameters
     SCAN_INTERVAL=30  # seconds between scans
     MAX_POSITIONS=10  # maximum concurrent positions
     POSITION_SIZE_PCT=0.1  # 10% of portfolio per position
     MAX_DAILY_LOSS=0.05  # 5% max daily loss
     ```

### MCP (Model Context Protocol) Setup
The system is designed to work with MCP for efficient data access. To enable MCP tools:
1. Ensure MCP servers are running and accessible
2. The system will automatically detect and use MCP tools when available
3. When MCP tools are not available, the system falls back to traditional API calls
4. MCP availability is gracefully handled throughout the codebase

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

### With Custom Position Size
```bash
python run_trading_bot.py --position-size 0.05  # 5% of portfolio per position
```

### Live Trading (Use with Extreme Caution)
```bash
python run_trading_bot.py --live --api-key YOUR_API_KEY --secret-key YOUR_SECRET_KEY
```

### Disabling Specific Components
```bash
python run_trading_bot.py --disable-smart-routing --disable-advanced-orders
```

### Running Research & Analysis
```bash
python run_research.py
```

### Running Paper Trading Script (Alternative)
```bash
python run_paper_trade.py --symbol AAPL --strategy-config config/strategy.yaml
```

## Configuration

### Main Configuration (`config/config.yaml`)
Controls system-wide settings:
```yaml
# System settings
scan_interval: 30  # seconds between market checks
max_positions: 10
position_size_pct: 0.1  # 10% of portfolio per trade
max_daily_loss: 0.05  # 5% maximum daily loss
max_drawdown: 0.15  # 15% maximum drawdown
max_daily_trades: 10

# Feature flags
enable_smart_routing: true
enable_advanced_orders: true
enable_execution_analysis: true
enable_adaptive_execution: true
enable_execution_monitoring: true

# Market hours settings
respect_market_hours: true
trade_premarket: true
trade_postmarket: false
```

### Strategy Parameters (`config/strategy_params.yaml`)
Controls strategy-specific parameters:
```yaml
# Trend following strategy
trend_following:
  short_window: 20
  medium_window: 50
  long_window: 200
  entry_threshold: 0.5
  exit_threshold: -0.3

# Options strategy parameters
options:
  min_premium_return: 0.05  # 5% minimum return
  max_days_to_expiry: 45
  min_days_to_expiry: 7
  min_confidence_score: 0.6

# Screening parameters
screening:
  technical_weight: 0.25
  fundamental_weight: 0.25
  quality_weight: 0.15
  sentiment_weight: 0.15
  volume_liquidity_weight: 0.10
  options_weight: 0.10  # NEW: Options-specific factors
```

### Environment Variables
Can be used to override configuration files:
- `SCAN_INTERVAL`: Seconds between market scans (default: 30)
- `MAX_POSITIONS`: Maximum concurrent positions (default: 10)
- `POSITION_SIZE_PCT`: Position size as portfolio percentage (default: 0.1)
- `MAX_DAILY_LOSS`: Maximum daily loss percentage (default: 0.05)
- `ENABLE_SMART_ROUTING`: Enable smart order routing (default: true)
- `ENABLE_ADVANCED_ORDERS`: Enable advanced order types (default: true)

## Safety Features

### Default Safe Mode
- **Paper Trading First**: System defaults to paper trading mode using Webull's paper trading environment
- **Explicit Live Trading Required**: Live trading requires explicit `--live` flag and API credentials
- **No Automatic Live Execution**: No path exists for accidental live trading activation

### Risk Management
- **Position Sizing**: Limits individual position size to configurable percentage of portfolio
- **Daily Loss Limits**: Stops trading if daily loss exceeds threshold
- **Drawdown Protection**: Monitors and limits maximum drawdown
- **Trade Frequency Limits**: Caps maximum number of trades per day
- **Exposure Controls**: Limits total portfolio exposure

### Error Handling & Recovery
- **Comprehensive Exception Handling**: Graceful degradation when components fail
- **MCP Fallback**: Automatic fallback to traditional APIs when MCP tools unavailable
- **Validation Checks**: Data validation at multiple points in the pipeline
- **Position Reconciliation**: Regular synchronization with broker positions
- **Health Monitoring**: Component health checks and automatic restart capabilities

### Logging & Monitoring
- **Audit Logging**: Complete audit trail of all trading decisions and executions
- **Alert System**: Configurable alerts for significant events, errors, and risk limit breaches
- **Performance Monitoring**: Real-time tracking of strategy performance and execution quality
- **Debug Mode**: Detailed logging available for troubleshooting

### Graceful Shutdown
- **Signal Handling**: Properly handles SIGINT (Ctrl+C) and SIGTERM for clean shutdown
- **Position Closure**: Can be configured to close positions on shutdown
- **State Persistence**: Saves state to allow resumption after restart
- **Resource Cleanup**: Properly closes connections and releases resources

## Development & Contributing

### Code Structure
Follow the existing modular architecture:
- Each component has a single, well-defined responsibility
- Dependencies are injected rather than hardcoded
- Interfaces are clearly defined between layers
- Error handling follows consistent patterns

### Coding Standards
- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Include docstrings for all public functions and classes
- Add type hints where beneficial
- Write clear, concise comments explaining non-obvious logic

### Testing
- Unit tests located in `tests/unit/`
- Integration tests in `tests/integration/`
- Run tests with: `python -m pytest`
- Aim for high test coverage on critical components
- Mock external dependencies in unit tests

### MCP Integration Patterns
When adding new MCP tool usage:
1. Follow the contract-metadata-first approach to prevent look-ahead bias
2. Implement graceful fallback to traditional APIs when MCP unavailable
3. Use the `_safe_mcp_call` pattern for safe MCP tool invocation
4. Handle potential None returns from MCP calls appropriately
5. Log MCP availability status for debugging

### Adding New Strategies
1. Create new strategy file in `trading_bot/strategies/`
2. Implement required interface (signal calculation methods)
3. Register strategy in appropriate workflows if needed
4. Add unit tests for new strategy functionality
5. Update documentation to reflect new strategy

## Project Status

### Verified Working Components
- ✅ MCP data access detection and fallback mechanisms
- ✅ Signal generation (fixed timezone/datetime comparison issues)
- ✅ Trade execution logic (Webull integration)
- ✅ Research pipeline (walk-forward analysis, reporting)
- ✅ Report generation (comprehensive performance reports)
- ✅ Enhanced stock screening with options-specific factors
- ✅ Opportunity generation for options strategies
- ✅ Position reconciliation and risk management
- ✅ Phase 11 execution component integration
- ✅ Error handling and logging systems
- ✅ All options strategies: vertical spreads, covered calls, cash-secured puts, iron condors, calendar spreads, straddles, strangles, butterflies, collars, diagonal spreads, protective puts

### Recent Enhancements (Based on Research Subagent Findings)
- **Implemented additional options strategies**: Added straddle, strangle, butterfly, collar, diagonal spread, and protective put strategies with complete signal generation, position sizing, and exit logic
- **Enhanced backtesting capabilities**: Improved walk-forward analysis to properly test and compare multiple options strategies through dynamic strategy loading
- **Fixed critical bugs**: Resolved numerous issues in exit methods, parameter passing, and data handling across all strategy modules
- **Migrated to Webull exclusively**: Removed all remaining Alpaca references and migrated to Webull MCP tools throughout the codebase
- **Improved error handling and logging**: Replaced print statements with proper logging calls in multiple modules
- **Fixed TypeError in enhanced_robustness.py**: Resolved format string errors and missing module issues
- **Options-Specific Stock Screening**: Added Put/Call Ratio, options activity, and market depth analysis to stock screener
- **Enhanced Factor Weights**: Updated multi-factor model to include 10% weighting for options-specific factors
- **Contract-Metadata-First Approach**: All new MCP usage follows research-grade methodology to prevent look-ahead bias

### Known Limitations
- **MCP Dependency**: Optimal performance requires MCP servers to be running
- **Broker Specific**: Currently optimized for Webull broker
- **Market Hours Logic**: May require adjustment for international markets
- **Strategy Parameters**: Default parameters may need tuning for specific market conditions
- **Live Trading Caution**: Live trading should only be attempted after extensive paper trading validation

## Important Notes

### Intended Use
This system is designed for:
- Research and development of automated trading strategies
- Paper trading and strategy validation
- Educational purposes for learning algorithmic trading
- Potential live trading (only after extensive validation and with proper risk management)

### Risk Disclosure
Options trading involves significant risk and is not suitable for all investors. Past performance is not indicative of future results. The system's creators are not liable for any trading losses.

### Regulatory Compliance
Users are responsible for ensuring their use of this system complies with all applicable laws and regulations in their jurisdiction, including:
- Securities trading regulations
- Tax reporting requirements
- Brokerage account agreements
- Exchange rules and policies

### Data Sources
- Stock data provided by yfinance (subject to their terms of service)
- Options data provided by Webull API (subject to their terms of service)
- Users must comply with all data provider terms of use

### Execution Responsibility
- The system provides tools for automated trading but does not guarantee profits
- Users retain full responsibility for all trading decisions and outcomes
- Manual oversight is recommended, especially during initial deployment
- Regular review of trading activity and performance is essential

### Continuous Improvement
This is an evolving system. Users are encouraged to:
- Contribute improvements back to the community
- Share research findings and strategy enhancements
- Report bugs and issues for community benefit
- Stay updated with latest developments in algorithmic trading

## Getting Help

For questions and support:
1. Review the documentation in this README and related files
2. Examine the source code and comments for implementation details
3. Look at the research outputs in the `research_outputs/` directory
4. Check the commit history for recent changes and improvements
5. Consider reaching out to the developer community for specific questions

---
*Last Updated: 2026-10-12*
*Version: 1.2.0 (Enhanced with multiple options strategies and bug fixes)*