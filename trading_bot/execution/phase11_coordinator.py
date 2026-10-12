"""Phase 11 Coordinator: Main Integration Module for Advanced Execution.

This module coordinates all Phase 11 components:
- Smart Order Routing (VWAP, TWAP, POV)
- Advanced Order Types (Iceberg, Pegged)
- Execution Analysis (Slippage, Quality Metrics)
- Adaptive Execution (Market Condition Detection)
- Execution Monitoring (Performance Tracking & Alerts)

Provides a unified interface for the autonomous trading system to access
Phase 11 execution capabilities.
"""

import os
import sys
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, Any

# Add project root to path for imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
if project_root not in sys.path:
    sys.path.append(project_root)

logger = logging.getLogger(__name__)

# Import Phase 11 components
try:
    from .phase11_smart_order_routing import (
        SmartOrderRouter, OrderSlice, SliceAlgorithm,
        create_smart_order_router
    )
    from .phase11_advanced_order_types import (
        AdvancedOrderManager, AdvancedOrderType,
        create_advanced_order_manager
    )
    from .phase11_execution_analysis import (
        ExecutionAnalyzer,
        create_execution_analyzer
    )
    from .phase11_adaptive_execution import (
        AdaptiveExecutionEngine, MarketCondition,
        create_adaptive_execution_engine
    )
    from .phase11_execution_monitor import (
        ExecutionMonitor, ExecutionRecord,
        create_execution_monitor
    )
    PHASE_11_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Some Phase 11 components not available: {e}")
    PHASE_11_AVAILABLE = False


class Phase11Coordinator:
    """Main coordinator for Phase 11 advanced execution capabilities."""

    def __init__(self,
                 enable_smart_routing: bool = True,
                 enable_advanced_orders: bool = True,
                 enable_execution_analysis: bool = True,
                 enable_adaptive_execution: bool = True,
                 enable_execution_monitoring: bool = True):
        """Initialize the Phase 11 coordinator.

        Args:
            enable_smart_routing: Enable smart order routing algorithms
            enable_advanced_orders: Enable advanced order types
            enable_execution_analysis: Enable execution quality analysis
            enable_adaptive_execution: Enable adaptive execution based on market conditions
            enable_execution_monitoring: Enable execution monitoring and alerting
        """
        self.enable_smart_routing = enable_smart_routing
        self.enable_advanced_orders = enable_advanced_orders
        self.enable_execution_analysis = enable_execution_analysis
        self.enable_adaptive_execution = enable_adaptive_execution
        self.enable_execution_monitoring = enable_execution_monitoring

        # Initialize components if enabled and available
        self.smart_router = None
        self.advanced_order_manager = None
        self.execution_analyzer = None
        self.adaptive_engine = None
        self.execution_monitor = None

        if PHASE_11_AVAILABLE:
            self._initialize_components()
        else:
            logger.warning("Phase 11 components not fully available - running in limited mode")

        # Execution tracking
        self.active_executions: Dict[str, Dict] = {}
        self.execution_history: List[Dict] = []

        logger.info(f"Phase11Coordinator initialized with: "
                   f"smart_routing={enable_smart_routing}, "
                   f"advanced_orders={enable_advanced_orders}, "
                   f"execution_analysis={enable_execution_analysis}, "
                   f"adaptive_execution={enable_adaptive_execution}, "
                   f"execution_monitoring={enable_execution_monitoring}")

    def _initialize_components(self):
        """Initialize all Phase 11 components."""
        try:
            if self.enable_smart_routing:
                self.smart_router = create_smart_order_router()
                logger.debug("Smart order router initialized")

            if self.enable_advanced_orders:
                self.advanced_order_manager = create_advanced_order_manager()
                logger.debug("Advanced order manager initialized")

            if self.enable_execution_analysis:
                self.execution_analyzer = create_execution_analyzer()
                logger.debug("Execution analyzer initialized")

            if self.enable_adaptive_execution:
                self.adaptive_engine = create_adaptive_execution_engine()
                logger.debug("Adaptive execution engine initialized")

            if self.enable_execution_monitoring:
                self.execution_monitor = create_execution_monitor()
                logger.debug("Execution monitor initialized")

        except Exception as e:
            logger.error(f"Error initializing Phase 11 components: {e}")
            # Continue with whatever components were successfully initialized

    def analyze_market_conditions(self, symbol: str, market_data: Dict) -> Dict:
        """Analyze current market conditions for a symbol.

        Args:
            symbol: Stock symbol to analyze
            market_data: Current market data (price, volume, volatility, etc.)

        Returns:
            Dictionary with market condition analysis
        """
        if not self.enable_adaptive_execution or not self.adaptive_engine:
            return {'condition': 'unknown', 'confidence': 0.0}

        try:
            # Update market data in adaptive engine
            self.adaptive_engine.update_market_data(symbol, market_data)

            # Detect current market condition
            condition = self.adaptive_engine.detect_market_condition(symbol)

            # Get execution parameters for this condition
            params = self.adaptive_engine.get_execution_parameters(symbol)

            return {
                'condition': condition.value if hasattr(condition, 'value') else str(condition),
                'confidence': getattr(condition, 'confidence', 0.8),  # Default confidence
                'parameters': params,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error analyzing market conditions for {symbol}: {e}")
            return {'condition': 'error', 'confidence': 0.0, 'error': str(e)}

    def create_execution_plan(self,
                            symbol: str,
                            side: str,
                            quantity: int,
                            max_price: Optional[float] = None,
                            min_price: Optional[float] = None,
                            market_data: Optional[Dict] = None,
                            urgency: str = 'normal') -> Dict:
        """Create an optimized execution plan for an order.

        Args:
            symbol: Stock symbol
            side: 'buy' or 'sell'
            quantity: Number of shares/contracts
            max_price: Maximum price to pay (for buys) or minimum to receive (for sells)
            min_price: Minimum price to pay (for buys) or maximum to receive (for sells)
            market_data: Current market data for analysis
            urgency: Execution urgency ('low', 'normal', 'high', 'immediate')

        Returns:
            Dictionary containing execution plan recommendations
        """
        execution_id = f"{symbol}_{side}_{quantity}_{int(datetime.now().timestamp())}"

        plan = {
            'execution_id': execution_id,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'urgency': urgency,
            'timestamp': datetime.now().isoformat(),
            'recommended_approach': 'standard',
            'algorithms': [],
            'order_types': [],
            'parameters': {},
            'warnings': []
        }

        try:
            # Analyze market conditions if data provided
            market_conditions = {}
            if market_data and self.enable_adaptive_execution:
                market_conditions = self.analyze_market_conditions(symbol, market_data)
                plan['market_conditions'] = market_conditions

            # Determine if smart routing is beneficial
            if self.enable_smart_routing and self.smart_router:
                # For large orders, recommend smart routing
                if quantity > 100:  # Threshold for considering smart routing
                    plan['recommended_approach'] = 'smart_routing'

                    # Get algorithm recommendation based on urgency and conditions
                    urgency_map = {
                        'low': ('VWAP', SliceAlgorithm.VWAP),
                        'normal': ('TWAP', SliceAlgorithm.TWAP),
                        'high': ('POV', SliceAlgorithm.POV),
                        'immediate': ('POV', SliceAlgorithm.POV)  # POV with high participation rate
                    }

                    algo_name, algo_enum = urgency_map.get(urgency, ('TWAP', SliceAlgorithm.TWAP))

                    # Adjust based on market conditions
                    condition = market_conditions.get('condition', 'normal')
                    if condition in ['volatile', 'illiquid'] and urgency != 'immediate':
                        # In volatile/illiquid markets, VWAP often works better than TWAP
                        algo_name, algo_enum = 'VWAP', SliceAlgorithm.VWAP
                    elif condition == 'liquid' and urgency in ['high', 'immediate']:
                        # In liquid markets with urgency, POV can be aggressive
                        algo_name, algo_enum = 'POV', SliceAlgorithm.POV

                    plan['algorithms'].append({
                        'name': algo_name,
                        'type': algo_enum.value if hasattr(algo_enum, 'value') else str(algo_enum),
                        'reason': f'Recommended for {urgency} urgency in {condition} market'
                    })

            # Determine if advanced order types are beneficial
            if self.enable_advanced_orders and self.advanced_order_manager:
                # For large orders or illiquid markets, consider advanced types
                if quantity > 500 or market_conditions.get('condition') in ['illiquid', 'volatile']:
                    plan['recommended_approach'] = 'advanced_orders'

                    # Iceberg orders for large quantities to hide true size
                    if quantity > 1000:
                        plan['order_types'].append({
                            'name': 'Iceberg',
                            'type': AdvancedOrderType.ICEBERG.value,
                            'reason': f'Large order ({quantity}) benefits from iceberg to hide true size',
                            'suggested_display_quantity': min(100, max(10, quantity // 10))
                        })

                    # Pegged orders for volatile markets to track reference price
                    if market_conditions.get('condition') == 'volatile':
                        plan['order_types'].append({
                            'name': 'Pegged',
                            'type': AdvancedOrderType.PEGGED.value,
                            'reason': 'Volatile market benefits from pegged orders tracking mid-point',
                            'reference_price_type': 'midpoint'
                        })

            # Standard approach fallback
            if plan['recommended_approach'] == 'standard':
                plan['algorithms'].append({
                    'name': 'TWAP',
                    'type': SliceAlgorithm.TWAP.value,
                    'reason': 'Default balanced approach for normal conditions'
                })

            # Add execution parameters
            plan['parameters'] = {
                'max_price': max_price,
                'min_price': min_price,
                'urgency': urgency,
                'estimated_duration_minutes': self._estimate_execution_duration(quantity, urgency, plan),
                'participation_rate': self._suggest_participation_rate(urgency, market_conditions)
            }

            # Add warnings based on analysis
            plan['warnings'] = self._generate_warnings(symbol, quantity, market_conditions, urgency)

            # Store in active executions
            self.active_executions[execution_id] = {
                'plan': plan,
                'status': 'planned',
                'created_at': datetime.now()
            }

            logger.info(f"Created execution plan {execution_id}: {plan['recommended_approach']} "
                       f"for {quantity} {symbol} {side}")

            return plan

        except Exception as e:
            logger.error(f"Error creating execution plan for {symbol}: {e}")
            plan['error'] = str(e)
            plan['recommended_approach'] = 'standard_fallback'
            return plan

    def execute_order(self,
                     execution_id: str,
                     broker_interface: Any = None) -> Dict:
        """Execute an order based on the execution plan.

        Args:
            execution_id: ID of the execution plan to execute
            broker_interface: Interface to broker/execution system (optional for simulation)

        Returns:
            Dictionary with execution results
        """
        if execution_id not in self.active_executions:
            return {
                'success': False,
                'error': f'Execution plan {execution_id} not found',
                'execution_id': execution_id
            }

        plan = self.active_executions[execution_id]['plan']
        self.active_executions[execution_id]['status'] = 'executing'

        start_time = datetime.now()

        try:
            result = {
                'execution_id': execution_id,
                'symbol': plan['symbol'],
                'side': plan['side'],
                'quantity': plan['quantity'],
                'status': 'started',
                'start_time': start_time.isoformat(),
                'approach_used': plan['recommended_approach'],
                'details': {}
            }

            # Execute based on recommended approach
            if plan['recommended_approach'] == 'smart_routing' and self.smart_router:
                result.update(self._execute_via_smart_routing(plan, broker_interface))
            elif plan['recommended_approach'] == 'advanced_orders' and self.advanced_order_manager:
                result.update(self._execute_via_advanced_orders(plan, broker_interface))
            else:
                # Standard execution (could be TWAP/VWAP/POV via smart router or direct)
                result.update(self._execute_via_standard_method(plan, broker_interface))

            # Calculate execution time
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            result['end_time'] = end_time.isoformat()
            result['execution_time_seconds'] = execution_time

            # Update plan status
            self.active_executions[execution_id]['status'] = result.get('status', 'failed')
            self.active_executions[execution_id]['result'] = result

            # Move to history
            self.execution_history.append({
                'execution_id': execution_id,
                'plan': plan,
                'result': result,
                'completed_at': end_time
            })

            # Record in execution monitor if enabled
            if self.enable_execution_monitoring and self.execution_monitor:
                self._record_execution_for_monitoring(plan, result)

            # Analyze execution quality if enabled
            if self.enable_execution_analysis and self.execution_analyzer:
                self._analyze_execution_quality(plan, result)

            logger.info(f"Executed order {execution_id}: {result.get('status', 'unknown')} "
                       f"({result.get('filled_quantity', 0)}/{plan['quantity']} filled)")

            return result

        except Exception as e:
            logger.error(f"Error executing order {execution_id}: {e}")
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            error_result = {
                'execution_id': execution_id,
                'symbol': plan['symbol'],
                'side': plan['side'],
                'quantity': plan['quantity'],
                'status': 'error',
                'error': str(e),
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'execution_time_seconds': execution_time
            }

            self.active_executions[execution_id]['status'] = 'error'
            self.active_executions[execution_id]['result'] = error_result

            return error_result

    def _execute_via_smart_routing(self, plan: Dict, broker_interface: Any) -> Dict:
        """Execute using smart order routing algorithms.

        Args:
            plan: Execution plan
            broker_interface: Broker interface for actual execution

        Returns:
            Execution result dictionary
        """
        # For now, simulate execution - in reality this would interface with broker
        symbol = plan['symbol']
        side = plan['side']
        quantity = plan['quantity']

        # Get the recommended algorithm
        algorithm_name = 'TWAP'  # Default
        if plan['algorithms']:
            algorithm_name = plan['algorithms'][0]['name']

        # Simulate smart routing execution
        # In practice, this would create sliced orders via the smart router
        filled_quantity = quantity  # Assume full fill for simulation
        average_price = 100.0  # Placeholder - would come from actual execution

        # Calculate slippage (simulated)
        benchmark_price = 100.0  # Would come from market data
        slippage_bps = ((average_price - benchmark_price) / benchmark_price) * 10000

        return {
            'status': 'completed',
            'filled_quantity': filled_quantity,
            'average_price': average_price,
            'slippage_bps': slippage_bps,
            'algorithm_used': algorithm_name,
            'slices_executed': max(1, quantity // 100),  # Simulate slicing
            'details': {
                'approach': 'smart_routing',
                'algorithm': algorithm_name,
                'simulation_mode': True
            }
        }

    def _execute_via_advanced_orders(self, plan: Dict, broker_interface: Any) -> Dict:
        """Execute using advanced order types.

        Args:
            plan: Execution plan
            broker_interface: Broker interface for actual execution

        Returns:
            Execution result dictionary
        """
        # For now, simulate execution
        symbol = plan['symbol']
        side = plan['side']
        quantity = plan['quantity']

        # Get the recommended order type
        order_type_name = 'ICEBERG'  # Default
        if plan['order_types']:
            order_type_name = plan['order_types'][0]['name']

        # Simulate advanced order execution
        filled_quantity = quantity  # Assume full fill for simulation
        average_price = 100.0  # Placeholder

        # Calculate slippage (simulated)
        benchmark_price = 100.0
        slippage_bps = ((average_price - benchmark_price) / benchmark_price) * 10000

        return {
            'status': 'completed',
            'filled_quantity': filled_quantity,
            'average_price': average_price,
            'slippage_bps': slippage_bps,
            'order_type_used': order_type_name,
            'details': {
                'approach': 'advanced_orders',
                'order_type': order_type_name,
                'simulation_mode': True
            }
        }

    def _execute_via_standard_method(self, plan: Dict, broker_interface: Any) -> Dict:
        """Execute using standard methods (could be TWAP/VWAP via smart router).

        Args:
            plan: Execution plan
            broker_interface: Broker interface for actual execution

        Returns:
            Execution result dictionary
        """
        # Fall back to smart router if available for standard algorithms
        if self.smart_router and plan['algorithms']:
            return self._execute_via_smart_routing(plan, broker_interface)
        else:
            # Direct execution simulation
            symbol = plan['symbol']
            side = plan['side']
            quantity = plan['quantity']

            filled_quantity = quantity  # Assume full fill
            average_price = 100.0  # Placeholder
            benchmark_price = 100.0
            slippage_bps = ((average_price - benchmark_price) / benchmark_price) * 10000

            algorithm_used = plan['algorithms'][0]['name'] if plan['algorithms'] else 'MARKET'

            return {
                'status': 'completed',
                'filled_quantity': filled_quantity,
                'average_price': average_price,
                'slippage_bps': slippage_bps,
                'algorithm_used': algorithm_used,
                'details': {
                    'approach': 'standard',
                    'algorithm': algorithm_used,
                    'simulation_mode': True
                }
            }

    def _record_execution_for_monitoring(self, plan: Dict, result: Dict):
        """Record execution in the execution monitor.

        Args:
            plan: Original execution plan
            result: Execution result
        """
        if not self.execution_monitor:
            return

        try:
            execution_record = {
                'symbol': plan['symbol'],
                'side': plan['side'],
                'quantity': plan['quantity'],
                'executed_quantity': result.get('filled_quantity', 0),
                'algorithm_used': result.get('algorithm_used', result.get('order_type_used', 'unknown')),
                'average_price': result.get('average_price', 0.0),
                'benchmark_price': 100.0,  # Would come from market data in real implementation
                'slippage_bps': result.get('slippage_bps', 0.0),
                'execution_time_seconds': result.get('execution_time_seconds', 0.0),
                'success': result.get('status') == 'completed',
                'market_conditions': plan.get('market_conditions', {}),
                'metadata': {
                    'execution_id': plan['execution_id'],
                    'approach': plan['recommended_approach'],
                    'urgency': plan['urgency']
                }
            }

            self.execution_monitor.record_execution(execution_record)

        except Exception as e:
            logger.error(f"Error recording execution for monitoring: {e}")

    def _analyze_execution_quality(self, plan: Dict, result: Dict):
        """Analyze execution quality using the execution analyzer.

        Args:
            plan: Original execution plan
            result: Execution result
        """
        if not self.execution_analyzer:
            return

        try:
            # This would analyze the actual execution against benchmarks
            # For now, just log that analysis would occur
            logger.debug(f"Would analyze execution quality for {plan['execution_id']}")

        except Exception as e:
            logger.error(f"Error analyzing execution quality: {e}")

    def _estimate_execution_duration(self, quantity: int, urgency: str, plan: Dict) -> int:
        """Estimate execution duration in minutes.

        Args:
            quantity: Order quantity
            urgency: Execution urgency
            plan: Execution plan

        Returns:
            Estimated duration in minutes
        """
        # Base duration per 100 shares
        base_duration_per_100 = 5  # 5 minutes per 100 shares normally

        # Adjust for urgency
        urgency_multipliers = {
            'low': 2.0,      # Take more time for better price
            'normal': 1.0,
            'high': 0.5,     # Rush execution
            'immediate': 0.25 # Execute as fast as possible
        }

        urgency_multiplier = urgency_multipliers.get(urgency, 1.0)

        # Adjust for algorithm type
        algorithm_multiplier = 1.0
        if plan['algorithms']:
            algo_name = plan['algorithms'][0]['name'].upper()
            if 'VWAP' in algo_name:
                algorithm_multiplier = 1.2  # VWAP takes longer
            elif 'TWAP' in algo_name:
                algorithm_multiplier = 1.0  # TWAP baseline
            elif 'POV' in algo_name:
                algorithm_multiplier = 0.8  # POV can be faster

        # Calculate duration
        duration = (quantity / 100) * base_duration_per_100 * urgency_multiplier * algorithm_multiplier

        # Apply reasonable bounds
        return max(1, min(int(duration), 60))  # Between 1 minute and 1 hour

    def _suggest_participation_rate(self, urgency: str, market_conditions: Dict) -> float:
        """Suggest participation rate for POV algorithms.

        Args:
            urgency: Execution urgency
            market_conditions: Current market conditions

        Returns:
            Suggested participation rate (0.0 to 1.0)
        """
        # Base participation rate
        base_rate = 0.1  # 10% of volume

        # Adjust for urgency
        urgency_adjustments = {
            'low': 0.5,      # 5% of volume
            'normal': 1.0,   # 10% of volume
            'high': 2.0,     # 20% of volume
            'immediate': 3.0 # 30% of volume
        }

        rate = base_rate * urgency_adjustments.get(urgency, 1.0)

        # Adjust for market conditions
        condition = market_conditions.get('condition', 'normal')
        if condition == 'illiquid':
            rate *= 0.5  # Reduce participation in illiquid markets
        elif condition == 'volatile':
            rate *= 1.5  # Increase participation in volatile markets (more volume)

        # Apply reasonable bounds
        return max(0.01, min(rate, 0.5))  # Between 1% and 50%

    def _generate_warnings(self, symbol: str, quantity: int, market_conditions: Dict, urgency: str) -> List[str]:
        """Generate warnings for the execution plan.

        Args:
            symbol: Stock symbol
            quantity: Order quantity
            market_conditions: Market condition analysis
            urgency: Execution urgency

        Returns:
            List of warning messages
        """
        warnings = []

        # Large order warning
        if quantity > 1000:
            warnings.append(f"Large order size ({quantity}) may impact market price")

        # Market condition warnings
        condition = market_conditions.get('condition', 'normal')
        if condition == 'illiquid':
            warnings.append("Illiquid market detected - execution may be slow or expensive")
        elif condition == 'volatile':
            warnings.append("Volatile market detected - consider using pegged orders or iceberg")

        # Urgency warnings
        if urgency == 'immediate':
            warnings.append("Immediate urgency may result in poor execution price")
        elif urgency == 'high':
            warnings.append("High urgency may increase slippage")

        # Algorithm-specific warnings
        if market_conditions.get('confidence', 1.0) < 0.5:
            warnings.append("Low confidence in market condition detection - consider conservative approach")

        return warnings

    def get_execution_status(self, execution_id: str) -> Dict:
        """Get status of an execution.

        Args:
            execution_id: ID of execution to check

        Returns:
            Dictionary with execution status
        """
        if execution_id in self.active_executions:
            exec_data = self.active_executions[execution_id]
            return {
                'execution_id': execution_id,
                'status': exec_data['status'],
                'created_at': exec_data['created_at'].isoformat(),
                'plan': exec_data['plan'],
                'result': exec_data.get('result')
            }
        elif any(h['execution_id'] == execution_id for h in self.execution_history):
            # Found in history
            for hist in self.execution_history:
                if hist['execution_id'] == execution_id:
                    return {
                        'execution_id': execution_id,
                        'status': 'completed',
                        'completed_at': hist['completed_at'].isoformat(),
                        'plan': hist['plan'],
                        'result': hist['result']
                    }

        return {
            'execution_id': execution_id,
            'status': 'not_found',
            'error': f'Execution {execution_id} not found'
        }

    def get_performance_summary(self) -> Dict:
        """Get overall performance summary from all Phase 11 components.

        Returns:
            Dictionary with performance summary
        """
        summary = {
            'phase_11_components': {
                'smart_routing_enabled': self.enable_smart_routing and self.smart_router is not None,
                'advanced_orders_enabled': self.enable_advanced_orders and self.advanced_order_manager is not None,
                'execution_analysis_enabled': self.enable_execution_analysis and self.execution_analyzer is not None,
                'adaptive_execution_enabled': self.enable_adaptive_execution and self.adaptive_engine is not None,
                'execution_monitoring_enabled': self.enable_execution_monitoring and self.execution_monitor is not None
            },
            'execution_stats': {
                'active_executions': len([e for e in self.active_executions.values() if e['status'] in ['planned', 'executing']]),
                'completed_executions': len([e for e in self.active_executions.values() if e['status'] == 'completed']),
                'failed_executions': len([e for e in self.active_executions.values() if e['status'] in ['failed', 'error']]),
                'total_planned': len(self.active_executions),
                'total_historical': len(self.execution_history)
            }
        }

        # Add execution monitor summary if available
        if self.enable_execution_monitoring and self.execution_monitor:
            summary['execution_monitoring'] = self.execution_monitor.get_execution_summary()
            summary['algorithm_performance'] = self.execution_monitor.get_algorithm_performance_summary()

        return summary

    def shutdown(self):
        """Shutdown all Phase 11 components gracefully."""
        logger.info("Shutting down Phase 11 coordinator...")

        # Stop execution monitor if running
        if self.enable_execution_monitoring and self.execution_monitor:
            try:
                self.execution_monitor.stop()
            except Exception as e:
                logger.error(f"Error stopping execution monitor: {e}")

        # Clear active executions
        self.active_executions.clear()

        logger.info("Phase 11 coordinator shutdown complete")


def create_phase11_coordinator(
    enable_smart_routing: bool = True,
    enable_advanced_orders: bool = True,
    enable_execution_analysis: bool = True,
    enable_adaptive_execution: bool = True,
    enable_execution_monitoring: bool = True
) -> Phase11Coordinator:
    """Factory function to create a Phase11Coordinator instance.

    Args:
        enable_smart_routing: Enable smart order routing algorithms
        enable_advanced_orders: Enable advanced order types
        enable_execution_analysis: Enable execution quality analysis
        enable_adaptive_execution: Enable adaptive execution based on market conditions
        enable_execution_monitoring: Enable execution monitoring and alerting

    Returns:
        Configured Phase11Coordinator instance
    """
    return Phase11Coordinator(
        enable_smart_routing=enable_smart_routing,
        enable_advanced_orders=enable_advanced_orders,
        enable_execution_analysis=enable_execution_analysis,
        enable_adaptive_execution=enable_adaptive_execution,
        enable_execution_monitoring=enable_execution_monitoring
    )


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=== Phase 11 Coordinator Demo ===\n")

    # Create coordinator
    coordinator = create_phase11_coordinator(
        enable_smart_routing=True,
        enable_advanced_orders=True,
        enable_execution_analysis=True,
        enable_adaptive_execution=True,
        enable_execution_monitoring=True
    )

    # Demo market data
    market_data_aapl = {
        'price': 150.0,
        'volume': 25000000,
        'volatility': 0.25,
        'bid': 149.95,
        'ask': 150.05,
        'spread_bps': 6.7,
        'market_condition': 'normal'
    }

    market_data_tsla = {
        'price': 250.0,
        'volume': 15000000,
        'volatility': 0.45,
        'bid': 249.80,
        'ask': 250.20,
        'spread_bps': 16.0,
        'market_condition': 'volatile'
    }

    print("1. Market Condition Analysis")
    aapl_conditions = coordinator.analyze_market_conditions('AAPL', market_data_aapl)
    print(f"   AAPL: {aapl_conditions}")

    tsla_conditions = coordinator.analyze_market_conditions('TSLA', market_data_tsla)
    print(f"   TSLA: {tsla_conditions}")
    print()

    print("2. Creating Execution Plans")

    # Small order - should use standard approach
    small_plan = coordinator.create_execution_plan(
        symbol='AAPL',
        side='buy',
        quantity=50,
        urgency='normal',
        market_data=market_data_aapl
    )
    print(f"   Small AAPL buy (50 shares): {small_plan['recommended_approach']}")
    if small_plan['algorithms']:
        print(f"     Algorithm: {small_plan['algorithms'][0]['name']}")
    print()

    # Medium order - might use smart routing
    medium_plan = coordinator.create_execution_plan(
        symbol='AAPL',
        side='buy',
        quantity=500,
        urgency='normal',
        market_data=market_data_aapl
    )
    print(f"   Medium AAPL buy (500 shares): {medium_plan['recommended_approach']}")
    if medium_plan['algorithms']:
        print(f"     Algorithm: {medium_plan['algorithms'][0]['name']}")
    if medium_plan['warnings']:
        print(f"     Warnings: {medium_plan['warnings']}")
    print()

    # Large order in volatile market - should use advanced approaches
    large_plan = coordinator.create_execution_plan(
        symbol='TSLA',
        side='sell',
        quantity=1500,
        urgency='high',
        market_data=market_data_tsla
    )
    print(f"   Large TSLA sell (1500 shares): {large_plan['recommended_approach']}")
    if large_plan['algorithms']:
        print(f"     Algorithm: {large_plan['algorithms'][0]['name']}")
    if large_plan['order_types']:
        print(f"     Order Types: {[ot['name'] for ot in large_plan['order_types']]}")
    if large_plan['warnings']:
        print(f"     Warnings: {large_plan['warnings']}")
    print()

    print("3. Executing Orders (Simulation)")

    # Execute small order
    small_result = coordinator.execute_order(small_plan['execution_id'])
    print(f"   Small order result: {small_result['status']} "
          f"({small_result.get('filled_quantity', 0)}/{small_plan['quantity']} filled)")
    print()

    # Execute medium order
    medium_result = coordinator.execute_order(medium_plan['execution_id'])
    print(f"   Medium order result: {medium_result['status']} "
          f"({medium_result.get('filled_quantity', 0)}/{medium_plan['quantity']} filled)")
    print()

    # Execute large order
    large_result = coordinator.execute_order(large_plan['execution_id'])
    print(f"   Large order result: {large_result['status']} "
          f"({large_result.get('filled_quantity', 0)}/{large_plan['quantity']} filled)")
    print()

    print("4. Execution Status")
    for exec_id in [small_plan['execution_id'], medium_plan['execution_id'], large_plan['execution_id']]:
        status = coordinator.get_execution_status(exec_id)
        print(f"   {exec_id}: {status['status']}")
    print()

    print("5. Performance Summary")
    perf_summary = coordinator.get_performance_summary()
    print(f"   Components Enabled: {sum(perf_summary['phase_11_components'].values())}/5")
    print(f"   Active Executions: {perf_summary['execution_stats']['active_executions']}")
    print(f"   Completed Executions: {perf_summary['execution_stats']['completed_executions']}")
    print(f"   Failed Executions: {perf_summary['execution_stats']['failed_executions']}")
    print()

    # Shutdown
    print("6. Shutting down coordinator...")
    coordinator.shutdown()
    print("   Coordinator shutdown complete")

    print("\n=== Phase 11 Coordinator Demo Complete ===")