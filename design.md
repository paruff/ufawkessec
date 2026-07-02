# uFawkesSec — Design v0.2

_Security Plane of the Fawkes IDP Family_

**Status:** Draft — 2026-06-23
**Depends on:** sec-specification.md v0.2, uFawkesPipe design.md v0.2

---

## 1. Component and Network Map

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  fawkes-net  (external Docker bridge, created once via `make network`)          │
│                                                                                 │
│  ╔══════════════════════════════╗   ╔═══════════════════════════════════════╗   │
│  ║  uFawkesRes (pre-existing)   ║   ║  uFawkesSec (this repo)               ║   │
│  ║                              ║   ║                                       ║   │
│  ║  postgres:5432  [VERIFY]     ║   ║  defectdojo:8080  (Django)            ║   │
│  ║  valkey:6379    [VERIFY]     ║   ║  defectdojo-nginx (proxy)             ║   │
│  ╚══════════════════════════════╝   ║  defectdojo-celery-beat               ║   │
│             ▲  ▲                   ║  defectdojo-celery-worker              ║   │
│             │  │  (DB + cache)     ║  infisical:8082                        ║   │
│             └──┤                   ║  trivy-server:4954 (internal)          ║   │
│                │                   ║  falco (no-driver, reads /host/proc)   ║   │
│                └───────────────────╚═══════════════════════════════════════╝   │
│                                                                                 │
│  ╔══════════════════════════════════════════════════════════════════════════╗   │
│  ║  uFawkesPipe (separate repo, same network)                               ║   │
│  ║                                                                          ║   │
│  ║  woodpecker-agent  ──spawn──►  step containers:                         ║   │
│  ║                                  policy-check   → reads policy/ bundle  ║   │
│  ║                                  generate-sbom  → writes sbom.cdx.json  ║   │
│  ║                                  sign-image     → cosign signs OCI img  ║   │
│  ║                                  upload-defectdojo → POST :8080         ║   │
│  ║                                  vuln-scan-*    → trivy-server:4954     ║   │
│  ╚══════════════════════════════════════════════════════════════════════════╝   │
└─────────────────────────────────────────────────────────────────────────────────┘

External:
  OCI Registry  ◄──image push + signature──  sign-image step
  Falco webhook ──alert──►  OBS_WEBHOOK_URL (uFawkesObs, optional)
```

---

## 2. File Structure (target state after all issues merged)

```
uFawkesSec/
  compose.yaml                    # 7 services + fawkes-net external network
  Makefile                        # extended: add up/down/network/logs targets
  .woodpecker.yml                 # uFawkesSec's own self-CI (lint + test only)
  .pipeline.yml                   # updated: supply-chain flags enabled
  .pre-commit-config.yaml         # unchanged
  .gitleaks.toml                  # unchanged
  .secrets.baseline               # unchanged
  .yamllint                       # unchanged
  .markdownlint.json              # unchanged
  policy/
    no-privileged.rego
    no-host-network.rego
    no-latest-tag.rego
    required-healthcheck.rego
    no-root-user.rego
    deny.rego                     # helper: common deny rule pattern
  config/
    falco/
      falco.yaml                  # Falco config (json_output, webhook)
    infisical/
      .env.example                # documents required env vars (no values)
    defectdojo/
      .env.example                # documents required env vars (no values)
  tests/
    unit/
      test_pipeline_yml.py        # existing (assumed)
      test_compose_yaml.py        # NEW: validates compose.yaml structure
      test_policy.py              # NEW: conftest Python wrapper tests
  docs/
    quickstart.md                 # startup sequence, prerequisites
    policy-guide.md               # how to add/modify Rego policies
  README.md                       # currently empty — must be written (SEC-008)
```

---

## 3. `compose.yaml` Design

### 3.1 Design decisions

**DefectDojo:** The official DefectDojo compose requires Django + Nginx + Celery Beat +
Celery Worker. Postgres and the Celery broker (Redis/Valkey) are assumed to come from
uFawkesRes. This means DefectDojo's `DATABASE_URL` and `CELERY_BROKER_URL` env vars
must point to `postgres:5432` and `valkey:6379` respectively. These are assumptions —
see Open Question Q1 and Q2 in spec before implementing.

**Infisical:** The Infisical container requires an `ENCRYPTION_KEY` (32-byte random hex)
and a `JWT_AUTH_SECRET`. Both are injected via Docker secrets (not env vars) to avoid
appearing in `docker inspect` output or compose logs.

**Trivy server:** Running Trivy in server mode allows all pipeline step containers to
share a single, cached CVE database rather than downloading it independently on each run.
This meaningfully reduces pipeline duration on a single-node dev machine. The server
listens only on the internal `fawkes-net`; it is not exposed to the host.

**Falco:** The `falco-no-driver` image uses eBPF rather than a kernel module, which is
safer for Docker-on-developer-laptop scenarios. It requires `--privileged` on the Falco
container itself (necessary to access `/host/proc` and load the eBPF probe) — this is
a deliberate, documented exception to the `no-privileged.rego` policy. The policy must
explicitly allow the `falco` service by name.

### 3.2 Target `compose.yaml` structure

```yaml
# uFawkesSec compose.yaml — v0.2
# Prerequisites: uFawkesRes running on fawkes-net (postgres:5432, valkey:6379)
# Run: make network && make up

services:
  defectdojo:
    image: defectdojo/defectdojo-django:2.38.0 # VERIFY tag before use
    container_name: defectdojo
    environment:
      DD_DATABASE_URL: postgresql://dojo:${DOJO_DB_PASSWORD}@postgres:5432/dojo
      DD_CELERY_BROKER_URL: redis://valkey:6379/0
      DD_SECRET_KEY_FILE: /run/secrets/defectdojo_secret_key
      DD_ALLOWED_HOSTS: "*"
    secrets:
      - defectdojo_secret_key
    volumes:
      - defectdojo-media:/app/media
    depends_on:
      defectdojo-celery-worker:
        condition: service_started
    networks:
      - fawkes-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/v2/"]
      interval: 30s
      timeout: 10s
      retries: 5

  defectdojo-nginx:
    image: defectdojo/defectdojo-nginx:2.38.0 # VERIFY tag before use
    container_name: defectdojo-nginx
    ports:
      - "8080:8080"
    depends_on:
      - defectdojo
    networks:
      - fawkes-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/"]
      interval: 30s
      timeout: 5s
      retries: 3

  defectdojo-celery-beat:
    image: defectdojo/defectdojo-django:2.38.0
    container_name: defectdojo-celery-beat
    command: /entrypoint-celery-beat.sh
    environment:
      DD_DATABASE_URL: postgresql://dojo:${DOJO_DB_PASSWORD}@postgres:5432/dojo
      DD_CELERY_BROKER_URL: redis://valkey:6379/0
      DD_SECRET_KEY_FILE: /run/secrets/defectdojo_secret_key
    secrets:
      - defectdojo_secret_key
    networks:
      - fawkes-net

  defectdojo-celery-worker:
    image: defectdojo/defectdojo-django:2.38.0
    container_name: defectdojo-celery-worker
    command: /entrypoint-celery-worker.sh
    environment:
      DD_DATABASE_URL: postgresql://dojo:${DOJO_DB_PASSWORD}@postgres:5432/dojo
      DD_CELERY_BROKER_URL: redis://valkey:6379/0
      DD_SECRET_KEY_FILE: /run/secrets/defectdojo_secret_key
    secrets:
      - defectdojo_secret_key
    networks:
      - fawkes-net
    healthcheck:
      test: ["CMD", "celery", "-A", "dojo", "inspect", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  infisical:
    image: infisical/infisical:v0.93.1 # VERIFY tag; Infisical releases frequently
    container_name: infisical
    environment:
      ENCRYPTION_KEY_FILE: /run/secrets/infisical_encryption_key
      AUTH_SECRET_FILE: /run/secrets/infisical_auth_secret
      DB_CONNECTION_URI: postgresql://infisical:${INFISICAL_DB_PASSWORD}@postgres:5432/infisical
      REDIS_URL: redis://valkey:6379/1
    secrets:
      - infisical_encryption_key
      - infisical_auth_secret
    ports:
      - "8082:8080"
    networks:
      - fawkes-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/status"]
      interval: 30s
      timeout: 5s
      retries: 3

  # aquasec/trivy:latest intentionally unpinned — needs current CVE database.
  # Documented exception to pinned-image policy.
  trivy-server:
    image: aquasec/trivy:latest
    container_name: trivy-server
    command: server --listen 0.0.0.0:4954
    networks:
      - fawkes-net
    volumes:
      - trivy-cache:/root/.cache/trivy
    healthcheck:
      test: ["CMD", "trivy", "health"]
      interval: 60s
      timeout: 10s
      retries: 3

  falco:
    # privileged: true is a documented exception — required for eBPF probe loading.
    # Exception is encoded in policy/no-privileged.rego allow-list.
    image: falcosecurity/falco-no-driver:0.39.2 # VERIFY tag
    container_name: falco
    privileged: true
    volumes:
      - /proc:/host/proc:ro
      - /dev:/host/dev:ro
      - ./config/falco/falco.yaml:/etc/falco/falco.yaml:ro
    environment:
      FALCO_WEBHOOK_URL: ${FALCO_WEBHOOK_URL:-}
    networks:
      - fawkes-net

secrets:
  defectdojo_secret_key:
    environment: DEFECTDOJO_SECRET_KEY
  infisical_encryption_key:
    environment: INFISICAL_ENCRYPTION_KEY
  infisical_auth_secret:
    environment: INFISICAL_AUTH_SECRET

volumes:
  defectdojo-media:
  trivy-cache:

networks:
  fawkes-net:
    external: true
    name: fawkes-net
```

**CAUTION on Docker secrets syntax used above:** The `secrets.*.environment` key is
available in Docker Compose v2.4+ for injecting secrets from env vars. Verify this
syntax works in your Docker Compose version before implementing. An alternative is
writing secret values to files and using the `file:` syntax instead.

---

## 4. Policy Distribution Pattern

uFawkesPipe's `policy-check` step must consume Rego policies from uFawkesSec. Two options:

**Option A — Git clone at pipeline time (recommended for v0.2):**

```yaml
- name: policy-check
  image: openpolicyagent/conftest:v0.57.0
  commands:
    - apk add --no-cache git
    - git clone --depth 1 https://github.com/paruff/uFawkesSec /tmp/sec
    - conftest test --policy /tmp/sec/policy/ compose.yaml .pipeline.yml
```

Simple. No artifact publishing required. Adds ~10s to pipeline. Relies on GitHub availability.

**Option B — Policy bundle as OCI artifact (v0.3):**
Publish `policy/` as an OCI artifact using `conftest push` to the internal registry.
`conftest pull` in the pipeline step. More robust but requires registry setup.

**Decision for v0.2:** Option A. Document Option B in `docs/policy-guide.md` as the
upgrade path.

---

## 5. Cosign Key Management

For v0.2, Cosign uses a static key pair stored in Woodpecker native secrets. This is
acceptable for a single-node dev environment. The key generation command:

```bash
cosign generate-key-pair
# produces cosign.key (private) and cosign.pub (public)
# Store cosign.key content in Woodpecker secret: cosign_private_key
# Store passphrase in Woodpecker secret: cosign_password
# Commit cosign.pub to the repo (it's public)
```

The `sign-image` step in uFawkesPipe:

```yaml
- name: sign-image
  image: bitnami/cosign:2.4.1 # VERIFY tag
  environment:
    COSIGN_PRIVATE_KEY:
      from_secret: cosign_private_key
    COSIGN_PASSWORD:
      from_secret: cosign_password
  commands:
    - cosign sign --key env://COSIGN_PRIVATE_KEY
      --yes
      ${REGISTRY_USERNAME}/${CI_REPO_NAME}:${CI_COMMIT_SHA:0:7}
  when:
    - branch: main
```

**CAUTION:** I am not fully certain the `bitnami/cosign` image exposes the CLI exactly
as shown above. Verify the image's entrypoint and supported CLI flags against
https://hub.docker.com/r/bitnami/cosign before implementing SEC-002.

---

## 6. Falco Configuration (`config/falco/falco.yaml`)

```yaml
# Minimal Falco config for uFawkesSec v0.2
rules_file:
  - /etc/falco/falco_rules.yaml # built-in default rules

json_output: true
json_include_output_property: true

stdout_output:
  enabled: true

http_output:
  enabled: true
  url: "${FALCO_WEBHOOK_URL}" # empty string disables this safely
  insecure: true # acceptable for internal fawkes-net

log_level: info
```

---

## 7. Makefile Changes

Extend the existing Makefile with:

```makefile
.PHONY: up down network logs-defectdojo logs-falco

network: ## Create fawkes-net if it does not exist
 docker network create fawkes-net || true

up: network ## Start uFawkesSec stack (requires uFawkesRes running)
 docker compose up -d
 @echo "DefectDojo: http://localhost:8080"
 @echo "Infisical:  http://localhost:8082"

down: ## Stop uFawkesSec stack
 docker compose down

logs-defectdojo: ## Tail DefectDojo logs
 docker compose logs -f defectdojo defectdojo-nginx

logs-falco: ## Tail Falco security events
 docker compose logs -f falco

cosign-keygen: ## Generate Cosign key pair (run once; store private key in Woodpecker secret)
 cosign generate-key-pair
 @echo "Store cosign.key in Woodpecker secret 'cosign_private_key'"
 @echo "Commit cosign.pub to the repo"
 @rm -f cosign.key  # do not leave the private key on disk
```

---

## 8. Test Design

### 8.1 `tests/unit/test_compose_yaml.py` (new)

Parse `compose.yaml` with `pyyaml`. Assert:

- All 7 expected service names present
- `fawkes-net` declared as external network
- `defectdojo` and `infisical` have `healthcheck` blocks
- `falco` is the only service with `privileged: true`
- No image tag is `:latest` except `trivy-server` (assert `trivy-server` image contains `latest`)
- All secrets referenced in services are declared in the top-level `secrets:` block

### 8.2 `tests/unit/test_policy.py` (new)

Use Python `subprocess` to call `conftest test --policy policy/ --no-color <fixture>`.
Provide fixture YAML files in `tests/fixtures/`:

- `compose-clean.yaml` — passes all policies
- `compose-privileged.yaml` — has a non-Falco privileged container; assert conftest exits non-zero
- `compose-host-network.yaml` — has `network_mode: host`; assert conftest exits non-zero
- `compose-latest-tag.yaml` — has a non-Trivy image tagged `:latest`; assert conftest exits non-zero

**Note:** This requires `conftest` to be installed in the test environment. Add it to
`tests/requirements.txt`. I am not certain of the current `conftest` pip package name —
verify at https://pypi.org/project/conftest/ before adding to requirements. If it is
not available via pip, call the Docker image via subprocess instead.

### 8.3 `tests/unit/test_pipeline_yml.py` (assumed existing — verify contents)

The repo already has `tests/unit/` but I could not read its contents. Before writing
new tests, read what exists to avoid duplication.

---

## 9. Risks and Mitigations

| Risk                                                                                                | Likelihood | Mitigation                                                                                                                                                              |
| --------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| DefectDojo's Celery broker requires Redis protocol — Valkey is Redis-compatible but version matters | Medium     | Test with `valkey-cli ping` from defectdojo-celery-worker before calling it working                                                                                     |
| Infisical v0.93.1 `ENV_FILE` secret injection syntax may differ from shown                          | High       | Read Infisical compose docs at https://infisical.com/docs/self-hosting/deployment-options/docker-compose before SEC-004                                                 |
| Falco eBPF probe fails to load on kernel < 4.14 or on macOS Docker Desktop                          | High       | Document host kernel requirement in `docs/quickstart.md`; provide fallback Falco config with `--driver none` for local dev (rules still load, syscall capture disabled) |
| Policy git clone in pipeline adds GitHub as a dependency of every build                             | Medium     | Cache with Woodpecker's workspace or switch to Option B (OCI bundle) if pipeline becomes flaky                                                                          |
| `no-latest-tag.rego` policy must not block the Trivy server image                                   | High       | Add explicit allow-list in `no-latest-tag.rego` for `aquasec/trivy:latest`; covered in tests                                                                            |
| DefectDojo first-run requires database migration — `docker compose up` alone is not sufficient      | High       | Add `make migrate` target that runs `docker compose exec defectdojo python manage.py migrate`; document in quickstart                                                   |
