"""Fed Funds Futures Strategy Planner V2 — FastAPI backend."""

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="FF Strategy Planner V2", version="2.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

CFG = json.loads(Path("strategy_config.json").read_text())


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PlanRequest(BaseModel):
    product:    str
    timeframe:  str   = "1D"
    strategy:   str   = "auto"
    risk_usd:   float = 500.0

class BacktestRequest(BaseModel):
    product:    str
    timeframe:  str   = "1D"
    strategy:   str   = "auto"
    risk_usd:   float = 500.0
    lookback:   int   = 150


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "config": CFG,
    })


@app.get("/api/config")
async def get_config():
    return JSONResponse(CFG)


@app.get("/api/chart-data")
async def chart_data(product: str, timeframe: str = "1D"):
    """Return OHLCV + indicator data for the chart."""
    from services.qh_api import get_ohlcv, build_spread
    from services.indicators import compute_all

    spread_def = next((s for s in CFG["spreads"] if s["name"] == product), None)

    try:
        if spread_def:
            df = build_spread(spread_def["leg1"], spread_def["leg2"], timeframe)
        else:
            df = get_ohlcv(product, timeframe)

        indics = compute_all(df)
        tail = df.tail(300)

        ohlcv = [
            {
                "time":  int(ts.timestamp()),
                "open":  round(float(row["open"]), 5),
                "high":  round(float(row["high"]), 5),
                "low":   round(float(row["low"]), 5),
                "close": round(float(row["close"]), 5),
                "volume": int(row["volume"]),
            }
            for ts, row in tail.iterrows()
        ]

        ind_out = {}
        for name, series in indics.items():
            s = series.reindex(tail.index).dropna()
            ind_out[name] = [
                {"time": int(ts.timestamp()), "value": round(float(v), 5)}
                for ts, v in s.items()
            ]

        return JSONResponse({"ohlcv": ohlcv, "indicators": ind_out})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-plan")
async def generate_plan(req: PlanRequest):
    from services.planner import generate_plan as _gen

    spread_def = next((s for s in CFG["spreads"] if s["name"] == req.product), None)
    is_spread = spread_def is not None

    try:
        plan = _gen(
            product    = req.product,
            timeframe  = req.timeframe,
            strategy   = req.strategy,
            risk_usd   = req.risk_usd,
            is_spread  = is_spread,
            spread_def = spread_def,
        )
        return JSONResponse(plan)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backtest")
async def run_backtest(req: BacktestRequest):
    from services.backtest import run_backtest as _bt

    spread_def = next((s for s in CFG["spreads"] if s["name"] == req.product), None)
    is_spread = spread_def is not None

    try:
        result = _bt(
            product    = req.product,
            timeframe  = req.timeframe,
            strategy   = req.strategy,
            risk_usd   = req.risk_usd,
            is_spread  = is_spread,
            spread_def = spread_def,
            lookback   = req.lookback,
        )
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
