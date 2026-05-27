# Data Pipeline with CI/CD (Activity 10)

A small order-enrichment ETL pipeline with a GitHub Actions workflow that runs tests on every PR and deploys to an S3 staging bucket after merge.

## Problem this repo solves

The baseline pipeline (on `main`) has zero automation. Bugs are caught only when someone notices broken output in staging. Deployments are manual — copy files to a server, hope you didn't miss one. There's no green-checkmark contract between "tests pass on my laptop" and "the same code is what's running in staging".

The fix branch adds two GitHub Actions workflows:

- **CI** runs on every push and pull request — lints, runs the test suite, fails the PR if anything goes red.
- **Deploy** runs only on merges to `main` — builds an artifact, uploads it to an S3 staging bucket, posts a deployment summary in the run UI.

## Pipeline

```
orders.csv
   │
   ▼
parse_row  ──▶  validate_order ──▶  enrich  ──▶  enriched.json
                     │
                     ▼
                 failures list (with error_code)
```

## Local development

```bash
pip install -r requirements.txt
python -m src.pipeline tests/fixtures/orders.csv data/output/enriched.json
pytest -v --cov=src
```

Expected output: 6 enriched rows, 4 failures, all 9 tests passing with ~95%+ coverage.

## CI/CD

See `.github/workflows/ci.yml` and `.github/workflows/deploy.yml` for the workflow definitions, and `DEPLOYMENT.md` for the runbook.
