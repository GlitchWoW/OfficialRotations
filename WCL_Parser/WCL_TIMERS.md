# WCL Timers Generator

This tool pulls top public logs from Warcraft Logs (WCL) and generates Lorrgs timer strings for the specs/bosses you configure.

## Setup

1. Create a WCL API client (client credentials flow).
2. Set env vars (do not commit secrets):

```powershell
$env:WCL_CLIENT_ID="your_client_id"
$env:WCL_CLIENT_SECRET="your_client_secret"
```

If you want them to persist across terminals:

```powershell
[Environment]::SetEnvironmentVariable("WCL_CLIENT_ID","<your_client_id>","User")
[Environment]::SetEnvironmentVariable("WCL_CLIENT_SECRET","<your_client_secret>","User")
```

## Class/Spec Names

Generate the authoritative list from WCL:

```powershell
python WCL_Parser\wcl_timers.py --list-specs --list-specs-out WCL_Parser\WCL_CLASSES_SPECS.md
```

Use the exact `className` and `specName` values from that file.

## Configuration

Edit `WCL_Parser/wcl_timers.json`.

Key fields:
- `difficultyIds`: list of WCL difficulty IDs. `4` = Heroic, `5` = Mythic.
- `zones`: list of zones to include.
  - `id`: WCL zone ID.
  - `encounters`: list of encounter objects.
    - `name`: WCL encounter name.
    - `npcId`: **required** NPC ID used in `LorrgsTimers` (always prefer explicit IDs).
- `specs`: map of spec label -> spec config.
  - `className`: WCL class name (e.g., `Monk`).
  - `specName`: WCL spec name (e.g., `Mistweaver`).
  - `metric`: WCL ranking metric. For healers use `hps`. For DPS use `dps`.
  - `topN`: optional, number of top public logs to aggregate for this spec (default `1`). Can be overridden by `--top`.
  - `mode`: default action mode for spells: `toggle` or `spell`.
  - `label`: default toggle label (e.g., `Ramp`, `Cooldowns`).
  - `spells`: list of spell entries to track.

### Spell entries

Each spell entry can be:
- an integer spell ID (uses the spec default `mode` and `label`), or
- an object with overrides:
  - `id`: spell ID (required)
  - `mode`: `toggle` or `spell` (optional)
  - `label`: toggle label (optional; used when mode is `toggle`)

Examples:

```json
"spells": [322118, 325197, 115310]
```

```json
"mode": "toggle",
"label": "Ramp",
"spells": [
  { "id": 325197, "label": "Ramp" },
  { "id": 115310, "mode": "spell" }
]

"MW Monk": {
  "className": "Monk",
  "specName": "Mistweaver",
  "metric": "hps",
  "topN": 5,
  "anchorMode": "nearest_boss_event",
  "anchorSpells": [322118],
  "spells": [
    { "id": 322118, "label": "Ramp" }
    ]
},
"Holy Pally": {
  "className": "Paladin",
  "specName": "Holy",
  "metric": "hps",
  "topN": 5,
  "anchorMode": "nearest_boss_event",
  "anchorSpells": [216331, 31884],
  "spells": [
    { "id": 216331, "mode": "spell" },
    { "id": 31884, "mode": "spell" }
  ]
}
```

In the second example:
- Yu'lon and Chi-Ji will emit `{Ramp}` entries
- Revival will emit `{spell:115310}` entries

## Run

```powershell
python WCL_Parser\wcl_timers.py --spec "MW Monk"
```

To aggregate across top 5 logs:

```powershell
python WCL_Parser\wcl_timers.py --spec "MW Monk" --top 5
```

To run all specs in the config (may take a while):

```powershell
python WCL_Parser\wcl_timers.py
```

## Updating LorrgsTimers.lua

To add missing spec blocks to `common/LorrgsTimers.lua`, run with:

```powershell
python WCL_Parser\wcl_timers.py --update-main
```

To ensure no updates are made:

```powershell
python WCL_Parser\wcl_timers.py --no-update-main
```

## Output

- Generated file: `WCL_Parser/LorrgsTimers_generated.lua`
- This is auto-merged by `common/LorrgsTimers.lua` for both Heroic (`dynamicTimers`) and Mythic (`dynamicMythic`).

## Notes

- The script selects the **top public** log for each boss/spec/difficulty based on the configured `metric`.
- If you want to use a specific log or aggregate multiple logs, we can extend the script.
- Always keep `npcId` in config to avoid name mismatches between WCL and your local boss list.
