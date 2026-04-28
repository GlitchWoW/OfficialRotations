import argparse
import json
import os
from collections import Counter
from typing import Any, Dict, List, Optional

from wcl_timers import fetch_casts, find_player_id, get_fight_info, get_token, gql, resolve_encounter


def fetch_zone(token: str, zone_id: int) -> Dict[str, Any]:
    query = f'query {{ worldData {{ zone(id: {zone_id}) {{ id name encounters {{ id name }} }} }} }}'
    data = gql(token, query)
    zone = data.get("data", {}).get("worldData", {}).get("zone")
    if not zone:
        raise RuntimeError(f"Zone {zone_id} not found in worldData")
    return zone


def choose_rankings(
    token: str,
    encounter_id: int,
    class_name: str,
    spec_name: str,
    difficulty_id: int,
    metric: str,
    top_n: int,
) -> List[Dict[str, Any]]:
    query = (
        'query { worldData { encounter(id: %d) { '
        'characterRankings(difficulty:%d, className:"%s", specName:"%s", metric:%s, page:1) '
        '} } }'
    ) % (encounter_id, difficulty_id, class_name, spec_name, metric)
    res = gql(token, query)
    rankings_data = res.get("data", {}).get("worldData", {}).get("encounter", {}).get("characterRankings", {})
    rankings = rankings_data.get("rankings", [])
    public = []
    for ranking in rankings:
        if not ranking.get("hidden") and not str(ranking.get("report", {}).get("code", "")).startswith("a:"):
            public.append(ranking)
        if len(public) >= top_n:
            break
    return public


def parse_spell_csv(value: str) -> List[int]:
    items = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        items.append(int(part))
    if not items:
        raise RuntimeError("Expected at least one spell id")
    return items


def parse_name_map(value: Optional[str]) -> Dict[int, str]:
    if not value:
        return {}
    out: Dict[int, str] = {}
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        spell_id_str, label = part.split(":", 1)
        out[int(spell_id_str.strip())] = label.strip()
    return out


def normalize_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(events, key=lambda event: event.get("timestamp", 0))


def first_followup_after_trigger(
    events: List[Dict[str, Any]],
    trigger_spell_id: int,
    followup_spell_ids: List[int],
    max_gap_ms: Optional[int] = None,
) -> Dict[str, Any]:
    followup_set = set(followup_spell_ids)
    counts: Counter[str] = Counter()
    trigger_count = 0
    matched_count = 0
    unmatched_count = 0

    for index, event in enumerate(events):
        spell_id = event.get("abilityGameID")
        if spell_id != trigger_spell_id:
            continue

        trigger_count += 1
        trigger_ts = event.get("timestamp", 0)
        found = False

        for next_event in events[index + 1:]:
            next_spell_id = next_event.get("abilityGameID")
            next_ts = next_event.get("timestamp", 0)

            if max_gap_ms is not None and (next_ts - trigger_ts) > max_gap_ms:
                break

            if next_spell_id in followup_set:
                counts[str(next_spell_id)] += 1
                matched_count += 1
                found = True
                break

        if not found:
            unmatched_count += 1

    return {
        "counts": counts,
        "trigger_count": trigger_count,
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
    }


def to_named_counts(counter: Counter[str], spell_names: Dict[int, str]) -> Dict[str, int]:
    named: Dict[str, int] = {}
    for spell_id_str, count in counter.items():
        spell_id = int(spell_id_str)
        label = spell_names.get(spell_id, spell_id_str)
        named[label] = count
    return named


def build_percentages(counter: Counter[str], total: int, spell_names: Dict[int, str]) -> Dict[str, float]:
    if total <= 0:
        return {}
    out: Dict[str, float] = {}
    for spell_id_str, count in counter.items():
        spell_id = int(spell_id_str)
        label = spell_names.get(spell_id, spell_id_str)
        out[label] = round((count / total) * 100.0, 2)
    return out


def choose_encounters(token: str, zone_id: int, encounter_filters: Optional[List[str]]) -> List[Dict[str, Any]]:
    zone = fetch_zone(token, zone_id)
    if not encounter_filters:
        return zone.get("encounters", [])
    return [resolve_encounter(token, zone_id, entry) for entry in encounter_filters]


def main():
    parser = argparse.ArgumentParser(description="Analyze first cast followups from top Warcraft Logs dungeon runs")
    parser.add_argument("--zone", type=int, required=True, help="WCL zone id, for example 45 for Mythic+ Season 3")
    parser.add_argument("--difficulty", type=int, required=True, help="WCL difficulty id, for example 10 for Mythic+")
    parser.add_argument("--class-name", required=True, help="WCL class name, for example Shaman")
    parser.add_argument("--spec-name", required=True, help="WCL spec name, for example Restoration")
    parser.add_argument("--metric", default="hps", help="WCL rankings metric, for example hps or dps")
    parser.add_argument("--top", type=int, default=10, help="Top public logs per encounter to inspect")
    parser.add_argument("--trigger", type=int, required=True, help="Trigger spell id")
    parser.add_argument("--followups", required=True, help="Comma-separated followup spell ids")
    parser.add_argument("--spell-names", default="", help="Optional CSV of spellId:Label entries")
    parser.add_argument("--encounters", default="", help="Optional comma-separated encounter names or ids")
    parser.add_argument("--max-gap-ms", type=int, default=None, help="Optional maximum time between trigger and followup")
    parser.add_argument("--report-out", default="", help="Optional path to write JSON output")
    args = parser.parse_args()

    token = get_token()
    followup_spell_ids = parse_spell_csv(args.followups)
    encounter_filters = [item.strip() for item in args.encounters.split(",") if item.strip()]
    spell_names = parse_name_map(args.spell_names)
    spell_names.setdefault(args.trigger, str(args.trigger))
    for spell_id in followup_spell_ids:
        spell_names.setdefault(spell_id, str(spell_id))

    encounters = choose_encounters(token, args.zone, encounter_filters)

    overall_counter: Counter[str] = Counter()
    overall_trigger_count = 0
    overall_matched_count = 0
    overall_unmatched_count = 0
    logs_processed = 0
    per_encounter: Dict[str, Any] = {}
    failures: List[Dict[str, Any]] = []

    for encounter in encounters:
        encounter_counter: Counter[str] = Counter()
        encounter_trigger_count = 0
        encounter_matched_count = 0
        encounter_unmatched_count = 0

        rankings = choose_rankings(
            token=token,
            encounter_id=int(encounter["id"]),
            class_name=args.class_name,
            spec_name=args.spec_name,
            difficulty_id=args.difficulty,
            metric=args.metric,
            top_n=args.top,
        )

        for ranking in rankings:
            report_code = ranking["report"]["code"]
            fight_id = int(ranking["report"]["fightID"])
            player_name = ranking["name"]
            try:
                report = get_fight_info(token, report_code, fight_id)
                player_id = find_player_id(report, player_name, args.class_name)
                events = normalize_events(fetch_casts(token, report_code, fight_id, player_id, [args.trigger] + followup_spell_ids))
                analysis = first_followup_after_trigger(
                    events=events,
                    trigger_spell_id=args.trigger,
                    followup_spell_ids=followup_spell_ids,
                    max_gap_ms=args.max_gap_ms,
                )
                encounter_counter.update(analysis["counts"])
                encounter_trigger_count += analysis["trigger_count"]
                encounter_matched_count += analysis["matched_count"]
                encounter_unmatched_count += analysis["unmatched_count"]
                overall_counter.update(analysis["counts"])
                overall_trigger_count += analysis["trigger_count"]
                overall_matched_count += analysis["matched_count"]
                overall_unmatched_count += analysis["unmatched_count"]
                logs_processed += 1
            except Exception as exc:
                failures.append(
                    {
                        "encounter": encounter["name"],
                        "report": report_code,
                        "fight_id": fight_id,
                        "player": player_name,
                        "error": str(exc),
                    }
                )

        per_encounter[encounter["name"]] = {
            "encounter_id": int(encounter["id"]),
            "logs_requested": len(rankings),
            "counts": to_named_counts(encounter_counter, spell_names),
            "percentages": build_percentages(encounter_counter, encounter_matched_count, spell_names),
            "trigger_count": encounter_trigger_count,
            "matched_count": encounter_matched_count,
            "unmatched_count": encounter_unmatched_count,
        }

    result = {
        "zone_id": args.zone,
        "difficulty_id": args.difficulty,
        "class_name": args.class_name,
        "spec_name": args.spec_name,
        "metric": args.metric,
        "top_n_per_encounter": args.top,
        "trigger_spell_id": args.trigger,
        "trigger_spell_name": spell_names.get(args.trigger, str(args.trigger)),
        "followup_spell_ids": followup_spell_ids,
        "followup_spell_names": {str(spell_id): spell_names.get(spell_id, str(spell_id)) for spell_id in followup_spell_ids},
        "max_gap_ms": args.max_gap_ms,
        "logs_processed": logs_processed,
        "overall_counts": to_named_counts(overall_counter, spell_names),
        "overall_percentages": build_percentages(overall_counter, overall_matched_count, spell_names),
        "overall_trigger_count": overall_trigger_count,
        "overall_matched_count": overall_matched_count,
        "overall_unmatched_count": overall_unmatched_count,
        "per_encounter": per_encounter,
        "failures": failures,
    }

    if args.report_out:
        with open(args.report_out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
