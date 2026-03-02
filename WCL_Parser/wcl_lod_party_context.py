import json
import os
import sys
import urllib.parse
import urllib.request
from bisect import bisect_left

LOD_ID = 85222
REPORTS = [
    ("Fr1v4QhXNtg8HmTP", 1),
    ("xfjB4MnrmwbDpZ9a", 5),
    ("M6BWJvgPYfXjmTwy", 11),
    ("GC1kwVny63th2MBD", 1),
    ("YFJnhaHzR3bPC6gp", 1),
]
WINDOW_MS = 2000
THRESHOLDS = [95, 90, 85, 80, 70]


def get_env(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def get_token():
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": get_env("WCL_CLIENT_ID"),
        "client_secret": get_env("WCL_CLIENT_SECRET"),
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://www.warcraftlogs.com/oauth/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))["access_token"]


def gql(token, query, variables=None):
    payload = {"query": query, "variables": variables or {}}
    req = urllib.request.Request(
        "https://www.warcraftlogs.com/api/v2/client",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "errors" in data:
        raise RuntimeError(str(data["errors"]))
    return data


def get_report_meta(token, code, fight_id):
    q = """
    query($code:String!, $fightIDs:[Int]) {
      reportData {
        report(code:$code) {
          fights(fightIDs:$fightIDs) { id startTime endTime }
          playerDetails(fightIDs:$fightIDs, includeCombatantInfo:true)
        }
      }
    }
    """
    r = gql(token, q, {"code": code, "fightIDs": [fight_id]})
    report = r["data"]["reportData"]["report"]
    return report["fights"][0], report["playerDetails"]["data"]["playerDetails"]


def pick_holy_paladin(details):
    pals = [h for h in details.get("healers", []) if h.get("type") == "Paladin"]
    for p in pals:
        for s in p.get("specs") or []:
            sname = s.get("spec") if isinstance(s, dict) else s
            if str(sname or "").lower() == "holy":
                return p
    return pals[0] if pals else None


def party_ids(details):
    out = []
    for role in ("healers", "dps", "tanks"):
        for p in details.get(role, []):
            pid = p.get("id")
            if pid is not None:
                out.append(int(pid))
    return sorted(set(out))


def fetch_events(token, code, fight_id, dtype, start_time, end_time, source_id=None, filter_expr=None):
    q = """
    query($code:String!, $fightIDs:[Int], $dtype:EventDataType!, $start:Float, $end:Float, $sourceID:Int, $filter:String) {
      reportData {
        report(code:$code) {
          events(dataType:$dtype, fightIDs:$fightIDs, startTime:$start, endTime:$end, sourceID:$sourceID, filterExpression:$filter, useAbilityIDs:true, includeResources:true) {
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
        vars = {
            "code": code,
            "fightIDs": [fight_id],
            "dtype": dtype,
            "start": start,
            "end": end_time,
            "sourceID": source_id,
            "filter": filter_expr,
        }
        ev = gql(token, q, vars)["data"]["reportData"]["report"]["events"]
        out.extend(ev.get("data", []))
        start = ev.get("nextPageTimestamp")
        if not start:
            break
    return out


def hp_pct(ev):
    hp = ev.get("hitPoints")
    mhp = ev.get("maxHitPoints")
    if hp is None or not mhp:
        return None
    return max(0.0, min(100.0, (float(hp) / float(mhp)) * 100.0))


def build_samples(events, valid_party):
    out = {pid: [] for pid in valid_party}
    for e in events:
        tid = e.get("targetID")
        ts = e.get("timestamp")
        if tid not in out or ts is None:
            continue
        p = hp_pct(e)
        if p is None:
            continue
        out[tid].append((int(ts), p))
    for pid in out:
        out[pid].sort(key=lambda x: x[0])
    return out


def nearest(samples, ts):
    if not samples:
        return None
    times = [t for t, _ in samples]
    i = bisect_left(times, ts)
    cand = []
    if i < len(samples):
        cand.append(samples[i])
    if i > 0:
        cand.append(samples[i - 1])
    if not cand:
        return None
    t, p = min(cand, key=lambda x: abs(x[0] - ts))
    if abs(t - ts) > WINDOW_MS:
        return None
    return p


def main():
    token = get_token()

    combined = {thr: [] for thr in THRESHOLDS}
    examples = {"2_below_90": 0, "3_below_95": 0, "casts": 0}

    for code, fight_id in REPORTS:
        fight, details = get_report_meta(token, code, fight_id)
        pal = pick_holy_paladin(details)
        if not pal:
            print(f"[WARN] {code} fight {fight_id}: no Holy Paladin")
            continue

        pal_id = int(pal["id"])
        pals_name = pal.get("name", str(pal_id))
        pids = party_ids(details)

        casts = fetch_events(
            token,
            code,
            fight_id,
            "Casts",
            int(fight["startTime"]),
            int(fight["endTime"]),
            source_id=pal_id,
            filter_expr=f"ability.id={LOD_ID}",
        )

        heal = fetch_events(token, code, fight_id, "Healing", int(fight["startTime"]), int(fight["endTime"]))
        dmg = fetch_events(token, code, fight_id, "DamageTaken", int(fight["startTime"]), int(fight["endTime"]))
        samples = build_samples(heal + dmg, pids)

        by_thr = {thr: [] for thr in THRESHOLDS}
        local_examples = {"2_below_90": 0, "3_below_95": 0, "casts": 0}

        for c in casts:
            ts = c.get("timestamp")
            if ts is None:
                continue
            local_examples["casts"] += 1
            examples["casts"] += 1

            count_below = {thr: 0 for thr in THRESHOLDS}
            for pid in pids:
                hp = nearest(samples.get(pid), int(ts))
                if hp is None:
                    continue
                for thr in THRESHOLDS:
                    if hp < thr:
                        count_below[thr] += 1

            for thr in THRESHOLDS:
                by_thr[thr].append(count_below[thr])
                combined[thr].append(count_below[thr])

            if count_below[90] >= 2:
                local_examples["2_below_90"] += 1
                examples["2_below_90"] += 1
            if count_below[95] >= 3:
                local_examples["3_below_95"] += 1
                examples["3_below_95"] += 1

        print(f"\n=== {code} fight {fight_id} | {pals_name} | LoD casts={local_examples['casts']} ===")
        if local_examples["casts"] == 0:
            print("- No Light of Dawn casts")
            continue
        for thr in THRESHOLDS:
            arr = by_thr[thr]
            avg = sum(arr) / len(arr) if arr else 0
            print(f"- Avg party units below {thr}% at LoD cast: {avg:.2f}")
        print(f"- % casts with >=2 units below 90%: {(local_examples['2_below_90']/local_examples['casts'])*100:.1f}%")
        print(f"- % casts with >=3 units below 95%: {(local_examples['3_below_95']/local_examples['casts'])*100:.1f}%")

    print("\n=== COMBINED LoD context (5 logs) ===")
    if examples["casts"] == 0:
        print("No Light of Dawn casts found")
    else:
        for thr in THRESHOLDS:
            arr = combined[thr]
            avg = sum(arr) / len(arr) if arr else 0
            print(f"- Avg party units below {thr}% at LoD cast: {avg:.2f}")
        print(f"- % casts with >=2 units below 90%: {(examples['2_below_90']/examples['casts'])*100:.1f}%")
        print(f"- % casts with >=3 units below 95%: {(examples['3_below_95']/examples['casts'])*100:.1f}%")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
