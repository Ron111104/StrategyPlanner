"""V2 Backtest Engine — realistic ladder simulation with trade lifecycle.

Simulates: sequential fills, partial exits, MAE/MFE, full PnL tracking.
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

from services.qh_api import get_ohlcv, build_spread
from services.indicators import compute_all
from services.planner import (
    detect_execution_state, select_strategy, build_adaptive_ladder,
    classify_trade_type, TICK, TICK_VAL, CFG
)


# ===========================================================================
# TRADE LIFECYCLE STATE MACHINE
# ===========================================================================

class LadderTrade:
    """Simulates a single ladder trade through its lifecycle:
    planned → opened → scaled → trimmed → closed
    """

    def __init__(self, direction: str, entries: list, exits: list,
                 stop: float, signal_bar: int, strategy_name: str):
        self.direction = direction
        self.entries = entries  # [{"level", "size"}]
        self.exits = exits     # [{"level", "size"}]
        self.stop = stop
        self.signal_bar = signal_bar
        self.strategy_name = strategy_name

        self.state = "planned"  # planned|opened|scaled|trimmed|closed
        self.fills = []         # [{"bar", "price", "size", "type"}]
        self.position = 0       # current lot count
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.max_adverse = 0.0   # MAE in ticks
        self.max_favorable = 0.0 # MFE in ticks
        self.open_bar = None
        self.close_bar = None
        self.entry_fill_idx = 0  # next entry to fill
        self.exit_fill_idx = 0   # next exit to fill
        self.weighted_entry = 0.0
        self.peak_position = 0

    def try_fill_entries(self, bar_idx: int, high: float, low: float) -> bool:
        """Attempt to fill next entry level. Sequential — one per bar max."""
        if self.entry_fill_idx >= len(self.entries):
            return False

        entry = self.entries[self.entry_fill_idx]
        level = entry["level"]
        size = entry["size"]

        filled = False
        if self.direction == "LONG" and low <= level:
            filled = True
        elif self.direction == "SHORT" and high >= level:
            filled = True

        if filled:
            self.fills.append({"bar": bar_idx, "price": level, "size": size, "type": "entry"})
            self.position += size
            self.peak_position = max(self.peak_position, self.position)
            # Update weighted entry
            total_cost = sum(f["price"] * f["size"] for f in self.fills if f["type"] == "entry")
            total_lots = sum(f["size"] for f in self.fills if f["type"] == "entry")
            self.weighted_entry = total_cost / total_lots if total_lots > 0 else level
            self.entry_fill_idx += 1

            if self.state == "planned":
                self.state = "opened"
                self.open_bar = bar_idx
            elif self.entry_fill_idx > 1:
                self.state = "scaled"

        return filled

    def try_fill_exits(self, bar_idx: int, high: float, low: float) -> bool:
        """Attempt to fill next exit level. Sequential."""
        if self.exit_fill_idx >= len(self.exits) or self.position <= 0:
            return False

        exit_lvl = self.exits[self.exit_fill_idx]
        level = exit_lvl["level"]
        size = min(exit_lvl["size"], self.position)

        filled = False
        if self.direction == "LONG" and high >= level:
            filled = True
        elif self.direction == "SHORT" and low <= level:
            filled = True

        if filled:
            # Realize PnL for this tranche
            if self.direction == "LONG":
                pnl = (level - self.weighted_entry) * size
            else:
                pnl = (self.weighted_entry - level) * size

            self.realized_pnl += pnl
            self.position -= size
            self.fills.append({"bar": bar_idx, "price": level, "size": size, "type": "exit"})
            self.exit_fill_idx += 1
            self.state = "trimmed"

            if self.position <= 0:
                self.state = "closed"
                self.close_bar = bar_idx

        return filled

    def check_stop(self, bar_idx: int, high: float, low: float) -> bool:
        """Check if stop is hit. Closes entire remaining position."""
        if self.position <= 0:
            return False

        hit = False
        if self.direction == "LONG" and low <= self.stop:
            hit = True
        elif self.direction == "SHORT" and high >= self.stop:
            hit = True

        if hit:
            if self.direction == "LONG":
                pnl = (self.stop - self.weighted_entry) * self.position
            else:
                pnl = (self.weighted_entry - self.stop) * self.position

            self.realized_pnl += pnl
            self.fills.append({"bar": bar_idx, "price": self.stop, "size": self.position, "type": "stop"})
            self.position = 0
            self.state = "closed"
            self.close_bar = bar_idx

        return hit

    def update_mae_mfe(self, high: float, low: float):
        """Track max adverse/favorable excursion."""
        if self.position <= 0 or self.weighted_entry == 0:
            return

        if self.direction == "LONG":
            adverse = (self.weighted_entry - low) / TICK
            favorable = (high - self.weighted_entry) / TICK
        else:
            adverse = (high - self.weighted_entry) / TICK
            favorable = (self.weighted_entry - low) / TICK

        self.max_adverse = max(self.max_adverse, adverse)
        self.max_favorable = max(self.max_favorable, favorable)

    def close_at_market(self, bar_idx: int, price: float):
        """Force close at end of data."""
        if self.position <= 0:
            return
        if self.direction == "LONG":
            pnl = (price - self.weighted_entry) * self.position
        else:
            pnl = (self.weighted_entry - price) * self.position

        self.realized_pnl += pnl
        self.fills.append({"bar": bar_idx, "price": price, "size": self.position, "type": "market_close"})
        self.position = 0
        self.state = "closed"
        self.close_bar = bar_idx

    def to_dict(self) -> dict:
        total_ticks = self.realized_pnl / TICK if TICK > 0 else 0
        pnl_usd = total_ticks * TICK_VAL
        bars_held = (self.close_bar - self.open_bar) if self.open_bar and self.close_bar else 0

        # Determine result
        if self.realized_pnl > 0:
            result = "WIN"
        elif self.realized_pnl < 0:
            result = "LOSS"
        else:
            result = "FLAT"

        # Ladder efficiency: how many entries filled vs planned
        ladder_eff = self.entry_fill_idx / len(self.entries) * 100 if self.entries else 0

        return {
            "signal_bar": self.signal_bar,
            "direction": self.direction,
            "strategy": self.strategy_name,
            "state": self.state,
            "result": result,
            "weighted_entry": round(self.weighted_entry, 6),
            "pnl_ticks": round(total_ticks, 2),
            "pnl_usd": round(pnl_usd, 2),
            "realized_pnl": round(self.realized_pnl, 6),
            "mae_ticks": round(self.max_adverse, 1),
            "mfe_ticks": round(self.max_favorable, 1),
            "bars_held": bars_held,
            "peak_position": self.peak_position,
            "fills_count": len(self.fills),
            "entries_filled": self.entry_fill_idx,
            "entries_planned": len(self.entries),
            "exits_filled": self.exit_fill_idx,
            "exits_planned": len(self.exits),
            "ladder_efficiency": round(ladder_eff, 1),
            "stop": self.stop,
        }


# ===========================================================================
# MAIN BACKTEST ENGINE
# ===========================================================================

def run_backtest(product: str, timeframe: str, strategy: str,
                 risk_usd: float, is_spread: bool = False, spread_def: dict = None,
                 lookback: int = 100, **kwargs) -> dict:
    """V2 walk-forward backtest with ladder simulation."""

    # Load data
    trade_type_info = classify_trade_type(product)
    if trade_type_info["type"] == "calendar_spread" or (is_spread and spread_def):
        sdef = spread_def or trade_type_info["legs"]
        df = build_spread(sdef["leg1"], sdef["leg2"], timeframe)
    else:
        df = get_ohlcv(product, timeframe)

    if len(df) < 60:
        raise ValueError("Not enough data for backtest (need 60+ bars)")

    df = df.tail(lookback + 60).copy()
    df = df.reset_index()
    ts_col = df.columns[0]

    completed_trades = []
    active_trade: Optional[LadderTrade] = None
    warmup = 50
    cooldown = 0  # bars to wait after trade closes

    equity_series = []  # running equity
    cumulative_pnl = 0.0

    for i in range(warmup, len(df)):
        high = float(df["high"].iloc[i])
        low = float(df["low"].iloc[i])
        close = float(df["close"].iloc[i])

        # --- MANAGE ACTIVE TRADE ---
        if active_trade and active_trade.state != "closed":
            # Priority: check stop first
            if active_trade.check_stop(i, high, low):
                pass  # stopped out
            else:
                # Try to fill more entries
                active_trade.try_fill_entries(i, high, low)
                # Try to fill exits
                active_trade.try_fill_exits(i, high, low)
                # Update MAE/MFE
                active_trade.update_mae_mfe(high, low)

            # If still open at last bar, close at market
            if i == len(df) - 1 and active_trade.position > 0:
                active_trade.close_at_market(i, close)

            # If closed, record and reset
            if active_trade.state == "closed":
                completed_trades.append(active_trade.to_dict())
                cumulative_pnl += active_trade.to_dict()["pnl_usd"]
                cooldown = 2  # wait 2 bars before next signal
                active_trade = None

        # --- GENERATE NEW SIGNAL ---
        elif cooldown > 0:
            cooldown -= 1

        elif active_trade is None and i < len(df) - 5:
            window = df.iloc[:i+1].set_index(ts_col)

            try:
                indics = compute_all(window)
                last_close = float(window["close"].iloc[-1])
                atr_val = float(indics["atr14"].iloc[-1])
                if np.isnan(atr_val) or atr_val <= 0:
                    continue

                # Detect execution state
                vap_data = {"imbalance": 0.0, "poc": None, "val": None, "vah": None}
                exec_state = detect_execution_state(window, indics, vap_data)

                # Select strategy
                strat = select_strategy(exec_state, indics, last_close, vap_data,
                                       "outright", strategy)

                # Build ladder
                ladder = build_adaptive_ladder(last_close, strat, atr_val, risk_usd, vap_data)

                # Create trade object
                active_trade = LadderTrade(
                    direction=ladder["direction"],
                    entries=[{"level": e["level"], "size": e["size"]} for e in ladder["entries"]],
                    exits=[{"level": e["level"], "size": e["size"]} for e in ladder["exits"]],
                    stop=ladder["stop"],
                    signal_bar=i,
                    strategy_name=strat["name"],
                )

            except Exception:
                continue

        # Record equity
        equity_series.append({"bar": i - warmup, "equity": round(cumulative_pnl, 2)})

    return _build_summary(completed_trades, equity_series)


# ===========================================================================
# SUMMARY & METRICS
# ===========================================================================

def _build_summary(trades: list, equity_series: list) -> dict:
    if not trades:
        return {
            "trades": [],
            "equity_curve": equity_series,
            "summary": _empty_summary(),
        }

    wins = [t for t in trades if t["result"] == "WIN"]
    losses = [t for t in trades if t["result"] == "LOSS"]
    pnls_usd = [t["pnl_usd"] for t in trades]
    pnls_ticks = [t["pnl_ticks"] for t in trades]

    # Equity curve stats
    equity_vals = np.cumsum(pnls_usd)
    rolling_max = np.maximum.accumulate(equity_vals)
    drawdowns = equity_vals - rolling_max
    max_dd = float(np.min(drawdowns)) if len(drawdowns) > 0 else 0.0

    # Sharpe (annualized assuming daily)
    if len(pnls_usd) > 1 and np.std(pnls_usd) > 0:
        sharpe = float(np.mean(pnls_usd) / np.std(pnls_usd) * np.sqrt(252))
    else:
        sharpe = 0.0

    # Expectancy
    win_rate = len(wins) / len(trades) if trades else 0
    avg_win = float(np.mean([t["pnl_usd"] for t in wins])) if wins else 0
    avg_loss = float(np.mean([abs(t["pnl_usd"]) for t in losses])) if losses else 0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    # Holding time
    hold_times = [t["bars_held"] for t in trades if t["bars_held"] > 0]
    avg_hold = float(np.mean(hold_times)) if hold_times else 0

    # Ladder efficiency
    ladder_effs = [t["ladder_efficiency"] for t in trades]
    avg_ladder_eff = float(np.mean(ladder_effs)) if ladder_effs else 0

    # MAE/MFE
    maes = [t["mae_ticks"] for t in trades]
    mfes = [t["mfe_ticks"] for t in trades]

    # Risk efficiency: realized / max_favorable
    risk_effs = []
    for t in trades:
        if t["mfe_ticks"] > 0:
            risk_effs.append(t["pnl_ticks"] / t["mfe_ticks"])
    avg_risk_eff = float(np.mean(risk_effs)) * 100 if risk_effs else 0

    # Profit factor
    gross_profit = sum(t["pnl_usd"] for t in wins) if wins else 0
    gross_loss = abs(sum(t["pnl_usd"] for t in losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Execution quality (avg confidence from ladder efficiency + win rate blend)
    exec_quality = min(100, avg_ladder_eff * 0.4 + win_rate * 100 * 0.4 + min(100, sharpe * 20) * 0.2)

    summary = {
        "total": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate * 100, 1),
        "avg_return_ticks": round(float(np.mean(pnls_ticks)), 2),
        "avg_return_usd": round(float(np.mean(pnls_usd)), 2),
        "total_pnl_usd": round(sum(pnls_usd), 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999.0,
        "expectancy_usd": round(expectancy, 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown_usd": round(max_dd, 2),
        "avg_hold_bars": round(avg_hold, 1),
        "avg_mae_ticks": round(float(np.mean(maes)), 1) if maes else 0,
        "avg_mfe_ticks": round(float(np.mean(mfes)), 1) if mfes else 0,
        "risk_efficiency_pct": round(avg_risk_eff, 1),
        "ladder_efficiency_pct": round(avg_ladder_eff, 1),
        "execution_quality": round(exec_quality, 1),
    }

    # Drawdown curve
    dd_curve = [
        {"bar": i, "drawdown": round(float(d), 2)}
        for i, d in enumerate(drawdowns)
    ]

    return {
        "trades": trades[:200],
        "equity_curve": equity_series,
        "drawdown_curve": dd_curve,
        "summary": summary,
    }


def _empty_summary() -> dict:
    return {
        "total": 0, "wins": 0, "losses": 0, "win_rate": 0,
        "avg_return_ticks": 0, "avg_return_usd": 0, "total_pnl_usd": 0,
        "profit_factor": 0, "expectancy_usd": 0, "sharpe": 0,
        "max_drawdown_usd": 0, "avg_hold_bars": 0, "avg_mae_ticks": 0,
        "avg_mfe_ticks": 0, "risk_efficiency_pct": 0,
        "ladder_efficiency_pct": 0, "execution_quality": 0,
    }
