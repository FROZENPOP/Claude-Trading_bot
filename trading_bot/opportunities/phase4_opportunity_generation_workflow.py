"""Phase 4 Workflow: Option Opportunity Generation

This workflow implements Phase 4 of the autonomous options trading system:
- Takes ranked stock list from Phase 3
- Gets market data for each stock
- Uses subagents to generate options opportunities in parallel (where possible)
- Applies existing options strategies to identify high-probability trades
- Filters and ranks opportunities by expected return and probability
- Outputs ranked list of opportunities for Phase 5 (Individual trade ranking)

Uses subagents for parallel opportunity generation where beneficial.
"""

export const meta = {
  name: 'phase4-option-opportunity-generation',
  description: 'Generate options opportunities from ranked stocks using parallel subagents',
  phases: [
    { title: 'Setup', detail: 'Load ranked stocks from Phase 3 and prepare data download' },
    { title: 'Data Download', detail: 'Download market data for all ranked stocks' },
    { title: 'Opportunity Generation', detail: 'Generate options opportunities in parallel using subagents' },
    { title: 'Filtering & Ranking', detail: 'Filter and rank opportunities by quality metrics' }
  ]
}

// Phase 1: Setup - Load ranked stocks from Phase 3 and prepare
phase('Setup')

// Load ranked stocks from Phase 3 system
// In a real implementation, this would read from the output of Phase 3 workflow
const phase3Result = await agent(
  `Load ranked stocks from Phase 3 system`,
  {
    label: 'Load Phase 3 Results',
    phase: 'Setup',
    schema: {
      type: 'object',
      properties: {
        ranked_stocks: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              symbol: { type: 'string' },
              research_score: { type: 'number' },
              recommendation: { type: 'string' },
              current_price: { type: 'number' },
              signal_strength: { type: 'number' }
            },
            required: ['symbol', 'research_score', 'recommendation']
          }
        },
        source: { type: 'string' }
      },
      required: ['ranked_stocks']
    }
  }
)

// Prepare date range for data download (last 100 days for technical analysis)
const endDate = new Date().toISOString().split('T')[0]
const startDate = new Date(Date.now() - 100 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]

// Phase 2: Data Download - Get market data for all ranked stocks
phase('Data Download')

// Download market data for all ranked stocks
const marketData = await agent(
  `Download market data for ${phase3Result.ranked_stocks.length} stocks`,
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
    symbols: phase3Result.ranked_stocks.map(s => s.symbol),
    start_date: startDate,
    end_date: endDate
  }
)

// Phase 3: Opportunity Generation - Generate opportunities in parallel using subagents
phase('Opportunity Generation')

// Create opportunity generation tasks for each stock
const opportunityTasks = phase3Result.ranked_stocks.map(stock => () =>
  agent(
    `Generate options opportunities for ${stock.symbol}`,
    {
      label: `Opportunities ${stock.symbol}`,
      phase: 'Opportunity Generation',
      schema: {
        type: 'object',
        properties: {
          symbol: { type: 'string' },
          opportunities: {
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
          }
        },
        required: ['symbol', 'opportunities']
      }
    },
    {
      symbol: stock.symbol,
      stock_data: stock,
      market_data: marketData[stock.symbol] || {},
      lookback_days: 100
    }
  )
)

// Run all opportunity generation tasks in parallel
const opportunityResults = await parallel(opportunityTasks)

// Flatten and filter results
const allOpportunities = opportunityResults
  .filter(result => result !== null && result !== undefined)
  .reduce((acc, result) => acc.concat(result.opportunities || []), [])

console.log(`Generated ${allOpportunities.length} raw opportunities`)

// Phase 4: Filtering & Ranking - Filter and rank opportunities by quality metrics
phase('Filtering & Ranking')

// Filter opportunities by quality criteria
const filteredOpportunities = allOpportunities
  .filter(opp =>
    opp.expected_return >= 0.05 &&  // Minimum 5% return
    opp.probability_of_profit >= 0.6 &&  // Minimum 60% probability
    opp.days_to_expiry >= 7 &&  // Minimum 1 week to expiry
    opp.days_to_expiry <= 45   // Maximum 6 weeks to expiry
  )

// Sort by expected return (descending) then by probability of profit
const rankedOpportunities = filteredOpportunities
  .sort((a, b) => {
    // Primary sort: expected return (higher is better)
    if (b.expected_return !== a.expected_return) {
      return b.expected_return - a.expected_return;
    }
    // Secondary sort: probability of profit (higher is better)
    return b.probability_of_profit - a.probability_of_profit;
  })

// Prepare final output
const output = {
  phase: 'Phase 4 - Option Opportunity Generation',
  timestamp: new Date().toISOString(),
  phase3_source: phase3Result.source || 'unknown',
  stocks_processed: phase3Result.ranked_stocks.length,
  opportunities_generated: allOpportunities.length,
  opportunities_filtered: filteredOpportunities.length,
  opportunities_ranked: rankedOpportunities.length,
  top_opportunities: rankedOpportunities.slice(0, 10), // Top 10 for Phase 5
  all_opportunities: rankedOpportunities,
  statistics: {
    avg_expected_return: rankedOpportunities.reduce((sum, o) => sum + o.expected_return, 0) / rankedOpportunities.length,
    max_expected_return: Math.max(...rankedOpportunities.map(o => o.expected_return)),
    min_expected_return: Math.min(...rankedOpportunities.map(o => o.expected_return)),
    avg_probability: rankedOpportunities.reduce((sum, o) => sum + o.probability_of_profit, 0) / rankedOpportunities.length,
    strategy_distribution: rankedOpportunities.reduce((acc, opp) => {
      acc[opp.strategy_type] = (acc[opp.strategy_type] || 0) + 1
      return acc
    }, {})
  }
}

// Log completion
log(`Phase 4 complete: Processed ${phase3Result.ranked_stocks.length} stocks, generated ${allOpportunities.length} opportunities, ranked ${rankedOpportunities.length} high-quality opportunities`)

// Return the ranked opportunities for next phase
return output