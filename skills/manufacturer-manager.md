# Manufacturer Manager

Manage the 3D printer factory for ONE day. Bash tool only. Do NOT advance the day.

Your current state, supplier catalog, parts needing orders, and an ACTION HINT are already provided in the prompt.
Do NOT run assessment/list/catalog commands. Go directly to actions.

## Fast path

Use the "Recommended bash" line from ACTION HINT whenever it is not `none`.
Run it as ONE Bash call, chaining releases and purchase orders with `&&`.

If Recommended bash is `none` AND WHOLESALE PRICE RAISE is `none`, do not call Bash. Just write the summary.

## Rules

### Production
- Release pending sales orders from oldest to newest using the recommended release commands.
- Do not split orders; the CLI only releases whole sales orders.

### Parts ordering
- Order only parts listed in "Parts needing orders" (already includes demand buffer).
- Do not duplicate open purchase orders already shown in the state.
- Use the pre-fetched supplier name and product names exactly.

### Wholesale price changes — execute when the hint says so
- **WHOLESALE PRICE RAISE**: if this line is NOT `none`, append those commands to your bash call.
  They trigger when utilisation >= 200% or demand_modifier >= 2.0 with large backlog.
- Never lower wholesale price unless finished stock exceeds 15 units per model AND no pending sales orders exist.
- Max change: 10% per day.

```bash
./start_cli.sh production release 4 && ./start_cli.sh purchase create --supplier ChipSupply\ Co --product sensor_autonivel --qty 20 && ./start_cli.sh price set P3D-Classic 420.0
```

## Summary (required, plain ASCII, no emojis)

End with exactly:
```
## END-OF-DAY SUMMARY
- Stock: <raw parts and finished goods>
- Actions taken: <orders released, parts ordered, price changes, or "none">
- Risk: <one sentence>
```
