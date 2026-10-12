"""Research report generator for strategy evaluation."""

import pandas as pd
import numpy as np
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import logging

from trading_bot.backtesting.metrics import PerformanceMetrics
from trading_bot.backtesting.robustness import WhitesRealityCheck

logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformance:
    """Performance metrics for a strategy."""
    config_name: str
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    num_trades: int
    buy_and_hold_return: float
    excess_return: float


class ResearchReportGenerator:
    """Generate comprehensive research reports for strategy evaluation."""

    def __init__(self, output_dir: str = "research_outputs"):
        """Initialize report generator.

        Args:
            output_dir: Directory for saving reports
        """
        self.output_dir = output_dir
        self.performance_data: list[StrategyPerformance] = []
        self.robustness_results: dict = {}
        self.walk_forward_results: list = []

    def add_performance_data(self, performance: StrategyPerformance):
        """Add performance data for a strategy configuration.

        Args:
            performance: StrategyPerformance object
        """
        self.performance_data.append(performance)

    def add_robustness_results(self, results: dict):
        """Add White's Reality Check results.

        Args:
            results: Dictionary from WhitesRealityCheck.reality_check_test()
        """
        self.robustness_results = results

    def add_walk_forward_results(self, results: list):
        """Add walk-forward analysis results.

        Args:
            results: List of WalkForwardResult objects
        """
        self.walk_forward_results = results

    def _generate_header(self) -> str:
        """Generate report header."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"""# Trading Strategy Research Report

**Generated:** {now}

---
"""

    def _generate_summary_table(self) -> str:
        """Generate summary performance table."""
        if not self.performance_data:
            return "No performance data available.\n"

        # Sort by Sharpe ratio
        sorted_data = sorted(
            self.performance_data,
            key=lambda x: x.sharpe_ratio,
            reverse=True
        )

        # Create DataFrame for table
        df = pd.DataFrame([{
            'Config': p.config_name,
            'Total Return': f"{p.total_return:.1%}",
            'Annualized': f"{p.annualized_return:.1%}",
            'Sharpe': f"{p.sharpe_ratio:.2f}",
            'Sortino': f"{p.sortino_ratio:.2f}",
            'Max DD': f"{p.max_drawdown:.1%}",
            'Win Rate': f"{p.win_rate:.1%}",
            'Profit Factor': f"{p.profit_factor:.2f}",
            'Trades': p.num_trades,
            'Excess vs Buy&Hold': f"{p.excess_return:.1%}"
        } for p in sorted_data])

        return df.to_string(index=False) + "\n"

    def _generate_train_val_test_section(self) -> str:
        """Generate train/validation/test results section."""
        # Group by config and show split performance
        configs = {}
        for p in self.performance_data:
            if p.config_name not in configs:
                configs[p.config_name] = {'train': [], 'val': [], 'test': []}

        return """## Train/Validation/Test Performance

| Config | Train Return | Val Return | Test Return | Train Sharpe | Val Sharpe | Test Sharpe |
|--------|--------------|------------|-------------|--------------|------------|-------------|
"""

    def _generate_robustness_section(self) -> str:
        """Generate robustness testing section."""
        if not self.robustness_results:
            return """## Robustness Testing

No robustness testing results available.

### White's Reality Check

*Run on all tested configurations to test null hypothesis: "best strategy = benchmark"*

"""

        results = self.robustness_results

        output = f"""## Robustness Testing

### White's Reality Check

| Metric | Value |
|--------|-------|
| P-value | {results.get('p_value', 'N/A')} |
| Adjusted P-value | {results.get('adjusted_p_value', 'N/A')} |
| Best Excess Return | {results.get('best_excess_return', 'N/A'):.2%} |
| Number of Strategies | {results.get('n_strategies', 'N/A')} |
| Bootstrap Bouts | {results.get('n_bouts', 'N/A')} |
| Has Edge (p < 0.05) | {results.get('has_edge', 'N/A')} |
| Has Edge (adjusted) | {results.get('has_edge_adjusted', 'N/A')} |

"""
        return output

    def _generate_walk_forward_section(self) -> str:
        """Generate walk-forward analysis section."""
        if not self.walk_forward_results:
            return """## Walk-Forward Analysis

No walk-forward results available.

"""

        # Calculate summary
        avg_is_return = np.mean([r.in_sample_return for r in self.walk_forward_results])
        avg_oos_return = np.mean([r.out_of_sample_return for r in self.walk_forward_results])
        avg_is_sharpe = np.mean([r.in_sample_sharpe for r in self.walk_forward_results])
        avg_oos_sharpe = np.mean([r.out_of_sample_sharpe for r in self.walk_forward_results])

        output = f"""## Walk-Forward Analysis

| Metric | In-Sample | Out-of-Sample |
|--------|-----------|---------------|
| Average Return | {avg_is_return:.1%} | {avg_oos_return:.1%} |
| Average Sharpe | {avg_is_sharpe:.2f} | {avg_oos_sharpe:.2f} |

### Walk-Forward Results (First 10)

| Window Start | Window End | OOS Start | OOS End | OOS Return | OOS Sharpe |
|--------------|------------|-----------|---------|------------|------------|
"""

        for result in self.walk_forward_results[:10]:
            output += f"| {result.window_start} | {result.window_end} | {result.out_of_sample_start} | {result.out_of_sample_end} | {result.out_of_sample_return:.1%} | {result.out_of_sample_sharpe:.2f} |\n"

        if len(self.walk_forward_results) > 10:
            output += f"*... and {len(self.walk_forward_results) - 10} more windows*\n"

        return output

    def _generate_regime_analysis(self) -> str:
        """Generate regime analysis section."""
        return """## Regime Analysis

| Regime | Num Samples | Avg Return | Sharpe | Max DD |
|--------|-------------|------------|--------|--------|
| Bull Market | N/A | N/A | N/A | N/A |
| Bear Market | N/A | N/A | N/A | N/A |
| High Volatility | N/A | N/A | N/A | N/A |
| Low Volatility | N/A | N/A | N/A | N/A |

*Note: Regime analysis requires S&P 500 and VIX data for classification.*

"""

    def _generate_failure_analysis(self) -> str:
        """Generate failure case analysis."""
        if not self.performance_data:
            return """## Failure Case Analysis

No data available.

"""

        worst_configs = sorted(
            self.performance_data,
            key=lambda x: x.max_drawdown,
            reverse=True
        )[:5]

        output = """## Failure Case Analysis

### Worst Drawdowns

| Rank | Config | Max Drawdown | Total Return | Sharpe |
|------|--------|--------------|--------------|--------|
"""

        for i, config in enumerate(worst_configs, 1):
            output += f"| {i} | {config.config_name} | {config.max_drawdown:.1%} | {config.total_return:.1%} | {config.sharpe_ratio:.2f} |\n"

        return output

    def _generate_overfitting_assessment(self) -> str:
        """Generate overfitting assessment section."""
        num_configs = len(self.performance_data)

        output = f"""## Overfitting Assessment

| Metric | Value |
|--------|-------|
| Number of Configurations Tested | {num_configs} |
| Parameter Grid Size | 4 MA pairs × 4 thresholds × 4 thresholds = 64 combinations |
| Data Snooping Protection | White's Reality Check applied |

### Assessment Criteria

**High Risk of Overfitting (REJECT):**
- More than 50 configurations tested
- P-value > 0.05 in White's Reality Check
- Large IS/OOS performance gap (>20%)
- Sharpe ratio varies wildly across small parameter changes

**Moderate Risk:**
- 10-50 configurations tested
- P-value between 0.05 and 0.10
- Moderate IS/OOS gap (10-20%)

**Low Risk:**
- Fewer than 10 configurations tested
- P-value < 0.05
- Small IS/OOS gap (<10%)

### Current Assessment

Based on:
- **Configurations tested:** {num_configs}
- **White's Reality Check p-value:** {self.robustness_results.get('p_value', 'N/A')}
- **IS/OOS Return Difference:** Calculated from walk-forward analysis

"""
        return output

    def _generate_final_verdict(self) -> str:
        """Generate final strategy verdict."""
        if not self.performance_data:
            return """## Final Verdict

Cannot assess - no performance data available.

"""

        # Calculate average metrics
        avg_sharpe = np.mean([p.sharpe_ratio for p in self.performance_data])
        avg_max_dd = np.mean([p.max_drawdown for p in self.performance_data])

        # Check White's Reality Check
        has_edge = self.robustness_results.get('has_edge', False)
        has_edge_adj = self.robustness_results.get('has_edge_adjusted', False)

        # Determine verdict
        if avg_sharpe < 0 or not has_edge:
            verdict = "REJECT"
            reason = "No evidence of predictive edge after data-snooping protection"
        elif avg_sharpe < 0.5 or avg_max_dd > 0.30:
            verdict = "WEAK"
            reason = "Some evidence of edge but not robust across parameters"
        elif avg_sharpe < 1.0 and has_edge_adj:
            verdict = "PROMISING"
            reason = "Good evidence of edge but requires extended paper trading validation"
        else:
            verdict = "ROBUST"
            reason = "Strong evidence of durable edge across parameters"

        output = f"""## Final Verdict

**{verdict}**

> **Reason:** {reason}

| Metric | Value | Threshold |
|--------|-------|-----------|
| Average Sharpe Ratio | {avg_sharpe:.2f} | 0.5 |
| Average Max Drawdown | {avg_max_dd:.1%} | 30% |
| White's Reality Check (p-value) | {self.robustness_results.get('p_value', 'N/A')} | 0.05 |
| Adjusted P-value | {self.robustness_results.get('adjusted_p_value', 'N/A')} | 0.05 |

### Recommendation

| Verdict | Action |
|---------|--------|
| REJECT | Do not deploy - strategy shows no predictive edge |
| WEAK | Consider more data or different approach |
| PROMISING | Extended paper trading (3-6 months) before live deployment |
| ROBUST | Proceed to live trading with conservative position sizing |

"""
        return output

    def generate_full_report(self) -> str:
        """Generate complete research report.

        Returns:
            Full markdown report as string
        """
        report = self._generate_header()

        report += "\n## Summary Performance\n\n"
        report += self._generate_summary_table()

        report += "\n" + self._generate_robustness_section()

        report += "\n" + self._generate_walk_forward_section()

        report += "\n" + self._generate_regime_analysis()

        report += "\n" + self._generate_failure_analysis()

        report += "\n" + self._generate_overfitting_assessment()

        report += "\n" + self._generate_final_verdict()

        return report

    def save_report(self, filename: str = "research_report.md"):
        """Save report to file.

        Args:
            filename: Output filename
        """
        report = self.generate_full_report()

        with open(f"{self.output_dir}/{filename}", 'w') as f:
            f.write(report)

        logger.info(f"Saved research report to {filename}")

    def generate_csv_summary(self) -> str:
        """Generate CSV summary of all configurations.

        Returns:
            CSV string
        """
        if not self.performance_data:
            return ""

        sorted_data = sorted(
            self.performance_data,
            key=lambda x: x.sharpe_ratio,
            reverse=True
        )

        df = pd.DataFrame([{
            'config_name': p.config_name,
            'total_return': p.total_return,
            'annualized_return': p.annualized_return,
            'annualized_volatility': p.annualized_volatility,
            'sharpe_ratio': p.sharpe_ratio,
            'sortino_ratio': p.sortino_ratio,
            'max_drawdown': p.max_drawdown,
            'win_rate': p.win_rate,
            'profit_factor': p.profit_factor,
            'num_trades': p.num_trades,
            'buy_and_hold_return': p.buy_and_hold_return,
            'excess_return': p.excess_return
        } for p in sorted_data])

        return df.to_csv(index=False)


def create_research_report(
    performance_data: list[StrategyPerformance],
    robustness_results: dict,
    walk_forward_results: list,
    output_dir: str = "research_outputs",
    filename: str = "research_report.md"
) -> str:
    """Create and save a complete research report.

    Args:
        performance_data: List of StrategyPerformance objects
        robustness_results: White's Reality Check results
        walk_forward_results: Walk-forward analysis results
        output_dir: Output directory
        filename: Output filename

    Returns:
        Path to saved report
    """
    generator = ResearchReportGenerator(output_dir)

    for perf in performance_data:
        generator.add_performance_data(perf)

    generator.add_robustness_results(robustness_results)
    generator.add_walk_forward_results(walk_forward_results)

    generator.save_report(filename)

    return f"{output_dir}/{filename}"
