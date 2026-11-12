# Signature Extension: X3 Portfolio Builder

The extension imports GitHub repositories through the allowlisted read-only tools of GitHub's official
MCP server, constructs case-study candidates, checks technology and outcome claims against code, and
requires human approval before an item enters the portfolio index. It never treats a README outcome
claim as proof by itself. `approve_case_study_candidate` converts only the code-verifiable summary and
technologies into a private evidence item; quarantined README claims never enter proposal grounding.

`python -m evals.runners.portfolio_builder_eval` regenerates the committed synthetic snapshot study in
`evals/results/portfolio_builder.json`. Across 12 authored repository snapshots it measured 1.00
technology precision, 1.00 technology recall, 1.00 recall for planted unsupported outcome claims, zero
false positives and a 100% human-approval requirement. These fixtures deliberately exercise the parser
and safety boundary; they are not a claim about live GitHub accuracy. Live validation remains pending
until a user supplies `GITHUB_TOKEN`, and the token is never committed.

