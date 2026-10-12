"""Phase 5 Workflow: Individual Trade Ranking

This workflow implements Phase 5 of the autonomous options trading system:
- Takes ranked opportunities from Phase 4
- Gets market data for each opportunity
- Uses subagents to rank individual trades in parallel (where possible)
- Applies comprehensive trade scoring (quality, risk, context, liquidity)
- Filters and ranks trades by individual trade score
- Outputs ranked list of trades for Phase 6 (Portfolio risk management)

Uses subagents for parallel trade ranking where beneficial.
"""

export const meta = {
  name: 'phase5-individual-trade-ranking',
  description: 'Rank individual trades from opportunities using parallel subagents',
  phases: [
    { title: 'Setup', detail: 'Load ranked opportunities from Phase 4 and prepare' },
    { title: 'Data Download', detail: 'Download market data for all opportunities' },
    { title: 'Trade Ranking', detail: 'Rank individual trades in parallel using subagents' },
    { title: 'Filtering & Output', detail: 'Filter and rank trades for final output' }
  ]
}

// Phase 1: Setup - Load ranked opportunities from Phase 4 and prepare
phase('Setup')

// Load ranked opportunities from Phase 4 system
const phase4Result = await agent(
  `Load ranked opportunities from Phase 4 system`,
  {
    label: 'Load Phase 4 Results',
    phase: 'Setup',
    schema: {
      type: 'object',
      properties: {
        ranked_opportunities: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              symbol: { type: 'string' },
              strategy_type: { type: 'string' },
              long_strike: { type: 'number' },
              short_strike: { type: 'number' },
              expiration_date: { type: 'string', format: 'date-time' },
              days_to_expiry: { type: 'integer' },
              net_debit: { type: 'number' },
              max_profit: { type: 'number' },
              max_loss: { type: 'number' },
              expected_return: { type: 'number' },
              probability_of_profit: { type: 'number' },
              underlying_price: { type: 'number' }
            },
            required: ['symbol', 'strategy_type', 'expected_return']
          }
        },
        source: { type: 'string' }
      },
      required: ['ranked_opportunities']
    }
  }
)

// Prepare data download parameters (using lookback period from config)
const lookbackDays = 100

// Phase 2: Data Download - Get market data for all opportunities
phase('Data Download')

// Download market data for all ranked opportunities
const marketData = await agent(
  `Download market data for ${phase4Result.ranked_opportunities.length} opportunities`,
  {
    label: 'Download Market Data',
    phase: 'Data Download',
    schema: {
      type: 'object',
      additionalProperties: {
        type: 'object',
        properties: {
          date: { type: 'string', format: 'date-time' },
          open: { type: 'number' },
          high: { type: 'number' },
          low: { type: 'number' },
          close: { type: 'number' },
          volume: { type: 'number' },
          adjusted_close: { type: 'number' }
        }
      }
    }
  },
  {
    symbols: phase4Result.ranked_opportunities.map(o => o.symbol),
    lookback_days: lookbackDays
  }
)

// Phase 3: Trade Ranking - Rank individual trades in parallel using subagents
phase('Trade Ranking')

// Create trade ranking tasks for each opportunity
const tradeRankingTasks = phase4Result.ranked_opportunities.map(opportunity => () =>
  agent(
    `Rank individual trade for ${opportunity.symbol}`,
    {
      label: `Trade Rank ${opportunity.symbol}`,
      phase: 'Trade Ranking',
      schema: {
        type: 'object',
        properties: {
          symbol: { type: 'string' },
          individual_trade_score: { type: 'number' },
          trade_quality_score: { type: 'number' },
          risk_score: { type: 'number' },
          context_score: { type: 'number' },
          liquidity_score: { type: 'number' },
          ranking_factors: { type: 'object' }
        },
        required: ['symbol', 'individual_trade_score']
      }
    },
    {
      opportunity: opportunity,
      market_data: marketData[opportunity.symbol] || {},
      lookback_days: lookbackDays
    }
  )
)

// Run all trade ranking tasks in parallel
const tradeRankingResults = await parallel(tradeRankingTasks)

// Flatten and filter results
const rankedTrades = tradeRankingResults
  .filter(result => result !== null && result !== undefined)
  .map(result => ({
    ...result.opportunity, // Spread properties from opportunity
    individual_trade_score: result.individual_trade_score,
    trade_quality_score: result.trade_quality_score,
    risk_score: result.risk_score,
    context_score: result.context_score,
    liquidity_score: result.liquidity_score,
    ranking_factors: result.ranking_factors || {},
    ranking_timestamp: new Date().toISOString()
  }))

console.log(`Ranked ${rankedTrades.length} individual trades`)

// Phase 4: Filtering & Output - Filter and rank trades for final output
phase('Filtering & Output')

// Filter trades by quality criteria
const filteredTrades = rankedTrades
  .filter(trade =>
    trade.individual_trade_score >= 0.5 &&  // Minimum 50% overall score
    trade.risk_score >= 0.4 &&              // Minimum 40% risk score
    trade.liquidity_score >= 0.3            // Minimum 30% liquidity score
  )

// Sort by individual trade score (descending)
const finalRankedTrades = filteredTrades
  .sort((a, b) => b.individual_trade_score - a.individual_trade_score)

// Prepare final output
const output = {
  phase: 'Phase 5 - Individual Trade Ranking',
  timestamp: new Date().toISOString(),
  phase4_source: phase4Result.source || 'unknown',
  opportunities_processed: phase4Result.ranked_opportunities.length,
  trades_ranked: rankedTrades.length,
  trades_filtered: filteredTrades.length,
  trades_output: finalRankedTrades.length,
  top_trades: finalRankedTrades.slice(0, 5), // Top 5 for Phase 6
  all_trades: finalRankedTrades,
  statistics: {
    avg_trade_score: finalRankedTrades.reduce((sum, t) => sum + t.individual_trade_score, 0) / finalRankedTrades.length,
    max_trade_score: Math.max(...finalRankedTrades.map(t => t.individual_trade_score)),
    min_trade_score: Math.min(...finalRankedTrades.map(t => t.individual_trade_score)),
    avg_quality_score: finalRankedTrades.reduce((sum, t) => sum + t.trade_quality_score, 0) / finalRankedTrades.length,
    avg_risk_score: finalRankedTrades.reduce((sum, t) => sum + t.risk_score, 0) / finalRankedTrades.length,
    score_distribution: finalRankedTrades.reduce((acc, trade) => {
      const scoreBand = Math.floor(trade.individual_trade_score * 10) / 10; // 0.0, 0.1, 0.2, etc.
      acc[scoreBand] = (acc[scoreBand] || 0) + 1
      return acc
    }, {})
  }
}

// Save output to file for next phase
const fs = await import('fs')
const path = await import('path')
const outputDir = path.join(process.cwd(), 'trading_bot', 'outputs')
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true })
}
const outputFile = path.join(outputDir, 'phase5_ranked_trades.json')
fs.writeFileSync(outputFile, JSON.stringify(output, null, 2))
console.log(`Phase 5 results saved to ${outputFile}`)

// Log completion
log(`Phase 5 complete: Processed ${phase4Result.ranked_opportunities.length} opportunities, ranked ${rankedTrades.length} trades, output ${finalRankedTrades.length} quality trades`)

// Return the ranked trades for next phase
return output