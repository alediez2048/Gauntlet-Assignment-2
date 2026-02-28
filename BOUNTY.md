# Polyfolio — Bounty Submission

## Customer

Crypto-native retail investors who want a unified view of their traditional portfolio alongside prediction market positions. These users actively trade on Polymarket and need a single dashboard to track both conventional assets and event-based positions.

## Feature

**Polymarket Prediction Market Integration** — browse, search, and analyze live prediction markets from Polymarket directly within Polyfolio. Users can:

- **Browse** active prediction markets with real-time odds, volume, and outcomes
- **Search** markets by keyword or category (Crypto, Politics, Economics)
- **Analyze** individual markets with detailed bid/ask spreads and volume data
- **Track positions** — full CRUD for Polymarket positions stored as orders with `DataSource.POLYMARKET`
- **AI-powered insights** — the agent chat routes prediction market queries automatically using keyword and LLM-based routing with 6 eval cases

## Data Source

**Polymarket Gamma API** (`https://gamma-api.polymarket.com`)

The agent accesses Polymarket data through the open-source project's NestJS API layer (`/api/v1/polymarket/*`), which proxies requests to the Gamma API. This ensures all data flows through the application's existing auth and middleware stack.

### Gamma API fields used

`question`, `slug`, `outcomes`, `outcomePrices`, `volume24hr`, `category`, `endDate`, `description`, `active`, `lastTradePrice`, `bestBid`, `bestAsk`

## Architecture

### Backend (NestJS)

- `PolymarketModule` with service, controller, and Prisma integration
- 5 REST endpoints: `GET /markets`, `GET /markets/:slug`, `POST /positions`, `GET /positions`, `DELETE /positions/:id`
- Position CRUD creates `SymbolProfile` (dataSource: POLYMARKET) and `Order` records

### Agent (Python/FastAPI)

- `explore_prediction_markets` tool with 4 actions: browse, search, analyze, positions
- `PredictionMarketInput` Pydantic schema for validation
- Full integration across 11 touch points in the routing/orchestration layer
- 9 unit tests + 6 eval cases (69 total)

### Frontend (Angular)

- Neobrutalist design system applied globally via Material component overrides
- Blue (#1d4ed8) / Purple (#7c3aed) color palette
- Dark mode support for all neobrutalist elements

## Impact

Polyfolio is the first unified portfolio tracker that combines traditional asset management with prediction market tracking, powered by an AI agent. This bridges the gap between DeFi event markets and conventional portfolio analysis, giving crypto-native investors a single source of truth for all their positions.

## Stateful CRUD

Prediction market positions are persisted in the database via Prisma:

- **Create**: `POST /api/v1/polymarket/positions` — upserts SymbolProfile + creates Order
- **Read**: `GET /api/v1/polymarket/positions` — lists user's POLYMARKET orders with SymbolProfile
- **Delete**: `DELETE /api/v1/polymarket/positions/:id` — removes order (ownership-checked)
