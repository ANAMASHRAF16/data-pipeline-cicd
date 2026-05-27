# Data Pipeline with CI/CD (Activity 10)

[![CI](https://github.com/ANAMASHRAF16/data-pipeline-cicd/actions/workflows/ci.yml/badge.svg)](https://github.com/ANAMASHRAF16/data-pipeline-cicd/actions/workflows/ci.yml)
[![Deploy](https://github.com/ANAMASHRAF16/data-pipeline-cicd/actions/workflows/deploy.yml/badge.svg)](https://github.com/ANAMASHRAF16/data-pipeline-cicd/actions/workflows/deploy.yml)

A small order-enrichment ETL pipeline with a GitHub Actions workflow that runs tests on every PR and deploys to an S3 staging bucket after merge.

## Problem this repo solves

The baseline pipeline (on `main` before the fix branch is merged) has zero automation. Bugs are caught only when someone notices broken output in staging. Deployments are manual — copy files to a server, hope you didn't miss one. There's no green-checkmark contract between "tests pass on my laptop" and "the same code is what's running in staging".

The fix adds two GitHub Actions workflows:

- **CI** runs on every push and pull request — lints, runs the test suite with coverage gating, fails the PR if anything goes red.
- **Deploy** runs only on merges to `main` — re-runs tests on the merge commit, builds an artifact, uploads it to an S3 staging bucket, posts a deployment summary in the run UI.

## Pipeline architecture

```
orders.csv
   │
   ▼
parse_row  ──▶  validate_order ──▶  enrich  ──▶  enriched.json
                     │
                     ▼
                 failures list (with error_code from a fixed enum)
```

## CI/CD flow

```
Developer pushes a feature branch
        │
        ▼
CI workflow runs        ──▶  ruff lint + pytest + 85% coverage gate
        │                            │ fail
        │ all green                  ▼
        ▼                       PR cannot be merged
PR review + merge to main
        │
        ▼
Deploy workflow runs    ──▶  smoke-test → zip artifact → S3 upload
        │                            │
        ▼                            ▼
Deployment summary           s3://staging-bucket/data-pipeline-<sha>.zip
in GitHub UI                 s3://staging-bucket/data-pipeline-latest.zip
```

## Local development

```bash
pip install -r requirements.txt
python -m src.pipeline tests/fixtures/orders.csv data/output/enriched.json
pytest tests/ -v --cov=src
```

Expected output: 6 enriched rows out of 10 in the sample fixture (4 fail validation), 11 tests passing with ~95%+ coverage.

## Continuous integration

Workflow: `.github/workflows/ci.yml`

- Triggered on: every push to any branch except `main`, and every PR targeting `main`
- Steps: install deps → ruff lint → pytest with coverage → upload coverage XML as a workflow artifact
- Coverage gate: 85% minimum (CI fails if dropped below)
- Status check name: `Lint + Test` — this is the name to reference in branch protection

## Continuous deployment

Workflow: `.github/workflows/deploy.yml`

- Triggered on: push to `main` (typically from a merged PR)
- Steps: smoke-test → build artifact → configure AWS credentials → upload to S3 with metadata → update `latest` pointer → write deployment summary
- Concurrency group: `deploy-staging` with `cancel-in-progress: true` — fast successive merges don't race; the latest commit always wins

## Setup

See [DEPLOYMENT.md](DEPLOYMENT.md) for one-time setup of the S3 bucket, IAM user, GitHub Secrets, and branch protection rules.

## Required GitHub Secrets

| Secret | Purpose |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user with `s3:PutObject` on the staging bucket |
| `AWS_SECRET_ACCESS_KEY` | companion secret |
| `STAGING_BUCKET` | bucket name, e.g. `data-pipeline-staging-871728574007` |

## Trade-offs documented

- **Re-run tests on the deploy workflow** — costs ~20 seconds per deploy but protects against force-pushes that bypass CI
- **Static FX table** — keeps the pipeline deterministic for tests; production would call a live FX service
- **Error codes as a fixed enum** — bounds downstream metric/log cardinality (no unbounded raw exception strings)
- **`data-pipeline-latest.zip` pointer** — duplicates storage but makes staging consumers' integration code trivial (always fetch `latest`)
