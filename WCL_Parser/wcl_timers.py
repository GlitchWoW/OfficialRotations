import json, os, re, sys, urllib.request, urllib.parse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

CONFIG_DEFAULT = os.path.join('WCL_Parser', 'wcl_timers.json')
OUT_DEFAULT = os.path.join('WCL_Parser', 'LorrgsTimers_generated.lua')


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def load_config(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def get_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing env var {name}")
    return val


def get_token() -> str:
    data = urllib.parse.urlencode({
        'grant_type': 'client_credentials',
        'client_id': get_env('WCL_CLIENT_ID'),
        'client_secret': get_env('WCL_CLIENT_SECRET'),
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://www.warcraftlogs.com/oauth/token',
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))['access_token']


def gql(token: str, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        'https://www.warcraftlogs.com/api/v2/client',
        data=body,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))


def normalize_name(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', s.lower())


def load_boss_npc_map(path: str) -> Dict[str, List[int]]:
    rx = re.compile(r'\[(\d+)\]\s*=\s*{\s*name\s*=\s*"([^"]+)"')
    mapping: Dict[str, List[int]] = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            m = rx.search(line)
            if not m:
                continue
            npc_id = int(m.group(1))
            name = m.group(2)
            key = normalize_name(name)
            mapping.setdefault(key, []).append(npc_id)
    return mapping


def resolve_encounter(token: str, zone_id: int, entry: Any) -> Dict[str, Any]:
    query = f'query {{ worldData {{ zone(id: {zone_id}) {{ id name encounters {{ id name }} }} }} }}'
    data = gql(token, query)
    zone = data.get('data', {}).get('worldData', {}).get('zone')
    if not zone:
        raise RuntimeError(f"Zone {zone_id} not found in worldData")
    encounters = zone.get('encounters', [])
    by_norm = {normalize_name(e['name']): e for e in encounters}

    if isinstance(entry, dict):
        name = entry.get('name')
    else:
        name = entry
    if isinstance(name, int):
        match = next((e for e in encounters if e['id'] == name), None)
        if not match:
            raise RuntimeError(f"Encounter id {name} not found in zone {zone_id}")
        return match
    key = normalize_name(str(name))
    if key in by_norm:
        return by_norm[key]
    match = None
    for e in encounters:
        en = normalize_name(e['name'])
        if key in en or en in key:
            match = e
            break
    if not match:
        raise RuntimeError(f"Encounter '{name}' not found in zone {zone_id}")
    return match


def resolve_npc_id(encounter_name: str, npc_map: Dict[str, List[int]], override_npc_id: Optional[int] = None) -> int:
    if override_npc_id:
        return int(override_npc_id)
    en = normalize_name(encounter_name)
    if en in npc_map:
        return npc_map[en][0]
    best = None
    best_len = 0
    for name_norm, ids in npc_map.items():
        if name_norm in en or en in name_norm:
            if len(name_norm) > best_len:
                best = ids[0]
                best_len = len(name_norm)
    if best is not None:
        return best
    raise RuntimeError(f"No NPC id match for encounter '{encounter_name}'. Provide npcId in config.")


def choose_rankings(token: str, encounter_id: int, class_name: str, spec_name: str, difficulty_id: int, metric: str, top_n: int) -> List[Dict[str, Any]]:
    query = (
        'query { worldData { encounter(id: %d) { '
        'characterRankings(difficulty:%d, className:"%s", specName:"%s", metric:%s, page:1) '
        '} } }'
    ) % (encounter_id, difficulty_id, class_name, spec_name, metric)
    res = gql(token, query)
    rankings = res['data']['worldData']['encounter']['characterRankings']['rankings']
    public = []
    for r in rankings:
        if not r.get('hidden') and not str(r.get('report', {}).get('code', '')).startswith('a:'):
            public.append(r)
        if len(public) >= top_n:
            break
    if public:
        return public
    if not rankings:
        raise RuntimeError("No rankings found")
    return rankings[:top_n]


def get_fight_info(token: str, report_code: str, fight_id: int) -> Dict[str, Any]:
    query = f'''query {{
      reportData {{
        report(code: "{report_code}") {{
          fights(fightIDs: [{fight_id}]) {{ id startTime endTime encounterID difficulty kill }}
          playerDetails(fightIDs: [{fight_id}], includeCombatantInfo: false)
        }}
      }}
    }}'''
    res = gql(token, query)
    return res['data']['reportData']['report']


def find_player_id(report: Dict[str, Any], player_name: str, class_name: str) -> int:
    details = report['playerDetails']['data']['playerDetails']
    for role in ('healers', 'dps', 'tanks'):
        for p in details.get(role, []):
            if p.get('name') == player_name and p.get('type') == class_name:
                return p['id']
    raise RuntimeError(f"Player {player_name} ({class_name}) not found in report")


def fetch_casts(token: str, report_code: str, fight_id: int, source_id: int, spell_ids: List[int]) -> List[Dict[str, Any]]:
    filter_expr = ' or '.join([f"ability.id={sid}" for sid in spell_ids])
    query = '''query($code:String!, $fightIDs:[Int], $sourceID:Int, $start:Float, $filter:String) {
      reportData {
        report(code:$code) {
          events(dataType:Casts, fightIDs:$fightIDs, sourceID:$sourceID, startTime:$start, filterExpression:$filter, useAbilityIDs:true) {
            data
            nextPageTimestamp
          }
        }
      }
    }'''
    start = None
    all_events = []
    while True:
        vars = {'code': report_code, 'fightIDs': [fight_id], 'sourceID': source_id, 'start': start, 'filter': filter_expr}
        res = gql(token, query, vars)
        ev = res['data']['reportData']['report']['events']
        all_events.extend(ev['data'])
        if not ev.get('nextPageTimestamp'):
            break
        start = ev['nextPageTimestamp']
    return all_events


def format_times(events: List[Dict[str, Any]], fight_start: float) -> List[str]:
    times = []
    for e in events:
        ts = e['timestamp']
        offset = (ts - fight_start) / 1000.0
        if offset < 0:
            continue
        m = int(offset // 60)
        s = int(round(offset % 60))
        times.append(f"{m:02d}:{s:02d}")
    times = sorted(set(times), key=lambda t: (int(t.split(':')[0]), int(t.split(':')[1])))
    return times


def format_times_by_spell(events: List[Dict[str, Any]], fight_start: float) -> Dict[int, List[float]]:
    by_spell: Dict[int, List[float]] = {}
    for e in events:
        sid = e.get('abilityGameID')
        if not sid:
            continue
        offset = (e['timestamp'] - fight_start) / 1000.0
        if offset < 0:
            continue
        by_spell.setdefault(int(sid), []).append(offset)
    for sid, arr in by_spell.items():
        arr.sort()
    return by_spell


def aggregate_median_per_index(time_lists: List[List[float]]) -> List[float]:
    # time_lists: list of ordered time lists (per log)
    # For cast index i, compute median of logs that have i-th cast.
    if not time_lists:
        return []
    max_len = max(len(lst) for lst in time_lists)
    out: List[float] = []
    for i in range(max_len):
        vals = [lst[i] for lst in time_lists if len(lst) > i]
        if not vals:
            continue
        vals.sort()
        mid = len(vals) // 2
        if len(vals) % 2 == 1:
            out.append(vals[mid])
        else:
            out.append((vals[mid - 1] + vals[mid]) / 2.0)
    return out


def seconds_to_timestr(seconds: float) -> str:
    mm = int(seconds // 60)
    ss = int(round(seconds % 60))
    return f"{mm:02d}:{ss:02d}"


def build_lua_string(times: List[str], label: str) -> str:
    return "\\n".join([f"{{time:{t}}} - {{{label}}}" for t in times])


def build_dsl_table(actions: List[Tuple[int, Dict[str, Any]]]) -> Dict[int, List[Dict[str, Any]]]:
    # actions: list of (timeSeconds, actionDict)
    table: Dict[int, List[Dict[str, Any]]] = {}
    for t, a in actions:
        table.setdefault(t, []).append(a)
    return table


def normalize_spell_entries(spell_entries: List[Any], default_label: str, default_mode: str) -> List[Dict[str, Any]]:
    out = []
    for entry in spell_entries:
        if isinstance(entry, int):
            out.append({"id": entry, "label": default_label, "mode": default_mode})
        elif isinstance(entry, dict):
            sid = entry.get("id")
            if not sid:
                raise RuntimeError("Spell entry missing id")
            out.append({
                "id": int(sid),
                "label": entry.get("label", default_label),
                "mode": entry.get("mode", default_mode),
            })
        else:
            raise RuntimeError("Invalid spell entry; must be int or object with id")
    return out


def lua_val(v: Any) -> str:
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    raise TypeError(v)


def lua_dsl_table(tbl: Dict[int, List[Dict[str, Any]]]) -> str:
    lines = ["{"] 
    for t in sorted(tbl.keys()):
        lines.append(f"    [{t}] = {{")
        for act in tbl[t]:
            lines.append("        { " + ", ".join([
                f"method = {lua_val(act.get('method'))}",
                f"ID = {lua_val(act.get('ID'))}",
                f"occurrence = {lua_val(act.get('occurrence'))}",
                f"spellId = {lua_val(act.get('spellId'))}",
                f"toggle = {lua_val(act.get('toggle'))}",
            ]) + " },")
        lines.append("    },")
    lines.append("}")
    return "\n".join(lines)


def write_lua(path: str, data_by_bucket: Dict[str, Dict[str, Dict[int, Dict[int, List[Dict[str, Any]]]]]]):
    lines = []
    lines.append("local generated = {")
    for bucket_name in ("dynamicTimers", "dynamicMythic"):
        bucket = data_by_bucket.get(bucket_name, {})
        lines.append(f"    {bucket_name} = {{")
        for spec, bosses in bucket.items():
            lines.append(f"        [\"{spec}\"] = {{")
            for boss_id, dsl_tbl in bosses.items():
                lines.append(f"            [{boss_id}] = {lua_dsl_table(dsl_tbl)},")
            lines.append("        },")
        lines.append("    },")
    lines.append("}")
    lines.append("")
    lines.append("return generated")
    with open(path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


def upsert_specs_into_main(main_path: str, data_by_bucket: Dict[str, Dict[str, Dict[int, Dict[int, List[Dict[str, Any]]]]]]):
    text = Path(main_path).read_text(encoding="utf-8")

    def find_range(src: str, open_idx: int) -> Tuple[int, int]:
        brace = 0
        for idx in range(open_idx, len(src)):
            if src[idx] == "{":
                brace += 1
            elif src[idx] == "}":
                brace -= 1
                if brace == 0:
                    return open_idx, idx
        raise RuntimeError("Unbalanced braces")

    def find_block_bounds(src: str, name: str) -> Tuple[int, int]:
        marker = f"LorrgsTimers.{name} = {{"
        start = src.find(marker)
        if start == -1:
            raise RuntimeError(f"Could not find {name} block in {main_path}")
        open_idx = src.find("{", start)
        _, close_idx = find_range(src, open_idx)
        return open_idx, close_idx

    def build_spec_block(spec: str, bosses: Dict[int, Dict[int, List[Dict[str, Any]]]]) -> str:
        lines = [f'    ["{spec}"] = {{']
        for boss_id, dsl_tbl in bosses.items():
            lines.append(f"        [{boss_id}] = {lua_dsl_table(dsl_tbl)},")
        lines.append("    },")
        return "\n".join(lines)

    def replace_or_insert_spec(src: str, block_open: int, block_close: int, spec: str, spec_block: str) -> str:
        spec_anchor = f'["{spec}"] = {{'
        search_start = block_open
        while True:
            i = src.find(spec_anchor, search_start, block_close)
            if i == -1:
                # insert before block close
                return src[:block_close] + "\n" + spec_block + "\n" + src[block_close:]
            # validate this spec is at top-level depth inside block
            depth = 0
            for k in range(block_open, i):
                if src[k] == "{":
                    depth += 1
                elif src[k] == "}":
                    depth -= 1
            if depth == 1:
                spec_open = src.find("{", i)
                _, spec_close = find_range(src, spec_open)
                # include trailing comma after spec block, if present
                after = spec_close + 1
                while after < len(src) and src[after] in " \t\r\n":
                    after += 1
                if after < len(src) and src[after] == ",":
                    after += 1
                return src[:i] + spec_block + src[after:]
            search_start = i + len(spec_anchor)

    out = text
    for bucket_name in ("dynamicTimers", "dynamicMythic"):
        bucket = data_by_bucket.get(bucket_name, {})
        if not bucket:
            continue

        open_idx, close_idx = find_block_bounds(out, bucket_name)
        # process each spec and recalc bounds after each mutation
        for spec, bosses in bucket.items():
            spec_block = build_spec_block(spec, bosses)
            out = replace_or_insert_spec(out, open_idx, close_idx, spec, spec_block)
            open_idx, close_idx = find_block_bounds(out, bucket_name)

    Path(main_path).write_text(out, encoding="utf-8")


def fetch_class_specs(token: str) -> List[Dict[str, Any]]:
    query = 'query { gameData { classes { name specs { name } } } }'
    res = gql(token, query)
    return res['data']['gameData']['classes']


def format_class_specs_md(classes: List[Dict[str, Any]]) -> str:
    lines = []
    lines.append("# WCL Class/Spec Names")
    lines.append("")
    lines.append("Use these exact `className` and `specName` values in `wcl_timers.json`.")
    lines.append("")
    for c in classes:
        lines.append(f"## {c['name']}")
        for s in c.get('specs', []):
            lines.append(f"- {s['name']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Generate Lorrgs timers from WCL')
    ap.add_argument('--config', default=CONFIG_DEFAULT)
    ap.add_argument('--spec', default='Holy Pally', help='Spec label to build (as in config spec key). Comma-separated for multiple.')
    ap.add_argument('--out', default=OUT_DEFAULT)
    ap.add_argument('--update-main', action='store_true', help='Upsert generated spec entries into common/LorrgsTimers.lua (add or replace)')
    ap.add_argument('--no-update-main', action='store_true', help='Disable updating common/LorrgsTimers.lua')
    ap.set_defaults(update_main=True)
    ap.add_argument('--list-specs', action='store_true', help='Print all valid class/spec names from WCL and exit.')
    ap.add_argument('--list-specs-out', default=None, help='Write class/spec list to a markdown file and exit.')
    ap.add_argument('--top', type=int, default=None, help='Number of top public logs to aggregate (overrides config).')
    args = ap.parse_args()

    cfg = load_config(args.config)
    token = get_token()

    if args.list_specs:
        classes = fetch_class_specs(token)
        md = format_class_specs_md(classes)
        if args.list_specs_out:
            with open(args.list_specs_out, 'w', encoding='utf-8') as f:
                f.write(md)
            print(f"Wrote {args.list_specs_out}")
        else:
            print(md)
        return

    npc_map = load_boss_npc_map(os.path.join('common', 'lists', 'unitIsBossList.lua'))

    spec_filter = None
    if args.spec:
        spec_filter = {s.strip() for s in args.spec.split(',') if s.strip()}

    difficulty_ids = cfg.get('difficultyIds')
    if difficulty_ids is None:
        difficulty_ids = [int(cfg.get('difficultyId', 4))]
    difficulty_ids = [int(d) for d in difficulty_ids]
    zones = cfg.get('zones', [])
    specs_cfg = cfg.get('specs', {})
    top_n = int(cfg.get('topN', 1))
    if args.top is not None:
        top_n = int(args.top)

    out_data_by_bucket: Dict[str, Dict[str, Dict[int, Dict[int, List[Dict[str, Any]]]]]] = {
        "dynamicTimers": {},
        "dynamicMythic": {},
    }

    for spec_label, sc in specs_cfg.items():
        if spec_filter and spec_label not in spec_filter:
            continue
        class_name = sc['className']
        spec_name = sc['specName']
        metric = sc.get('metric')
        if not metric:
            raise RuntimeError(f"Spec {spec_label} missing metric")
        spec_top_n = int(sc.get('topN', top_n))
        default_label = sc.get('label', 'Ramp')
        default_mode = sc.get('mode', 'toggle')
        spell_entries = normalize_spell_entries(sc.get('spells', []), default_label, default_mode)
        if not spell_entries:
            raise RuntimeError(f"Spec {spec_label} missing spells list")
        spell_ids = sorted({e['id'] for e in spell_entries})
        entry_by_id = {e['id']: e for e in spell_entries}

        for z in zones:
            zone_id = int(z['id'])
            enc_entries = z.get('encounters', [])
            if not enc_entries:
                continue
            for entry in enc_entries:
                enc = resolve_encounter(token, zone_id, entry)
                enc_name = enc['name']
                enc_id = int(enc['id'])
                npc_override = None
                if isinstance(entry, dict):
                    npc_override = entry.get('npcId')
                npc_id = resolve_npc_id(enc_name, npc_map, npc_override)

                for difficulty_id in difficulty_ids:
                    bucket = "dynamicTimers" if difficulty_id == 4 else "dynamicMythic" if difficulty_id == 5 else "dynamicTimers"
                    out_bucket = out_data_by_bucket[bucket]
                    out_bucket.setdefault(spec_label, {})

                    rankings = choose_rankings(token, enc_id, class_name, spec_name, difficulty_id, metric, spec_top_n)

                    per_spell_times: Dict[int, List[List[float]]] = {sid: [] for sid in spell_ids}
                    used_reports = 0
                    for ranking in rankings:
                        report_code = ranking['report']['code']
                        fight_id = int(ranking['report']['fightID'])
                        player_name = ranking['name']

                        report = get_fight_info(token, report_code, fight_id)
                        fight = report['fights'][0]
                        fight_start = fight['startTime']

                        player_id = find_player_id(report, player_name, class_name)
                        events = fetch_casts(token, report_code, fight_id, player_id, spell_ids)
                        by_spell = format_times_by_spell(events, fight_start)
                        for sid in spell_ids:
                            per_spell_times[sid].append(by_spell.get(sid, []))
                        used_reports += 1

                    actions: List[Tuple[int, Dict[str, Any]]] = []
                    for sid, lists in per_spell_times.items():
                        aggregated = aggregate_median_per_index(lists)
                        entry = entry_by_id.get(sid)
                        if not entry:
                            continue
                        for sec in aggregated:
                            t_sec = int(round(sec))
                            if entry['mode'] == 'spell':
                                action = {
                                    "method": None,
                                    "ID": None,
                                    "occurrence": None,
                                    "spellId": int(sid),
                                    "toggle": None,
                                }
                            else:
                                action = {
                                    "method": None,
                                    "ID": None,
                                    "occurrence": None,
                                    "spellId": None,
                                    "toggle": entry['label'],
                                }
                            actions.append((t_sec, action))

                    dsl_tbl = build_dsl_table(actions)
                    out_bucket[spec_label][npc_id] = dsl_tbl

                    eprint(f"{spec_label} | {enc_name} | diff {difficulty_id} -> bossNpcId {npc_id} | logs {used_reports}")

    write_lua(args.out, out_data_by_bucket)
    if args.update_main and not args.no_update_main:
        upsert_specs_into_main(os.path.join("common", "LorrgsTimers.lua"), out_data_by_bucket)
    print(f"Wrote {args.out}")


if __name__ == '__main__':
    main()
