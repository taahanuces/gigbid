# Data Card

## Classification

GigBid keeps source type explicit on every normalized record:

| Classification | Meaning | May support reported experiments? |
| --- | --- | --- |
| `real_public_dataset` | Third-party public records with documented license and provenance | Yes, within the limitations below |
| `synthetic` | Locally authored smoke jobs, portfolios, messages or client histories | Plumbing and attack tests only |
| `private_user_data_not_committed` | A user's connected portfolio or OAuth-protected marketplace data | Only with consent; never committed |
| `instructor_hidden` | GigSim, personas or labels supplied for grading | Evaluation only; never used for training |

No Kaggle record is described as instructor data, live marketplace data or ground truth merely because
it came from a real posting.

## Selection and attribution

The immutable registry is [`data/sources.yaml`](../data/sources.yaml). It pins version numbers,
archive checksums, webpage attribution, license URLs and known limitations.

| Dataset | Use in GigBid | Version and inspected rows | License |
| --- | --- | --- | --- |
| [Upwork freelance jobs (+60k)](https://www.kaggle.com/datasets/ahmedmyalo/upwork-freelance-jobs-60k) | Primary 2023 job, client-risk and Connects corpus | v5; 63,950 read, 63,948 retained | [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| [Upwork Job Postings Dataset 2024 (50K Records)](https://www.kaggle.com/datasets/asaniczka/upwork-job-postings-dataset-2024-50k-records) | Out-of-period job/pricing holdout | v1; 53,058 read and retained | [ODC-By 1.0](https://opendatacommons.org/licenses/by/1-0/) |
| [Freelance Contracts Dataset (1.3 Million Entries)](https://www.kaggle.com/datasets/asaniczka/freelance-contracts-dataset-1-3-million-entries) | Historical price, duration and payment priors | v1; 1,292,791 read and retained | [ODC-By 1.0](https://opendatacommons.org/licenses/by/1-0/) |
| [All Upwork Job Postings - Monthly Tracker](https://www.kaggle.com/datasets/asaniczka/all-jobs-on-upwork-200k-plus) | Excluded after inspection | v4; overlaps the 50K source and omits descriptions | [ODC-By 1.0](https://opendatacommons.org/licenses/by/1-0/) |

The 60K source is selected for development because it uniquely includes full descriptions, skills,
client payment verification, spend, ratings, feedback, applicant ranges and Connects. The 2024 50K
source is later in time and therefore provides a better drift check than randomly mixing both sources.
The contracts source supplies observed historical payments but does not supply proposal text, reply
outcomes or causal labels. The monthly tracker adds volume but removes the text needed for risk,
fit and proposal experiments, so it is not processed.

## Reproducible preprocessing

`make data` performs two explicit stages:

1. `data.pipelines.fetch_kaggle` downloads exact Kaggle versions and rejects any archive whose SHA-256
   does not match the reviewed registry.
2. `data.pipelines.prepare_kaggle` streams the CSV files and writes normalized JSONL plus a generated
   manifest of transformations and actual row counts.

The normalizer:

- removes direct job URLs and original job/freelancer identifiers;
- creates stable pseudonymous IDs with SHA-256;
- redacts email addresses, phone numbers and payment-like strings;
- normalizes money and hourly/fixed pricing fields;
- truncates descriptions to 8,000 characters for bounded model input;
- preserves job text as untrusted content and records detectable injection phrases;
- splits the 2023 jobs deterministically into 51,035 training and 12,913 development records; and
- reserves all 53,058 2024 jobs as a temporal holdout.

Raw archives and normalized records are ignored by Git to avoid redistributing large third-party
copies. The scripts, registry and checksums are committed so another reviewer can reproduce them.

## Derived public profiles

`make public-profile` scans the normalized records and regenerates two small, committed artifacts:

- `data/derived/pricing_priors.json` contains category-specific p25, median and p75 values from
  1,292,791 contract rows. Hourly observations are restricted to USD 1–500 and fixed/milestone
  totals to USD 1–100,000; all rejection counts are recorded.
- `evals/results/public_data_profile.json` records category mix, pricing-model mix, budget quartiles,
  detected injection-signal rates and payment-verification rates for the development, training and
  temporal holdout splits.

The pricing node can use these as descriptive anchors while preserving the user's floor and explicit
client budget band. Every quote records the category, sample size and source when a prior was used.
These observational priors are not causal guidance and cannot establish that a price causes a reply
or hire.

## Synthetic data policy

`evals/datasets/smoke_*` contains tiny, original synthetic fixtures for deterministic tests. Any
additional portfolio, client history, review, proposal or conversation generated for the assignment
must contain `data_origin: synthetic`, a generator version and a seed. Synthetic labels may test
workflow logic and attacks but may not be blended into reported real-world outcome metrics.

`evals/datasets/simulator_fixture.json` is a reproducible mixed-provenance fixture: its 300 job records
come from the public Apache-2.0 development split, while hidden preferences and authored labels are
synthetic. `evals/datasets/synthetic_rag_benchmark.json` contains 90 authored persona-aligned jobs (30
per persona), including 18 planted attacks. The corresponding reply/hire results are always labelled
`synthetic_rule_based`; see `docs/SIMULATOR_EXPERIMENT.md`.

## Handling and privacy

Every portfolio chunk records tenant, persona, type, project, skills, date, client industry, source and
proposal outcome when applicable. Logs and traces redact email addresses, phone numbers, payment
details, credentials and OAuth tokens. Source URLs are never provided to agents as tools or treated as
instructions. Raw Kaggle data remains local and is not exposed from the web application.

## Limitations and permitted conclusions

- All public job data was collected by third parties through scraping. It may be incomplete, stale,
  duplicated, incorrectly parsed or inconsistent with Upwork's current terms and product behavior.
- The 2023 jobs overrepresent the publishers' search keywords; the 2024 holdout covers only a short
  time window. Neither is a random sample of the global freelance economy.
- Public postings have no authoritative `bid/watch/skip`, proposal-quality, reply or hire labels.
  Those require blinded human annotation or instructor labels before reporting decision accuracy.
- Contract payments are observational and survivor-biased. They can support descriptive price priors,
  not claims that a strategy causes replies or hires.
- Public job corpora do not replace portfolio evidence. RAG relevance, grounded-claim and proposal
  experiments require documented real or clearly synthetic portfolios and human relevance labels.
- GigSim remains the grading environment when supplied. Dataset-derived results must be reported
  separately from GigSim and hidden-evaluation results.
