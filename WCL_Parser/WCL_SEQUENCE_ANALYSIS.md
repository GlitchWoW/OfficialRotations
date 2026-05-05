# WCL Sequence Analysis

This tool answers questions like:

- What spell is cast most often after `Unleash Life`?
- What is the first follow-up after `Avenging Wrath`?
- Across top dungeon logs, what do players cast after a trigger spell?

It uses the same Warcraft Logs client credentials flow as `wcl_timers.py`.

## Setup

Set your WCL client credentials:

```powershell
$env:WCL_CLIENT_ID="your_client_id"
$env:WCL_CLIENT_SECRET="your_client_secret"
```

## Script

Run:

```powershell
python WCL_Parser\wcl_sequence_analysis.py --help
```

## Common Example

Restoration Shaman: first cast after `Unleash Life` among `Healing Wave`, `Riptide`, and `Chain Heal`, across top 10 Mythic+ Season 3 dungeon logs:

```powershell
python WCL_Parser\wcl_sequence_analysis.py `
  --zone 45 `
  --difficulty 10 `
  --class-name Shaman `
  --spec-name Restoration `
  --metric hps `
  --top 10 `
  --trigger 73685 `
  --followups 77472,61295,1064 `
  --spell-names 73685:Unleash Life,77472:Healing Wave,61295:Riptide,1064:Chain Heal
```




## Useful Flags

- `--zone`: WCL zone ID. Example: `45` for Mythic+ Season 3.
- `--difficulty`: WCL difficulty ID. Example: `10` for Mythic+.
- `--class-name`: WCL class name.
- `--spec-name`: WCL spec name.
- `--metric`: `hps` or `dps`.
- `--top`: top public logs per encounter.
- `--trigger`: trigger spell ID.
- `--followups`: comma-separated follow-up spell IDs.
- `--spell-names`: optional spell labels in `id:label` CSV form.
- `--encounters`: optional comma-separated encounter names or IDs.
- `--max-gap-ms`: optional cap on time between trigger and follow-up.
- `--report-out`: optional JSON output path.

## Output

The script prints JSON including:

- overall counts
- overall percentages
- total trigger count
- matched vs unmatched trigger counts
- per-encounter breakdown
- failed report lookups, if any

## Notes

- The script uses top public logs only.
- By default it inspects all encounters in the selected zone.
- The counted result is the first qualifying follow-up spell after each trigger cast.
