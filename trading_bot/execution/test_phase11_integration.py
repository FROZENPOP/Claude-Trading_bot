"""
Integration test for Phase 11 components of the Autonomous Options Trading System.

This test verifies that all Phase 11 components work together correctly:
- Smart Order Routing
- Advanced Order Types
- Execution Analysis
- Adaptive Execution
- Execution Monitoring
- Phase 11 Coordinator
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Add project root to path for imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
if project_root not in sys.path:
    sys.path.append(project_root)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import all Phase 11 components
try:
    from trading_bot.execution.phase11_smart_order_routing import (
        SmartOrderRouter, OrderSlice, SliceAlgorithm, create_smart_order_router
    )
    SMART_ROUTING_AVAILABLE = True
except ImportError as e:
    SMART_ROUTING_AVAILABLE = False
    SMART_ROUTING_ERROR = e

try:
    from trading_bot.execution.phase11_advanced_order_types import (
        AdvancedOrderManager, AdvancedOrderType, create_advanced_order_manager
    )
    ADVANCED_ORDERS_AVAILABLE = True
except ImportError as e:
    ADVANCED_ORDERS_AVAILABLE = False
    ADVANCED_ORDERS_ERROR = e

try:
    from trading_bot.execution.phase11_execution_analysis import (
        ExecutionAnalyzer, create_execution_analyzer
    )
    EXECUTION_ANALYSIS_AVAILABLE = True
except ImportError as e:
    EXECUTION_ANALYSIS_AVAILABLE = False
    EXECUTION_ANALYSIS_ERROR = e

try:
    from trading_bot.execution.phase11_adaptive_execution import (
        AdaptiveExecutionEngine, MarketCondition, create_adaptive_execution_engine
    )
    ADAPTIVE_EXECUTION_AVAILABLE = True
except ImportError as e:
    ADAPTIVE_EXECUTION_AVAILABLE = False
    ADAPTIVE_EXECUTION_ERROR = e

try:
    from trading_bot.execution.phase11_execution_monitor import (
        ExecutionMonitor, ExecutionRecord, create_execution_monitor
    )
    EXECUTION_MONITORING_AVAILABLE = True
except ImportError as e:
    EXECUTION_MONITORING_AVAILABLE = False
    EXECUTION_MONITORING_ERROR = e

try:
    from trading_bot.execution.phase11_coordinator import (
        Phase11Coordinator, create_phase11_coordinator
    )
    PHASE11_COORDINATOR_AVAILABLE = True
except ImportError as e:
    PHASE11_COORDINATOR_AVAILABLE = False
    PHASE11_COORDINATOR_ERROR = e

def test_imports():
    """Test that all Phase 11 components can be imported."""
    print("=== Testing Component Imports ===")

    all_imports_successful = True

    if not SMART_ROUTING_AVAILABLE:
        print(f"[FAIL] Failed to import Smart Order Routing: {SMART_ROUTING_ERROR}")
        all_imports_successful = False
    else:
        print("[PASS] Smart Order Routing imported successfully")

    if not ADVANCED_ORDERS_AVAILABLE:
        print(f"[FAIL] Failed to import Advanced Order Types: {ADVANCED_ORDERS_ERROR}")
        all_imports_successful = False
    else:
        print("[PASS] Advanced Order Types imported successfully")

    if not EXECUTION_ANALYSIS_AVAILABLE:
        print(f"[FAIL] Failed to import Execution Analysis: {EXECUTION_ANALYSIS_ERROR}")
        all_imports_successful = False
    else:
        print("[PASS] Execution Analysis imported successfully")

    if not ADAPTIVE_EXECUTION_AVAILABLE:
        print(f"[FAIL] Failed to import Adaptive Execution: {ADAPTIVE_EXECUTION_ERROR}")
        all_imports_successful = False
    else:
        print("[PASS] Adaptive Execution imported successfully")

    if not EXECUTION_MONITORING_AVAILABLE:
        print(f"[FAIL] Failed to import Execution Monitoring: {EXECUTION_MONITORING_ERROR}")
        all_imports_successful = False
    else:
        print("[PASS] Execution Monitoring imported successfully")

    if not PHASE11_COORDINATOR_AVAILABLE:
        print(f"[FAIL] Failed to import Phase 11 Coordinator: {PHASE11_COORDINATOR_ERROR}")
        all_imports_successful = False
    else:
        print("[PASS] Phase 11 Coordinator imported successfully")

    return all_imports_successful

def test_component_creation():
    """Test that all Phase 11 components can be created."""
    print("\n=== Testing Component Creation ===")

    if not SMART_ROUTING_AVAILABLE:
        print(f"[FAIL] Skipping Smart Order Router creation - import failed: {SMART_ROUTING_ERROR}")
        return False

    try:
        smart_router = create_smart_order_router()
        print(f"[PASS] Smart Order Router created successfully: {smart_router}")
    except Exception as e:
        print(f"[FAIL] Failed to create Smart Order Router: {e}")
        import traceback
        traceback.print_exc()
        return False

    if not ADVANCED_ORDERS_AVAILABLE:
        print(f"[FAIL] Skipping Advanced Order Manager creation - import failed: {ADVANCED_ORDERS_ERROR}")
        return False

    try:
        advanced_order_manager = create_advanced_order_manager()
        print(f"[PASS] Advanced Order Manager created successfully: {advanced_order_manager}")
    except Exception as e:
        print(f"[FAIL] Failed to create Advanced Order Manager: {e}")
        import traceback
        traceback.print_exc()
        return False

    if not EXECUTION_ANALYSIS_AVAILABLE:
        print(f"[FAIL] Skipping Execution Analyzer creation - import failed: {EXECUTION_ANALYSIS_ERROR}")
        return False

    try:
        execution_analyzer = create_execution_analyzer()
        print(f"[PASS] Execution Analyzer created successfully: {execution_analyzer}")
    except Exception as e:
        print(f"[FAIL] Failed to create Execution Analyzer: {e}")
        import traceback
        traceback.print_exc()
        return False

    if not ADAPTIVE_EXECUTION_AVAILABLE:
        print(f"[FAIL] Skipping Adaptive Execution Engine creation - import failed: {ADAPTIVE_EXECUTION_ERROR}")
        return False

    try:
        adaptive_engine = create_adaptive_execution_engine()
        print(f"[PASS] Adaptive Execution Engine created successfully: {adaptive_engine}")
    except Exception as e:
        print(f"[FAIL] Failed to create Adaptive Execution Engine: {e}")
        import traceback
        traceback.print_exc()
        return False

    if not EXECUTION_MONITORING_AVAILABLE:
        print(f"[FAIL] Skipping Execution Monitor creation - import failed: {EXECUTION_MONITORING_ERROR}")
        return False

    try:
        execution_monitor = create_execution_monitor()
        print(f"[PASS] Execution Monitor created successfully: {execution_monitor}")
    except Exception as e:
        print(f"[FAIL] Failed to create Execution Monitor: {e}")
        import traceback
        traceback.print_exc()
        return False

    if not PHASE11_COORDINATOR_AVAILABLE:
        print(f"[FAIL] Skipping Phase 11 Coordinator creation - import failed: {PHASE11_COORDINATOR_ERROR}")
        return False

    try:
        coordinator = create_phase11_coordinator()
        print(f"[PASS] Phase 11 Coordinator created successfully: {coordinator}")
    except Exception as e:
        print(f"[FAIL] Failed to create Phase 11 Coordinator: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

def test_coordinator_functionality():
    """Test basic functionality of the Phase 11 coordinator."""
    print("\n=== Testing Coordinator Functionality ===")

    if not PHASE11_COORDINATOR_AVAILABLE:
        print(f"[FAIL] Skipping Coordinator functionality test - import failed: {PHASE11_COORDINATOR_ERROR}")
        return False

    try:
        coordinator = create_phase11_coordinator(
            enable_smart_routing=True,
            enable_advanced_orders=True,
            enable_execution_analysis=True,
            enable_adaptive_execution=True,
            enable_execution_monitoring=True
        )

        # Test market data
        market_data = {
            'price': 150.0,
            'volume': 25000000,
            'volatility': 0.25,
            'bid': 149.95,
            'ask': 150.05,
            'spread_bps': 6.7
        }

        # Test market condition analysis
        conditions = coordinator.analyze_market_conditions('AAPL', market_data)
        print(f"[PASS] Market condition analysis: {conditions.get('condition', 'unknown')}")

        # Test execution plan creation
        plan = coordinator.create_execution_plan(
            symbol='AAPL',
            side='buy',
            quantity=500,
            urgency='normal',
            market_data=market_data
        )
        print(f"[PASS] Execution plan created: {plan.get('recommended_approach', 'unknown')}")

        # Test execution (simulation)
        result = coordinator.execute_order(plan['execution_id'])
        print(f"[PASS] Order execution: {result.get('status', 'unknown')}")

        # Test status retrieval
        status = coordinator.get_execution_status(plan['execution_id'])
        print(f"[PASS] Status retrieval: {status.get('status', 'unknown')}")

        # Test performance summary
        summary = coordinator.get_performance_summary()
        print(f"[PASS] Performance summary: {summary.get('phase_11_components', {})}")

        # Cleanup
        coordinator.shutdown()
        print("[PASS] Coordinator shutdown successful")

        return True

    except Exception as e:
        print(f"[FAIL] Coordinator functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_individual_components():
    """Test individual component functionality."""
    print("\n=== Testing Individual Components ===")

    # Test Smart Order Router
    if not SMART_ROUTING_AVAILABLE:
        print(f"[FAIL] Skipping Smart Order Router test - import failed: {SMART_ROUTING_ERROR}")
        return False

    try:
        router = create_smart_order_router()
        # Test creating an order slice using the OrderSlice alias
        slice_obj = OrderSlice(
            symbol='AAPL',
            side='buy',
            quantity=1000,
        )
        print("[PASS] Smart Order Router: Order slice creation successful")
    except Exception as e:
        print(f"[FAIL] Smart Order Router test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test Advanced Order Manager
    if not ADVANCED_ORDERS_AVAILABLE:
        print(f"[FAIL] Skipping Advanced Order Manager test - import failed: {ADVANCED_ORDERS_ERROR}")
        return False

    try:
        manager = create_advanced_order_manager()
        # Test creating an iceberg order
        iceberg_order = manager.create_iceberg_order(
            symbol='AAPL',
            side='buy',
            total_quantity=5000,
            price=150.0,
            display_quantity=500
        )
        print("[PASS] Advanced Order Manager: Iceberg order creation successful")
    except Exception as e:
        print(f"[FAIL] Advanced Order Manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test Execution Analyzer
    if not EXECUTION_ANALYSIS_AVAILABLE:
        print(f"[FAIL] Skipping Execution Analyzer test - import failed: {EXECUTION_ANALYSIS_ERROR}")
        return False

    try:
        analyzer = create_execution_analyzer()
        # Test analyzing execution quality (with dummy data)
        analysis = analyzer.analyze_execution(
            symbol='AAPL',
            side='buy',
            quantity=100,
            executed_quantity=100,
            average_price=150.0,
            start_time=datetime.now() - timedelta(minutes=5),
            end_time=datetime.now()
        )
        print("[PASS] Execution Analyzer: Analysis completion successful")
    except Exception as e:
        print(f"[FAIL] Execution Analyzer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test Adaptive Execution Engine
    if not ADAPTIVE_EXECUTION_AVAILABLE:
        print(f"[FAIL] Skipping Adaptive Execution Engine test - import failed: {ADAPTIVE_EXECUTION_ERROR}")
        return False

    try:
        engine = create_adaptive_execution_engine()
        # Test updating market data
        engine.update_market_data('AAPL', {
            'price': 150.0,
            'volume': 25000000,
            'volatility': 0.25
        })
        # Test detecting market condition
        condition = engine.detect_market_condition('AAPL')
        print("[PASS] Adaptive Execution Engine: Market condition detection successful")
    except Exception as e:
        print(f"[FAIL] Adaptive Execution Engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test Execution Monitor
    if not EXECUTION_MONITORING_AVAILABLE:
        print(f"[FAIL] Skipping Execution Monitor test - import failed: {EXECUTION_MONITORING_ERROR}")
        return False

    try:
        monitor = create_execution_monitor()
        # Test recording an execution
        execution_id = monitor.record_execution({
            'symbol': 'AAPL',
            'side': 'buy',
            'quantity': 100,
            'executed_quantity': 100,
            'algorithm_used': 'TWAP',
            'average_price': 150.0,
            'benchmark_price': 149.50,
            'slippage_bps': 3.3,
            'execution_time_seconds': 120.0,
            'success': True
        })
        print("[PASS] Execution Monitor: Execution recording successful")

        # Test getting summary
        summary = monitor.get_execution_summary()
        print("[PASS] Execution Monitor: Summary retrieval successful")

        # Cleanup
        monitor.stop()
    except Exception as e:
        print(f"[FAIL] Execution Monitor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

def main():
    """Run all Phase 11 integration tests."""
    print("Phase 11 Integration Test Suite")
    print("=" * 50)

    all_passed = True

    # Test imports
    if not test_imports():
        all_passed = False

    # Test component creation
    if not test_component_creation():
        all_passed = False

    # Test individual components
    if not test_individual_components():
        all_passed = False

    # Test coordinator functionality
    if not test_coordinator_functionality():
        all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("[PASS] ALL TESTS PASSED - Phase 11 integration is working correctly!")
        return 0
    else:
        print("[FAIL] SOME TESTS FAILED - Please check the output above")
        return 1

if __name__ == "__main__":
    sys.exit(main())