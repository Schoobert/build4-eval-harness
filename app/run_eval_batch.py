"""
run_eval_batch.py — Run the evaluation harness against all 15 incidents.

Saves results to data/eval_results_v1.json and prints a summary.
"""

import json
import sys
import time
from pathlib import Path

# Ensure the app/ directory is on the path so eval_harness can be imported
# regardless of the working directory the script is invoked from.
sys.path.insert(0, str(Path(__file__).parent))

from eval_harness import run_evaluation

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

INCIDENTS_FILE = DATA_DIR / "synthetic_incidents.json"
RESULTS_FILE = DATA_DIR / "eval_results_v1.json"

SLEEP_BETWEEN_CALLS = 2  # seconds


def load_incident_ids() -> list[str]:
    with open(INCIDENTS_FILE) as f:
        incidents = json.load(f)
    return [i["incident_id"] for i in incidents]


def print_summary(results: list[dict]) -> None:
    total = len(results)
    overall_passed = sum(1 for r in results if r["overall_pass"])

    # Collect pass counts per criterion across all results
    criterion_ids = ["C1", "C2", "C3", "C4", "C5"]
    criterion_names = {
        "C1": "Key Facts Accurate",
        "C2": "Root Cause Identified",
        "C3": "Remediation Steps Present",
        "C4": "Appropriate Tone",
        "C5": "No Speculation",
    }

    print("\n" + "=" * 50)
    print("EVALUATION SUMMARY")
    print("=" * 50)
    print(f"Total incidents evaluated : {total}")
    print(f"Overall pass (all 5 pass) : {overall_passed} / {total} "
          f"({overall_passed / total * 100:.0f}%)")
    print()
    print("Pass rate per criterion:")
    for cid in criterion_ids:
        passed = sum(
            1 for r in results
            if r["scores"].get(cid, {}).get("result") == "pass"
        )
        print(f"  {cid} {criterion_names[cid]:<28} {passed:>2} / {total} "
              f"({passed / total * 100:.0f}%)")
    print("=" * 50)


def main() -> None:
    incident_ids = load_incident_ids()
    results = []

    for incident_id in incident_ids:
        print(f"Evaluating {incident_id}...", end=" ", flush=True)
        try:
            result = run_evaluation(incident_id)
            results.append(result)
            status = "PASS" if result["overall_pass"] else "FAIL"
            print(f"done ({status})")
        except Exception as e:
            print(f"ERROR: {e}")

        if incident_id != incident_ids[-1]:
            time.sleep(SLEEP_BETWEEN_CALLS)

    # Save full results
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {RESULTS_FILE.relative_to(PROJECT_ROOT)}")

    print_summary(results)


if __name__ == "__main__":
    main()
