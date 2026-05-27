# Deployment Runbook

## Overview

This pipeline uses two GitHub Actions workflows defined in `.github/workflows/`.

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | every push (not `main`) and every PR targeting `main` | lint, test, fail the PR if anything is red |
| `deploy.yml` | push to `main` (typically from a merged PR) | re-run tests on `main`, build a zip artifact, upload to S3 staging bucket |

Merging to `main` is gated by CI via GitHub branch protection (see "Branch protection" below). The deploy workflow re-runs the test suite on `main` before uploading — defence in depth against a force-push that lands untested code on `main`.

## One-time AWS setup

Create an S3 bucket to hold staging artifacts. Naming convention: `data-pipeline-staging-<account-id>`.

```bash
aws s3 mb s3://data-pipeline-staging-871728574007 --region us-east-1
```

Create an IAM user with the minimal policy needed (least privilege):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:PutObjectAcl"],
      "Resource": "arn:aws:s3:::data-pipeline-staging-871728574007/*"
    }
  ]
}
```

Generate an access key for that user.

## One-time GitHub setup

In the repo settings → **Secrets and variables → Actions**:

| Type | Name | Value |
|---|---|---|
| Repository secret | `AWS_ACCESS_KEY_ID` | the IAM user's access key |
| Repository secret | `AWS_SECRET_ACCESS_KEY` | the IAM user's secret |
| Repository secret | `STAGING_BUCKET` | `data-pipeline-staging-871728574007` |
| Repository variable | `AWS_REGION` | `us-east-1` (optional — defaults to `us-east-1`) |

## Branch protection

Settings → **Branches → Branch protection rules → Add rule** for `main`:

- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging
  - Select `Lint + Test` (from the CI workflow)
- ✅ Require branches to be up to date before merging
- ✅ Do not allow bypassing the above settings

With this in place, no commit reaches `main` without a green CI run.

## What the deploy job does

1. **Re-runs the test suite** on the merge commit (smoke-test). 20 second cost; insures against force-pushes that bypass CI.
2. **Builds the artifact**: a zip of `src/`, `requirements.txt`, and `README.md`. Filename includes the short git SHA so every deploy is uniquely identifiable.
3. **Uploads to S3** with metadata: `git-sha`, `git-ref`, and `deployed-at` timestamp on every object.
4. **Updates `data-pipeline-latest.zip`** as a stable pointer to the most recent deploy.
5. **Writes a deployment summary** that's visible in the GitHub Actions UI for each run.

## Rollback

To roll back to a previous artifact:

```bash
aws s3 cp s3://data-pipeline-staging-871728574007/data-pipeline-<old-sha>.zip \
          s3://data-pipeline-staging-871728574007/data-pipeline-latest.zip
```

Or trigger a `git revert` and let the deploy workflow handle it forward.

## Pulling the latest staging artifact

```bash
aws s3 cp s3://data-pipeline-staging-871728574007/data-pipeline-latest.zip .
unzip data-pipeline-latest.zip
python -m src.pipeline orders.csv enriched.json
```

## Failure modes and recovery

| Symptom | Likely cause | Fix |
|---|---|---|
| CI fails with `ModuleNotFoundError` | `requirements.txt` missing a dep | Add to requirements.txt; CI verifies the lock |
| CI fails on `--cov-fail-under=85` | Coverage dropped below 85% | Add tests for new code or lower the threshold (justify in PR) |
| Deploy fails with `Access Denied` | IAM policy missing `s3:PutObject` | Add the action to the policy on the deploy IAM user |
| Deploy fails with `STAGING_BUCKET secret is not configured` | Secret missing | Add the secret in Settings → Secrets and variables |
| Two deploys racing on quick successive merges | `concurrency` group should serialise them | The latest commit always wins via `cancel-in-progress: true` |

## Cost notes

S3 storage for staging artifacts: ~$0.023/GB-month. Each zip is ~20 KB; at 10 deploys/day for a year, total storage is roughly 70 MB → $0.002/month. Effectively free.

GitHub Actions minutes: each CI run takes ~45 seconds, each deploy ~60 seconds. On a public repo, Actions minutes are free; on private, they consume from the included quota.
