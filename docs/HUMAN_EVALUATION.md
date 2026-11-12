# Human Evaluation Protocol

Run `python -m evals.runners.prepare_human_studies` to regenerate two preregistered studies from the
fixed synthetic benchmark. The script produces 30 anonymised V0-versus-V2 proposal pairs, a separate
blinding key, and 30 V2 proposals for judge calibration under `evals/human_studies/`.

For the blind panel, give classmates only `proposal_pairwise_panel.json`. Each rater records A, B or tie
for overall preference, grounding and personalisation, plus a short reason. Do not open or distribute the
key until ratings are frozen. Record rater identifiers as pseudonyms and report the number of raters and
votes; do not invent missing votes.

For calibration, the assignment author must inspect the job, proposal and cited evidence and set every
`human_label` to `pass` or `fail`. Then run `python -m evals.runners.judge_calibration`. It computes exact
agreement and Cohen's kappa. Until all 30 labels exist, the result intentionally reports
`awaiting_author_labels` and no kappa. AI-generated labels are not substitutes for the required human
labels.
