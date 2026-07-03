# uFawkesSec

**Security Plane of the Fawkes IDP Family** — Automated security feedback loops for containerized workloads.

---

## What This Is

uFawkesSec is the security plane of the Fawkes Internal Developer Platform family. It deploys a curated stack of open-source security services (DefectDojo, Infisical, Trivy, Falco) as Docker Compose services, enabling supply-chain integrity, policy-as-code, secret lifecycle management, and runtime vulnerability telemetry — all running on a single Docker node. uFawkesSec integrates with uFawkesPipe to inject security gates into CI/CD pipelines without requiring developers to configure security tools.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  fawkes-net  (external Docker bridge, created via `make network`)                                    │
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
│  ╚═══════════════════════════════════════════════════════════════════════════╝   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**External integrations:**

- OCI Registry ◄──image push + signature── `sign-image` step
- Falco webhook ──alert──► `OBS_WEBHOOK_URL` (uFawkesObs, optional)

---

## Services

| Service                    | Image                                  | Port (Host)       | Role                                   |
| -------------------------- | -------------------------------------- | ----------------- | -------------------------------------- |
| `defectdojo`               | `defectdojo/defectdojo-django:2.38.0`  | `8080`            | Security findings aggregation (Django) |
| `defectdojo-nginx`         | `defectdojo/defectdojo-nginx:2.38.0`   | `8080`            | Reverse proxy for DefectDojo           |
| `defectdojo-celery-beat`   | `defectdojo/defectdojo-django:2.38.0`  | —                 | Periodic task scheduler                |
| `defectdojo-celery-worker` | `defectdojo/defectdojo-django:2.38.0`  | —                 | Async task worker                      |
| `infisical`                | `infisical/infisical:v0.93.1`          | `8082`            | Zero-trust secrets store               |
| `trivy-server`             | `aquasec/trivy:latest`                 | `4954` (internal) | Shared Trivy CVE cache server          |
| `falco`                    | `falcosecurity/falco-no-driver:0.39.2` | —                 | Runtime container security monitoring  |

> **Note:** All images are pinned except `trivy-server` (intentional `:latest` for current CVE database — allow-listed in `policy/no-latest-tag.rego`).

---

## Quick Start

```bash
git clone https://github.com/paruff/uFawkesSec
cd uFawkesSec
make up          # starts all services (requires uFawkesRes running)
# Full detail: see docs/quickstart.md
```

See [docs/quickstart.md](docs/quickstart.md) for prerequisites, environment setup, migration, and smoke test checklist.

---

## Integration: uFawkesPipe → uFawkesSec

uFawkesPipe consumes uFawkesSec services via the shared `fawkes-net` network:

| Connection        | Purpose                                                  | Endpoint                                                                                                 |
| ----------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| **DefectDojo**    | POST Gitleaks/Trivy findings from pipeline steps         | `http://defectdojo:8080/api/v2/`                                                                         |
| **Trivy Server**  | Shared CVE database cache for `trivy image` scans        | `http://trivy-server:4954`                                                                               |
| **Policy Bundle** | Rego policies fetched at pipeline time (v0.2: Git clone) | `git clone https://github.com/paruff/uFawkesSec /tmp/sec` then `conftest test --policy /tmp/sec/policy/` |

**v0.2 Pattern (Git clone):**

```yaml
- name: policy-check
  image: openpolicyagent/conftest:v0.57.0
  commands:
    - apk add --no-cache git
    - git clone --depth 1 https://github.com/paruff/uFawkesSec /tmp/sec
    - conftest test --policy /tmp/sec/policy/ compose.yaml .pipeline.yml
```

**v0.3 Roadmap (OCI bundle):**

```yaml
- name: pull-policy-bundle
  image: openpolicyagent/conftest:v0.57.0
  commands:
    - conftest pull oci://internal-registry.example.com/uFawkesSec/policies:latest
- name: policy-check
  commands:
    - conftest test --policy /tmp/policies compose.yaml .pipeline.yml
```

---

## Security Domains

| Domain                      | v0.2 Status                                                                                         | v0.3 Roadmap                                                          |
| --------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **Supply Chain Integrity**  | SBOM generation via Trivy + Cosign image signing in Woodpecker pipeline; keys in Woodpecker secrets | SLSA attestation, Rekor transparency log, Kyverno policy enforcement  |
| **Policy as Code**          | Conftest + Rego policies in Woodpecker pipeline against `compose.yaml` and `.pipeline.yml`          | OPA server deployment, admission webhooks, runtime policy enforcement |
| **Secret Lifecycle**        | Infisical deployed as service; Woodpecker fetches scoped tokens at build time                       | Infisical agent sidecar injection at runtime, Vault migration         |
| **Vulnerability Telemetry** | DefectDojo aggregates findings; Gitleaks + Trivy POST to it from uFawkesPipe                        | DefectDojo product policies, threshold-based pipeline gates           |
| **Runtime Shielding**       | Falco monitors Docker socket; webhook alerts to configurable endpoint                               | Falco rules authoring, PagerDuty/Slack integration                    |

---

## Documentation

| File                   | Purpose                                           |
| ---------------------- | ------------------------------------------------- |
| `docs/quickstart.md`   | Startup sequence, prerequisites, troubleshooting  |
| `docs/policy-guide.md` | How to author, test, and maintain Rego policies   |
| `design.md`            | Technical design, architecture, component details |
| `specification.md`     | Requirements, acceptance criteria, open questions |

---

## Commands

```bash
make network      # Create fawkes-net (idempotent)
make up           # Start stack (requires uFawkesRes)
make down         # Stop stack
make migrate      # Run DefectDojo DB migration + create superuser
make cosign-keygen # Generate Cosign key pair
make logs-defectdojo # Tail DefectDojo logs
make logs-falco   # Tail Falco security events
make test         # Run unit tests
make validate     # Run pre-commit hooks (lint, format, security)
```

---

## Requirements

- **Docker Engine** 24.0+ with Compose v2.4+
- **uFawkesRes** running (provides `postgres:5432`, `valkey:6379` on `fawkes-net`)
- **Host kernel** 4.14+ (Linux) for Falco eBPF; macOS Docker Desktop works but captures no syscall events

---

## License

MIT — see [LICENSE](LICENSE) for details.
