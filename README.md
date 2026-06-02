# AI Incident Report Checker

**[Live App](https://build4-eval-harness.streamlit.app/)** · **[Loom Walkthrough](https://www.loom.com/share/08799b841b224fd8a30ecf0a76faca7d)**

![Landing page - Sample incident or custom incident can be submitted for evaluation](https://raw.githubusercontent.com/Schoobert/build4-eval-harness/main/images/screenshot1.png)

---

## What this is and what problem it solves

AI teams ship systems that make consequential decisions — loan approvals, content removals, medical recommendations. When something goes wrong, someone has to investigate what happened, write it up, and present it to leadership. While AI can help compile this information, it is essential that these summaries are accurate, grounded, and free of speculation.

This tool evaluates whether AI-generated incident summaries meet that standard automatically, using a defined rubric, in seconds. It is designed for Trust & Safety leads, AI governance teams, and compliance operators who need to know if their AI's outputs can be trusted before they reach a decision-maker.

---

## How to try it

1. Go to [build4-eval-harness.streamlit.app](https://build4-eval-harness.streamlit.app/)
2. Select a sample incident from the dropdown — or toggle to **"Evaluate my own incident"** and fill in the fields with a real incident from your team
3. Click **Generate & Score Summary**
4. The tool generates a plain-language governance summary of the incident, then scores it against a 5-criterion rubric using a second Claude API call (LLM-as-judge)
5. Results show pass/fail on each criterion with a written justification

---

## How it works

The tool uses a two-call Claude API architecture:

**Call 1 — Summary generation:** The incident details are passed to Claude with a structured system prompt (v3, the best-performing version after three iterations) that instructs it to write a plain-language governance committee summary in three sections: Incident Overview, Root Cause, and Remediation Steps.

**Call 2 — LLM-as-judge scoring:** The generated summary, the original incident, and a 5-criterion rubric are passed to a second Claude call. The judge scores each criterion pass or fail with a written justification. The five criteria are:
- **C1 — Key Facts Accurate:** Does the summary correctly reflect the incident without distortion?
- **C2 — Root Cause Identified:** Does the summary trace the failure to its origin, not just its symptoms?
- **C3 — Remediation Steps Present:** Are concrete, specific next steps included?
- **C4 — Appropriate Tone:** Is the language professional and calibrated for a governance audience?
- **C5 — No Speculation:** Does every claim trace back to the source incident data?

**Prompt iteration:** The summary prompt went through three versions. v1 had a 13% overall pass rate — a "Risk Assessment" section systematically invited speculation. Removing it in v2 raised the pass rate to 93%. A residual tone failure in v2 (casual vocabulary when describing AI hallucination) was fixed in v3 with an explicit technical language rule, reaching 100%.

**Calibration:** After running the LLM judge against all 15 test incidents, I manually scored each one using the same rubric — 75 individual judgements. The judge agreed with my scores 100% of the time, establishing it as a reliable proxy for human review on this task.

---

## What I learned

Working on this build forced me to think about AI quality in a way that most AI tooling discussions skip entirely. A few things that stuck:

**Evals are a feedback loop, not a one-time score.** The most useful thing this build taught me is that running an eval once tells you almost nothing. It is the iteration — v1 to v2 to v3, with a specific failure identified and fixed each time — that creates signal. A 13% pass rate is not a failure; it is a diagnosis.

**Rubric design is harder than it looks.** Writing pass/fail criteria that are specific enough for an LLM judge to apply consistently, while remaining legible to a non-technical human reviewer, required more iteration than I expected. The criteria that sound obvious ("key facts accurate") are the ones that need the most precise failure standards to be useful in practice.

**LLM-as-judge is powerful but requires calibration.** Using a model to evaluate another model's output solves the scale problem, but it introduces its own reliability question. The calibration step — comparing judge scores to human scores — is what makes the results credible rather than circular. Without it, you are measuring consistency, not correctness.

**The non-technical user is the hardest design problem.** The original tool only evaluated synthetic demo data. It looked complete from a technical standpoint but failed the most basic product test: a real user could not bring their own problem to it. Adding the custom incident form was a small code change but a significant shift in what the tool actually is.

---

## Production considerations

This is a demo-grade implementation. For production use, the following would be added:

- **Authentication:** User sessions, role-based access, audit logging of who evaluated what
- **Multi-tenancy:** Per-team rubric configuration and result history
- **Custom rubrics:** Allow teams to define their own criteria rather than using the built-in five
- **Persistence:** Store evaluation results in a database for trend analysis and reporting
- **Rate limiting:** Per-user API call limits to prevent abuse
- **Scrubbing:** PII detection on custom incident inputs before they are sent to the API
- **Calibration tooling:** A built-in interface for teams to run periodic human-vs-judge calibration on their own eval sets

---

## Technical details

- **Language:** Python 3.14
- **Framework:** Streamlit
- **Model:** claude-sonnet-4-6 (Anthropic)
- **Eval architecture:** Two-call LLM-as-judge pipeline
- **Test data:** 15 synthetic AI incident reports across 5 failure categories
- **Rubric:** 5-criterion pass/fail binary scoring
- **Calibration:** 100% human/judge agreement across 75 comparisons (15 incidents × 5 criteria)
- **Prompt versions:** v1 (13% pass), v2 (93% pass), v3 (100% pass)
- **Deployment:** Streamlit Community Cloud
- **Repository:** [github.com/Schoobert/build4-eval-harness](https://github.com/Schoobert/build4-eval-harness)

---
