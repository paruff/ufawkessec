# uFawkesSec — Specification v0.2

_Security Plane of the Fawkes IDP Family_

**Status:** Draft — 2026-06-23
**Author:** Platform Engineering (solo contributor)
**Repo:** https://github.com/paruff/uFawkesSec
**Companion repos:** uFawkesRes (resource plane), uFawkesPipe (CI/CD plane)

---

## Baseline state (observed from repo read, 2026-06-23)

The following files exist in main. Everything else is absent.

| File                               | Content summary                                                                                                      |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `.pipeline.yml`                    | Declarative pipeline contract spec (83 lines); supply-chain block has all flags `enabled: false`; no Woodpecker YAML |
| `Makefile`                         | `test`, `test-unit`, `validate`, `pre-commit-setup`, `pre-commit-run`, `clean` targets; no `up`/`down` targets       |
| `.pre-commit-config.yaml`          | gitleaks v8.18.1, detect-secrets v1.4.0, yamllint v1.33.0, markdownlint-cli v0.38.0, prettier v3.1.0                 |
| `.gitleaks.toml`                   | Present (contents not read — assumed standard config)                                                                |
| `.secrets.baseline`                | Present                                                                                                              |
| `.yamllint` / `.markdownlint.json` | Present                                                                                                              |
| `tests/unit/`                      | Directory present; contents not readable via web                                                                     |
| `README.md`                        | **Empty — 0 bytes**                                                                                                  |
| `compose.yaml`                     | **Does not exist**                                                                                                   |
| `.woodpecker.yml`                  | **Does not exist**                                                                                                   |

**Implication:** uFawkesSec is a skeleton. Every substantive file described below is new work.

---

## uFawkesRes assumptions (repo not publicly indexed — verify before implementation)

I could not read `github.com/paruff/uFawkesRes`. The following are **assumptions** based on
your description ("postgres db, valkey cache, etc"). Verify each before encoding them as
interface contracts:

| Assumption                                                                           | Flag       |
| ------------------------------------------------------------------------------------ | ---------- |
| uFawkesRes exposes a Docker Compose stack on a shared network named `fawkes-net`     | **VERIFY** |
| Postgres is reachable at `postgres:5432` on `fawkes-net`                             | **VERIFY** |
| Valkey is reachable at `valkey:6379` on `fawkes-net`                                 | **VERIFY** |
| DefectDojo's backing Postgres lives in uFawkesRes (not self-contained in uFawkesSec) | **VERIFY** |
| uFawkesRes is started before uFawkesSec (`depends_on` or documented startup order)   | **VERIFY** |
| No other services are in uFawkesRes that uFawkesSec must connect to                  | **VERIFY** |

If any assumption is wrong, the `compose.yaml` network declarations and `depends_on` chains
in design.md §3 must be updated before implementing SEC-003.

---

## 1. Purpose and Scope

uFawkesSec is the security plane of the Fawkes IDP family. Its job is to transform the
four security domains described in the scope document from passive scanner logs into an
active, automated feedback loop that runs without human prompting.

The four domains and their v0.2 scope decisions:

| Domain                      | v0.2 target                                                                                                                | Out of scope for v0.2                                                  |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **Supply chain integrity**  | SBOM generation via Trivy + Cosign image signing in Woodpecker pipeline (key pair in Woodpecker secrets)                   | Attestation (SLSA), Rekor transparency log, Kyverno policy enforcement |
| **Policy as code**          | Conftest + Rego policies checked in Woodpecker pipeline against `compose.yaml` and `.pipeline.yml`                         | OPA server deployment, admission webhooks, runtime policy              |
| **Secret lifecycle**        | Infisical deployed as a service in `compose.yaml`; Woodpecker fetches scoped tokens at build time                          | Infisical agent sidecar injection at runtime, Vault migration          |
| **Vulnerability telemetry** | DefectDojo deployed in `compose.yaml` backed by uFawkesRes Postgres; Gitleaks + Trivy findings POST to it from uFawkesPipe | DefectDojo product policies, threshold-based pipeline gates (v0.3)     |
| **Runtime shielding**       | Falco deployed as a service monitoring the Docker socket; webhook alerts to a configurable endpoint                        | Falco rules authoring, PagerDuty/Slack integration (v0.3)              |

---

## 2. Personas and JTBD

| Persona                 | Job To Be Done                                                                          |
| ----------------------- | --------------------------------------------------------------------------------------- |
| **Platform engineer**   | Stand up the full security stack with `make up` in under 15 min on a single Docker node |
| **Security engineer**   | See aggregated findings from every repo in DefectDojo without touching CI config        |
| **App developer**       | Know within the pipeline run whether their commit introduced a secret or a CRITICAL CVE |
| **Compliance reviewer** | Confirm that every image shipped has a signed SBOM and that policy gates were enforced  |

---

## 3. Functional Requirements

### 3.1 Services deployed by uFawkesSec (`compose.yaml`)

| Service                    | Image (pinned)                         | Port on host           | Role                                                        |
| -------------------------- | -------------------------------------- | ---------------------- | ----------------------------------------------------------- |
| `defectdojo`               | `defectdojo/defectdojo-django:2.38.0`  | `8080`                 | Security findings aggregation                               |
| `defectdojo-nginx`         | `defectdojo/defectdojo-nginx:2.38.0`   | —                      | Reverse proxy for defectdojo (required by official compose) |
| `defectdojo-celery-beat`   | `defectdojo/defectdojo-django:2.38.0`  | —                      | Periodic task runner                                        |
| `defectdojo-celery-worker` | `defectdojo/defectdojo-django:2.38.0`  | —                      | Async task worker                                           |
| `infisical`                | `infisical/infisical:v0.93.1`          | `8082`                 | Zero-trust secrets store                                    |
| `trivy-server`             | `aquasec/trivy:latest`                 | `4954` (internal only) | Shared Trivy cache server                                   |
| `falco`                    | `falcosecurity/falco-no-driver:0.39.2` | —                      | Runtime container security                                  |

**Note on DefectDojo version:** `2.38.0` is pinned based on the latest stable tag I am
aware of (knowledge cutoff August 2025). You must verify the current stable tag at
https://github.com/DefectDojo/django-DefectDojo/releases before implementing SEC-003.

**Note on Trivy tag:** `aquasec/trivy:latest` is intentionally unpinned for the server
container so the CVE database stays current. This is a documented exception consistent
with uFawkesPipe convention.

### 3.2 Network topology

All uFawkesSec services join `fawkes-net` (external, created by `make network` in
uFawkesPipe or via `make network` in uFawkesSec). This allows:

- uFawkesPipe step containers to POST findings directly to `http://defectdojo:8080`
- Trivy step containers to use `http://trivy-server:4954` as a shared cache
- Infisical to be reachable at `http://infisical:8082` by Woodpecker agent

DefectDojo's Postgres backend is provided by uFawkesRes at `postgres:5432` on `fawkes-net`.
DefectDojo's Celery broker is Valkey at `valkey:6379` on `fawkes-net`. **(VERIFY both.)**

uFawkesSec does **not** deploy its own Postgres or Valkey.

### 3.3 Cosign supply chain step (in uFawkesPipe)

uFawkesSec does not run its own pipeline. Instead, it contributes two Woodpecker steps
that are added to uFawkesPipe's `.woodpecker.yml` as part of this work:

**Step: `generate-sbom`** (after `build`, before `deploy-portainer`)

- Image: `aquasec/trivy:latest`
- Command: `trivy image --format cyclonedx --output artifacts/security/sbom.cdx.json <image-ref>`
- Writes to uFawkesPipe's shared workspace artifact dir

**Step: `sign-image`** (after `generate-sbom`)

- Image: `bitnami/cosign:2.4.1`
- Uses Woodpecker secrets: `cosign_private_key`, `cosign_password` # pragma: allowlist secret
- Command: `cosign sign --key env://COSIGN_PRIVATE_KEY <image-ref>`
- Only runs on `branch: main`

**Note on Cosign version:** Verify the current stable Cosign image tag at
https://hub.docker.com/r/bitnami/cosign before implementing SEC-002.

### 3.4 Conftest policy-as-code step (in uFawkesPipe)

**Step: `policy-check`** (after `lint-yaml`, before `build`)

- Image: `openpolicyagent/conftest:v0.57.0` (verify this tag exists)
- Tests: `policy/` directory in uFawkesSec repo (consumed by uFawkesPipe via a mounted
  or fetched policy bundle — see design.md §4 for the policy distribution pattern)
- Checks: `compose.yaml`, `.pipeline.yml`, Dockerfile (if present)

**Minimum policy set for v0.2** (in `uFawkesSec/policy/`):

| Policy file                 | What it enforces                                                               |
| --------------------------- | ------------------------------------------------------------------------------ |
| `no-privileged.rego`        | No container in compose.yaml may have `privileged: true`                       |
| `no-host-network.rego`      | No container may use `network_mode: host`                                      |
| `no-latest-tag.rego`        | No image tag may be `:latest` (exception: Trivy scanner, documented)           |
| `required-healthcheck.rego` | All services must declare a `healthcheck` block                                |
| `no-root-user.rego`         | No service may declare `user: root` or omit `user:` (warn, not gate, for v0.2) |

### 3.5 Infisical secret lifecycle (v0.2 scope)

- Infisical is deployed as a service in `compose.yaml` with its own encryption key
  injected via Docker secret (not env var)
- Woodpecker agent is configured with `WOODPECKER_SECRET_BACKEND=infisical` and
  `INFISICAL_URL=http://infisical:8082` — **CAUTION:** verify Woodpecker v3 supports
  native Infisical backend before encoding this. I am not certain this integration
  exists in Woodpecker v3. An alternative is having Woodpecker fetch secrets from
  Infisical via a dedicated pipeline step using the Infisical CLI.
- Runtime secret injection (e.g. injecting DB passwords into app containers at boot)
  is **out of scope for v0.2**

### 3.6 Falco runtime shielding (v0.2 scope)

- Falco runs in `falco-no-driver` mode (userspace via eBPF or /proc — no kernel module)
- Mounts: `/host/proc:/host/proc:ro`, `/host/dev:/host/dev:ro` (read-only host proc)
- Alert output: `json_output: true` to stdout; Falco webhook to `OBS_WEBHOOK_URL` for
  uFawkesObs log aggregation (non-blocking if webhook unavailable)
- Default Falco rule set only for v0.2; custom rules are v0.3
- **Note:** Falco no-driver mode requires the host kernel to support eBPF (Linux 4.14+).
  Verify your host kernel version before deploying.

### 3.7 `.pipeline.yml` supply-chain flags (enablement)

The existing `.pipeline.yml` has all supply-chain flags set to `enabled: false`. This
spec enables them:

```yaml
supply-chain:
  sbom:
    enabled: true
    format: cyclonedx
    output: artifacts/security/sbom.cdx.json
  image-signing:
    enabled: true
    tool: cosign
  attestation:
    enabled: false # v0.3
  container-scan:
    enabled: true
    tool: trivy
    server: http://trivy-server:4954
```

### 3.8 Secrets required (new, beyond uFawkesPipe)

| Secret name                | Used by                         | Description                                       |
| -------------------------- | ------------------------------- | ------------------------------------------------- |
| `cosign_private_key`       | `sign-image` step (uFawkesPipe) | Cosign private key (PEM)                          |
| `cosign_password`          | `sign-image` step               | Cosign key passphrase                             |
| `infisical_encryption_key` | Infisical service               | Master encryption key (Docker secret)             |
| `falco_webhook_url`        | Falco service                   | Alert destination (optional; empty = stdout only) |
| `defectdojo_secret_key`    | DefectDojo service              | Django SECRET_KEY                                 |

---

## 4. Non-Functional Requirements

| Concern                    | Requirement                                                                                                                      |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **Single-node constraint** | Full uFawkesSec stack runs on the same Docker node as uFawkesPipe; total RAM budget including uFawkesRes and uFawkesPipe is 8 GB |
| **Startup order**          | uFawkesRes must be running before `make up` in uFawkesSec (Postgres/Valkey health required by DefectDojo)                        |
| **Idempotency**            | `make down && make up` restores a clean working state; DefectDojo data persists in a named volume                                |
| **Image pinning**          | All service images pinned to specific tags except Trivy server (documented exception)                                            |
| **Test coverage**          | `pytest tests/unit/` must pass; 60% total, 80% diff coverage per existing `.pipeline.yml` thresholds                             |
| **Policy linting**         | All `.rego` files pass `conftest verify` before merge                                                                            |
| **Secret hygiene**         | No secrets in any tracked file; `.gitleaks.toml` and `.secrets.baseline` already in repo and must remain clean                   |

---

## 5. Acceptance Criteria

1. `make up` starts all 7 services with no errors (requires uFawkesRes already running).
2. DefectDojo is accessible at `http://localhost:8080` and accepts an authenticated API request.
3. Infisical is accessible at `http://localhost:8082`.
4. A push to uFawkesPipe on a repo with a planted secret: `secrets-scan` fails; DefectDojo receives the Gitleaks finding. # pragma: allowlist secret
5. A push on `main` with a clean codebase: `sign-image` succeeds; `cosign verify` on the pushed image confirms the signature.
6. `conftest test --policy policy/ compose.yaml` passes with zero violations.
7. Falco container is running and `docker logs falco` shows at least one syscall event line.
8. `pytest tests/unit/` passes with zero failures.
9. `pre-commit run --all-files` passes with zero errors.

---

## 6. Open Questions (must resolve before indicated issue)

| #   | Question                                                                                                                     | Blocks  |
| --- | ---------------------------------------------------------------------------------------------------------------------------- | ------- |
| Q1  | Does uFawkesRes expose Postgres at `postgres:5432` and Valkey at `valkey:6379` on `fawkes-net`?                              | SEC-003 |
| Q2  | Does DefectDojo's official compose require a separate Redis/Valkey, or can it share uFawkesRes Valkey?                       | SEC-003 |
| Q3  | Does Woodpecker v3 support a native Infisical secrets backend, or must Infisical be called via CLI step?                     | SEC-004 |
| Q4  | What is the current stable DefectDojo image tag? Verify at github.com/DefectDojo/django-DefectDojo/releases                  | SEC-003 |
| Q5  | Does the host kernel support eBPF (Linux 4.14+) for Falco no-driver mode?                                                    | SEC-006 |
| Q6  | What is the `etc` in "postgres db, valkey cache, etc" for uFawkesRes? Are there other services uFawkesSec should connect to? | All     |
