#!/usr/bin/env python3
"""
Generate analysis charts from simulation metrics CSVs.

Usage:
    python scripts/plot_analysis.py                          # both scenarios
    python scripts/plot_analysis.py --scenarios calm-market  # single scenario
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = REPO_ROOT / "logs"
REPORTS_DIR = REPO_ROOT / "reports"


# ── Data loading ──────────────────────────────────────────────────────────────

def load(scenario_name: str) -> pd.DataFrame:
    path = LOGS_DIR / f"metrics_{scenario_name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No metrics file: {path}")
    df = pd.read_csv(path).fillna(0)
    df = df.sort_values("day").reset_index(drop=True)
    return df


# ── Chart 1: Inventory over time ──────────────────────────────────────────────

def chart_inventory(df: pd.DataFrame, scenario_name: str, ax: plt.Axes) -> None:
    days = df["day"]

    ax.plot(days, df.get("mfg_parts_total", 0), label="Parts stock (Manufacturer)",
            marker="o", ms=3, linewidth=1.8, color="steelblue")

    if "ret_total_stock" in df.columns:
        ax.plot(days, df["ret_total_stock"], label="Printers stock (Retailer)",
                marker="s", ms=3, linewidth=1.8, color="forestgreen")

    # demand modifier as shaded background
    ax2 = ax.twinx()
    ax2.fill_between(days, df.get("demand_modifier", 1.0), alpha=0.12, color="orange")
    ax2.plot(days, df.get("demand_modifier", 1.0), color="orange", alpha=0.4, linewidth=1, linestyle="--")
    ax2.set_ylabel("Demand modifier", color="darkorange", fontsize=8)
    ax2.tick_params(axis="y", labelcolor="darkorange", labelsize=7)
    ax2.set_ylim(0, max(float(df.get("demand_modifier", pd.Series([1])).max()) * 2, 3))

    ax.set_title(f"1. Inventory Over Time — {scenario_name}", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Units")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(days.min(), days.max())


# ── Chart 2: Prices over time ─────────────────────────────────────────────────

def chart_prices(df: pd.DataFrame, scenario_name: str, ax: plt.Axes) -> None:
    days = df["day"]

    # Pick one representative provider price (kit_piezas preferred)
    prov_col = next(
        (c for c in df.columns if "prov_price_kit_piezas" in c),
        next((c for c in df.columns if c.startswith("prov_price_")), None)
    )
    if prov_col and df[prov_col].sum() > 0:
        ax.plot(days, df[prov_col], label=f"Provider: {prov_col.replace('prov_price_', '')}",
                marker="o", ms=3, linewidth=1.8, color="purple")

    mfg_col = next((c for c in df.columns if "mfg_price_P3D-Classic" in c), None)
    if mfg_col and df[mfg_col].sum() > 0:
        ax.plot(days, df[mfg_col], label="Manufacturer wholesale (P3D-Classic)",
                marker="s", ms=3, linewidth=1.8, color="steelblue")

    ret_col = next((c for c in df.columns if "ret_price_P3D-Classic" in c), None)
    if ret_col and df[ret_col].sum() > 0:
        ax.plot(days, df[ret_col], label="Retailer retail (P3D-Classic)",
                marker="^", ms=3, linewidth=1.8, color="forestgreen")

    ax.set_title(f"2. Prices Over Time — {scenario_name}", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Price (€)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(days.min(), days.max())


# ── Chart 3: Order fulfillment ────────────────────────────────────────────────

def chart_fulfillment(df: pd.DataFrame, scenario_name: str, ax: plt.Axes) -> None:
    days = df["day"].values
    placed = df.get("orders_placed_today", pd.Series(np.zeros(len(df)))).values
    fulfilled = df.get("orders_fulfilled_today", pd.Series(np.zeros(len(df)))).values
    backordered = df.get("orders_backordered_today", pd.Series(np.zeros(len(df)))).values

    x = np.arange(len(days))
    w = 0.28

    ax.bar(x - w, placed, w, label="Placed", color="steelblue", alpha=0.85)
    ax.bar(x,     fulfilled, w, label="Fulfilled", color="forestgreen", alpha=0.85)
    ax.bar(x + w, backordered, w, label="Backordered (new)", color="tomato", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(days.astype(int), rotation=45, ha="right", fontsize=7)
    ax.set_title(f"3. Order Fulfillment — {scenario_name}", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Orders")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25, axis="y")


# ── Chart 4: Events overlay ───────────────────────────────────────────────────

def chart_events(df: pd.DataFrame, scenario_name: str, ax: plt.Axes) -> None:
    days = df["day"].values
    modifier = df.get("demand_modifier", pd.Series(np.ones(len(df)))).values

    colors = ["#d73027" if m >= 2.0 else "#fc8d59" if m >= 1.4 else
              "#fee08b" if m >= 1.1 else "#91bfdb" if m <= 0.85 else "#d1e5f0"
              for m in modifier]

    bars = ax.bar(days, modifier, color=colors, width=0.8, alpha=0.9)
    ax.axhline(y=1.0, color="gray", linestyle="--", linewidth=1, alpha=0.6)

    legend_items = [
        mpatches.Patch(color="#d73027", label="Peak demand (≥2.0×)"),
        mpatches.Patch(color="#fc8d59", label="High demand (≥1.4×)"),
        mpatches.Patch(color="#fee08b", label="Mild uptick (≥1.1×)"),
        mpatches.Patch(color="#d1e5f0", label="Normal (~1.0×)"),
        mpatches.Patch(color="#91bfdb", label="Soft demand (≤0.85×)"),
    ]
    ax.legend(handles=legend_items, fontsize=7, loc="upper right")
    ax.set_title(f"4. Scenario Events (Demand Modifier) — {scenario_name}", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Demand Modifier")
    ax.set_ylim(0, max(float(np.max(modifier)) * 1.3, 1.5))
    ax.grid(True, alpha=0.25, axis="y")


# ── Full dashboard for one scenario ──────────────────────────────────────────

def plot_dashboard(scenario_name: str) -> Path:
    df = load(scenario_name)
    fig, axes = plt.subplots(4, 1, figsize=(13, 22))
    plt.subplots_adjust(hspace=0.45)

    chart_inventory(df, scenario_name, axes[0])
    chart_prices(df, scenario_name, axes[1])
    chart_fulfillment(df, scenario_name, axes[2])
    chart_events(df, scenario_name, axes[3])

    fig.suptitle(f"Supply Chain Simulation — {scenario_name}", fontsize=15, fontweight="bold", y=0.995)

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"{scenario_name}_dashboard.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ── Side-by-side comparison ───────────────────────────────────────────────────

def plot_comparison() -> None:
    try:
        calm = load("calm-market")
        holiday = load("holiday-rush")
    except FileNotFoundError as exc:
        print(f"[SKIP] Comparison: {exc}")
        return

    fig, axes = plt.subplots(3, 2, figsize=(20, 18))
    plt.subplots_adjust(hspace=0.45, wspace=0.3)

    for col, (df, name) in enumerate([(calm, "calm-market"), (holiday, "holiday-rush")]):
        chart_inventory(df, name, axes[0, col])
        chart_prices(df, name, axes[1, col])
        chart_fulfillment(df, name, axes[2, col])

    fig.suptitle("Scenario Comparison: Calm Market vs Holiday Rush",
                 fontsize=16, fontweight="bold", y=0.998)

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / "comparison.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate analysis charts from simulation metrics.")
    parser.add_argument("--scenarios", nargs="+", default=["calm-market", "holiday-rush"])
    parser.add_argument("--no-compare", action="store_true")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(exist_ok=True)

    for name in args.scenarios:
        try:
            plot_dashboard(name)
        except FileNotFoundError as exc:
            print(f"[SKIP] {exc}")

    if not args.no_compare:
        plot_comparison()

    return 0


if __name__ == "__main__":
    sys.exit(main())
