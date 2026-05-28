#!/usr/bin/env python3
"""
Generate analysis charts from simulation metrics CSVs.

Required charts (Part 5 of week 8):
  1. Inventory over time        — parts @ manufacturer, finished @ manufacturer, stock @ retailer
  2. Prices over time           — provider price, manufacturer wholesale, retailer retail
  3. Order fulfillment          — daily bar: placed / fulfilled / backordered
  4. Events overlay             — demand modifier strip chart

Detailed per-actor dashboards (extra):
  5. provider_detail   — stock per product | prices per tier | orders by status
  6. manufacturer_detail — parts per component | finished stock | SO pipeline | utilisation
  7. retailer_detail   — stock per model | prices per model | daily order breakdown

Usage:
    python scripts/plot_analysis.py                           # both scenarios
    python scripts/plot_analysis.py --scenarios calm-market   # single scenario
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

# ── palette helpers ────────────────────────────────────────────────────────────

PROVIDER_COLORS = ["#7b2d8b", "#a855f7", "#c084fc", "#e9d5ff", "#6d28d9"]
MANUFACTURER_COLORS = ["#1e40af", "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe"]
RETAILER_COLORS = ["#065f46", "#059669", "#34d399", "#6ee7b7", "#a7f3d0"]
DEMAND_COLOR = "darkorange"


def _color_cycle(palette: list[str]):
    """Cycle through a palette indefinitely."""
    i = 0
    while True:
        yield palette[i % len(palette)]
        i += 1


# ── Data loading ───────────────────────────────────────────────────────────────

def load(scenario_name: str) -> pd.DataFrame:
    path = LOGS_DIR / f"metrics_{scenario_name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No metrics file: {path}")
    df = pd.read_csv(path).fillna(0)
    df = df.sort_values("day").reset_index(drop=True)
    df = df.drop_duplicates(subset=["day"], keep="last")  # keep last row for repeated days
    return df


def _cols(df: pd.DataFrame, prefix: str, exclude: list[str] | None = None) -> list[str]:
    """Return columns that start with `prefix`, sorted, minus any in `exclude`."""
    ex = set(exclude or [])
    return sorted(c for c in df.columns if c.startswith(prefix) and c not in ex)


# ══════════════════════════════════════════════════════════════════════════════
# PART 5 — Required charts
# ══════════════════════════════════════════════════════════════════════════════

def chart_inventory(df: pd.DataFrame, scenario_name: str, ax: plt.Axes) -> None:
    """Chart 1 — inventory over time (3 lines + demand modifier shading)."""
    days = df["day"]

    ax.plot(days, df.get("mfg_parts_total", 0),
            label="Parts stock (Manufacturer)", marker="o", ms=3, lw=1.8, color=MANUFACTURER_COLORS[0])

    finished_total = df.get("mfg_finished_total", pd.Series(np.zeros(len(df))))
    if finished_total.sum() > 0:
        ax.plot(days, finished_total,
                label="Finished printers (Manufacturer)", marker="D", ms=3, lw=1.8,
                color=MANUFACTURER_COLORS[2])

    if "ret_total_stock" in df.columns:
        ax.plot(days, df["ret_total_stock"],
                label="Printer stock (Retailer)", marker="s", ms=3, lw=1.8, color=RETAILER_COLORS[0])

    ax2 = ax.twinx()
    mod = df.get("demand_modifier", pd.Series(np.ones(len(df))))
    ax2.fill_between(days, mod, alpha=0.10, color=DEMAND_COLOR)
    ax2.plot(days, mod, color=DEMAND_COLOR, alpha=0.45, lw=1, ls="--")
    ax2.set_ylabel("Demand modifier", color=DEMAND_COLOR, fontsize=8)
    ax2.tick_params(axis="y", labelcolor=DEMAND_COLOR, labelsize=7)
    ax2.set_ylim(0, max(float(mod.max()) * 2.0, 3))

    ax.set_title(f"1. Inventory Over Time — {scenario_name}", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Units")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(days.min(), days.max())


def chart_prices(df: pd.DataFrame, scenario_name: str, ax: plt.Axes) -> None:
    """Chart 2 — prices over time (provider / manufacturer wholesale / retailer retail)."""
    days = df["day"]

    prov_col = next(
        (c for c in df.columns if c == "prov_price_CTRL-V2_t1"),
        next((c for c in df.columns if c == "prov_price_CTRL-V2"), None)
    )
    if prov_col and df[prov_col].sum() > 0:
        label = prov_col.replace("prov_price_", "Provider: ").replace("_t", " tier ")
        ax.plot(days, df[prov_col], label=label, marker="o", ms=3, lw=1.8, color=PROVIDER_COLORS[0])

    mfg_col = next((c for c in df.columns if c.startswith("mfg_price_")), None)
    if mfg_col and df[mfg_col].sum() > 0:
        ax.plot(days, df[mfg_col],
                label=f"Manufacturer wholesale ({mfg_col.replace('mfg_price_', '')})",
                marker="s", ms=3, lw=1.8, color=MANUFACTURER_COLORS[0])

    ret_col = next((c for c in df.columns if c.startswith("ret_price_")), None)
    if ret_col and df[ret_col].sum() > 0:
        ax.plot(days, df[ret_col],
                label=f"Retailer retail ({ret_col.replace('ret_price_', '')})",
                marker="^", ms=3, lw=1.8, color=RETAILER_COLORS[0])

    ax.set_title(f"2. Prices Over Time — {scenario_name}", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Price (€)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(days.min(), days.max())


def chart_fulfillment(df: pd.DataFrame, scenario_name: str, ax: plt.Axes) -> None:
    """Chart 3 — daily order fulfillment bar chart."""
    days = df["day"].values
    placed      = df.get("orders_placed_today",      pd.Series(np.zeros(len(df)))).values
    fulfilled   = df.get("orders_fulfilled_today",   pd.Series(np.zeros(len(df)))).values
    backordered = df.get("orders_backordered_today",  pd.Series(np.zeros(len(df)))).values

    x = np.arange(len(days))
    w = 0.28

    ax.bar(x - w, placed,      w, label="Placed",           color="#3b82f6", alpha=0.85)
    ax.bar(x,     fulfilled,   w, label="Fulfilled",         color="#059669", alpha=0.85)
    ax.bar(x + w, backordered, w, label="Backordered (new)", color="#ef4444", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(days.astype(int), rotation=45, ha="right", fontsize=7)
    ax.set_title(f"3. Order Fulfillment — {scenario_name}", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Orders")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25, axis="y")


def chart_events(df: pd.DataFrame, scenario_name: str, ax: plt.Axes) -> None:
    """Chart 4 — demand modifier strip chart (event overlay)."""
    days = df["day"].values
    modifier = df.get("demand_modifier", pd.Series(np.ones(len(df)))).values

    colors = [
        "#d73027" if m >= 2.0 else
        "#fc8d59" if m >= 1.4 else
        "#fee08b" if m >= 1.1 else
        "#91bfdb" if m <= 0.85 else
        "#d1e5f0"
        for m in modifier
    ]

    ax.bar(days, modifier, color=colors, width=0.8, alpha=0.9)
    ax.axhline(y=1.0, color="gray", ls="--", lw=1, alpha=0.6)

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


# ══════════════════════════════════════════════════════════════════════════════
# DETAILED PER-ACTOR DASHBOARDS
# ══════════════════════════════════════════════════════════════════════════════

# ── Provider detail ────────────────────────────────────────────────────────────

def plot_provider_detail(df: pd.DataFrame, scenario_name: str) -> Path:
    """Three-panel provider dashboard:
    (a) Stock per product over time
    (b) Price per product / per tier over time
    (c) Orders by status (pending / in-transit / delivered) — stacked area
    """
    days = df["day"]
    fig, axes = plt.subplots(3, 1, figsize=(13, 16))
    plt.subplots_adjust(hspace=0.45)
    fig.suptitle(f"Provider Detail — {scenario_name}", fontsize=14, fontweight="bold", y=0.995)

    # (a) Stock per product
    ax = axes[0]
    stock_cols = _cols(df, "prov_stock_")
    colors = _color_cycle(PROVIDER_COLORS)
    for col in stock_cols:
        product = col.replace("prov_stock_", "")
        ax.plot(days, df[col], label=product, marker="o", ms=3, lw=1.8, color=next(colors))
    if "prov_total_stock" in df.columns and len(stock_cols) > 1:
        ax.plot(days, df["prov_total_stock"], label="TOTAL", ls="--", lw=1.2, color="black", alpha=0.5)
    ax.set_title("(a) Provider stock per product", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Units")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(days.min(), days.max())

    # Add demand modifier shading
    ax2 = ax.twinx()
    mod = df.get("demand_modifier", pd.Series(np.ones(len(df))))
    ax2.fill_between(days, mod, alpha=0.07, color=DEMAND_COLOR)
    ax2.set_ylabel("Demand modifier", color=DEMAND_COLOR, fontsize=7)
    ax2.tick_params(axis="y", labelcolor=DEMAND_COLOR, labelsize=6)
    ax2.set_ylim(0, max(float(mod.max()) * 2.5, 3))

    # (b) Prices per product per tier
    ax = axes[1]
    # Group by product: find all prov_price_{product}_t{qty} columns
    tier_cols = _cols(df, "prov_price_", exclude=_cols(df, "prov_price_") )
    # Actually: tier cols have "_t" in name; plain cols don't
    plain_price_cols = [c for c in df.columns if c.startswith("prov_price_") and "_t" not in c]
    tier_price_cols  = [c for c in df.columns if c.startswith("prov_price_") and "_t" in c]

    if tier_price_cols:
        colors = _color_cycle(PROVIDER_COLORS)
        for col in sorted(tier_price_cols):
            label = col.replace("prov_price_", "").replace("_t", " ≥")
            ax.plot(days, df[col], label=label, lw=1.5, marker=".", ms=3, color=next(colors))
    elif plain_price_cols:
        colors = _color_cycle(PROVIDER_COLORS)
        for col in plain_price_cols:
            label = col.replace("prov_price_", "")
            ax.plot(days, df[col], label=label, lw=1.8, marker="o", ms=3, color=next(colors))
    else:
        ax.text(0.5, 0.5, "No price data", transform=ax.transAxes, ha="center")

    ax.set_title("(b) Provider prices per product / tier", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Unit price (€)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(days.min(), days.max())

    # (c) Orders by status — stacked area
    ax = axes[2]
    pending    = df.get("prov_orders_pending",    pd.Series(np.zeros(len(df)))).values
    in_transit = df.get("prov_orders_in_transit", pd.Series(np.zeros(len(df)))).values
    delivered  = df.get("prov_orders_delivered",  pd.Series(np.zeros(len(df)))).values
    x = days.values

    ax.stackplot(x, pending, in_transit, delivered,
                 labels=["Pending", "In transit", "Delivered"],
                 colors=[PROVIDER_COLORS[0], PROVIDER_COLORS[2], PROVIDER_COLORS[4]],
                 alpha=0.75)
    ax.set_title("(c) Provider orders by status (cumulative)", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Order count")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.25, axis="y")
    ax.set_xlim(days.min(), days.max())

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"{scenario_name}_provider_detail.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ── Manufacturer detail ────────────────────────────────────────────────────────

def plot_manufacturer_detail(df: pd.DataFrame, scenario_name: str) -> Path:
    """Four-panel manufacturer dashboard:
    (a) Raw parts inventory per component
    (b) Finished-printer stock per model
    (c) Sales order pipeline by status (stacked bar)
    (d) Production utilisation % + wholesale price per model
    """
    days = df["day"]
    fig, axes = plt.subplots(4, 1, figsize=(13, 22))
    plt.subplots_adjust(hspace=0.48)
    fig.suptitle(f"Manufacturer Detail — {scenario_name}", fontsize=14, fontweight="bold", y=0.995)

    # (a) Raw parts per component
    ax = axes[0]
    part_cols = _cols(df, "mfg_part_")
    if part_cols:
        colors = _color_cycle(MANUFACTURER_COLORS)
        for col in part_cols:
            part = col.replace("mfg_part_", "")
            ax.plot(days, df[col], label=part, marker="o", ms=3, lw=1.8, color=next(colors))
    elif "mfg_parts_total" in df.columns:
        ax.plot(days, df["mfg_parts_total"], label="Total parts", marker="o", ms=3, lw=1.8,
                color=MANUFACTURER_COLORS[0])
    ax.set_title("(a) Raw-parts inventory per component", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Units")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(days.min(), days.max())

    # Demand modifier shade
    ax2 = ax.twinx()
    mod = df.get("demand_modifier", pd.Series(np.ones(len(df))))
    ax2.fill_between(days, mod, alpha=0.07, color=DEMAND_COLOR)
    ax2.set_ylabel("Demand modifier", color=DEMAND_COLOR, fontsize=7)
    ax2.tick_params(axis="y", labelcolor=DEMAND_COLOR, labelsize=6)
    ax2.set_ylim(0, max(float(mod.max()) * 2.5, 3))

    # (b) Finished stock per model
    ax = axes[1]
    finished_cols = _cols(df, "mfg_finished_", exclude=["mfg_finished_total"])
    if finished_cols:
        colors = _color_cycle(MANUFACTURER_COLORS)
        for col in finished_cols:
            model = col.replace("mfg_finished_", "")
            ax.plot(days, df[col], label=model, marker="s", ms=3, lw=1.8, color=next(colors))
    elif "mfg_finished_total" in df.columns:
        ax.plot(days, df["mfg_finished_total"], label="Total finished", marker="s", ms=3, lw=1.8,
                color=MANUFACTURER_COLORS[0])
    else:
        ax.text(0.5, 0.5, "No finished-stock data", transform=ax.transAxes, ha="center")
    ax.set_title("(b) Finished-printer stock per model", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Units")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(days.min(), days.max())

    # (c) Sales order pipeline — stacked bar by status
    ax = axes[2]
    statuses = ["pending", "released", "in_progress", "shipped", "completed", "delivered"]
    status_colors = ["#93c5fd", "#3b82f6", "#1d4ed8", "#16a34a", "#15803d", "#d1d5db"]
    x = np.arange(len(days))
    bottom = np.zeros(len(days))
    for status, color in zip(statuses, status_colors):
        col = f"mfg_so_{status}"
        vals = df.get(col, pd.Series(np.zeros(len(df)))).values
        if vals.sum() > 0:
            ax.bar(x, vals, bottom=bottom, label=status, color=color, alpha=0.85, width=0.8)
            bottom += vals

    tick_step = max(1, len(days) // 20)
    ax.set_xticks(x[::tick_step])
    ax.set_xticklabels(days.values[::tick_step].astype(int), rotation=45, ha="right", fontsize=7)
    ax.set_title("(c) Sales order pipeline by status (stacked)", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Orders")
    ax.legend(fontsize=7, ncol=3)
    ax.grid(True, alpha=0.25, axis="y")

    # (d) Production utilisation % + wholesale prices
    ax = axes[3]
    if "mfg_utilisation_pct" in df.columns and df["mfg_utilisation_pct"].sum() > 0:
        ax.fill_between(days, df["mfg_utilisation_pct"], alpha=0.2, color=MANUFACTURER_COLORS[1])
        ax.plot(days, df["mfg_utilisation_pct"], label="Utilisation %",
                lw=1.8, color=MANUFACTURER_COLORS[0])
        ax.axhline(100, color="red", ls="--", lw=1, alpha=0.5, label="100% capacity")
    ax.set_title("(d) Production utilisation % + wholesale prices", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Utilisation (%)")
    ax.set_ylim(0, 120)
    ax.grid(True, alpha=0.25)

    ax3 = ax.twinx()
    price_cols = _cols(df, "mfg_price_")
    colors = _color_cycle(MANUFACTURER_COLORS[2:])
    for col in price_cols:
        if df[col].sum() > 0:
            model = col.replace("mfg_price_", "")
            ax3.plot(days, df[col], label=f"Wholesale {model}", ls="--", lw=1.5,
                     marker="^", ms=3, color=next(colors))
    ax3.set_ylabel("Wholesale price (€)", color="gray", fontsize=8)
    ax3.tick_params(axis="y", labelcolor="gray", labelsize=7)

    # Merge legends
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax3.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="upper left")
    ax.set_xlim(days.min(), days.max())
    ax3.set_xlim(days.min(), days.max())

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"{scenario_name}_manufacturer_detail.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ── Retailer detail ────────────────────────────────────────────────────────────

def plot_retailer_detail(df: pd.DataFrame, scenario_name: str) -> Path:
    """Three-panel retailer dashboard:
    (a) Stock per printer model over time
    (b) Retail price per model over time
    (c) Daily customer orders: placed / fulfilled / backordered + total backorder line
    """
    days = df["day"]
    fig, axes = plt.subplots(3, 1, figsize=(13, 16))
    plt.subplots_adjust(hspace=0.45)
    fig.suptitle(f"Retailer Detail — {scenario_name}", fontsize=14, fontweight="bold", y=0.995)

    # (a) Stock per model
    ax = axes[0]
    stock_cols = _cols(df, "ret_stock_")
    if stock_cols:
        colors = _color_cycle(RETAILER_COLORS)
        for col in stock_cols:
            model = col.replace("ret_stock_", "")
            ax.plot(days, df[col], label=model, marker="o", ms=3, lw=1.8, color=next(colors))
        if "ret_total_stock" in df.columns and len(stock_cols) > 1:
            ax.plot(days, df["ret_total_stock"], label="TOTAL", ls="--", lw=1.2, color="black", alpha=0.5)
    elif "ret_total_stock" in df.columns:
        ax.plot(days, df["ret_total_stock"], label="Total stock", marker="o", ms=3, lw=1.8,
                color=RETAILER_COLORS[0])
    ax.set_title("(a) Retailer stock per printer model", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Units")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(days.min(), days.max())

    # Demand modifier shade
    ax2 = ax.twinx()
    mod = df.get("demand_modifier", pd.Series(np.ones(len(df))))
    ax2.fill_between(days, mod, alpha=0.07, color=DEMAND_COLOR)
    ax2.set_ylabel("Demand modifier", color=DEMAND_COLOR, fontsize=7)
    ax2.tick_params(axis="y", labelcolor=DEMAND_COLOR, labelsize=6)
    ax2.set_ylim(0, max(float(mod.max()) * 2.5, 3))

    # (b) Retail prices per model
    ax = axes[1]
    price_cols = _cols(df, "ret_price_")
    if price_cols:
        colors = _color_cycle(RETAILER_COLORS)
        for col in price_cols:
            model = col.replace("ret_price_", "")
            ax.plot(days, df[col], label=model, marker="s", ms=3, lw=1.8, color=next(colors))
    else:
        ax.text(0.5, 0.5, "No retail price data", transform=ax.transAxes, ha="center")
    ax.set_title("(b) Retail price per model", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Retail price (€)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(days.min(), days.max())

    # (c) Daily orders breakdown
    ax = axes[2]
    days_arr = days.values
    placed      = df.get("orders_placed_today",      pd.Series(np.zeros(len(df)))).values
    fulfilled   = df.get("orders_fulfilled_today",   pd.Series(np.zeros(len(df)))).values
    backordered = df.get("orders_backordered_today",  pd.Series(np.zeros(len(df)))).values
    bo_total    = df.get("orders_backordered_total",  pd.Series(np.zeros(len(df)))).values

    x = np.arange(len(days_arr))
    w = 0.26

    ax.bar(x - w, placed,      w, label="Placed",           color="#60a5fa", alpha=0.85)
    ax.bar(x,     fulfilled,   w, label="Fulfilled",         color="#34d399", alpha=0.85)
    ax.bar(x + w, backordered, w, label="Backordered (new)", color="#f87171", alpha=0.85)

    # Total backorder line on secondary y-axis
    ax4 = ax.twinx()
    ax4.plot(x, bo_total, color="#b91c1c", ls="-.", lw=1.5, label="Total backlog")
    ax4.set_ylabel("Total backlog", color="#b91c1c", fontsize=8)
    ax4.tick_params(axis="y", labelcolor="#b91c1c", labelsize=7)

    tick_step = max(1, len(days_arr) // 20)
    ax.set_xticks(x[::tick_step])
    ax.set_xticklabels(days_arr[::tick_step].astype(int), rotation=45, ha="right", fontsize=7)
    ax.set_title("(c) Daily customer orders: placed / fulfilled / backordered", fontweight="bold")
    ax.set_xlabel("Simulated Day")
    ax.set_ylabel("Orders (today)")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax4.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8)
    ax.grid(True, alpha=0.25, axis="y")

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"{scenario_name}_retailer_detail.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# Full dashboard (required Part 5 charts) + detail dashboards
# ══════════════════════════════════════════════════════════════════════════════

def plot_dashboard(scenario_name: str) -> None:
    df = load(scenario_name)

    # Part 5 required: 4 charts in one figure
    fig, axes = plt.subplots(4, 1, figsize=(13, 24))
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

    # Extra detailed dashboards
    plot_provider_detail(df, scenario_name)
    plot_manufacturer_detail(df, scenario_name)
    plot_retailer_detail(df, scenario_name)


# ── Side-by-side comparison ────────────────────────────────────────────────────

def plot_comparison() -> None:
    try:
        calm    = load("calm-market")
        holiday = load("holiday-rush")
    except FileNotFoundError as exc:
        print(f"[SKIP] Comparison: {exc}")
        return

    fig, axes = plt.subplots(3, 2, figsize=(22, 18))
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


# ── Entry point ────────────────────────────────────────────────────────────────

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
