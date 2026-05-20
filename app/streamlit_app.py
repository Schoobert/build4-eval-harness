"""
streamlit_app.py — AI Eval Harness dashboard for governance committee review.

Run from project root:
    streamlit run app/streamlit_app.py
"""

import json
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Ensure app/ is importable as a module sibling
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

DATA_DIR = PROJECT_ROOT / "data"
CRITERIA_ORDER = ["C1", "C2", "C3", "C4", "C5"]
CRITERIA_NAMES = {
    "C1": "Key Facts Accurate",
    "C2": "Root Cause Identified",
    "C3": "Remediation Steps Present",
    "C4": "Appropriate Tone",
    "C5": "No Speculation",
}
SEVERITY_COLORS = {
    "Critical": "#c0392b",
    "High": "#e67e22",
    "Medium": "#f1c40f",
    "Low": "#27ae60",
}

# ---------------------------------------------------------------------------
# Data loaders (cached)
# ---------------------------------------------------------------------------

@st.cache_data
def load_incidents():
    with open(DATA_DIR / "synthetic_incidents.json") as f:
        return json.load(f)


@st.cache_data
def load_eval_results(version: str):
    path = DATA_DIR / f"eval_results_{version}.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


@st.cache_data
def load_calibration():
    with open(DATA_DIR / "calibration_results.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def pass_badge(result: str) -> str:
    if result == "pass":
        return "🟢 Pass"
    return "🔴 Fail"


def rate_color(rate: float) -> str:
    if rate >= 0.9:
        return "green"
    if rate >= 0.7:
        return "orange"
    return "red"


def colored_rate(rate: float) -> str:
    pct = f"{rate * 100:.0f}%"
    color = rate_color(rate)
    return f":{color}[**{pct}**]"


# ---------------------------------------------------------------------------
# Page 1 — Run Evaluation
# ---------------------------------------------------------------------------

def page_run_evaluation():
    st.header("Run Evaluation")

    st.markdown(
        """
This page runs the full evaluation pipeline — live, using the Claude API.

Here's what happens step by step:

1. **You pick an incident.** An "incident" is one of 15 fictional AI system failures used as test cases — things like a loan model that discriminated against certain applicants, or a medical AI that broke after a software update.

2. **You pick a prompt version.** The AI that writes the summary was given different written instructions in v1, v2, and v3. Each version was an attempt to fix problems found in the previous one. v3 is the best-performing version.

3. **You click the button.** Two things happen automatically:
   - A first Claude API call writes a plain-language summary of the incident, as if for a governance committee.
   - A second Claude API call reads that summary and scores it against a 5-criterion rubric — pass or fail on each one, with a written justification.

This second step is called **LLM-as-judge**: using a language model to evaluate the output of another language model against a defined standard.
        """
    )
    st.divider()

    incidents = load_incidents()
    incident_options = {
        f"{inc['incident_id']} — {inc['incident_title']}": inc["incident_id"]
        for inc in incidents
    }

    # "Try this example" defaults
    DEFAULT_INCIDENT = "INC-001 — Loan Approval Model Disparate Impact on Hispanic Applicants"
    DEFAULT_VERSION = "v3"

    st.info(
        "**Try this example:** INC-001 with prompt v3 — "
        "a Critical severity fairness incident that showcases the full pipeline.",
        icon="💡",
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        selected_label = st.selectbox(
            "Incident",
            options=list(incident_options.keys()),
            index=list(incident_options.keys()).index(DEFAULT_INCIDENT),
        )
    with col2:
        prompt_version = st.selectbox(
            "Prompt version",
            options=["v1", "v2", "v3"],
            index=["v1", "v2", "v3"].index(DEFAULT_VERSION),
        )

    incident_id = incident_options[selected_label]

    if st.button("Generate & Score Summary", type="primary"):
        from eval_harness import run_evaluation

        with st.spinner("Calling Claude to generate summary and score rubric…"):
            result = run_evaluation(incident_id, prompt_version=prompt_version)

        st.session_state["last_result"] = result

    result = st.session_state.get("last_result")
    if result and result["incident_id"] == incident_id:
        _render_result(result)


def _render_result(result: dict):
    overall = result["overall_pass"]
    if overall:
        st.success("### Overall: PASS — all 5 criteria met", icon="✅")
    else:
        st.error("### Overall: FAIL — one or more criteria not met", icon="❌")

    st.subheader("Generated Summary")
    st.markdown(result["generated_summary"])

    st.subheader("Rubric Scores")
    rows = []
    for cid in CRITERIA_ORDER:
        score = result["scores"].get(cid, {})
        rows.append({
            "Criterion": f"{cid} — {CRITERIA_NAMES[cid]}",
            "Result": pass_badge(score.get("result", "")),
            "Justification": score.get("justification", ""),
        })

    # Render as a styled table
    for row in rows:
        with st.container():
            c1, c2, c3 = st.columns([2, 1, 4])
            c1.markdown(f"**{row['Criterion']}**")
            c2.markdown(row["Result"])
            c3.markdown(row["Justification"])
        st.divider()


# ---------------------------------------------------------------------------
# Page 2 — Prompt Version Comparison
# ---------------------------------------------------------------------------

def page_version_comparison():
    st.header("Prompt Version Comparison")

    st.markdown(
        """
This page shows whether the AI summaries were passing or failing — across all 15 test incidents, for each of the 5 rubric criteria — and how that changed as the instructions were rewritten.

Each column (v1, v2, v3) is a different version of the instructions given to the summary-writing AI. The numbers show what percentage of the 15 incidents passed each criterion under that version.

**This table is the core of what evaluation engineering looks like in practice.** It turns a vague question — "is the AI doing a good job?" — into a specific, measurable answer. When something fails, you can see exactly which criterion broke and use that to fix the instructions. When you fix it, the numbers improve. That's the loop this project is designed to show.

The table below tells the full story: v1 had real problems, v2 fixed most of them, and v3 reached 100% across the board.
        """
    )
    st.divider()

    versions = ["v1", "v2", "v3"]
    all_results = {v: load_eval_results(v) for v in versions}

    # Build pass-rate matrix: {cid -> {version -> rate}}
    matrix = {cid: {} for cid in CRITERIA_ORDER}
    overall_rates = {}

    for version, results in all_results.items():
        if not results:
            for cid in CRITERIA_ORDER:
                matrix[cid][version] = None
            overall_rates[version] = None
            continue

        cid_totals = {cid: 0 for cid in CRITERIA_ORDER}
        cid_passes = {cid: 0 for cid in CRITERIA_ORDER}
        overall_passes = 0

        for r in results:
            overall_passes += int(r.get("overall_pass", False))
            for cid in CRITERIA_ORDER:
                score = r.get("scores", {}).get(cid, {})
                cid_totals[cid] += 1
                cid_passes[cid] += int(score.get("result") == "pass")

        n = len(results)
        for cid in CRITERIA_ORDER:
            matrix[cid][version] = cid_passes[cid] / cid_totals[cid] if cid_totals[cid] else None
        overall_rates[version] = overall_passes / n if n else None

    # Render table header
    header_cols = st.columns([3, 1, 1, 1])
    header_cols[0].markdown("**Criterion**")
    for i, v in enumerate(versions):
        header_cols[i + 1].markdown(f"**{v}**")
    st.divider()

    for cid in CRITERIA_ORDER:
        row_cols = st.columns([3, 1, 1, 1])
        row_cols[0].markdown(f"{cid} — {CRITERIA_NAMES[cid]}")
        for i, v in enumerate(versions):
            rate = matrix[cid].get(v)
            if rate is None:
                row_cols[i + 1].markdown("—")
            else:
                row_cols[i + 1].markdown(colored_rate(rate))

    st.divider()
    overall_cols = st.columns([3, 1, 1, 1])
    overall_cols[0].markdown("**Overall (all 5 pass)**")
    for i, v in enumerate(versions):
        rate = overall_rates.get(v)
        if rate is None:
            overall_cols[i + 1].markdown("—")
        else:
            overall_cols[i + 1].markdown(colored_rate(rate))

    st.divider()

    st.subheader("What changed between versions?")
    st.markdown(
        """
**v1 → v2: Eliminating speculation**

The v1 prompt produced summaries that passed on factual accuracy, root cause,
and remediation — but consistently added a "Risk Assessment" section that
speculated about legal exposure, reputational harm, and operational costs not
present in the source incident records. This caused C4 (Appropriate Tone) and
C5 (No Speculation) failures on many incidents.

v2 added an explicit instruction: *do not introduce consequences, risks, or
harms beyond what the incident record states*. This eliminated the speculation
failures and raised pass rates on C4 and C5 sharply.

**v2 → v3: Tone calibration for AI system failures**

A residual v2 failure mode was dramatic framing when describing AI system
malfunctions — language like "alarming," "caused chaos," or "critical failure"
that overstated severity relative to the documented incident rating. v3 added a
tone calibration note reminding the model that High severity incidents, while
serious, do not warrant alarming language, and that the audience (a governance
committee) expects measured, factual prose. This brought the remaining C4 and
C5 failures to zero.
        """
    )


# ---------------------------------------------------------------------------
# Page 3 — Calibration Results
# ---------------------------------------------------------------------------

def page_calibration():
    st.header("Calibration Results")

    st.markdown(
        """
After the AI judge scored all 15 incidents, Derek went through each one manually and scored them using the same rubric — 5 criteria per incident, pass or fail, for a total of 75 individual judgements.

**Calibration** is the process of comparing those human scores to the AI judge scores. It answers a simple but important question: does the AI judge agree with a human who knows what good looks like?

If they agree most of the time, it means the AI judge can be trusted as a reliable stand-in for human review — which is the whole point of using LLM-as-judge evaluation. If they disagree a lot, it's a signal that the rubric is unclear, or that the judge is being too strict or too lenient in ways a human wouldn't be.

The metrics below show the results.
        """
    )
    st.divider()

    cal = load_calibration()

    agree_rate = cal["overall_agreement_rate"]
    total = cal["total_comparisons"]
    agrees = cal["total_agreements"]
    hp_jf = cal["total_human_pass_judge_fail"]
    hf_jp = cal["total_human_fail_judge_pass"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Overall Agreement", f"{agree_rate * 100:.1f}%")
    m2.metric("Comparisons", f"{agrees}/{total}")
    m3.metric("Judge Too Strict", hp_jf, help="Human passed, judge failed")
    m4.metric("Judge Too Lenient", hf_jp, help="Human failed, judge passed")

    st.divider()
    st.subheader("Per-Criterion Agreement")

    header_cols = st.columns([3, 1, 1, 1])
    header_cols[0].markdown("**Criterion**")
    header_cols[1].markdown("**Agreement**")
    header_cols[2].markdown("**H-pass / J-fail**")
    header_cols[3].markdown("**H-fail / J-pass**")
    st.divider()

    for cid in CRITERIA_ORDER:
        c = cal["per_criterion"].get(cid, {})
        rate = c.get("agreement_rate", 0)
        row_cols = st.columns([3, 1, 1, 1])
        row_cols[0].markdown(f"{cid} — {CRITERIA_NAMES[cid]}")
        row_cols[1].markdown(colored_rate(rate))
        row_cols[2].markdown(str(c.get("human_pass_judge_fail", 0)))
        row_cols[3].markdown(str(c.get("human_fail_judge_pass", 0)))

    st.divider()

    st.subheader("What is calibration and why does it matter?")
    st.markdown(
        """
**Calibration** measures how closely an automated evaluator (the LLM judge)
agrees with a human reviewer on the same set of judgements. High agreement
means the judge is a reliable proxy for human opinion; systematic disagreement
points to rubric gaps or judge bias that need to be corrected before results
can be trusted.

For a governance committee, calibration answers the question: *"Can we trust
the scores the AI judge is giving us?"* If the judge is systematically stricter
or more lenient than a human expert would be, the pass rates reported by the
harness will be misleading.

**A note on interpreting these results**

The v3 summaries are high quality — the prompt was refined specifically to
eliminate the failure modes seen in v1 and v2. As a result, both the human
reviewer and the LLM judge agreed that all 75 criterion scores (15 incidents ×
5 criteria) were passing. 100% agreement is a strong signal, but it also means
there were no disagreements to probe. Calibration is most diagnostic when the
judge and human diverge; a future exercise with more varied summary quality, or
a deliberately flawed prompt, would provide a richer test of judge reliability.
The current results establish a useful baseline: when both rater types see
high-quality output, they agree completely.
        """
    )


# ---------------------------------------------------------------------------
# Page 4 — Incident Library
# ---------------------------------------------------------------------------

def page_incident_library():
    st.header("Incident Library")

    st.markdown(
        """
These are the 15 fictional AI incident reports used as test inputs throughout this project. They were written to be realistic — the kind of thing an AI governance team at a large company might actually encounter.

The incidents cover a wide range of AI failure types:

- **Bias and fairness issues** — an AI that treated different groups of people unequally
- **Model drift** — an AI that worked fine at launch but quietly degraded over time as real-world data changed
- **Data pipeline failures** — an AI that broke because the data feeding it changed in an unexpected way
- **Security incidents** — an AI that leaked information it shouldn't have, or was manipulated by bad actors
- **Policy violations** — an AI that behaved outside the boundaries it was supposed to operate within

Browsing these shows the range of situations the evaluation harness was designed to handle. Each incident has a severity rating (Critical, High, Medium, or Low) that reflects how serious the failure was.
        """
    )
    st.divider()

    incidents = load_incidents()
    options = {
        f"{inc['incident_id']} — {inc['incident_title']}": inc
        for inc in incidents
    }

    selected_label = st.selectbox("Select incident", options=list(options.keys()))
    inc = options[selected_label]

    severity = inc.get("severity", "")
    color = SEVERITY_COLORS.get(severity, "#888888")

    st.markdown(
        f"<span style='background:{color};color:white;padding:3px 10px;"
        f"border-radius:4px;font-weight:bold'>{severity}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(f"### {inc['incident_title']}")

    col1, col2 = st.columns(2)
    col1.markdown(f"**Date:** {inc['incident_date']}")
    col2.markdown(f"**System:** {inc['system_name']}")

    st.subheader("Description")
    st.write(inc["incident_description"])

    st.subheader("Root Cause")
    st.write(inc["root_cause"])

    st.subheader("Remediation Steps")
    for i, step in enumerate(inc["remediation_steps"], 1):
        st.markdown(f"{i}. {step}")


# ---------------------------------------------------------------------------
# App shell
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="AI Eval Harness",
        page_icon="🔍",
        layout="wide",
    )

    with st.sidebar:
        st.title("AI Eval Harness")
        st.markdown("**About this project**")
        st.markdown(
            "Derek built this to show what AI evaluation engineering looks like "
            "in practice — specifically for governance and Trust & Safety roles.\n\n"
            "The core idea: a non-technical policy operator can define what "
            "\"good\" looks like for an AI system (a rubric), and then use a "
            "second AI to automatically check whether the first one is meeting "
            "that standard. This tool makes that loop visible and measurable.\n\n"
            "The four pages each show a different part of the build:\n"
            "- **Run Evaluation** — watch the full pipeline run live\n"
            "- **Prompt Comparison** — see how rewriting the instructions improved results\n"
            "- **Calibration** — check whether the AI judge agrees with a human reviewer\n"
            "- **Incident Library** — browse the 15 test cases used throughout"
        )
        st.divider()
        page = st.radio(
            "Navigate",
            options=[
                "Run Evaluation",
                "Prompt Version Comparison",
                "Calibration Results",
                "Incident Library",
            ],
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("Powered by Claude · Anthropic")

    if page == "Run Evaluation":
        page_run_evaluation()
    elif page == "Prompt Version Comparison":
        page_version_comparison()
    elif page == "Calibration Results":
        page_calibration()
    elif page == "Incident Library":
        page_incident_library()


if __name__ == "__main__":
    main()
