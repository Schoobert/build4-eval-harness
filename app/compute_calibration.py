#!/usr/bin/env python3
import json
from datetime import datetime, timezone

HUMAN_LABELS_PATH = "data/human_labels.json"
EVAL_RESULTS_PATH = "data/eval_results_v3.json"
RUBRIC_PATH = "prompts/rubric.json"
OUTPUT_PATH = "data/calibration_results.json"

CRITERIA_ORDER = ["C1", "C2", "C3", "C4", "C5"]


def load_json(path):
    with open(path) as f:
        return json.load(f)


def main():
    human_labels = load_json(HUMAN_LABELS_PATH)
    eval_results = load_json(EVAL_RESULTS_PATH)
    rubric = load_json(RUBRIC_PATH)

    criterion_names = {c["criterion_id"]: c["criterion_name"] for c in rubric["criteria"]}

    judge_by_id = {r["incident_id"]: r["scores"] for r in eval_results}
    human_by_id = {h["incident_id"]: h["scores"] for h in human_labels}

    shared_ids = sorted(set(judge_by_id) & set(human_by_id))
    n_incidents = len(shared_ids)

    # Per-criterion tallies
    per_criterion = {
        cid: {"agree": 0, "human_pass_judge_fail": 0, "human_fail_judge_pass": 0, "total": 0}
        for cid in CRITERIA_ORDER
    }

    incident_rows = []

    for iid in shared_ids:
        h_scores = human_by_id[iid]
        j_scores = judge_by_id[iid]
        row = {"incident_id": iid, "criteria": {}}
        for cid in CRITERIA_ORDER:
            h = h_scores[cid]["result"]
            j = j_scores[cid]["result"]
            agree = h == j
            hp_jf = h == "pass" and j == "fail"
            hf_jp = h == "fail" and j == "pass"
            per_criterion[cid]["agree"] += int(agree)
            per_criterion[cid]["human_pass_judge_fail"] += int(hp_jf)
            per_criterion[cid]["human_fail_judge_pass"] += int(hf_jp)
            per_criterion[cid]["total"] += 1
            row["criteria"][cid] = {
                "human": h,
                "judge": j,
                "agree": agree,
                "human_pass_judge_fail": hp_jf,
                "human_fail_judge_pass": hf_jp,
            }
        incident_rows.append(row)

    total_comparisons = n_incidents * len(CRITERIA_ORDER)
    total_agree = sum(pc["agree"] for pc in per_criterion.values())
    total_hp_jf = sum(pc["human_pass_judge_fail"] for pc in per_criterion.values())
    total_hf_jp = sum(pc["human_fail_judge_pass"] for pc in per_criterion.values())
    overall_agreement_rate = total_agree / total_comparisons if total_comparisons else 0

    per_criterion_summary = {}
    for cid in CRITERIA_ORDER:
        pc = per_criterion[cid]
        per_criterion_summary[cid] = {
            "criterion_name": criterion_names[cid],
            "agreement_rate": pc["agree"] / pc["total"] if pc["total"] else 0,
            "agreements": pc["agree"],
            "human_pass_judge_fail": pc["human_pass_judge_fail"],
            "human_fail_judge_pass": pc["human_fail_judge_pass"],
            "total": pc["total"],
        }

    # Print summary table
    col_w = 30
    print()
    print("=" * 72)
    print("  CALIBRATION RESULTS — Human vs. LLM Judge (v3)")
    print("=" * 72)
    print(f"  Incidents compared:    {n_incidents}")
    print(f"  Total comparisons:     {total_comparisons}")
    print(f"  Overall agreement:     {total_agree}/{total_comparisons} ({overall_agreement_rate*100:.1f}%)")
    print(f"  Judge too strict*:     {total_hp_jf}  (human pass, judge fail)")
    print(f"  Judge too lenient*:    {total_hf_jp}  (human fail, judge pass)")
    print()
    print(f"  {'Criterion':<{col_w}}  {'Agreement':>10}  {'H-pass/J-fail':>14}  {'H-fail/J-pass':>14}")
    print(f"  {'-'*col_w}  {'-'*10}  {'-'*14}  {'-'*14}")
    for cid in CRITERIA_ORDER:
        s = per_criterion_summary[cid]
        name = f"[{cid}] {s['criterion_name']}"
        rate = f"{s['agreements']}/{s['total']} ({s['agreement_rate']*100:.0f}%)"
        hp_jf = str(s["human_pass_judge_fail"])
        hf_jp = str(s["human_fail_judge_pass"])
        print(f"  {name:<{col_w}}  {rate:>10}  {hp_jf:>14}  {hf_jp:>14}")
    print()
    print("  * 'Judge too strict'  = human said pass, judge said fail")
    print("  * 'Judge too lenient' = human said fail, judge said pass")
    print()

    results = {
        "prompt_version": "v3",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "incidents_compared": n_incidents,
        "total_comparisons": total_comparisons,
        "overall_agreement_rate": round(overall_agreement_rate, 4),
        "total_agreements": total_agree,
        "total_human_pass_judge_fail": total_hp_jf,
        "total_human_fail_judge_pass": total_hf_jp,
        "per_criterion": per_criterion_summary,
        "per_incident": incident_rows,
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"  Results saved to {OUTPUT_PATH}")
    print()


if __name__ == "__main__":
    main()
