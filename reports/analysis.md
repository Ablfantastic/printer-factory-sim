# Supply Chain Simulation — Analysis Report

**Scenarios:** calm-market (25 days) · holiday-rush (25 days)  
**Agents:** Provider (ChipSupply Co) · Manufacturer (Factory) · Retailer (PrinterWorld)  
**Charts:** See `reports/*.png`

---

## Chart 1 — Inventory Over Time

### calm-market

The retailer's printer stock collapses from 16 units on day 1 to zero by day 3 and never recovers. Manufacturer raw-parts stock oscillates between 78 and 245 units, declining mid-run as the manufacturer consumes parts to fulfil a growing backlog. The flat orange band (demand modifier 0.75–1.05×) confirms demand was stable, so the collapse is structural: the retailer's initial stock of 16 units lasts roughly one day of demand (~8–10 orders/day), and replenishment lead times (2–5 days production + shipping) are too long to keep pace.

### holiday-rush

Retailer stock hits zero by day 3 — even before Black Friday — and stays there for the entire 25-day run. The manufacturer's parts stock tells the more interesting story: it peaks at 278 on day 8 (Black Friday eve), drops slightly through the peak (days 9–12) as parts are consumed in production, then climbs relentlessly from 343 (day 13) to **1,216 units by day 25**. This growth happens because purchase orders placed during the frantic days 1–12 keep arriving from the provider long after the demand peak has passed, a textbook **bullwhip accumulation**. The retailer's finished-printer stock stays at 0 throughout because every printer produced is immediately dispatched to clear backordered customer orders.

---

## Chart 2 — Prices Over Time

### Both scenarios

Prices are completely flat in both runs: provider kit_piezas stays at €135, manufacturer P3D-Classic wholesale at €370, retailer P3D-Classic retail at €479.99 for all 25 days. None of the three agents ever triggered a price-change action. The reason is a **skill-implementation gap**: the `run_simulation.py` agent turns implement fulfil/release/restock decisions but not pricing logic. The price-adjustment branches in the skill files (raise 5–10% on high demand, lower 5–10% on excess stock) were not ported to the automated runner. In a real deployment, retail prices would have risen sharply around days 9–11 (Black Friday peak) and fallen from day 17 as demand softened. The absence of price signals means demand was never moderated by price, which amplified the order cascade seen in Chart 3.

---

## Chart 3 — Order Fulfillment

### calm-market

Orders placed per day hover at 4–10, matching the low demand modifier (0.75–1.05×). Fulfilled orders drop to near zero after day 3 because retailer stock is exhausted. The backordered total grows steadily from 0 to 43 by day 25 — a slow but persistent drain on customer satisfaction. There is no recovery because the manufacturer cannot ramp production faster than demand accumulates.

### holiday-rush

The fulfillment chart reveals the crisis clearly. Days 1–7: placed ≈10–15/day, fulfilled matches or nearly matches (stock is consumed quickly). Day 8 (BF eve, modifier 1.60×): 22 orders placed, 0 fulfilled — stock already exhausted. Day 9 (Black Friday, modifier 2.50×): **34 orders in a single day**, only 6 fulfilled, 6 newly backordered. Days 10–16: fulfilled orders appear in bursts (15 on day 10, 20 on day 13, 26 on day 16) as manufacturer shipments arrive and are immediately consumed by the backlog. From day 17 onwards, **zero orders are fulfilled** for the remaining 9 days: the manufacturer's production is stalled because the provider has run out of critical components (CTRL-V2, extrusor, sensor_autonivel all hit 0), and the provider agent never restocks (see "What went wrong" below). Total backordered: **190 orders by day 25**.

---

## Chart 4 — Events Overlay (Demand Modifier)

### calm-market

The demand modifier profile is flat (0.75–1.05×), reflected in a uniformly low bar chart. No event triggers any notable change in agent behaviour: prices stay fixed, orders stay small, backorders accumulate slowly. The scenario serves as a useful baseline: even without a demand shock, the system cannot maintain service levels because of structural lead-time mismatches.

### holiday-rush

The Black Friday spike (day 9: 2.50×, days 10–12: 2.20–1.70×) is clearly visible as red bars. The system's response is delayed: the manufacturer starts receiving large retailer purchase orders from day 3 onwards (as the retailer tries to rebuild stock), which triggers part orders to the provider from day 3–8. Those part orders deplete the provider's stock. When Black Friday hits, the manufacturer has parts but the provider is already dry — so new part orders after day 9 return 502 errors. The causal chain runs from the events overlay backward through Chart 3 (order spike) to Chart 1 (parts accumulation after day 13 = orphaned deliveries with no demand to consume them).

---

## Specific Questions — Holiday-Rush Run

### Did the manufacturer build stock ahead of Black Friday?

**Partially, but not intentionally.** The manufacturer's raw-parts stock rose from 245 (day 1) to 278 (day 8, BF eve), a modest 14% increase. This happened because the retailer began placing larger purchase orders from day 3 (as its stock depleted), which caused the manufacturer to release more sales orders and order more parts. However, this was reactive, not anticipatory — the manufacturer agent has no look-ahead and no signal about the upcoming demand spike. A smarter agent would have seen `demand_modifier = 1.60` on day 8 in the scenario and pre-ordered parts several lead times in advance. Instead, the parts for BF production were ordered on days 3–8, arriving from day 6–14, which is too late to help day 9 customers.

### When stockouts happened, whose decision was the proximate cause? Whose was the root cause?

**Proximate cause: the retailer.** The retailer started with 16 units of finished printers across three models and was receiving 13–14 customer orders per day. This stock lasted less than two days. The retailer agent placed reorder requests to the manufacturer from day 1, but lead times (production_days = 2–3 days + shipping) meant printers arrived only on days 3–5.

**Root cause: the provider's missing restock logic.** The provider skill explicitly states *"Do NOT let any product go to zero stock while purchase orders for it are pending."* However, the automated `provider_turn` function in `run_simulation.py` only reads and logs state — it never calls a restock API (which, additionally, does not exist as a REST endpoint; only as a CLI command that writes directly to the database). Without restocking, the provider depleted CTRL-V2 to 0, extrusor to 2, sensor_autonivel to 28, and kit_piezas to 14 by the time Black Friday hit. From day 20, every manufacturer purchase order fails with a 502 error. This is a skill-to-implementation gap: the skill described the rule but the automated runner did not implement it.

### Did prices stabilise or oscillate?

**Prices neither stabilised nor oscillated — they were frozen.** The automated agents do not implement price-adjustment logic. In the holiday-rush, a correctly implemented retailer agent would have raised retail prices ~5–10% around days 8–12 (multiple backorders, zero stock), which would have damped demand somewhat and eased the crisis. The absence of pricing feedback is partly why backorders reached 190: demand was never signalled to slow down.

### Can you identify a bullwhip moment?

**Yes — clearly visible in Chart 1.** From day 13 to day 25, the manufacturer's raw-parts stock grows from 343 to **1,216 units**, even though production is ongoing and retailer demand continues. The mechanism: during days 1–12, the manufacturer ordered large quantities of parts (with 4–6 day lead times) to keep up with Black Friday demand. Those orders continued arriving through days 13–25. Meanwhile, the production bottleneck (daily capacity 3–8 units/model, production_days 2–3) could not consume parts fast enough, and the provider's own stockouts (from depleting its stock to fill those same orders) prevented any new orders from succeeding. The result is a warehouse full of parts with no ability to convert them to printers — the upstream inventory signal was amplified relative to the original downstream demand, a classic **Forrester bullwhip**.

---

## Scenario Comparison

### What the agents do in calm-market that they do not in holiday-rush (and vice versa)

In the calm scenario, the manufacturer agent places modest part orders (buffer=5 units per part) and the retailer places conservative reorders (target=6, lot=4). The system settles into a low-level chronic backorder state without drama: stock is gone but orders are small, and the agents maintain predictable if insufficient service.

In the holiday-rush, the same agents — facing the same structural constraints — generate a far more volatile trajectory. The retailer's higher policy parameters (target=8, lot=6) trigger larger purchase orders from the manufacturer, which triggers larger part orders from the provider, which depletes the provider's stock faster. The holiday demand spike then arrives into a system that has already spent its buffers. The agents do not *do* anything fundamentally different, but the parameter magnification and the demand spike interact to produce collapse.

**Is this a success or failure?** The agents' *behaviour* is internally consistent with their policies. The *failure* is twofold: (1) no agent adjusts prices to dampen demand, and (2) the provider's restock logic was not implemented, removing the safety valve that would have kept parts flowing. A correctly implemented system with price feedback and provider restocking would likely show a smoother holiday-rush trajectory — higher prices dampening demand during the spike, provider rebuilding stock during off-peak days, and a controlled (not catastrophic) backorder peak.

---

## Known Limitations

| Issue | Impact |
|---|---|
| Provider restock not implemented in runner | Provider stock depletes permanently; cascade failure from day 20 |
| Price logic not implemented in runner | No demand moderation; backorders accumulate unchecked |
| Metrics captured at start of day (before fulfillment) | `orders_placed_today`/`orders_fulfilled_today` backfilled from API for holiday-rush; estimated for calm-market |
| calm-market fulfillment data lost (DB reset before holiday-rush run) | Fulfillment chart for calm-market uses estimated values |
| Run time ~45 min per scenario | Exceeds 30-min target; root cause is sequential API latency, not prompt size |
