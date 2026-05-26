"""V2 Strategy Engine — institutional STIR planning.

Flow: contract context → strategy selection → ladder construction → execution plan
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

from services.indicators import compute_all, zscore, atr as calc_atr
from services.qh_api import get_ohlcv, fetch_vap, vap_poc, vap_value_area, vap_imbalance, build_spread

CFG = json.loads(Path("strategy_config.json").read_text())
TICK = CFG["tick_size"]
TICK_VAL = CFG["tick_value"]
MAX_LOTS = CFG["max_position_lots"]


# ===========================================================================
# HELPERS
# ===========================================================================

def _round_tick(price: float, tick: float = TICK) -> float:
    return round(round(price / tick) * tick, 6)


def _ticks_between(a: float, b: float) -> int:
    return abs(int(round((a - b) / TICK)))


def _risk_lots(risk_usd: float, stop_ticks: int) -> int:
    if stop_ticks <= 0:
        return 1
    per_lot = stop_ticks * TICK_VAL
    return max(1, min(MAX_LOTS, int(risk_usd / per_lot)))


# ===========================================================================
# STEP 1 — CLASSIFY TRADE TYPE
# ===========================================================================

def classify_trade_type(product: str) -> dict:
    """Determine if product is outright, spread, or butterfly."""
    spread_def = next((s for s in CFG["spreads"] if s["name"] == product), None)
    if spread_def:
        return {"type": "calendar_spread", "legs": spread_def}

    fly_def = next((b for b in CFG["butterflies"] if b["name"] == product), None)
    if fly_def:
        return {"type": "butterfly", "legs": fly_def}

    return {"type": "outright", "legs": {"product": product}}


# ===========================================================================
# STEP 2 — EXECUTION STATE DETECTION (from market structure)
# ===========================================================================

def detect_execution_state(df: pd.DataFrame, indics: dict, vap_data: dict) -> dict:
    """Classify execution state from volume/price structure.
    Returns: state (accumulation|distribution|balanced|impulse), metrics.
    NOT a regime — an execution state."""

    last_close = float(df["close"].iloc[-1])
    n = min(20, len(df))
    recent = df.tail(n)

    # Volume concentration: how clustered is volume around POC?
    vol_total = float(recent["volume"].sum()) if "volume" in recent.columns else 1.0
    vol_std = float(recent["volume"].std()) if vol_total > 0 else 0.0
    vol_mean = float(recent["volume"].mean()) if vol_total > 0 else 1.0
    vol_concentration = 1.0 - min(1.0, vol_std / (vol_mean + 1e-9))

    # Directional bias from recent closes
    closes = recent["close"].values
    up_bars = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
    dn_bars = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i-1])
    total_bars = up_bars + dn_bars if (up_bars + dn_bars) > 0 else 1
    directional_ratio = abs(up_bars - dn_bars) / total_bars

    # Price range vs ATR — compression detection
    atr_val = float(indics["atr14"].iloc[-1]) if not np.isnan(indics["atr14"].iloc[-1]) else 0.01
    recent_range = float(recent["high"].max() - recent["low"].min())
    range_ratio = recent_range / (atr_val * n) if atr_val > 0 else 1.0

    # VAP imbalance
    vap_imb = vap_data.get("imbalance", 0.0)

    # Classify
    if directional_ratio > 0.6 and range_ratio > 0.8:
        state = "impulse"
    elif vol_concentration > 0.7 and abs(vap_imb) > 0.3:
        state = "accumulation" if vap_imb > 0 else "distribution"
    else:
        state = "balanced"

    return {
        "state": state,
        "vol_concentration": round(vol_concentration, 3),
        "directional_ratio": round(directional_ratio, 3),
        "range_ratio": round(range_ratio, 3),
        "vap_imbalance": round(vap_imb, 4),
        "avg_volume": round(vol_mean, 1),
    }


# ===========================================================================
# STEP 3 — STRATEGY SELECTION (library of 5 templates)
# ===========================================================================

def select_strategy(exec_state: dict, indics: dict, last_close: float,
                    vap_data: dict, trade_type: str, user_strategy: str = "auto") -> dict:
    """Select strategy template from library. Returns strategy object."""

    state = exec_state["state"]
    rsi_val = float(indics["rsi14"].iloc[-1]) if not np.isnan(indics["rsi14"].iloc[-1]) else 50.0
    vwap_val = float(indics["vwap"].iloc[-1]) if not np.isnan(indics["vwap"].iloc[-1]) else last_close
    bb_upper = float(indics["bb_upper"].iloc[-1]) if not np.isnan(indics["bb_upper"].iloc[-1]) else last_close + 0.05
    bb_lower = float(indics["bb_lower"].iloc[-1]) if not np.isnan(indics["bb_lower"].iloc[-1]) else last_close - 0.05
    atr_val = float(indics["atr14"].iloc[-1]) if not np.isnan(indics["atr14"].iloc[-1]) else 0.01
    poc = vap_data.get("poc")
    val_price = vap_data.get("val")
    vah_price = vap_data.get("vah")

    # Auto-select logic (or honor user choice)
    if user_strategy == "auto":
        if trade_type in ("calendar_spread", "butterfly"):
            chosen = "relative_value"
        elif state == "balanced" and (rsi_val > 65 or rsi_val < 35):
            chosen = "mean_reversion"
        elif state == "impulse":
            chosen = "continuation"
        elif state == "accumulation":
            chosen = "acceptance_break"
        elif state == "distribution" and exec_state["range_ratio"] < 0.5:
            chosen = "failed_move"
        else:
            chosen = "mean_reversion"
    else:
        chosen = user_strategy

    # -----------------------------------------------------------------------
    # STRATEGY TEMPLATES
    # -----------------------------------------------------------------------

    if chosen == "mean_reversion":
        # Entry near extremes, exit near mean
        dist_from_vwap = (last_close - vwap_val) / atr_val if atr_val > 0 else 0
        if dist_from_vwap > 0.3:
            direction = "SHORT"
            entry_zone = last_close + atr_val * 0.2
            target_zone = vwap_val
        elif dist_from_vwap < -0.3:
            direction = "LONG"
            entry_zone = last_close - atr_val * 0.2
            target_zone = vwap_val
        else:
            direction = "LONG" if rsi_val < 50 else "SHORT"
            entry_zone = last_close - atr_val * 0.15 if direction == "LONG" else last_close + atr_val * 0.15
            target_zone = vwap_val

        return {
            "name": "mean_reversion",
            "direction": direction,
            "entry_zone": entry_zone,
            "target_zone": target_zone,
            "stop_atr_mult": 1.5,
            "size_profile": "scale_in",
            "confidence_factors": {
                "rsi_extreme": min(100, abs(rsi_val - 50) * 2.5),
                "vwap_distance": min(100, abs(dist_from_vwap) * 80),
                "vol_concentration": exec_state["vol_concentration"] * 100,
            },
            "thesis": f"Price extended {abs(dist_from_vwap):.2f} ATR from VWAP. "
                      f"RSI at {rsi_val:.0f}. Expecting reversion to value.",
            "invalidation": f"Price accepts beyond {bb_upper:.5f} (long) or {bb_lower:.5f} (short)",
            "confirmation": "Return toward VWAP with volume increase",
        }

    elif chosen == "continuation":
        # Staggered entries in direction of momentum
        ema9 = float(indics["ema9"].iloc[-1]) if not np.isnan(indics["ema9"].iloc[-1]) else last_close
        ema21 = float(indics["ema21"].iloc[-1]) if not np.isnan(indics["ema21"].iloc[-1]) else last_close
        direction = "LONG" if ema9 > ema21 else "SHORT"
        pullback = atr_val * 0.3

        if direction == "LONG":
            entry_zone = last_close - pullback
            target_zone = last_close + atr_val * 1.5
        else:
            entry_zone = last_close + pullback
            target_zone = last_close - atr_val * 1.5

        return {
            "name": "continuation",
            "direction": direction,
            "entry_zone": entry_zone,
            "target_zone": target_zone,
            "stop_atr_mult": 2.0,
            "size_profile": "pyramid",
            "confidence_factors": {
                "directional_ratio": exec_state["directional_ratio"] * 100,
                "ema_alignment": 100 if (ema9 > ema21 and direction == "LONG") or (ema9 < ema21 and direction == "SHORT") else 30,
                "momentum": rsi_val if direction == "LONG" else (100 - rsi_val),
            },
            "thesis": f"Directional participation ({exec_state['directional_ratio']:.0%}) with "
                      f"EMA alignment. Trail into continuation.",
            "invalidation": f"EMA crossover or RSI divergence below 40" if direction == "LONG" else "EMA crossover or RSI above 60",
            "confirmation": "Higher lows with volume on extensions" if direction == "LONG" else "Lower highs with volume on drops",
        }

    elif chosen == "acceptance_break":
        # Small probe, add on confirmation of acceptance
        if poc and not np.isnan(poc):
            key_level = poc
        elif vah_price and not np.isnan(vah_price):
            key_level = vah_price
        else:
            key_level = last_close

        direction = "LONG" if last_close > key_level else "SHORT"
        entry_zone = key_level + TICK * 2 if direction == "LONG" else key_level - TICK * 2
        target_zone = key_level + atr_val * 1.2 if direction == "LONG" else key_level - atr_val * 1.2

        return {
            "name": "acceptance_break",
            "direction": direction,
            "entry_zone": entry_zone,
            "target_zone": target_zone,
            "stop_atr_mult": 1.2,
            "size_profile": "accumulation",
            "confidence_factors": {
                "vol_at_level": exec_state["vol_concentration"] * 100,
                "acceptance_signal": 80 if exec_state["state"] == "accumulation" else 40,
                "structure_break": min(100, _ticks_between(last_close, key_level) * 10),
            },
            "thesis": f"Sustained participation at {key_level:.5f}. "
                      f"Price accepting {'above' if direction == 'LONG' else 'below'} key level.",
            "invalidation": f"Price rejects back {'below' if direction == 'LONG' else 'above'} {key_level:.5f}",
            "confirmation": "Volume builds at new level, POC migrates",
        }

    elif chosen == "failed_move":
        # Fade extension with no participation
        direction = "SHORT" if last_close > vwap_val else "LONG"
        entry_zone = last_close + atr_val * 0.1 if direction == "SHORT" else last_close - atr_val * 0.1
        target_zone = vwap_val

        return {
            "name": "failed_move",
            "direction": direction,
            "entry_zone": entry_zone,
            "target_zone": target_zone,
            "stop_atr_mult": 1.0,
            "size_profile": "scale_in",
            "confidence_factors": {
                "thin_extension": max(0, 100 - exec_state["vol_concentration"] * 150),
                "range_compression": max(0, 100 - exec_state["range_ratio"] * 100),
                "failed_auction": 80 if exec_state["range_ratio"] < 0.4 else 30,
            },
            "thesis": f"Extension with no volume support. Range ratio {exec_state['range_ratio']:.2f} "
                      f"signals failed probe. Fade back to value.",
            "invalidation": "Volume acceptance at extension — new POC forming at extreme",
            "confirmation": "Quick reversal with delta shift, single prints left behind",
        }

    else:  # relative_value
        direction = "LONG"  # will be overridden by spread logic
        entry_zone = last_close
        target_zone = last_close

        return {
            "name": "relative_value",
            "direction": direction,
            "entry_zone": entry_zone,
            "target_zone": target_zone,
            "stop_atr_mult": 1.5,
            "size_profile": "equal",
            "confidence_factors": {
                "spread_zscore": 50,
                "relative_displacement": 50,
                "vol_match": 50,
            },
            "thesis": "Relative value between contracts — spread dislocation.",
            "invalidation": "Spread continues to widen beyond 2 sigma",
            "confirmation": "Spread mean-reverts with declining vol",
        }


# ===========================================================================
# STEP 4 — ADAPTIVE LADDER CONSTRUCTION
# ===========================================================================

def build_adaptive_ladder(last_close: float, strategy: dict, atr_val: float,
                          risk_usd: float, vap_data: dict) -> dict:
    """Build entry/exit ladder from strategy template. Dynamic spacing & sizing."""

    direction = strategy["direction"]
    entry_zone = strategy["entry_zone"]
    target_zone = strategy["target_zone"]
    stop_mult = strategy["stop_atr_mult"]
    profile_name = strategy["size_profile"]

    # Get size profile
    profile = CFG["ladder"]["size_profiles"].get(profile_name, [1, 2, 3])
    num_entries = len(profile)
    total_lots_raw = sum(profile)

    # Compute spacing dynamically
    dist_to_entry = abs(last_close - entry_zone)
    if dist_to_entry < TICK:
        dist_to_entry = atr_val * 0.2
    entry_spacing = max(TICK * CFG["ladder"]["min_spacing_ticks"],
                        min(TICK * CFG["ladder"]["max_spacing_ticks"],
                            dist_to_entry / max(1, num_entries - 1)))

    # Stop distance
    stop_dist = atr_val * stop_mult
    stop_ticks = max(1, int(stop_dist / TICK))

    # Compute max lots from risk
    max_lots = _risk_lots(risk_usd, stop_ticks)

    # Scale profile to fit risk
    scale_factor = max_lots / total_lots_raw if total_lots_raw > 0 else 1
    sizes = [max(1, int(round(s * scale_factor))) for s in profile]
    total_lots = sum(sizes)

    # Build entry levels
    entries = []
    for i in range(num_entries):
        if direction == "LONG":
            lvl = _round_tick(entry_zone - i * entry_spacing)
        else:
            lvl = _round_tick(entry_zone + i * entry_spacing)

        confidence = max(20, min(95, 60 + (i * 10)))  # deeper = more confident
        entries.append({
            "level": lvl,
            "size": sizes[i],
            "confidence": confidence,
            "reason": ["probe", "accepted value", "major accumulation", "deep support", "max conviction"][min(i, 4)],
        })

    # Stop
    if direction == "LONG":
        stop_price = _round_tick(entries[-1]["level"] - stop_dist)
    else:
        stop_price = _round_tick(entries[-1]["level"] + stop_dist)

    # Build exit levels
    dist_to_target = abs(target_zone - last_close)
    num_exits = min(CFG["ladder"]["max_exit_levels"], 3)
    exit_spacing = dist_to_target / max(1, num_exits) if dist_to_target > TICK else atr_val * 0.3

    exits = []
    exit_reasons = ["trim", "reduce risk", "take profit", "full exit"]
    exit_sizes_pct = [0.3, 0.3, 0.4] if num_exits == 3 else [0.5, 0.5]

    for i in range(num_exits):
        if direction == "LONG":
            lvl = _round_tick(last_close + (i + 1) * exit_spacing)
        else:
            lvl = _round_tick(last_close - (i + 1) * exit_spacing)

        exit_lots = max(1, int(total_lots * exit_sizes_pct[i]))
        exits.append({
            "level": lvl,
            "size": exit_lots,
            "reason": exit_reasons[min(i, len(exit_reasons) - 1)],
        })

    # Weighted average entry
    weighted_entry = sum(e["level"] * e["size"] for e in entries) / total_lots if total_lots > 0 else entry_zone

    # Risk metrics
    tick_exposure = stop_ticks * total_lots
    max_loss_usd = tick_exposure * TICK_VAL
    expected_gain_ticks = _ticks_between(exits[-1]["level"] if exits else target_zone, weighted_entry)
    risk_reward = expected_gain_ticks / stop_ticks if stop_ticks > 0 else 0

    return {
        "direction": direction,
        "entries": entries,
        "exits": exits,
        "stop": stop_price,
        "total_lots": total_lots,
        "weighted_avg_entry": round(weighted_entry, 6),
        "stop_ticks": stop_ticks,
        "risk": {
            "max_loss_usd": round(max_loss_usd, 2),
            "tick_exposure": tick_exposure,
            "capital_at_risk": round(max_loss_usd, 2),
            "risk_reward": round(risk_reward, 2),
            "expected_hold_bars": "3-10",
        },
    }


# ===========================================================================
# STEP 5 — CROSS CONTRACT CONTEXT
# ===========================================================================

def compute_cross_contract_score(product: str, df: pd.DataFrame, timeframe: str) -> dict:
    """Compare product movement to neighbors. Returns 0-100 score + reasoning."""

    neighbors = CFG["cross_contract"]["neighbors"].get(product, [])
    if not neighbors:
        return {"score": 50, "reasoning": "No neighbors configured", "details": []}

    last_close = float(df["close"].iloc[-1])
    pct_change = float((df["close"].iloc[-1] - df["close"].iloc[-5]) / df["close"].iloc[-5] * 100) if len(df) >= 5 else 0.0

    details = []
    alignment_scores = []

    for nb in neighbors[:3]:
        try:
            nb_df = get_ohlcv(nb, timeframe)
            if len(nb_df) < 5:
                continue
            nb_pct = float((nb_df["close"].iloc[-1] - nb_df["close"].iloc[-5]) / nb_df["close"].iloc[-5] * 100)
            nb_vol = float(nb_df["volume"].tail(5).mean()) if "volume" in nb_df.columns else 0

            # Relative move
            rel_move = pct_change - nb_pct

            # Participation skew: compare volumes
            own_vol = float(df["volume"].tail(5).mean()) if "volume" in df.columns else 0
            vol_ratio = own_vol / (nb_vol + 1e-9)

            # Alignment: same direction = higher score
            same_dir = (pct_change > 0 and nb_pct > 0) or (pct_change < 0 and nb_pct < 0)
            align_score = 70 if same_dir else 30

            alignment_scores.append(align_score)
            details.append({
                "contract": nb,
                "pct_5bar": round(nb_pct, 4),
                "relative_move": round(rel_move, 4),
                "vol_ratio": round(vol_ratio, 2),
                "aligned": same_dir,
            })
        except Exception:
            continue

    if not alignment_scores:
        return {"score": 50, "reasoning": "Could not fetch neighbor data", "details": []}

    base_score = float(np.mean(alignment_scores))

    # Boost if volume skews toward this contract
    vol_ratios = [d["vol_ratio"] for d in details]
    if vol_ratios and np.mean(vol_ratios) > 1.2:
        base_score = min(100, base_score + 15)

    reasoning_parts = []
    for d in details:
        dir_label = "aligned" if d["aligned"] else "divergent"
        reasoning_parts.append(f"{d['contract']}: {d['pct_5bar']:+.4f}% ({dir_label})")

    return {
        "score": round(base_score, 1),
        "reasoning": " | ".join(reasoning_parts),
        "details": details,
        "own_pct_5bar": round(pct_change, 4),
    }


# ===========================================================================
# SPREAD / BUTTERFLY PLAN HELPERS
# ===========================================================================

def build_spread_plan_v2(spread_def: dict, timeframe: str, risk_usd: float,
                         user_strategy: str) -> dict:
    """V2 spread plan with z-score based relative value strategy."""
    spread_df = build_spread(spread_def["leg1"], spread_def["leg2"], timeframe)
    if len(spread_df) < 30:
        raise ValueError("Not enough spread history")

    indics = compute_all(spread_df)
    last_close = float(spread_df["close"].iloc[-1])
    atr_val = float(indics["atr14"].iloc[-1])
    if np.isnan(atr_val):
        atr_val = float(spread_df["close"].std())

    z = float(zscore(spread_df["close"], period=20).iloc[-1])
    mean20 = float(spread_df["close"].rolling(20).mean().iloc[-1])
    std20 = float(spread_df["close"].rolling(20).std().iloc[-1])

    # Direction from z-score
    if z > 0.5:
        direction = "SHORT"
    elif z < -0.5:
        direction = "LONG"
    else:
        direction = "LONG" if z < 0 else "SHORT"

    # Build strategy
    strategy = {
        "name": "relative_value",
        "direction": direction,
        "entry_zone": last_close,
        "target_zone": mean20,
        "stop_atr_mult": 1.5,
        "size_profile": "equal",
        "confidence_factors": {
            "spread_zscore": min(100, abs(z) * 40),
            "relative_displacement": min(100, abs(last_close - mean20) / (std20 + 1e-9) * 30),
            "vol_match": 60,
        },
        "thesis": f"Spread z-score at {z:.2f}. Expecting reversion to mean ({mean20:.5f}).",
        "invalidation": f"Spread widens beyond {mean20 + 2.5 * std20:.5f} or {mean20 - 2.5 * std20:.5f}",
        "confirmation": "Z-score declining with volume normalization",
    }

    ladder = build_adaptive_ladder(last_close, strategy, atr_val, risk_usd, {})

    return {
        "spread_metrics": {
            "zscore": round(z, 3),
            "mean": round(mean20, 5),
            "std": round(std20, 5),
            "last_spread": round(last_close, 5),
            "leg1": spread_def["leg1"],
            "leg2": spread_def["leg2"],
        },
        "strategy": strategy,
        "ladder": ladder,
    }


# ===========================================================================
# MASTER PLAN ENTRY POINT
# ===========================================================================

def generate_plan(product: str, timeframe: str, strategy: str,
                  risk_usd: float, is_spread: bool = False,
                  spread_def: dict = None, **kwargs) -> dict:
    """V2 plan generator — institutional-style output."""

    trade_type_info = classify_trade_type(product)
    trade_type = trade_type_info["type"]

    # --- SPREAD / BUTTERFLY ---
    if trade_type in ("calendar_spread", "butterfly") or (is_spread and spread_def):
        sdef = spread_def or trade_type_info["legs"]
        spread_plan = build_spread_plan_v2(sdef, timeframe, risk_usd, strategy)

        # Cross-contract context (use leg1)
        try:
            leg1_df = get_ohlcv(sdef["leg1"], timeframe)
            cross = compute_cross_contract_score(sdef["leg1"], leg1_df, timeframe)
        except Exception:
            cross = {"score": 50, "reasoning": "N/A", "details": []}

        # Confidence
        strat = spread_plan["strategy"]
        conf_values = list(strat["confidence_factors"].values())
        execution_quality = round(float(np.mean(conf_values)) * 0.7 + cross["score"] * 0.3, 1)

        return {
            "trade_type": trade_type,
            "product": product,
            "timeframe": timeframe,
            "strategy": strat,
            "ladder": spread_plan["ladder"],
            "spread_metrics": spread_plan["spread_metrics"],
            "cross_contract": cross,
            "execution_quality": min(100, execution_quality),
            "risk_usd": risk_usd,
            "thesis": strat["thesis"],
            "invalidation": strat["invalidation"],
            "confirmation": strat["confirmation"],
        }

    # --- OUTRIGHT ---
    df = get_ohlcv(product, timeframe)
    if len(df) < 30:
        raise ValueError("Not enough history for plan (need 30+ bars)")

    indics = compute_all(df)
    last_close = float(df["close"].iloc[-1])
    atr_val = float(indics["atr14"].iloc[-1])
    if np.isnan(atr_val):
        atr_val = float(df["close"].std() * 0.5)

    # VAP data
    vap_data = {"imbalance": 0.0, "poc": None, "val": None, "vah": None}
    try:
        vap_df = fetch_vap(product)
        vap_data["imbalance"] = vap_imbalance(vap_df)
        vap_data["poc"] = vap_poc(vap_df)
        vap_data["val"], vap_data["vah"] = vap_value_area(vap_df)
    except Exception:
        pass

    # Step 2: Execution state
    exec_state = detect_execution_state(df, indics, vap_data)

    # Step 3: Strategy selection
    strat = select_strategy(exec_state, indics, last_close, vap_data, trade_type, strategy)

    # Step 4: Build adaptive ladder
    ladder = build_adaptive_ladder(last_close, strat, atr_val, risk_usd, vap_data)

    # Step 5: Cross-contract context
    cross = compute_cross_contract_score(product, df, timeframe)

    # Execution quality score
    conf_values = list(strat["confidence_factors"].values())
    raw_conf = float(np.mean(conf_values))
    execution_quality = round(raw_conf * 0.5 + cross["score"] * 0.3 + exec_state["vol_concentration"] * 100 * 0.2, 1)
    execution_quality = min(100, max(0, execution_quality))

    # Contract context
    contract_context = {
        "last_price": round(last_close, 6),
        "atr": round(atr_val, 6),
        "execution_state": exec_state,
        "vap": vap_data,
    }

    # Execution notes
    execution_notes = {
        "invalidation": strat["invalidation"],
        "confirmation": strat["confirmation"],
        "thesis": strat["thesis"],
    }

    return {
        "trade_type": trade_type,
        "product": product,
        "timeframe": timeframe,
        "strategy": strat,
        "contract_context": contract_context,
        "ladder": ladder,
        "cross_contract": cross,
        "execution_quality": execution_quality,
        "execution_notes": execution_notes,
        "risk_usd": risk_usd,
    }
