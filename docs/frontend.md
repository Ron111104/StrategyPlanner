# Frontend Documentation

> Jinja2 template structure, Alpine.js reactive state, HTMX partial updates, TailwindCSS styling, and chart rendering.

---

## 1. Architecture Overview

The frontend is a **server-rendered** application with no build tools. All interactivity is provided by CDN-loaded libraries:

| Library | Version | CDN | Role |
|---|---|---|---|
| Alpine.js | 3.x | `cdn.jsdelivr.net/npm/alpinejs` | Reactive state management, DOM binding |
| HTMX | 1.x | `unpkg.com/htmx.org` | Partial page updates without full reload |
| TailwindCSS | 3.x | `cdn.tailwindcss.com` | Utility-first CSS framework |
| TradingView Lightweight Charts | 4.x | `unpkg.com/lightweight-charts` | Candlestick chart rendering |

### Why No Build Tools

- No `npm`, no `node_modules`, no `webpack`, no `vite`
- Zero frontend build step — templates are rendered server-side by Jinja2
- CDN libraries are loaded in `<script>` tags in the base layout
- Custom JavaScript lives in `app/static/js/` and is served as static files

---

## 2. Template Structure

```
app/templates/
├── layouts/
│   └── base.html          # Master layout with nav, sidebar, CDN imports
├── components/
│   ├── regime_badge.html   # Regime status indicator
│   ├── signal_card.html    # Strategy signal card
│   └── spread_row.html     # Spread quote table row
├── dashboard/
│   └── index.html          # Main dashboard page
├── strategy/
│   └── index.html          # Strategy planner page
├── risk/
│   └── index.html          # Risk manager page
├── ladder/
│   └── index.html          # Ladder planner page
└── replay/
    └── index.html          # Replay engine page
```

### Base Layout (`layouts/base.html`)

The base template defines:

1. **HTML head** — meta tags, TailwindCSS CDN, custom CSS
2. **Sidebar navigation** — Links to Dashboard, Strategy, Ladder, Risk, Replay
3. **Main content area** — `{% block content %}` for page-specific content
4. **Script imports** — Alpine.js, HTMX, TradingView LWC, custom JS files
5. **Dark theme** — `bg-gray-900 text-gray-100` base classes

### Navigation

The sidebar includes links for all pages:

```html
<a href="/" class="...">Dashboard</a>
<a href="/strategy" class="...">Strategy</a>
<a href="/ladder" class="...">Ladder</a>
<a href="/risk" class="...">Risk</a>
<a href="/replay" class="...">Replay</a>
```

---

## 3. Alpine.js Usage

Alpine.js provides reactive state management within each page. Each page defines an `x-data` component with state and methods.

### Pattern

```html
<div x-data="pageComponent()">
  <select x-model="selectedSymbol">
    <template x-for="sym in symbols">
      <option x-text="sym" :value="sym"></option>
    </template>
  </select>
  <button @click="generate()">Generate</button>
  <div x-show="loading">Loading...</div>
  <div x-show="result">
    <span x-text="result.avg_entry"></span>
  </div>
</div>

<script>
function pageComponent() {
  return {
    selectedSymbol: '',
    symbols: [],
    loading: false,
    result: null,
    async generate() {
      this.loading = true;
      const resp = await fetch('/api/endpoint', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ symbol: this.selectedSymbol })
      });
      this.result = await resp.json();
      this.loading = false;
    }
  }
}
</script>
```

### Key Directives Used

| Directive | Purpose | Example |
|---|---|---|
| `x-data` | Define reactive component state | `x-data="ladderPanel()"` |
| `x-model` | Two-way binding to form inputs | `x-model="symbol"` |
| `x-show` | Conditional display | `x-show="ladder !== null"` |
| `x-for` | Loop rendering | `x-for="level in ladder.levels"` |
| `x-text` | Text content binding | `x-text="level.entry_price"` |
| `@click` | Event handler | `@click="generate()"` |
| `:class` | Dynamic CSS classes | `:class="{'text-green-400': direction === 'long'}"` |

---

## 4. Ladder Page (`ladder/index.html`)

The ladder page is the most complex frontend component.

### State (`app/static/js/ladder.js`)

```javascript
function ladderPanel() {
  return {
    // Form state
    product: 'fed_funds',
    symbol: '',
    timeframe: '1H',
    strategy: '',
    direction: '',
    maxLevels: 5,
    // Data
    availableSymbols: [],
    strategies: [],
    ladder: null,
    mtf: null,
    loading: false,
    error: '',
    // Methods
    async init() { ... },
    async loadStrategies() { ... },
    async loadContracts() { ... },
    async generate() { ... },
    async loadMTF() { ... },
  }
}
```

### Generate Flow

1. User selects product, symbol, timeframe, strategy
2. Clicks "Generate Ladder" button
3. `generate()` calls `POST /ladder/generate` with JSON body
4. Response updates `this.ladder` state
5. Alpine.js reactively renders:
   - Ladder levels table
   - Summary panel (avg entry, stop, targets, R:R)
   - Context panel (regime, vol percentile, MTF score)
6. Optionally calls `loadMTF()` for multi-timeframe analysis

### Rendered Components

**Ladder Table:**

| Level | Entry Price | Lots | Cumulative | Distance | Risk $ |
|---|---|---|---|---|---|
| 1 | 95.500 | 7 | 7 | 0.000 | $0 |
| 2 | 95.485 | 11 | 18 | 0.015 | $34 |
| ... | ... | ... | ... | ... | ... |

**Summary Panel:**
- Average entry, total lots
- Stop price, stop distance (ticks)
- Target 1, Target 2
- Risk/Reward ratio
- Total risk USD, total reward USD

**Context Panel:**
- Active regime and macro bias
- Spacing method and value
- Volatility percentile
- MTF alignment score
- Confidence score

---

## 5. Dashboard Page

The dashboard provides an overview of:

1. **Regime Badge** — Current regime type and macro bias with color coding
2. **Market Snapshots** — Table of latest prices for all cached contracts
3. **Spread Quotes** — Table of all cached spread quotes in basis points
4. **Signal Cards** — Latest strategy signals with direction, confidence, entry/stop/target
5. **Chart** — TradingView Lightweight Charts candlestick chart for the selected symbol

### Chart Rendering

```javascript
const chart = LightweightCharts.createChart(container, {
  layout: { background: { color: '#1a1a2e' }, textColor: '#e0e0e0' },
  grid: { vertLines: { color: '#2a2a3e' }, horzLines: { color: '#2a2a3e' } },
  timeScale: { timeVisible: true },
});

const series = chart.addCandlestickSeries({
  upColor: '#26a69a',
  downColor: '#ef5350',
  borderVisible: false,
  wickUpColor: '#26a69a',
  wickDownColor: '#ef5350',
});

// Fetch OHLCV data
const resp = await fetch(`/market-data/ohlcv/${symbol}/${timeframe}`);
const data = await resp.json();
series.setData(data.bars.map(b => ({
  time: b.timestamp,
  open: b.open,
  high: b.high,
  low: b.low,
  close: b.close,
})));
```

---

## 6. HTMX Usage

HTMX is used for partial page updates without full navigation:

### Regime Badge Refresh

```html
<div hx-get="/components/regime-badge"
     hx-trigger="every 30s"
     hx-swap="innerHTML">
  <!-- Regime badge content auto-refreshes -->
</div>
```

### Signal Card Updates

```html
<div hx-post="/strategy/evaluate"
     hx-target="#signal-cards"
     hx-swap="innerHTML"
     hx-trigger="click from:#evaluate-btn">
</div>
```

---

## 7. Styling Conventions

### Dark Terminal Theme

All pages use a dark background with light text:

```
bg-gray-900    — Page background
bg-gray-800    — Card/panel backgrounds
bg-gray-700    — Input fields, hover states
text-gray-100  — Primary text
text-gray-400  — Secondary text
text-green-400 — Positive values, LONG direction
text-red-400   — Negative values, SHORT direction
text-yellow-400 — Warnings, EVENT regime
text-blue-400  — Links, TREND regime
```

### Responsive Grid

Pages use TailwindCSS grid for layout:

```html
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  <div class="bg-gray-800 rounded-lg p-4">Panel 1</div>
  <div class="bg-gray-800 rounded-lg p-4">Panel 2</div>
  <div class="bg-gray-800 rounded-lg p-4">Panel 3</div>
</div>
```

---

## 8. Frontend → Backend Interaction

All data flows through REST API calls:

| User Action | Frontend Call | Backend Handler |
|---|---|---|
| Load page | GET `/` | `pages.dashboard()` → Jinja2 render |
| Fetch market data | POST `/market-data/ingest` | `market_data.ingest_market_data()` |
| Change regime | PUT `/regime/update` | `regime.update_regime()` |
| Evaluate strategies | POST `/strategy/evaluate` | `strategy.evaluate_strategies()` |
| Generate ladder | POST `/ladder/generate` | `ladder.generate_ladder()` |
| Load MTF analysis | GET `/ladder/mtf/{sym}/{tf}` | `ladder.mtf_analysis()` |
| Load chart data | GET `/market-data/ohlcv/{sym}/{tf}` | `market_data.get_ohlcv()` |

---

## 9. Static File Serving

Static files are served from `app/static/` via FastAPI's `StaticFiles` mount:

```python
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
```

In templates:
```html
<script src="/static/js/ladder.js"></script>
<script src="/static/js/api.js"></script>
<script src="/static/js/chart.js"></script>
```
