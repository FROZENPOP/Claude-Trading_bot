# Graph Report - Claude-Trading_bot  (2026-10-12)

## Corpus Check
- 239 files · ~305,514 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: .log 6, (none) 2, .lock 1)

## Summary
- 3136 nodes · 5970 edges · 169 communities (97 shown, 72 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 430 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `72587018`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- os
- test_phase11_integration.py
- datetime
- enhanced_robustness_fixed.py
- stock_screener.py
- TransactionCostModel
- OptionsDataPipeline
- sys
- OptionsDataDownloader
- EventDrivenBacktest
- run_paper_trade.py
- ExecutionMonitor
- run_options_paper_trade.py
- pandas
- StockDiscovery
- ExecutionMonitor
- OptionOpportunityGenerator
- SignalGenerator
- vertical_spread.py
- PerformanceMetrics
- OptionsTradingScheduler
- VerticalSpreadStrategy
- paper_trading_monitor.py
- ExecutionQualityAnalyzer
- ResearchReportGenerator
- research_options_strategies.py
- RiskOptimizer
- Phase11Coordinator
- ProtectivePutStrategy
- PerformanceAnalytics
- CoveredCallStrategy
- robustness.py
- test_migration.py
- DiagonalSpreadStrategy
- DataValidator
- sizing.py
- OptionPricingModel
- demo_hybrid_data_approach.py
- .analyze_execution
- AlertManager
- OptionsPaperTradingEngine
- IronCondorStrategy
- DETAILED FINDINGS
- test_phase8_monitor.py
- EnhancedWalkForwardAnalyzer
- CalendarSpreadStrategy
- Phase 10: Risk Management and Optimization
- AutonomousTradingBot
- What's Working Correctly
- PaperTradingEngine
- TestRiskOptimizer
- AuditLogger
- IndividualTradeRanker
- engine.py
- Phase 9: Performance Analytics and Reporting
- mcp_tools_fixed.py
- Phase 8: Execution Monitoring and Position Tracking
- ._generate_bear_put_signals
- Complete Guide to Using RTK - Rust Token Killer
- .submit_pegged_order
- WalkForwardAnalyzer
- Development Sequence Completion Status
- Phase 4: Option Opportunity Generation - Framework Complete
- Phase 5: Individual Trade Ranking - Framework Complete
- Accomplishments
- debug_strategy.py
- Phase 2: Stock Discovery Layer - Completed
- OrderFactory
- PositionTracker
- Expanded Stock List for Screening
- RiskManager
- RiskChecker
- Options Trading Bot - Architecture Summary
- Completed Work
- DataDownloader
- AdaptiveExecutionEngine
- Implementation Fixes Summary
- Autonomous Options Trading Bot
- test_mcp_data_pipeline.py
- OptionPosition
- MCP Data Access Verification for Options Trading Research
- mcp_tools_interface.py
- Webull Migration Summary
- pipeline_test.py
- .execute_approved_trades
- Current Status - Autonomous Options Trading System
- main
- load_ranked_opportunities.js
- mcp_wrapper.py
- Phase 3: Stock Screening and Ranking - Framework Complete
- Phase 7 Alpaca Execution - Final Summary
- Next Steps for Autonomous Trading System Development
- Claude Trading Bot - Autonomous Options Trading System
- Component Details
- .assess_market_conditions
- .submit_order
- Webull Paper Trading Integration - COMPLETE
- Webull Paper Trading Integration Summary
- diagnostic_backtest.py
- Options Paper Trading System - Ready for Execution
- Phase 3: Stock Screening and Ranking - Execution Complete
- simple_diagnostic.py
- test_options_pipeline.py
- test_phase10_risk_optimizer.py
- .execute_adaptively
- .calculate_butterfly_pnl
- PIPELINE DIAGNOSIS: VERTICAL SPREAD STRATEGY ZERO TRADES ISSUE
- simple_opportunity_loader.py
- Usage
- test_webull_credentials.py
- MarketConditions
- .generate_collar_signals
- Development & Contributing
- SensitivityAnalysis
- Position
- enhanced_walk_forward_analysis
- ExecutionAnalyzer
- PortfolioGreeks
- .calculate_straddle_pnl
- .calculate_strangle_pnl
- Continuous Improvement Log
- Historical Options Data Validation Audit
- ✅ Integration Status: FULLY OPERATIONAL
- .verify_buying_power
- Phase 4 Framework Implementation Complete
- Phase 5 Framework Implementation Complete
- PIPELINE VERIFICATION: VERTICAL SPREAD STRATEGY FIX
- Important Notes
- AdaptiveExecutionManager
- demo_phase8_monitoring.py
- PIPELINE STAGE ANALYSIS
- Accomplishments
- Safety Features
- test_small_position_execution.py
- RiskLimits
- CashSecuredPutPosition
- demo_basic_monitoring
- Key Features
- Key Features
- _resolve_env_vars
- Components Created
- Integration Points
- Installation & Setup
- Project Status

## God Nodes (most connected - your core abstractions)
1. `SignalGenerator` - 91 edges
2. `VerticalSpreadStrategy` - 89 edges
3. `OptionsDataPipeline` - 57 edges
4. `EventDrivenBacktest` - 50 edges
5. `ExecutionMonitor` - 49 edges
6. `OptionPricingModel` - 47 edges
7. `TrendFollowingStrategy` - 47 edges
8. `WebullExecution` - 39 edges
9. `PerformanceMetrics` - 38 edges
10. `TransactionCostModel` - 37 edges

## Surprising Connections (you probably didn't know these)
- `Process:` --references--> `DataDownloader`  [INFERRED]
  PHASE3_STOCK_SCREENING_SUMMARY.md → trading_bot/data/downloader.py
- `1. Stock Screening Module (`trading_bot/screening/stock_screener.py`)` --references--> `CompositeTrendScore`  [INFERRED]
  PHASE3_STOCK_SCREENING_SUMMARY.md → trading_bot/strategies/composite_score.py
- `1. Option Opportunity Generation Module (`trading_bot/opportunities/option_generator.py`)` --references--> `VerticalSpreadStrategy`  [INFERRED]
  PHASE4_OPPORTUNITY_GENERATION_FRAMEWORK.md → trading_bot/strategies/vertical_spread.py
- `1. Individual Trade Ranker Module (`trading_bot/ranking/trade_ranker.py`)` --references--> `VerticalSpreadStrategy`  [INFERRED]
  PHASE5_INDIVIDUAL_TRADE_RANKING_FRAMEWORK.md → trading_bot/strategies/vertical_spread.py
- `Verification` --references--> `OptionsDataDownloader`  [INFERRED]
  MIGRATION_SUMMARY.md → trading_bot/data/options_downloader.py

## Import Cycles
- None detected.

## Communities (169 total, 72 thin omitted)

### Community 0 - "os"
Cohesion: 0.03
Nodes (12): check_account_powers(), debug_quote(), demo_long_only_strategy(), test_buying_power(), test_buying_power_success(), create_order_request(), Order, OrderRequest (+4 more)

### Community 1 - "test_phase11_integration.py"
Cohesion: 0.04
Nodes (23): create_adaptive_execution_engine(), MarketCondition, submit_order(), AdvancedOrderManager, AdvancedOrderParameters, AdvancedOrderType, create_advanced_order_manager(), OrderInstruction (+15 more)

### Community 2 - "datetime"
Cohesion: 0.05
Nodes (5): demo_factory_function(), MockExecutionMonitor, MockExecutionMonitor, calculate_time_to_expiration(), parse_option_symbol()

### Community 3 - "enhanced_robustness_fixed.py"
Cohesion: 0.05
Nodes (16): create_sample_data(), test_enhanced_walk_forward_analyzer(), create_sample_data(), main(), test_enhanced_walk_forward_analyzer(), test_enhanced_walk_forward_function(), trend_following_factory(), EnhancedWalkForwardAnalyzer (+8 more)

### Community 4 - "stock_screener.py"
Cohesion: 0.05
Nodes (7): Added Features:, convert_alpaca_bars_to_dataframe(), get_top_stocks(), MultiFactorModel, save_screening_results(), screen_stocks_batch(), StockResearchScore

### Community 5 - "TransactionCostModel"
Cohesion: 0.06
Nodes (13): get_strategy_class(), load_config(), main(), run_single_backtest(), load_strategy_config(), load_config(), run_research_pipeline(), TransactionCostModel (+5 more)

### Community 6 - "OptionsDataPipeline"
Cohesion: 0.06
Nodes (13): audit_diagnostic_trades(), main(), debug_bear_put_internal(), debug_detailed(), debug_pipeline_data(), main(), test_multiple_dates(), test_with_actual_strikes() (+5 more)

### Community 7 - "sys"
Cohesion: 0.05
Nodes (17): analyze_stock_ma(), main(), main(), test_account_access(), test_authentication(), test_feed_types(), test_options_access(), get_option_chain() (+9 more)

### Community 8 - "OptionsDataDownloader"
Cohesion: 0.07
Nodes (10): main(), test_data_availability(), test_data_characteristics(), test_execution_modeling(), test_for_biases(), test_greeks_and_iv_consistency(), OptionsDataValidator, validate_option_data() (+2 more)

### Community 9 - "EventDrivenBacktest"
Cohesion: 0.07
Nodes (7): test_basic_backtest(), EventDrivenBacktest, Trade, OptionsStrategyResult, ParameterSensitivity, run_parameter_sweep(), StrategyResult

### Community 10 - "run_paper_trade.py"
Cohesion: 0.06
Nodes (10): generate_reconciliation_entry(), PositionReconciler, ReconciliationReport, validate_position_sync(), get_alert_manager(), log_alert(), log_risk_violation(), get_audit_logger() (+2 more)

### Community 11 - "ExecutionMonitor"
Cohesion: 0.06
Nodes (5): AlgorithmPerformance, demo_alert(), ExecutionAlert, ExecutionMonitor, ExecutionRecord

### Community 12 - "run_options_paper_trade.py"
Cohesion: 0.06
Nodes (10): Verification, load_combined_workflow_output(), main(), Phase7WebullExecutor, create_order_request(), OrderRequest, WebullAccountInfo, WebullExecution (+2 more)

### Community 13 - "pandas"
Cohesion: 0.08
Nodes (16): debug_option_chain(), debug_signal_generation(), main(), debug_spread_generation(), main(), mcp__alpaca__get_stock_bars(), calculate_research_score_from_ma(), main() (+8 more)

### Community 14 - "StockDiscovery"
Cohesion: 0.06
Nodes (5): main(), discover_stocks_for_trading(), StockDiscovery, create_default_universe_config(), StockUniverse

### Community 15 - "ExecutionMonitor"
Cohesion: 0.06
Nodes (8): demo_performance_analytics(), main(), test_factory_function(), test_performance_analytics_creation(), test_strategy_performance(), test_trade_addition(), ExecutionMonitor, create_performance_analytics()

### Community 16 - "OptionOpportunityGenerator"
Cohesion: 0.07
Nodes (20): 1. Signal Generation Opportunity Generator Fix, 2. Webull Execution Module Bugs, Beneficial Enhancements Implemented, Benefits of Implementation, Claude Trading Bot - Changes Summary, Enhanced Stock Screening with Options-Specific Factors, Files Modified, Files Verified as Fixed (by Agents) (+12 more)

### Community 17 - "SignalGenerator"
Cohesion: 0.09
Nodes (5): main(), test_irregular_strike_spacing(), generate_signal(), Signal, SignalGenerator

### Community 18 - "vertical_spread.py"
Cohesion: 0.08
Nodes (12): check_method_source(), get_bull_call_source(), main(), get_underlying_price_source(), main(), test_get_underlying_price(), debug_bear_put_signals(), get_bear_put_source() (+4 more)

### Community 20 - "OptionsTradingScheduler"
Cohesion: 0.06
Nodes (10): create_default_scheduler(), demonstrate_scheduler(), end_of_day_reconciliation_task(), execution_task(), market_data_update_task(), OptionsTradingScheduler, risk_monitoring_task(), ScheduledTask (+2 more)

### Community 21 - "VerticalSpreadStrategy"
Cohesion: 0.07
Nodes (12): check_attributes(), check_strategy_attributes(), main(), test_bearish_signal_handling(), make_vertical_spread_strategy(), create_sample_stock_data(), test_options_data_access_summary(), test_walk_forward_analysis() (+4 more)

### Community 22 - "paper_trading_monitor.py"
Cohesion: 0.08
Nodes (6): create_monitor(), demonstrate_monitor(), PaperTradingMonitor, PerformanceMetric, PerformanceSnapshot, TradeRecord

### Community 23 - "ExecutionQualityAnalyzer"
Cohesion: 0.07
Nodes (5): create_execution_quality_analyzer(), ExecutionQualityAnalyzer, ExecutionResult, ExecutionSlice, VWAPCalculator

### Community 25 - "research_options_strategies.py"
Cohesion: 0.10
Nodes (10): demonstrate_prefetch_approach(), main(), OptionsBacktester, run_research(), run_robustness_testing(), run_smoke_test(), SignalGenerator, validate_strategy_edge() (+2 more)

### Community 28 - "ProtectivePutStrategy"
Cohesion: 0.11
Nodes (6): create_sample_data(), test_protective_put_strategy(), create_sample_data(), test_protective_put_strategy(), ProtectivePutPosition, ProtectivePutStrategy

### Community 30 - "CoveredCallStrategy"
Cohesion: 0.13
Nodes (4): BaseOptionStrategy, CashSecuredPutStrategy, CoveredCallPosition, CoveredCallStrategy

### Community 31 - "robustness.py"
Cohesion: 0.09
Nodes (5): main(), test_options_robustness(), run_options_parameter_sweep(), WhitesRealityCheck, StrategyPerformance

### Community 32 - "test_migration.py"
Cohesion: 0.08
Nodes (6): main(), test_exit_signal_creation(), test_imports(), test_position_info_creation(), test_webull_executor_import(), PositionInfo

### Community 34 - "DataValidator"
Cohesion: 0.10
Nodes (3): DataValidator, validate_data(), validate_multiple_symbols()

### Community 35 - "sizing.py"
Cohesion: 0.08
Nodes (4): calculate_position_for_risk(), ConstrainedSizing, PositionSizer, VolatilitySizing

### Community 36 - "OptionPricingModel"
Cohesion: 0.09
Nodes (4): black_scholes_call(), black_scholes_put(), calculate_greeks(), OptionPricingModel

### Community 37 - "demo_hybrid_data_approach.py"
Cohesion: 0.09
Nodes (12): demonstrate_contract_metadata_first_approach(), demonstrate_mcp_options_data(), demonstrate_yfinance_stock_data(), demonstrate_contract_metadata_first_approach(), demonstrate_mcp_options_data(), demonstrate_yfinance_stock_data(), main(), main() (+4 more)

### Community 38 - ".analyze_execution"
Cohesion: 0.09
Nodes (4): create_vwap_benchmark_calculator(), ExecutionMetrics, SlippageAnalysis, VWAPBenchmarkCalculator

### Community 40 - "OptionsPaperTradingEngine"
Cohesion: 0.12
Nodes (3): OptionsPaperTradingEngine, run_options_paper_trading(), SpreadSignal

### Community 42 - "DETAILED FINDINGS"
Cohesion: 0.10
Nodes (22): 10. Existing Diagnostic Behavior ✅ (Expected Failure), 11. OptionsDataPipeline Integration ✅, 1. Alpaca MCP Connectivity ✅, 2. Account Options Information ✅, 3. AAPL Option Contract Discovery ✅, 4. AAPL Option Chain Access ✅, 5. Option Quotes/Snapshots ✅, 6. Greeks and Implied Volatility ✅ (+14 more)

### Community 43 - "test_phase8_monitor.py"
Cohesion: 0.10
Nodes (8): main(), test_execution_monitor_creation(), test_exit_conditions(), test_exit_signal_creation(), test_position_info_creation(), test_position_management(), test_position_summary(), ExitSignal

### Community 44 - "EnhancedWalkForwardAnalyzer"
Cohesion: 0.10
Nodes (3): EnhancedWalkForwardAnalyzer, EnhancedWalkForwardResult, run_enhanced_walk_forward()

### Community 46 - "Phase 10: Risk Management and Optimization"
Cohesion: 0.08
Nodes (23): 1. `trading_bot/monitoring/risk_optimizer.py`, 2. `test_phase10_risk_optimizer.py`, 3. `demo_phase10_risk_optimizer.py`, Basic Setup, Components Created, Conclusion, Dynamic Position Sizing, Dynamic Position Sizing (+15 more)

### Community 48 - "What's Working Correctly"
Cohesion: 0.09
Nodes (22): 1. Market and Account Verification, 1. Option Selling Restriction, 2. Order Processing Pipeline, 2. Specific Contract Issues, 3. Quote and Price Handling, 4. Risk Management, 5. Error Handling and Reporting, 6. Workflow Integration (+14 more)

### Community 53 - "engine.py"
Cohesion: 0.10
Nodes (5): create_sample_data(), test_basic_backtest(), create_sample_data(), PortfolioState, PositionState

### Community 54 - "Phase 9: Performance Analytics and Reporting"
Cohesion: 0.10
Nodes (20): 1. `trading_bot/monitoring/analytics.py`, 2. `test_phase9_analytics.py`, 3. `demo_phase9_analytics.py`, Adding Completed Trades, Basic Setup, Components Created, Conclusion, Files Created for Reference (+12 more)

### Community 55 - "mcp_tools_fixed.py"
Cohesion: 0.10
Nodes (9): mcp__webull__get_account_info(), mcp__webull__get_option_bars(), mcp__webull__get_option_contracts(), mcp__webull__get_option_trades(), mcp__webull__get_stock_bars(), _transform_option_bars_data(), _transform_option_contracts_data(), _transform_option_trades_data() (+1 more)

### Community 56 - "Phase 8: Execution Monitoring and Position Tracking"
Cohesion: 0.11
Nodes (18): 1. `trading_bot/execution/phase8_execution_monitoring.py`, 2. `test_phase8_monitor.py`, 3. `demo_phase8_monitoring.py`, Adding Positions, Alert System, Basic Setup, Components Created, Exit Signals (+10 more)

### Community 58 - "Complete Guide to Using RTK - Rust Token Killer"
Cohesion: 0.11
Nodes (18): 1. `rtk gain`, 2. `rtk gain --history`, 3. `rtk discover`, 4. `rtk proxy <cmd>`, Benefits, Best Practices, Complete Guide to Using RTK - Rust Token Killer, Conclusion (+10 more)

### Community 59 - ".submit_pegged_order"
Cohesion: 0.11
Nodes (3): AdvancedOrderResult, IcebergOrder, PeggedOrder

### Community 60 - "WalkForwardAnalyzer"
Cohesion: 0.13
Nodes (3): run_walk_forward(), WalkForwardAnalyzer, WalkForwardResult

### Community 61 - "Development Sequence Completion Status"
Cohesion: 0.11
Nodes (17): Current System Status, Development Sequence Completion Status, Key Technical Accomplishments, Next Steps, Options-Specific Infrastructure, Options Trading Research System - Implementation Complete, Overview, Real Data Enforcement (+9 more)

### Community 62 - "Phase 4: Option Opportunity Generation - Framework Complete"
Cohesion: 0.11
Nodes (17): 1. Option Opportunity Generation Module (`trading_bot/opportunities/option_generator.py`), 2. Phase 4 Workflow Framework (`trading_bot/opportunities/phase4_opportunity_generation_workflow.py`), 3. Configuration File (`config/opportunity_generation.yaml`), Components Created, Current Status, Files Created/Modified, Input (from Phase 3):, Integration Points (+9 more)

### Community 63 - "Phase 5: Individual Trade Ranking - Framework Complete"
Cohesion: 0.11
Nodes (17): 1. Individual Trade Ranker Module (`trading_bot/ranking/trade_ranker.py`), 2. Phase 5 Workflow Framework (`trading_bot/ranking/phase5_individual_trade_ranking_workflow.py`), 3. Configuration File (`config/individual_trade_ranking.yaml`), Components Created, Current Status, Files Created/Modified, Input (from Phase 4):, Integration Points (+9 more)

### Community 64 - "Accomplishments"
Cohesion: 0.12
Nodes (16): 10. ✅ Verified End-to-End Functionality, 1. ✅ Paper Trading Only (UAT Environment), 2. ✅ Credential Verification & Security, 3. ✅ Risk Controls Preservation, 4. ✅ Sandbox Verification, 5. ✅ Actual Implementation with Subagents, 6. ✅ .env File Editing, 7. ✅ Strategy Revision for All Webull Option Types (+8 more)

### Community 66 - "Phase 2: Stock Discovery Layer - Completed"
Cohesion: 0.12
Nodes (16): 1. Stock Discovery Module (`trading_bot/discovery/stock_discovery.py`), 2. Stock Universe Module (`trading_bot/discovery/stock_universe.py`), 3. Configuration Files, 4. Demonstration Script (`demo_stock_discovery.py`), Components Created, Configuration Example, Current Implementation, Files Modified/Created (+8 more)

### Community 69 - "Expanded Stock List for Screening"
Cohesion: 0.12
Nodes (15): Expanded Stock List for Screening, Large Cap Consumer Cyclical, Large Cap Consumer Defensive, Large Cap Energy, Large Cap Financial, Large Cap Healthcare, Large Cap Industrial, Large Cap Materials (+7 more)

### Community 72 - "Options Trading Bot - Architecture Summary"
Cohesion: 0.13
Nodes (14): 1. Fixed Timezone/DateTime Comparison Issues, 2. Verified MCP Data Access Pipeline, 3. Successfully Generated Research Report, 4. Root Cause Analysis for Zero Trades, Architecture Summary, Core Modules, Data Flow, Files Cleaned Up (+6 more)

### Community 73 - "Completed Work"
Cohesion: 0.13
Nodes (14): 1. Options Data Pipeline, 2. Options Pricing and Greeks, 3. Core Options Strategies, 4. Signal Generation, 5. Options-Specific Risk Management, 6. Robustness Testing, Completed Work, Development Progress (+6 more)

### Community 74 - "DataDownloader"
Cohesion: 0.20
Nodes (3): DataDownloader, download_data(), download_single_symbol()

### Community 76 - "Implementation Fixes Summary"
Cohesion: 0.14
Nodes (13): 1. Validation Results Variable Not Initialized (Lines 1002-1003), 2. DateTime/Timedelta Namespace Issues (Multiple Locations), A. Added timedelta to imports (Line 10):, B. Replaced datetime.timedelta with timedelta:, C. Replaced datetime.datetime with dt.datetime:, DateTime Fixes Verification:, Files Modified, Implementation Fixes Summary (+5 more)

### Community 77 - "Autonomous Options Trading Bot"
Cohesion: 0.14
Nodes (13): Autonomous Options Trading Bot, Basic Usage (Paper Trading), Disabling Specific Components, Features, How It Works, Live Trading (Use with Extreme Caution), Market Conditions Detected, Notes (+5 more)

### Community 78 - "test_mcp_data_pipeline.py"
Cohesion: 0.20
Nodes (6): demonstrate_historical_option_data_access(), demonstrate_option_chain_construction(), demonstrate_option_contracts_access(), demonstrate_stock_data_access(), main(), show_expected_dataframe_structure()

### Community 80 - "MCP Data Access Verification for Options Trading Research"
Cohesion: 0.15
Nodes (12): 1. Historical Stock Data (yfinance), 2. Options Contract Data (MCP), 3. Historical Options Bar Data (MCP), 4. Historical Options Trades Data (MCP), Data Access Confirmed, Implications for Options Research Pipeline, Key Findings, MCP Data Access Verification for Options Trading Research (+4 more)

### Community 81 - "mcp_tools_interface.py"
Cohesion: 0.15
Nodes (5): mcp__webull__get_account_info(), mcp__webull__get_option_bars(), mcp__webull__get_option_contracts(), mcp__webull__get_option_trades(), mcp__webull__get_stock_bars()

### Community 82 - "Webull Migration Summary"
Cohesion: 0.15
Nodes (12): 1. Trading Bot Data Module, 2. Trading Bot Execution Module, 3. Phase 7 Execution Workflow, Clean Repository, Files Modified, Key Improvements, Notes, Overview (+4 more)

### Community 83 - "pipeline_test.py"
Cohesion: 0.18
Nodes (4): create_trending_data(), main(), test_full_pipeline(), run_diagnostic_backtest()

### Community 85 - "Current Status - Autonomous Options Trading System"
Cohesion: 0.17
Nodes (11): Configuration Examples, Current Status - Autonomous Options Trading System, Environment Notes, Immediate Next Steps, Key Files Created/Modified, Overall Progress, Phase 1: Options Trading Foundation - COMPLETE, Phase 2: Stock Discovery Layer - COMPLETE (+3 more)

### Community 87 - "load_ranked_opportunities.js"
Cohesion: 0.17
Nodes (6): fs, marketDataDict, path, rankedStocks, topStocksFromSummary, { spawn }

### Community 88 - "mcp_wrapper.py"
Cohesion: 0.17
Nodes (5): mcp__webull__get_account_info(), mcp__webull__get_option_bars(), mcp__webull__get_option_contracts(), mcp__webull__get_option_trades(), mcp__webull__get_stock_bars()

### Community 89 - "Phase 3: Stock Screening and Ranking - Framework Complete"
Cohesion: 0.17
Nodes (11): Component Testing:, Current Status, Files Created/Modified, Next Phase Ready For, Overview, Phase 3: Stock Screening and Ranking - Framework Complete, Ready for Implementation:, Technical Notes (+3 more)

### Community 90 - "Phase 7 Alpaca Execution - Final Summary"
Cohesion: 0.18
Nodes (10): Alpaca Options Levels Context, Conclusion, Critical Finding ⚠️, Development Progress Summary, Empirical Validation, Files Created, Key Accomplishments ✅, Overview (+2 more)

### Community 91 - "Next Steps for Autonomous Trading System Development"
Cohesion: 0.18
Nodes (10): Alternative Approach: Adapt Strategies for Long-Only Execution, Current Status Summary, Files Created for Reference, Immediate Next Step: Develop Phase 11 (Advanced Execution and Smart Order Routing), Long-Term Resolution Paths, Next Steps for Autonomous Trading System Development, Recommendation, Recommended Development Path Forward (+2 more)

### Community 92 - "Claude Trading Bot - Autonomous Options Trading System"
Cohesion: 0.18
Nodes (10): Claude Trading Bot - Autonomous Options Trading System, Configuration, Data Flow, Environment Variables, Getting Help, Main Configuration (`config/config.yaml`), Overview, Strategy Parameters (`config/strategy_params.yaml`) (+2 more)

### Community 93 - "Component Details"
Cohesion: 0.18
Nodes (11): Backtesting Layer (`trading_bot/backtesting/`), Component Details, Data Layer (`trading_bot/data/`), Execution Layer (`trading_bot/execution/`), Monitoring Layer (`trading_bot/monitoring/`), Opportunity Generation (`trading_bot/opportunities/`), Portfolio & Risk Management (`trading_bot/portfolio/`), Ranking (`trading_bot/ranking/`) (+3 more)

### Community 96 - "Webull Paper Trading Integration - COMPLETE"
Cohesion: 0.18
Nodes (10): 📁 Files Modified/Created, ✅ Integration Successfully Completed, 🔧 Key Features Implemented, MCP Integration, 🚀 Next Steps for Live Deployment, Security & Compliance, 🧪 Testing Verification, Verification & Risk Management (+2 more)

### Community 97 - "Webull Paper Trading Integration Summary"
Cohesion: 0.18
Nodes (10): 2. Updated Main Entry Point (`run_trading_bot.py`), 3. Environment Configuration (`.env`), Changes Made, Files Modified, Files Unchanged, Next Steps for Live Deployment, Overview, Testing Results (+2 more)

### Community 99 - "Options Paper Trading System - Ready for Execution"
Cohesion: 0.20
Nodes (9): Conclusion, Current Status, ⚠️ Environmental Issue, Files Created/Modified, Next Steps for User, Options Paper Trading System - Ready for Execution, Overview, Safety Features (+1 more)

### Community 100 - "Phase 3: Stock Screening and Ranking - Execution Complete"
Cohesion: 0.20
Nodes (9): Execution Summary, Files Created/Utilized, Next Immediate Steps, Phase 3: Stock Screening and Ranking - Execution Complete, Ready for Phase 4, Results Summary, Technical Success, Top 10 Ranked Stocks (+1 more)

### Community 101 - "simple_diagnostic.py"
Cohesion: 0.27
Nodes (4): main(), test_option_chain_and_spread_generation(), test_price_data_semantics(), test_signal_generation()

### Community 102 - "test_options_pipeline.py"
Cohesion: 0.20
Nodes (4): test_historical_data_logic(), test_mcp_option_bars(), test_mcp_option_contracts(), test_mcp_stock_data()

### Community 106 - "PIPELINE DIAGNOSIS: VERTICAL SPREAD STRATEGY ZERO TRADES ISSUE"
Cohesion: 0.22
Nodes (8): CONCLUSION, EXECUTIVE SUMMARY, Files Examined:, Methods with Issues:, PIPELINE DIAGNOSIS: VERTICAL SPREAD STRATEGY ZERO TRADES ISSUE, RECOMMENDED NEXT STEPS (PER USER INSTRUCTIONS), Specific Problematic Code Pattern:, TECHNICAL DETAILS

### Community 107 - "simple_opportunity_loader.py"
Cohesion: 0.31
Nodes (3): generate_bull_call_spreads(), load_ranked_opportunities(), main()

### Community 108 - "Usage"
Cohesion: 0.22
Nodes (9): Basic Usage (Paper Trading), Disabling Specific Components, Live Trading (Use with Extreme Caution), Running Paper Trading Script (Alternative), Running Research & Analysis, Usage, With Custom Check Interval, With Custom Position Size (+1 more)

### Community 109 - "test_webull_credentials.py"
Cohesion: 0.31
Nodes (4): main(), test_account_info(), test_basic_connectivity(), test_options_permissions()

### Community 112 - "Development & Contributing"
Cohesion: 0.25
Nodes (6): Adding New Strategies, Code Structure, Coding Standards, Development & Contributing, MCP Integration Patterns, Testing

### Community 120 - "Continuous Improvement Log"
Cohesion: 0.29
Nodes (6): Completed Improvements (2026-10-12), Continuous Improvement Log, Improvement Opportunities Identified, Initial State (2026-10-12), Ongoing Improvements (2026-10-12), Webull UAT Options Trading Bot Improvements

### Community 121 - "Historical Options Data Validation Audit"
Cohesion: 0.29
Nodes (6): Detected Biases and Issues, Historical Options Data Validation Audit, Limitations and Considerations, Next Steps, Test Details, Validation Summary

### Community 122 - "✅ Integration Status: FULLY OPERATIONAL"
Cohesion: 0.29
Nodes (6): Files Verified, ✅ Integration Status: FULLY OPERATIONAL, Next Steps, Trading Bot Operation, Verification Results, Webull Paper Trading Integration - VERIFICATION COMPLETE

### Community 124 - "Phase 4 Framework Implementation Complete"
Cohesion: 0.29
Nodes (6): Current System Status, Next Steps, Phase 4 Framework Implementation Complete, Ready For Execution, Summary, What Was Created

### Community 125 - "Phase 5 Framework Implementation Complete"
Cohesion: 0.29
Nodes (6): Current System Status, Next Steps, Phase 5 Framework Implementation Complete, Ready For Execution, Summary, What Was Created

### Community 126 - "PIPELINE VERIFICATION: VERTICAL SPREAD STRATEGY FIX"
Cohesion: 0.29
Nodes (6): CONCLUSION, EXECUTIVE SUMMARY, FIX APPLIED, MANUAL VERIFICATION COMPLETED, PIPELINE VERIFICATION: VERTICAL SPREAD STRATEGY FIX, VERIFICATION RESULTS

### Community 127 - "Important Notes"
Cohesion: 0.29
Nodes (7): Continuous Improvement, Data Sources, Execution Responsibility, Important Notes, Intended Use, Regulatory Compliance, Risk Disclosure

### Community 131 - "PIPELINE STAGE ANALYSIS"
Cohesion: 0.33
Nodes (6): 1. DATA ACQUISITION ✅ WORKING, 2. SIGNAL GENERATION ✅ WORKING, 3. STRATEGY PROCESSING ❌ BROKEN, 4. SPREAD GENERATION LOGIC ❌ BROKEN, 5. MANUAL VALIDATION ✅ CONFIRMS ISSUE, PIPELINE STAGE ANALYSIS

### Community 132 - "Accomplishments"
Cohesion: 0.33
Nodes (6): 1. Fixed Credentials Loading Issue, 2. Fixed Timezone/DateTime Comparison Issues, 3. Verified MCP Data Access Pipeline, 5. Created Options Paper Trading System, 6. Risk Management Implementation, Accomplishments

### Community 133 - "Safety Features"
Cohesion: 0.33
Nodes (6): Default Safe Mode, Error Handling & Recovery, Graceful Shutdown, Logging & Monitoring, Risk Management, Safety Features

### Community 140 - "Key Features"
Cohesion: 0.40
Nodes (5): Comprehensive Analytics, Core Functionality, Data Integration, Key Features, Paper Trading Focus

### Community 142 - "Key Features"
Cohesion: 0.40
Nodes (5): Compatibility, Key Features, MCP Integration, Security, Verification

### Community 144 - "Components Created"
Cohesion: 0.50
Nodes (4): 1. Stock Screening Module (`trading_bot/screening/stock_screener.py`), 2. Phase 3 Workflow Framework (`trading_bot/screening/phase3_stock_screening_workflow.py`), 3. Key Technical Features, Components Created

### Community 145 - "Integration Points"
Cohesion: 0.50
Nodes (4): Input (from Phase 2):, Integration Points, Output (to Phase 4):, Process:

### Community 146 - "Installation & Setup"
Cohesion: 0.50
Nodes (4): Installation & Setup, Installation Steps, MCP (Model Context Protocol) Setup, Prerequisites

### Community 147 - "Project Status"
Cohesion: 0.50
Nodes (4): Known Limitations, Project Status, Recent Enhancements (Based on Research Subagent Findings), Verified Working Components

## Knowledge Gaps
- **411 isolated node(s):** `fs`, `path`, `rankedStocks`, `topStocksFromSummary`, `marketDataDict` (+406 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1726 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **72 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `VerticalSpreadStrategy` connect `VerticalSpreadStrategy` to `datetime`, `enhanced_robustness_fixed.py`, `OptionsDataPipeline`, `EventDrivenBacktest`, `run_options_paper_trade.py`, `pandas`, `OptionOpportunityGenerator`, `SignalGenerator`, `vertical_spread.py`, `research_options_strategies.py`, `robustness.py`, `OptionPricingModel`, `OptionsPaperTradingEngine`, `EnhancedWalkForwardAnalyzer`, `IndividualTradeRanker`, `._generate_bear_put_signals`, `Phase 4: Option Opportunity Generation - Framework Complete`, `Phase 5: Individual Trade Ranking - Framework Complete`, `pipeline_test.py`, `diagnostic_backtest.py`, `simple_diagnostic.py`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `SignalGenerator` (e.g. with `DiagnosticBacktester` and `SignalGenerator`) actually correct?**
  _`SignalGenerator` has 18 INFERRED edges - model-reasoned connections that need verification._
- **What connects `fs`, `path`, `rankedStocks` to the rest of the system?**
  _411 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `os` be split into smaller, more focused modules?**
  _Cohesion score 0.03215993046501521 - nodes in this community are weakly interconnected._
- **Why does `AutonomousTradingBot` connect `AutonomousTradingBot` to `Development & Contributing`, `run_paper_trade.py`, `run_options_paper_trade.py`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Should `test_phase11_integration.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0436036036036036 - nodes in this community are weakly interconnected._
- **Why does `SignalGenerator` connect `SignalGenerator` to `datetime`, `enhanced_robustness_fixed.py`, `stock_screener.py`, `OptionsDataPipeline`, `.__init__`, `pandas`, `OptionOpportunityGenerator`, `vertical_spread.py`, `VerticalSpreadStrategy`, `research_options_strategies.py`, `ProtectivePutStrategy`, `CoveredCallStrategy`, `DiagonalSpreadStrategy`, `OptionPricingModel`, `IronCondorStrategy`, `CalendarSpreadStrategy`, `IndividualTradeRanker`, `pipeline_test.py`, `diagnostic_backtest.py`, `simple_diagnostic.py`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._