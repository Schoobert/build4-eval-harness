"""
eval_harness.py — Core evaluation engine for AI incident response summaries.

Pipeline:
  1. Load incident by ID from synthetic_incidents.json
  2. Load subject prompt v1 (system prompt for the summary writer)
  3. Call Claude to generate a governance committee summary
  4. Load the evaluation rubric
  5. Call Claude as an LLM judge to score the summary against the rubric
  6. Return a structured result dict
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

# Project layout: this file lives at app/eval_harness.py
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_incident(incident_id: str) -> dict:
    """Return the incident record matching incident_id, or raise ValueError."""
    with open(DATA_DIR / "synthetic_incidents.json") as f:
        incidents = json.load(f)

    for incident in incidents:
        if incident["incident_id"] == incident_id:
            return incident

    raise ValueError(
        f"Incident '{incident_id}' not found. "
        f"Available IDs: {[i['incident_id'] for i in incidents]}"
    )


def load_subject_prompt(version: str = "v1") -> str:
    """Return the system prompt for the given version (e.g. 'v1', 'v2')."""
    path = PROMPTS_DIR / f"subject_prompt_{version}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text()


def load_rubric() -> dict:
    """Return the parsed evaluation rubric."""
    with open(PROMPTS_DIR / "rubric.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Step 3 — Generate summary
# ---------------------------------------------------------------------------

def generate_summary(
    client: anthropic.Anthropic,
    incident: dict,
    system_prompt: str,
) -> str:
    """
    Call Claude with the subject system prompt and the incident JSON.
    Returns the plain-text governance committee summary.
    """
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": (
                    "Please write a governance committee summary for the "
                    "following AI incident report:\n\n"
                    + json.dumps(incident, indent=2)
                ),
            }
        ],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Step 5 — Judge summary against rubric
# ---------------------------------------------------------------------------

def judge_summary(
    client: anthropic.Anthropic,
    incident: dict,
    summary: str,
    rubric: dict,
) -> dict:
    """
    Call Claude as an LLM judge.

    The judge receives the original incident, the generated summary, and
    the full rubric. It returns a JSON object mapping each criterion_id to
    {"result": "pass" | "fail", "justification": "<one sentence>"}.
    """
    # Build a readable rubric block for the judge prompt
    criteria_block = "\n\n".join(
        f"**{c['criterion_id']}: {c['criterion_name']}**\n"
        f"Description: {c['description']}\n"
        f"Passing standard: {c['passing_standard']}\n"
        f"Failing standard: {c['failing_standard']}"
        for c in rubric["criteria"]
    )

    judge_system = (
        "You are an expert evaluator of AI governance communications. "
        "You will receive an original AI incident report, a summary written "
        "for a governance committee, and a rubric with 5 pass/fail criteria.\n\n"
        "Score the summary on each criterion and provide a one-sentence "
        "justification. Respond with a JSON object in exactly this format — "
        "no preamble, no markdown fences, no extra keys:\n"
        "{\n"
        '  "C1": {"result": "pass", "justification": "..."},\n'
        '  "C2": {"result": "fail", "justification": "..."},\n'
        '  "C3": {"result": "pass", "justification": "..."},\n'
        '  "C4": {"result": "pass", "justification": "..."},\n'
        '  "C5": {"result": "pass", "justification": "..."}\n'
        "}"
    )

    judge_user = (
        "## Original Incident Report\n\n"
        + json.dumps(incident, indent=2)
        + "\n\n## Generated Summary\n\n"
        + summary
        + "\n\n## Evaluation Rubric\n\n"
        + criteria_block
        + "\n\nScore the summary on all 5 criteria."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=judge_system,
        messages=[{"role": "user", "content": judge_user}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if the model wrapped the JSON
    if raw.startswith("```"):
        lines = raw.splitlines()
        # Drop the opening fence line (```json or ```) and the closing ``` line
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    return json.loads(raw)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_evaluation(incident_id: str, prompt_version: str = "v1") -> dict:
    """
    Run the full evaluation pipeline for a single incident.

    Args:
        incident_id:    e.g. "INC-001"
        prompt_version: e.g. "v1" or "v2" — determines which subject prompt is used

    Returns:
        {
            "incident_id":       str,
            "prompt_version":    str,
            "generated_summary": str,
            "scores":            {criterion_id: {"result": str, "justification": str}},
            "overall_pass":      bool,   # True only if all 5 criteria pass
            "timestamp":         str,    # ISO 8601 UTC
        }
    """
    # Reads ANTHROPIC_API_KEY from the environment automatically
    client = anthropic.Anthropic()

    # Steps 1–2: load inputs
    incident = load_incident(incident_id)
    system_prompt = load_subject_prompt(prompt_version)

    # Step 3: generate governance committee summary
    generated_summary = generate_summary(client, incident, system_prompt)

    # Step 4: load rubric
    rubric = load_rubric()

    # Step 5: judge the summary
    scores = judge_summary(client, incident, generated_summary, rubric)

    # Step 6: roll up to overall pass/fail
    overall_pass = all(v["result"] == "pass" for v in scores.values())

    return {
        "incident_id": incident_id,
        "prompt_version": prompt_version,
        "generated_summary": generated_summary,
        "scores": scores,
        "overall_pass": overall_pass,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    target_id = sys.argv[1] if len(sys.argv) > 1 else "INC-001"
    version = sys.argv[2] if len(sys.argv) > 2 else "v1"
    result = run_evaluation(target_id, prompt_version=version)
    print(json.dumps(result, indent=2))
