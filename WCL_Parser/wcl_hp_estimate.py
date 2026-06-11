import json
import os
import sys
import urllib.parse
import urllib.request
from bisect import bisect_left
from statistics import mean

SPELLS = {
    85673: "Word of Glory",
    85222: "Light of Dawn",
    20473: "Holy Shock",
    19750: "Flash of Light",
}

REPORTS = [
    ("Fr1v4QhXNtg8HmTP", 1),
    ("xfjB4MnrmwbDpZ9a", 5),
    ("M6BWJvgPYfXjmTwy", 11),
    ("GC1kwVny63th2MBD", 1),
    ("YFJnhaHzR3bPC6gp", 1),
]

WINDOW_MS = 2000


def get_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def get_token() -> str:
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": get_env("WCL_CLIENT_ID"),
            "client_secret": get_env("WCL_CLIENT_SECRET"),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://www.warcraftlogs.com/oauth/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))["access_token"]


def gql(token: str, query: str, variables=None):
    payload = {"query": query, "variables": variables or {}}
    req = urllib.request.Request(
        "https://www.warcraftlogs.com/api/v2/client",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    return data


def get_report_meta(token: str, code: str, fight_id: int):
    query = """
    query($code:String!, $fightIDs:[Int]) {
      reportData {
        report(code:$code) {
          fights(fightIDs:$fightIDs) { id startTime endTime name }
          playerDetails(fightIDs:$fightIDs, includeCombatantInfo:true)
        }
      }
    }
    """
    res = gql(token, query, {"code": code, "fightIDs": [fight_id]})
    report = res["data"]["reportData"]["report"]
    fight = report["fights"][0]
    details = report["playerDetails"]["data"]["playerDetails"]
    return fight, details


def pick_holy_paladin(details):
    healers = details.get("healers", [])
    pals = [h for h in healers if h.get("type") == "Paladin"]
    if not pals:
        return None

    # Prefer explicit Holy in specs if present
    for p in pals:
        specs = p.get("specs") or []
        for s in specs:
            if isinstance(s, dict):
                sname = (s.get("spec") or s.get("name") or "")
            else:
                sname = s or ""
            if str(sname).lower() == "holy":
                return p

    # Fallback first paladin healer
    return pals[0]


def fetch_cast_events(token: str, code: str, fight_id: int, source_id: int):
    filter_expr = " or ".join([f"ability.id={sid}" for sid in SPELLS.keys()])
    query = """
    query($code:String!, $fightIDs:[Int], $sourceID:Int, $start:Float, $filter:String) {
      reportData {
        report(code:$code) {
          events(dataType:Casts, fightIDs:$fightIDs, sourceID:$sourceID, startTime:$start, filterExpression:$filter, useAbilityIDs:true) {
            data
            nextPageTimestamp
          }
        }
      }
    }
    """
    out = []
    start = None
    while True:
        res = gql(
            token,
            query,
            {
                "code": code,
                "fightIDs": [fight_id],
                "sourceID": source_id,
                "start": start,
                "filter": filter_expr,
            },
        )
        ev = res["data"]["reportData"]["report"]["events"]
        out.extend(ev.get("data", []))
        start = ev.get("nextPageTimestamp")
        if not start:
            break
    return out


def fetch_events(token: str, code: str, fight_id: int, data_type: str, start_time: int, end_time: int):
    query = """
    query($code:String!, $fightIDs:[Int], $start:Float, $end:Float, $dtype:EventDataType!) {
      reportData {
        report(code:$code) {
          events(dataType:$dtype, fightIDs:$fightIDs, startTime:$start, endTime:$end, useAbilityIDs:true, includeResources:true) {
            data
            nextPageTimestamp
          }
        }
      }
    }
    """
    out = []
    start = start_time
    while True:
        res = gql(
            token,
            query,
            {
                "code": code,
                "fightIDs": [fight_id],
                "start": start,
                "end": end_time,
                "dtype": data_type,
            },
        )
        ev = res["data"]["reportData"]["report"]["events"]
        out.extend(ev.get("data", []))
        start = ev.get("nextPageTimestamp")
        if not start:
            break
    return out


def hp_percent_from_event(ev):
    # Common direct shapes
    hp = ev.get("hitPoints") or ev.get("targetHitPoints")
    mhp = ev.get("maxHitPoints") or ev.get("targetMaxHitPoints")
    if hp is not None and mhp:
        return max(0.0, min(100.0, (float(hp) / float(mhp)) * 100.0))

    # resource arrays (shape varies)
    for key in ("targetResources", "resources"):
        arr = ev.get(key)
        if not isinstance(arr, list):
            continue
        for r in arr:
            if not isinstance(r, dict):
                continue
            # Health is usually type 0 on WCL resources
            rtype = r.get("type")
            amount = r.get("amount")
            maximum = r.get("max") or r.get("maximum")
            if rtype == 0 and amount is not None and maximum:
                return max(0.0, min(100.0, (float(amount) / float(maximum)) * 100.0))

    return None


def build_hp_samples(events):
    # targetID -> list[(timestamp, hpPercent)] sorted
    out = {}
    for ev in events:
        tid = ev.get("targetID")
        ts = ev.get("timestamp")
        if tid is None or ts is None:
            continue
        hp_pct = hp_percent_from_event(ev)
        if hp_pct is None:
            continue
        out.setdefault(tid, []).append((int(ts), hp_pct))

    for tid in out:
        out[tid].sort(key=lambda x: x[0])
    return out


def nearest_hp(hp_samples, target_id, cast_ts):
    arr = hp_samples.get(target_id)
    if not arr:
        return None, "low"

    times = [t for t, _ in arr]
    i = bisect_left(times, cast_ts)

    candidates = []
    if i < len(arr):
        candidates.append(arr[i])
    if i > 0:
        candidates.append(arr[i - 1])

    if not candidates:
        return None, "low"

    best_t, best_hp = min(candidates, key=lambda x: abs(x[0] - cast_ts))
    dt = abs(best_t - cast_ts)

    if dt <= 300:
        conf = "high"
    elif dt <= 1000:
        conf = "medium"
    elif dt <= WINDOW_MS:
        conf = "low"
    else:
        return None, "low"

    return best_hp, conf


def percentile(sorted_vals, p):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = (len(sorted_vals) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def summarize(vals):
    if not vals:
        return None
    s = sorted(vals)
    return {
        "count": len(vals),
        "mean": round(mean(vals), 2),
        "p25": round(percentile(s, 0.25), 2),
        "p50": round(percentile(s, 0.50), 2),
        "p75": round(percentile(s, 0.75), 2),
        "min": round(s[0], 2),
        "max": round(s[-1], 2),
    }


def main():
    token = get_token()

    by_spell_all = {name: [] for name in SPELLS.values()}
    conf_counts_all = {name: {"high": 0, "medium": 0, "low": 0} for name in SPELLS.values()}
    per_report = []

    for code, fight_id in REPORTS:
        fight, details = get_report_meta(token, code, fight_id)
        pal = pick_holy_paladin(details)
        if not pal:
            print(f"[WARN] {code} fight {fight_id}: No Holy Paladin healer found, skipping")
            continue

        source_id = pal["id"]
        source_name = pal.get("name", str(source_id))

        casts = fetch_cast_events(token, code, fight_id, source_id)
        healing_events = fetch_events(token, code, fight_id, "Healing", int(fight["startTime"]), int(fight["endTime"]))
        damage_events = fetch_events(token, code, fight_id, "DamageTaken", int(fight["startTime"]), int(fight["endTime"]))
        hp_samples = build_hp_samples(healing_events + damage_events)

        by_spell = {name: [] for name in SPELLS.values()}
        conf_counts = {name: {"high": 0, "medium": 0, "low": 0} for name in SPELLS.values()}

        for c in casts:
            sid = c.get("abilityGameID")
            if sid not in SPELLS:
                continue
            spell_name = SPELLS[sid]
            target_id = c.get("targetID")
            ts = c.get("timestamp")
            if target_id is None or ts is None:
                conf_counts[spell_name]["low"] += 1
                continue

            hp, conf = nearest_hp(hp_samples, target_id, int(ts))
            conf_counts[spell_name][conf] += 1
            if hp is not None:
                by_spell[spell_name].append(hp)
                by_spell_all[spell_name].append(hp)
            conf_counts_all[spell_name][conf] += 1

        per_report.append(
            {
                "report": code,
                "fight": fight_id,
                "paladin": source_name,
                "summary": {k: summarize(v) for k, v in by_spell.items()},
                "confidence": conf_counts,
            }
        )

        print(f"\n=== {code} fight {fight_id} | {source_name} ===")
        for spell in SPELLS.values():
            s = summarize(by_spell[spell])
            c = conf_counts[spell]
            if not s:
                print(f"- {spell}: no estimateable casts | conf h/m/l = {c['high']}/{c['medium']}/{c['low']}")
            else:
                print(
                    f"- {spell}: n={s['count']} mean={s['mean']} p25={s['p25']} p50={s['p50']} p75={s['p75']} "
                    f"min={s['min']} max={s['max']} | conf h/m/l={c['high']}/{c['medium']}/{c['low']}"
                )

    combined = {k: summarize(v) for k, v in by_spell_all.items()}

    print("\n=== COMBINED (Top 5 logs provided) ===")
    for spell in SPELLS.values():
        s = combined[spell]
        c = conf_counts_all[spell]
        if not s:
            print(f"- {spell}: no estimateable casts | conf h/m/l = {c['high']}/{c['medium']}/{c['low']}")
        else:
            print(
                f"- {spell}: n={s['count']} mean={s['mean']} p25={s['p25']} p50={s['p50']} p75={s['p75']} "
                f"min={s['min']} max={s['max']} | conf h/m/l={c['high']}/{c['medium']}/{c['low']}"
            )

    out = {
        "reports": per_report,
        "combined": combined,
        "combinedConfidence": conf_counts_all,
        "notes": {
            "method": "Nearest target HP sample around cast timestamp from report events",
            "windowMs": WINDOW_MS,
            "confidence": {
                "high": "<=300ms from cast",
                "medium": "<=1000ms from cast",
                "low": "<=2000ms from cast",
            },
        },
    }

    out_path = os.path.join("WCL_Parser", "wcl_hp_estimate_output.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
