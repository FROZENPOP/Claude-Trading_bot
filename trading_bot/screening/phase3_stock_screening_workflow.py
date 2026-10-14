"""Phase 3 Workflow: Stock Screening and Ranking

This workflow implements Phase 3 of the autonomous options trading system:
- Takes discovered stocks from Phase 2
- Gets market data for each stock
- Uses subagents to screen stocks in parallel (where possible)
- Calculates research scores using enhanced multi-factor model
- Ranks stocks by research score
- Outputs ranked list for Phase 4 (Option opportunity generation)

Enhanced with better parallel processing, error handling, and adaptive chunking.
"""

export const meta = {
  name: 'phase3-stock-screening-enhanced',
  description: 'Screen and rank discovered stocks using parallel subagents with enhanced error handling',
  phases: [
    { title: 'Setup', detail: 'Load discovered stocks and prepare data download' },
    { title: 'Data Download', detail: 'Download market data for all stocks' },
    { title: 'Screening', detail: 'Screen stocks in parallel using subagents with adaptive chunking' },
    { title: 'Ranking', detail: 'Rank stocks by research score and prepare output' }
  ]
}

// Phase 1: Setup - Load discovered stocks and prepare
phase('Setup')

// Load discovered stocks from Phase 2 discovery system
const discoveryResult = await agent(
  `Load discovered stocks from Phase 2 system`,
  {
    label: 'Load Discovery Results',
    phase: 'Setup',
    schema: {
      type: 'object',
      properties: {
        stocks: { type: 'array', items: { type: 'string' } },
        source: { type: 'string' }
      },
      required: ['stocks']
    }
  }
)

// Prepare date range for data download (last 100 days)
const endDate = new Date().toISOString().split('T')[0]
const startDate = new Date(Date.now() - 100 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]

// Log discovery results
log(`Phase 3 Setup: Loaded ${discoveryResult.stocks.length} stocks from ${discoveryResult.source || 'unknown'} source`)

// Phase 2: Data Download - Get market data for all stocks
phase('Data Download')

// Download market data for all discovered stocks
const marketData = await agent(
  `Download market data for ${discoveryResult.stocks.length} stocks`,
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
    symbols: discoveryResult.stocks,
    start_date: startDate,
    end_date: endDate
  }
)

// Log data download results
const stocksWithData = Object.keys(marketData).filter(symbol => marketData[symbol] && Object.keys(marketData[symbol]).length > 0)
log(`Phase 2 Data Download: Retrieved market data for ${stocksWithData.length}/${discoveryResult.stocks.length} stocks`)

// Phase 3: Screening - Screen stocks in parallel using subagents with adaptive chunking
phase('Screening')

// Determine optimal chunk size based on number of stocks and system capabilities
// Aim for chunks of 10-20 stocks for optimal parallel processing
const stockCount = discoveryResult.stocks.length
const optimalChunkSize = Math.max(10, Math.min(20, Math.ceil(stockCount / 4))) // Target 4 chunks max
const chunks = []

for (let i = 0; i < stockCount; i += optimalChunkSize) {
  chunks.push(discoveryResult.stocks.slice(i, i + optimalChunkSize))
}

log(`Phase 3 Screening: Split ${stockCount} stocks into ${chunks.length} chunks of ~${optimalChunkSize} stocks each`)

// Process each chunk in parallel
const chunkResults = await Promise.all(
  chunks.map((chunk, index) =>
    agent(
      `Screen chunk ${index + 1}/${chunks.length} (${chunk.length} stocks)`,
      {
        label: `Screen Chunk ${index + 1}`,
        phase: 'Screening',
        schema: {
          type: 'object',
          properties: {
            results: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  symbol: { type: 'string' },
                  research_score: { type: 'number' },
                  composite_score: { type: 'number' },
                  signal_strength: { type: 'number' },
                  signal_type: { type: 'string' },
                  signal_confirmation: { type: 'string' },
                  recommendation: { type: 'string' },
                  current_price: { type: 'number' },
                  data_points: { type: 'integer' },
                  timestamp: { type: 'string', format: 'date-time' },
                  filtered: { type: 'boolean' },
                  error: { type: 'boolean' }
                }
              }
            },
            chunk_index: { type: 'integer' },
            stocks_processed: { type: 'integer' },
            stocks_valid: { type: 'integer' },
            stocks_filtered: { type: 'integer' },
            stocks_error: { type: 'integer' }
          },
          required: ['results', 'chunk_index', 'stocks_processed']
        }
      },
      {
        symbols: chunk,
        market_data: chunk.reduce((acc, symbol) => {
          acc[symbol] = marketData[symbol] || {}
          return acc
        }, {}),
        lookback_days: 100
      }
    )
  )
)

// Flatten results from all chunks
const screeningResults = chunkResults.flatMap(chunkResult => chunkResult.results || [])

// Collect statistics from all chunks
const totalProcessed = chunkResults.reduce((sum, chunk) => sum + (chunk.stocks_processed || 0), 0)
const totalValid = chunkResults.reduce((sum, chunk) => sum + (chunk.stocks_valid || 0), 0)
const totalFiltered = chunkResults.reduce((sum, chunk) => sum + (chunk.stocks_filtered || 0), 0)
const totalErrors = chunkResults.reduce((sum, chunk) => sum + (chunk.stocks_error || 0), 0)

// Filter out any failed screenings (null/undefined results)
const validResults = screeningResults.filter(result => result !== null && result !== undefined)

// Log screening results
log(`Phase 3 Screening: Processed ${totalProcessed} stocks`)
log(`  Valid: ${totalValid}, Filtered: ${totalFiltered}, Errors: ${totalErrors}`)

// Phase 4: Ranking - Rank stocks by research score and prepare output
phase('Ranking')

// Sort stocks by research score (descending)
const rankedResults = validResults
  .sort((a, b) => b.research_score - a.research_score)

// Prepare final output
const topN = args?.top_n ?? 20; // Default to 20 if not specified
const output = {
  phase: 'Phase 3 - Stock Screening and Ranking (Enhanced)',
  timestamp: new Date().toISOString(),
  discovery_source: discoveryResult.source || 'unknown',
  stocks_screened: discoveryResult.stocks.length,
  stocks_with_market_data: stocksWithData.length,
  stocks_processed: totalProcessed,
  stocks_valid: totalValid,
  stocks_filtered: totalFiltered,
  stocks_error: totalErrors,
  stocks_ranked: rankedResults.length,
  top_stocks: rankedResults.slice(0, topN), // Top N for Phase 4 (configurable)
  all_results: rankedResults,
  statistics: {
    avg_research_score: rankedResults.length > 0
      ? rankedResults.reduce((sum, r) => sum + r.research_score, 0) / rankedResults.length
      : 0,
    max_research_score: rankedResults.length > 0
      ? Math.max(...rankedResults.map(r => r.research_score))
      : 0,
    min_research_score: rankedResults.length > 0
      ? Math.min(...rankedResults.map(r => r.research_score))
      : 0,
    recommendation_distribution: rankedResults.reduce((acc, r) => {
      acc[r.recommendation] = (acc[r.recommendation] || 0) + 1
      return acc
    }, {}),
    confirmation_distribution: rankedResults.reduce((acc, r) => {
      acc[r.signal_confirmation || 'unknown'] = (acc[r.signal_confirmation || 'unknown'] || 0) + 1
      return acc
    }, {}),
    avg_factor_scores: {
      technical: rankedResults.length > 0
        ? rankedResults.reduce((sum, r) => sum + (r.factor_scores?.technical || 0), 0) / rankedResults.length
        : 0,
      fundamental: rankedResults.length > 0
        ? rankedResults.reduce((sum, r) => sum + (r.factor_scores?.fundamental || 0), 0) / rankedResults.length
        : 0,
      quality: rankedResults.length > 0
        ? rankedResults.reduce((sum, r) => sum + (r.factor_scores?.quality || 0), 0) / rankedResults.length
        : 0,
      sentiment: rankedResults.length > 0
        ? rankedResults.reduce((sum, r) => sum + (r.factor_scores?.sentiment || 0), 0) / rankedResults.length
        : 0,
      volume_liquidity: rankedResults.length > 0
        ? rankedResults.reduce((sum, r) => sum + (r.factor_scores?.volume_liquidity || 0), 0) / rankedResults.length
        : 0
    }
  }
}

// Log completion
log(`Phase 3 Complete: Screened ${discoveryResult.stocks.length} stocks, ranked ${rankedResults.length} valid results`)
log(`Top 5 stocks: ${rankedResults.slice(0, 5).map(r => `${r.symbol} (${r.research_score.toFixed(3)} - ${r.recommendation})`).join(', ')}`)

// Return the ranked results for next phase
return output