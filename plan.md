# uFawkesSec — Implementation Plan v0.2
*Lean issues for Deepseek v4 flash implementation*

**Status:** Draft — 2026-06-23
**Branch strategy:** One branch per issue: `feat/SEC-001-policy-rego`, etc. PRs to `main`.
**Test gate:** `pytest tests/unit/` + `pre-commit run --all-files` must pass on every PR.
**Definition of done per issue:** All acceptance criteria checked + test gate passing.

---

## Prerequisites (human actions before any issue can start)

These are not implementable by Deepseek. They require human decisions or credentials.

- [ ] **P1:** Confirm uFawkesRes services and network names (resolves Q1, Q2, Q6 from spec)
- [ ] **P2:** Verify DefectDojo current stable image tag at https://github.com/DefectDojo/django-DefectDojo/releases
- [ ] **P3:** Verify Infisical current stable image tag at https://hub.docker.com/r/infisical/infisical
- [ ] **P4:** Confirm Woodpecker v3 Infisical backend support (or accept CLI-based alternative)
- [ ] **P5:** Confirm host kernel supports eBPF for Falco no-driver mode (`uname -r`, must be 4.14+)
- [ ] **P6:** Run `cosign generate-key-pair`, store `cosign.key` in Woodpecker secret, commit `cosign.pub`

---

## SEC-001 · Write Rego policies and conftest fixtures

**Type:** feat / security
**Estimated effort:** 1.5 hr
**Depends on:** nothing (pure file creation)
**Branch:** `feat/SEC-001-policy-rego`

### Context
The `.pipeline.yml` references policy-as-code but no `policy/` directory exists. This
issue creates the Rego policy files and the test fixtures that validate them.
No Docker, no compose — pure text files + Python tests.

### Acceptance criteria
- [ ] `policy/` directory created with 5 `.rego` files: `no-privileged.rego`,
  `no-host-network.rego`, `no-latest-tag.rego`, `required-healthcheck.rego`,
  `no-root-user.rego`
- [ ] Each policy uses the `deny[msg]` rule pattern (standard Conftest pattern)
- [ ] `policy/no-privileged.rego` has an explicit allow-list for service name `falco`
- [ ] `policy/no-latest-tag.rego` has an explicit allow-list for images matching
  `aquasec/trivy:latest`
- [ ] `tests/fixtures/` directory created with 4 YAML fixtures:
  `compose-clean.yaml`, `compose-privileged.yaml`, `compose-host-network.yaml`,
  `compose-latest-tag.yaml`
- [ ] `tests/unit/test_policy.py` created; uses `subprocess` to call
  `conftest test --policy policy/ --no-color <fixture>` for each fixture
- [ ] Clean fixture passes all 5 policies (conftest exit 0)
- [ ] Each violation fixture fails exactly the policy it targets (conftest exit 1)
- [ ] `conftest` added to `tests/requirements.txt` (verify pip package name first;
  if not available via pip, use `docker run openpolicyagent/conftest:v0.57.0` in subprocess)
- [ ] `pytest tests/unit/test_policy.py` passes

### Implementation notes for Deepseek
The Conftest `deny[msg]` pattern for Docker Compose YAML looks like this conceptually:
```rego
package main

deny[msg] {
  service := input.services[name]
  service.privileged == true
  name != "falco"
  msg := sprintf("Service '%v' must not run as privileged", [name])
}
```
Verify the exact Conftest input format for `docker-compose.yaml` files by reading
https://www.conftest.dev/examples/ before writing the policies. The `input` object
structure depends on the file format being parsed.

---

## SEC-002 · Add `generate-sbom` and `sign-image` steps to uFawkesPipe

**Type:** feat / supply-chain
**Estimated effort:** 1 hr
**Depends on:** P6 (Cosign key pair must exist in Woodpecker secrets)
**Branch:** `feat/SEC-002-sbom-signing` (in **uFawkesPipe** repo, not uFawkesSec)
**Note:** This issue creates files in uFawkesPipe, not uFawkesSec. It is tracked here
because uFawkesSec owns the supply-chain security domain.

### Context
The `.pipeline.yml` supply-chain flags declare intent but no pipeline steps implement
them. This issue adds the two steps to uFawkesPipe's `.woodpecker.yml`.

### Acceptance criteria
- [ ] Step `generate-sbom` added to uFawkesPipe `.woodpecker.yml` after `build` step
- [ ] Image: `aquasec/trivy:latest`; command produces `artifacts/security/sbom.cdx.json`
  in CycloneDX format
- [ ] Step `sign-image` added after `generate-sbom`; image `bitnami/cosign:2.4.1` (verify)
- [ ] Both steps have `when: branch: main`
- [ ] Woodpecker secrets `cosign_private_key` and `cosign_password` are referenced via
  `from_secret:` (not hardcoded)
- [ ] `cosign.pub` committed to uFawkesSec repo root (public key only)
- [ ] `tests/unit/test_woodpecker_yml.py` in uFawkesPipe updated to assert both new
  step names exist and appear after `build`
- [ ] `pytest tests/unit/test_woodpecker_yml.py` passes

### Implementation notes for Deepseek
Do not hardcode image digests or registry URLs. Use Woodpecker built-in variables for
the image ref. Verify the `bitnami/cosign` CLI syntax from the image documentation
before writing the step commands. The `--yes` flag to `cosign sign` suppresses the
interactive confirmation prompt — verify it is supported in the version used.

---

## SEC-003 · Write `compose.yaml` for uFawkesSec

**Type:** feat / infra
**Estimated effort:** 2 hr
**Depends on:** P1 (uFawkesRes services confirmed), P2 (DefectDojo tag confirmed)
**Branch:** `feat/SEC-003-compose`

### Context
No `compose.yaml` exists. This is the core infrastructure file for the security plane.
It deploys DefectDojo (4 containers), Infisical, Trivy server, and Falco.

### Acceptance criteria
- [ ] `compose.yaml` created at repo root with all 7 services from design.md §3.2
- [ ] All non-Trivy images pinned to specific tags (no `:latest` except trivy-server)
- [ ] `fawkes-net` declared as external network; all services on it
- [ ] DefectDojo `DATABASE_URL` points to `postgres:5432` (from uFawkesRes)
- [ ] DefectDojo `CELERY_BROKER_URL` points to `valkey:6379` (from uFawkesRes)
- [ ] All sensitive values use Docker secrets (`/run/secrets/<name>`), not plain env vars
- [ ] `falco` is the only service with `privileged: true`
- [ ] `trivy-server` uses named volume `trivy-cache`
- [ ] `defectdojo-media` named volume declared
- [ ] `config/falco/falco.yaml` created per design.md §6
- [ ] `config/infisical/.env.example` created with commented placeholder vars
- [ ] `config/defectdojo/.env.example` created with commented placeholder vars
- [ ] `tests/unit/test_compose_yaml.py` created per design.md §8.1
- [ ] `pytest tests/unit/test_compose_yaml.py` passes
- [ ] `yamllint compose.yaml` reports zero errors

### Implementation notes for Deepseek
The Docker Compose `secrets` top-level block with `environment:` key syntax requires
Docker Compose v2.4+. Verify your Docker Compose version supports this before using it.
If not, use `file:` syntax and document the secret file placement in quickstart.md.
Do not invent DefectDojo environment variable names — read the official DefectDojo
environment variable documentation at https://documentation.defectdojo.com/getting_started/configuration/
before writing the `environment:` block.

---

## SEC-004 · Add `policy-check` step to uFawkesPipe

**Type:** feat / security
**Estimated effort:** 45 min
**Depends on:** SEC-001 (policy files must exist in uFawkesSec main)
**Branch:** `feat/SEC-004-policy-check` (in **uFawkesPipe** repo)

### Context
The Rego policies from SEC-001 must be enforced in every pipeline run. This step
clones the uFawkesSec policy bundle and runs Conftest against the application repo's
compose and pipeline contract files.

### Acceptance criteria
- [ ] Step `policy-check` added to uFawkesPipe `.woodpecker.yml` after `lint-yaml`,
  before `build`
- [ ] Image: `openpolicyagent/conftest:v0.57.0` (verify this tag exists)
- [ ] Commands: clone uFawkesSec shallow; run `conftest test --policy /tmp/sec/policy/`
  against `compose.yaml` and `.pipeline.yml` in the workspace
- [ ] Step is a hard gate (no `|| true`)
- [ ] `tests/unit/test_woodpecker_yml.py` in uFawkesPipe updated to assert
  `policy-check` exists and appears before `build`
- [ ] `pytest tests/unit/test_woodpecker_yml.py` passes

### Implementation notes for Deepseek
If the application repo being scanned does not have a `compose.yaml`, Conftest will
error. Add a guard: `[ -f compose.yaml ] && conftest test ... || echo "No compose.yaml"`.
Do not fail the pipeline if the file does not exist — warn only, for v0.2.

---

## SEC-005 · Extend Makefile with `up`, `down`, `network`, `migrate`, `cosign-keygen`

**Type:** chore
**Estimated effort:** 30 min
**Depends on:** SEC-003 (`compose.yaml` must exist)
**Branch:** `feat/SEC-005-makefile`

### Context
The current Makefile has no `up`/`down` targets. Developers cannot start the security
plane. The `migrate` target is critical — DefectDojo will not function without the
initial database migration.

### Acceptance criteria
- [ ] `make network` creates `fawkes-net` idempotently (`|| true`)
- [ ] `make up` calls `make network` then `docker compose up -d`; prints service URLs
- [ ] `make down` calls `docker compose down`
- [ ] `make migrate` runs `docker compose exec defectdojo python manage.py migrate`
  and `python manage.py createsuperuser --noinput`; documents required env vars
  `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD`, `DJANGO_SUPERUSER_EMAIL`
- [ ] `make cosign-keygen` generates a key pair, prints instructions for storing the
  private key, then deletes `cosign.key` from disk (does not leave private key at rest)
- [ ] `make logs-defectdojo` and `make logs-falco` tail the relevant containers
- [ ] All new targets documented in `make help` output
- [ ] No existing targets broken

---

## SEC-006 · Write `docs/quickstart.md`

**Type:** docs
**Estimated effort:** 1 hr
**Depends on:** SEC-003, SEC-005
**Branch:** `feat/SEC-006-quickstart`

### Context
README.md is empty. Developers have no path to get the security plane running.
This is the minimum viable documentation for v0.2.

### Acceptance criteria
- [ ] `docs/quickstart.md` covers prerequisites: Docker version, host kernel requirement
  for Falco eBPF (Linux 4.14+), uFawkesRes must be running first
- [ ] Step-by-step startup sequence:
  1. Set required environment variables (with reference to `.env.example` files)
  2. `make network`
  3. `make up`
  4. `make migrate` (first run only)
  5. Verify DefectDojo at `http://localhost:8080`
  6. Verify Infisical at `http://localhost:8082`
  7. Verify Falco: `docker logs falco`
- [ ] Smoke test checklist (8 steps matching acceptance criteria in spec)
- [ ] Troubleshooting section: Falco eBPF probe failure, DefectDojo migration errors,
  `fawkes-net` not found
- [ ] Link to `docs/policy-guide.md` for policy authoring
- [ ] `markdownlint` passes on this file

---

## SEC-007 · Write `docs/policy-guide.md`

**Type:** docs
**Estimated effort:** 45 min
**Depends on:** SEC-001
**Branch:** `feat/SEC-007-policy-guide`

### Context
Platform engineers need to know how to add policies, how the Conftest input format
works for Docker Compose YAML, and what the v0.3 OCI bundle upgrade path looks like.

### Acceptance criteria
- [ ] Explains the `deny[msg]` pattern with a worked example
- [ ] Documents the `input` object structure for compose.yaml files (verify from
  Conftest docs; do not invent field names)
- [ ] How to test a new policy locally: `conftest test --policy policy/ <fixture>`
- [ ] How to add an exception to an existing policy (allow-list pattern)
- [ ] Table of all 5 current policies with what they enforce and their exceptions
- [ ] Section: "Upgrading to OCI policy bundle (v0.3)" describing Option B from design.md §4
- [ ] `markdownlint` passes

---

## SEC-008 · Write `README.md`

**Type:** docs
**Estimated effort:** 30 min
**Depends on:** SEC-006, SEC-007
**Branch:** `feat/SEC-008-readme`

### Context
README.md is currently 0 bytes. This is the last issue — written after all implementation
is done so it accurately describes what was built.

### Acceptance criteria
- [ ] Title and one-line description matching repo topic tags
- [ ] What this is: 3-sentence plain-language summary
- [ ] Architecture diagram (ASCII, consistent with design.md §1)
- [ ] Services table: name, image, port, role
- [ ] Quick start: 4-line snippet linking to `docs/quickstart.md` for full detail
- [ ] Integration section: how uFawkesPipe connects to uFawkesSec (DefectDojo URL,
  Trivy server URL, policy bundle clone)
- [ ] Security domains section: 4 bullets (supply chain, policy, secrets, runtime)
  with current v0.2 status and v0.3 roadmap item
- [ ] `markdownlint` passes
- [ ] `make pre-commit-run` passes on all files

---

## Milestone summary

| Milestone | Issues | Target |
|---|---|---|
| **v0.2-policy** | SEC-001, SEC-004 | Week 3 |
| **v0.2-supply-chain** | SEC-002 | Week 3 |
| **v0.2-infra** | SEC-003, SEC-005 | Week 4 |
| **v0.2-docs** | SEC-006, SEC-007, SEC-008 | Week 4 |

---

## Notes for Deepseek implementation

1. **Do not invent DefectDojo environment variable names.** The official environment
   variable reference is at https://documentation.defectdojo.com/getting_started/configuration/
   Read it before writing the `compose.yaml` environment block. Wrong variable names
   will silently fail and produce a non-functional container.

2. **Do not invent Conftest Rego input schemas.** The structure of `input` when
   Conftest parses a Docker Compose YAML depends on Conftest's parsing behaviour.
   Verify by running `conftest parse compose.yaml` on a real file to see the
   actual object structure before writing `deny` rules against it.

3. **Infisical compose syntax changes frequently.** Infisical is a fast-moving project.
   The `ENCRYPTION_KEY_FILE` and `AUTH_SECRET_FILE` environment variable names shown
   in design.md are based on documented patterns but must be verified against the
   version being deployed before use.

4. **Read `tests/unit/` before writing new tests.** The directory exists but its
   contents were not readable in this session. Run `ls tests/unit/` in the actual
   repo before creating new files to avoid naming conflicts.

5. **One PR per issue, linear merge order.** The dependency chain is:
   SEC-001 → SEC-004 (policy in repo before step references it)
   SEC-003 → SEC-005 → SEC-006 (compose before Makefile before docs)
   SEC-001, SEC-002, SEC-003 can run in parallel with each other.
   SEC-008 is always last.
