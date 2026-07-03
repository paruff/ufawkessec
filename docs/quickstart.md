# uFawkesSec Quickstart — v0.2

Follow this guide to get the uFawkesSec security plane running in your local
environment.

---

## Prerequisites

### Required Software

- **Docker Engine** 24.0+ with Compose v2.4+ (`docker compose`, not
  `docker-compose`). Verify:

  ```bash
  docker compose version  # expect v2.4.0+
  ```

- **Docker network** — the `fawkes-net` network is created automatically
  by `make network` (idempotent). No manual network creation needed.

- **Host kernel** (Falco eBPF):
  - **Linux:** kernel 4.14+ required for Falco eBPF probe loading.
  - **macOS Docker Desktop:** Falco cannot attach eBPF probes because
    the Docker VM does not expose the host kernel. On macOS, Falco will
    start but capture no syscall events. For local dev, you can set
    `FALCO_BPF_PROBE=""` in the container environment to disable the
    probe (rules still load, syscall capture disabled).

### Prerequisite Services

**uFawkesRes must be running first.** The ufawkesSec compose stack
depends on PostgreSQL and Valkey from ufawkesRes:

| Service    | Dependency | Host/Port       |
| ---------- | ---------- | --------------- |
| DefectDojo | PostgreSQL | `postgres:5432` |
| DefectDojo | Valkey     | `valkey:6379`   |
| Infisical  | PostgreSQL | `postgres:5432` |
| Infisical  | Valkey     | `valkey:6379`   |

> **Tip:** Use `compose-standalone.yaml` if you want to run ufawkesSec
> without ufawkesRes. See [Standalone Mode](#standalone-mode-compose-standaloneyaml) below.

---

## Step-by-Step Startup

### 1. Set Required Environment Variables

Copy the example env files and fill in values:

```bash
cp config/defectdojo/.env.example .env
cp config/infisical/.env.example .env  # append to same .env
```

Edit `.env` and set all required variables. Generate secure random values
with:

```bash
openssl rand -hex 64   # for secret keys
openssl rand -hex 32   # for encryption keys
```

**Required variables:**

| Variable                   | Used by    | Generate with          |
| -------------------------- | ---------- | ---------------------- |
| `DEFECTDOJO_SECRET_KEY`    | DefectDojo | `openssl rand -hex 64` |
| `DEFECTDOJO_AES_KEY`       | DefectDojo | `openssl rand -hex 32` |
| `DOJO_DB_PASSWORD`         | DefectDojo | choose strong password |
| `INFISICAL_ENCRYPTION_KEY` | Infisical  | `openssl rand -hex 32` |
| `INFISICAL_AUTH_SECRET`    | Infisical  | `openssl rand -hex 64` |
| `INFISICAL_DB_PASSWORD`    | Infisical  | choose strong password |

### 2. Create the Network

```bash
make network
```

This creates the `fawkes-net` Docker network idempotently. Safe to run
multiple times — the `|| true` guard prevents errors if the network
already exists.

### 3. Start the Stack

```bash
make up
```

This runs `docker compose up -d` and prints the service URLs. You should
see:

```
DefectDojo: http://localhost:8080
Infisical:  http://localhost:8082
```

Wait 30–60 seconds for all services to become healthy. Check with:

```bash
docker compose ps
```

All services should show `healthy` in the STATUS column (except
`defectdojo-celery-beat` which has no healthcheck).

### 4. Run Database Migration (First Run Only)

DefectDojo requires an initial database migration and superuser creation:

```bash
make migrate
```

This runs:

1. `docker compose exec defectdojo python manage.py migrate`
2. `docker compose exec defectdojo python manage.py createsuperuser --noinput`

The following environment variables must be set before running `make migrate`:

| Variable                    | Purpose              |
| --------------------------- | -------------------- |
| `DJANGO_SUPERUSER_USERNAME` | Superuser login name |
| `DJANGO_SUPERUSER_PASSWORD` | Superuser password   |
| `DJANGO_SUPERUSER_EMAIL`    | Superuser email      |

Add these to your `.env` file.

### 5. Verify Services

#### DefectDojo

Open [http://localhost:8080](http://localhost:8080) in your browser.
Log in with the superuser credentials you set.

#### Infisical

Open [http://localhost:8082](http://localhost:8082) in your browser.
Infisical should show its setup/landing page.

#### Falco

Check that Falco is running and receiving events:

```bash
docker logs falco
```

On Linux (kernel 4.14+), you should see JSON-formatted security events
as they occur. On macOS, Falco will start but no syscall events will
be captured (eBPF probe cannot attach).

---

## Smoke Test Checklist

After completing the startup sequence, verify each service:

- [ ] `docker compose ps` shows all services `Up` (healthy)
- [ ] DefectDojo login page loads at `http://localhost:8080`
- [ ] DefectDojo superuser login works (credentials from `.env`)
- [ ] Infisical page loads at `http://localhost:8082`
- [ ] Falco container logs show activity: `docker logs falco` (JSON events
      on Linux; startup messages on macOS)
- [ ] Trivy server health check passes: `docker compose exec trivy-server trivy health`
- [ ] Celery worker is responding: `docker compose exec defectdojo celery -A dojo inspect ping`
- [ ] `make down` stops all containers cleanly (no orphan containers)

---

## Standalone Mode (`compose-standalone.yaml`)

If you do not have ufawkesRes running, use the standalone compose file:

```bash
docker compose -f compose-standalone.yaml up -d
```

This starts PostgreSQL and Valkey alongside the seven ufawkesSec
services. No external dependencies required.

Use `make migrate` as normal after startup. The standalone PostgreSQL
runs with the same `DOJO_DB_PASSWORD` you set in `.env`.

---

## Troubleshooting

### Falco eBPF Probe Failure

**Symptom:** `docker logs falco` shows `Unable to load the driver` or
`Error creating driver: bpf`.

**Cause:** Host kernel is below 4.14, or you are running macOS Docker
Desktop (Docker VM does not expose host kernel).

**Fix:** Set `FALCO_BPF_PROBE=""` to disable the eBPF probe. Edit the
`falco` service in `compose.yaml`:

```yaml
environment:
  - FALCO_BPF_PROBE=""
```

Restart Falco: `docker compose restart falco`. Falco rules still load
but syscall capture is disabled. Acceptable for local dev; production
always requires a Linux host with kernel 4.14+.

### DefectDojo Migration Errors

**Symptom:** `make migrate` fails with `django.db.utils.OperationalError:
could not connect to server`.

**Cause:** PostgreSQL from ufawkesRes is not running or not on
`fawkes-net`.

**Fix:**

1. Verify ufawkesRes is up: `docker compose -f <ufawkesres-path>/compose.yaml ps`
2. Verify PostgreSQL is on `fawkes-net`:
   ```bash
   docker network inspect fawkes-net | grep postgres
   ```
3. Verify `DOJO_DB_PASSWORD` in `.env` matches the ufawkesRes PostgreSQL
   password for the `dojo` role.

**Symptom:** `make migrate` fails with `relation "auth_user" already exists`.

**Cause:** Migration was already run. This is a first-run-only step.

**Fix:** Skip `make migrate`. The database is already initialized.

### fawkes-net Not Found

**Symptom:** `make up` fails with `network fawkes-net not found`.

**Cause:** The network was not created before starting containers.

**Fix:** Run `make network` to create it. The `make up` target depends
on `make network` but must be run as a single `make up` call — running
`docker compose up -d` directly without `make network` first will fail.

### Valkey Connection Issues

**Symptom:** DefectDojo logs show `Error connecting to Redis`.

**Cause:** Valkey from ufawkesRes is not running or not on `fawkes-net`.

**Fix:** Ensure ufawkesRes is running and Valkey is on `fawkes-net`:

```bash
docker network inspect fawkes-net | grep valkey
docker ps --filter name=valkey
```

---

## Next Steps

- **Add Rego policies:** See `docs/policy-guide.md` (planned for SEC-007)
  for how to author and test custom security policies.
- **Sign artifacts:** Run `make cosign-keygen` to generate a signing key
  pair. Store `cosign.key` in Woodpecker secret `cosign_private_key`.
- **Tail logs:** Use `make logs-defectdojo` or `make logs-falco` for
  real-time log monitoring.

---

## Reference

| File                             | Purpose                                       |
| -------------------------------- | --------------------------------------------- |
| `compose.yaml`                   | Suite-aware compose (requires uFawkesRes)     |
| `compose-standalone.yaml`        | Standalone compose (embedded DB and cache)    |
| `config/defectdojo/.env.example` | DefectDojo env var template                   |
| `config/infisical/.env.example`  | Infisical env var template                    |
| `Makefile`                       | `make up`, `make down`, `make network`, etc.  |
| `policy/*.rego`                  | Rego security policies for compose validation |
