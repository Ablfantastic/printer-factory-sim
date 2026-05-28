# Provider Manager

Manage the parts supplier for ONE day. Bash tool only. Do NOT advance the day.

Your current state, starting stock thresholds, catalog tiers, RESTOCK flags, and an ACTION HINT are already provided in the prompt.
Do NOT run assessment/list/catalog commands. Go directly to actions.

## Fast path

Build ONE bash call combining restocks + price changes (when applicable), chain with `&&`.

If Recommended bash is `none` AND SUPPLY SHORTAGE PRICE RAISE is `none`, do not call Bash. Just write the summary.

## Rules

### Restocking
- Restock only products marked `<- RESTOCK` or listed in Recommended bash.
- Restock quantity should bring stock back to the starting level.

### Price changes — execute when the hint says so
- **SUPPLY SHORTAGE PRICE RAISE**: if this line is NOT `none`, execute those commands. They are pre-computed. Chain them in the bash call.
- **Stock-level rules** (use when no supply hint): lower top tier 5-10% if stock > 150% starting; raise top tier 5-10% if stock < 30% starting.
- Max change: 15% per day. Do not change the same product two days in a row unless the shortage worsens.

```bash
./start_cli.sh restock sensor_autonivel 40 && ./start_cli.sh price set CTRL-V2 1 95.2 && ./start_cli.sh price set kit_piezas 1 57.2
```

## Summary (required, plain ASCII, no emojis)

End with exactly:
```
## END-OF-DAY SUMMARY
- Stock: <levels after changes>
- Actions taken: <restocks and price changes, or "none">
- Risk: <one sentence>
```
