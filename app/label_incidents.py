#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone

INCIDENTS_PATH = "data/synthetic_incidents.json"
EVAL_RESULTS_PATH = "data/eval_results_v3.json"
RUBRIC_PATH = "prompts/rubric.json"
OUTPUT_PATH = "data/human_labels.json"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_labels(labels):
    with open(OUTPUT_PATH, "w") as f:
        json.dump(labels, f, indent=2)


def load_existing_labels():
    if os.path.exists(OUTPUT_PATH):
        return load_json(OUTPUT_PATH)
    return []


def labeled_ids(labels):
    return {entry["incident_id"] for entry in labels}


def print_incident(incident):
    print(f"  Title:       {incident['incident_title']}")
    print(f"  ID:          {incident['incident_id']}")
    print(f"  Date:        {incident['incident_date']}")
    print(f"  Severity:    {incident['severity']}")
    print(f"  System:      {incident['system_name']}")
    print()
    print("  Description:")
    for line in incident["incident_description"].split(". "):
        print(f"    {line.strip()}.")
    print()
    print("  Root Cause:")
    print(f"    {incident['root_cause']}")
    print()
    print("  Remediation Steps:")
    for i, step in enumerate(incident["remediation_steps"], 1):
        print(f"    {i}. {step}")


def print_summary(summary_text):
    print("  " + "\n  ".join(summary_text.replace("**", "").splitlines()))


def print_rubric(criteria):
    for c in criteria:
        print(f"  [{c['criterion_id']}] {c['criterion_name']}")
        print(f"      {c['description']}")
        print(f"      PASS: {c['passing_standard']}")
        print(f"      FAIL: {c['failing_standard']}")
        print()


def prompt_criterion(criterion):
    cid = criterion["criterion_id"]
    name = criterion["criterion_name"]
    while True:
        raw = input(f"  [{cid}] {name} — (p)ass / (f)ail / (q)uit: ").strip().lower()
        if raw == "q":
            return None, None
        if raw in ("p", "f"):
            result = "pass" if raw == "p" else "fail"
            note = input(f"       Note (optional, press Enter to skip): ").strip()
            return result, note
        print("       Invalid input. Enter p, f, or q.")


def confirm_scores(criteria, scores):
    print()
    print("  Your scores:")
    for c in criteria:
        cid = c["criterion_id"]
        result = scores[cid]["result"]
        note = scores[cid]["note"]
        note_str = f"  ({note})" if note else ""
        print(f"    [{cid}] {c['criterion_name']}: {result.upper()}{note_str}")
    while True:
        raw = input("\n  Confirm? (y)es / (r)edo / (q)uit: ").strip().lower()
        if raw in ("y", "r", "q"):
            return raw
        print("  Invalid input. Enter y, r, or q.")


def label_incident(incident, summary_text, criteria):
    while True:
        clear_screen()
        total = 15
        print("=" * 70)
        print(f"  INCIDENT {incident['incident_id']}  |  Human Labeling Tool")
        print("=" * 70)
        print()
        print("[ INCIDENT DETAILS ]")
        print()
        print_incident(incident)
        print()
        print("[ GENERATED SUMMARY (v3) ]")
        print()
        print_summary(summary_text)
        print()
        print("[ RUBRIC ]")
        print()
        print_rubric(criteria)
        print("[ SCORE EACH CRITERION ]")
        print()

        scores = {}
        quit_requested = False
        for c in criteria:
            result, note = prompt_criterion(c)
            if result is None:
                quit_requested = True
                break
            scores[c["criterion_id"]] = {"result": result, "note": note}

        if quit_requested:
            return None

        decision = confirm_scores(criteria, scores)
        if decision == "q":
            return None
        if decision == "y":
            return scores
        # decision == "r": loop back and redo


def build_label_entry(incident_id, scores, criteria):
    overall_pass = all(scores[c["criterion_id"]]["result"] == "pass" for c in criteria)
    return {
        "incident_id": incident_id,
        "labeled_by": "human",
        "prompt_version": "v3",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scores": scores,
        "overall_pass": overall_pass,
    }


def print_final_summary(labels):
    total = len(labels)
    passing = sum(1 for e in labels if e["overall_pass"])
    print()
    print("=" * 70)
    print("  LABELING SESSION COMPLETE")
    print("=" * 70)
    print(f"  Incidents labeled:  {total} / 15")
    print(f"  Overall pass rate:  {passing}/{total} ({passing/total*100:.0f}%)" if total else "  No incidents labeled.")
    print(f"  Results saved to:   {OUTPUT_PATH}")
    print()


def main():
    incidents = load_json(INCIDENTS_PATH)
    eval_results = load_json(EVAL_RESULTS_PATH)
    rubric = load_json(RUBRIC_PATH)
    criteria = rubric["criteria"]

    summary_by_id = {r["incident_id"]: r["generated_summary"] for r in eval_results}

    labels = load_existing_labels()
    done = labeled_ids(labels)

    remaining = [inc for inc in incidents if inc["incident_id"] not in done]

    if not remaining:
        print("All 15 incidents have already been labeled.")
        print_final_summary(labels)
        return

    if done:
        print(f"Resuming session — {len(done)} of 15 incidents already labeled.")
        input("Press Enter to continue...")

    for incident in remaining:
        iid = incident["incident_id"]
        summary_text = summary_by_id.get(iid, "(no summary found)")

        scores = label_incident(incident, summary_text, criteria)

        if scores is None:
            print()
            print("  Session paused. Progress saved.")
            break

        entry = build_label_entry(iid, scores, criteria)
        labels.append(entry)
        save_labels(labels)

    all_done = len(labeled_ids(labels)) == 15
    if all_done:
        print_final_summary(labels)
    else:
        remaining_count = 15 - len(labeled_ids(labels))
        print(f"  {remaining_count} incident(s) remaining. Run again to resume.")
        print()


if __name__ == "__main__":
    main()
