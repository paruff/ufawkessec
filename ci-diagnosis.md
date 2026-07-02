# CI Diagnosis

## Failure Details

**Failure:** CI Pipeline — `startup_failure` on branch `chore/migrate-reusable-to-ufawkespipe`

**Location:** `.github/workflows/ci-pipeline.yml`, line 52-60, `build` job

**Evidence:**
- PR #5 attempts to migrate local reusable workflows (`./.github/workflows/reusable-*.yml`) to centralized `paruff/ufawkespipe/.github/workflows/reusable-*.yml@v1.0.0` (later bumped to `@v1.1.0`)
- The CI Pipeline workflow fails with `startup_failure` — no logs because the failure occurs at workflow parse/validation time, before any job runs
- The `build` job passes `validate-docker-compose`, `validate-jcasc`, and `validate-k8s` inputs to `paruff/ufawkespipe/.github/workflows/reusable-build.yml@v1.1.0`
- **These inputs do not exist** in the target reusable workflow. The ufawkespipe's `reusable-build.yml` (both v1.0.0 and v1.1.0) defines these inputs instead: `validate-prometheus`, `validate-otel`, `validate-tempo`, `validate-grafana`, `fail-on-latest`, `enable-coverage-gate`, `coverage-threshold`, `python-version`, `coverage-paths`
- The old input names (`validate-docker-compose`, `validate-jcasc`, `validate-k8s`) were from the **local** `reusable-build.yml` that was deleted in the migration commit
- GitHub Actions validates inputs at workflow parse time — undefined inputs cause a `startup_failure`

**Likely Cause:** The `build` job passes inputs (`validate-docker-compose`, `validate-jcasc`, `validate-k8s`) that are not defined in the target reusable workflow `paruff/ufawkespipe/.github/workflows/reusable-build.yml@v1.1.0`, causing GitHub Actions to reject the workflow at parse time.

**Confidence:** HIGH

**Proposed Fix:** Replace the invalid inputs in the `build` job's `with:` block with the correct input names used by the ufawkespipe `reusable-build.yml`. Since `ufawkessec` is a Python security repo without Prometheus/OTel/Tempo/Grafana configs, all `validate-*` inputs should be `false` and only `fail-on-latest` should remain `true`.

## Changed Files Since Last Known Good

The migration commit (390b9b4) changed `uses:` paths from local (`./.github/workflows/reusable-*.yml`) to remote (`paruff/ufawkespipe/.github/workflows/reusable-*.yml@v1.0.0`), but did not update the `build` job's `with:` block to match the remote workflow's different input schema.
