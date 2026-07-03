Files changed: Makefile (+33 lines: 8 new targets with ## help comments, .PHONY updated)
ci-diagnosis.md (auto-fixed by pre-commit end-of-file-fixer + prettier)

Tasks completed:
[PASS] 1. network target — docker network create fawkes-net || true (idempotent)
[PASS] 2. up target — depends on network, docker compose up -d, prints URLs
[PASS] 3. down target — docker compose down
[PASS] 4. migrate target — exec defectdojo migrate + createsuperuser, documents env vars
[PASS] 5. cosign-keygen target — generate-key-pair, print instructions, rm cosign.key
[PASS] 6. logs-defectdojo target — docker compose logs -f defectdojo defectdojo-nginx
[PASS] 7. logs-falco target — docker compose logs -f falco
[PASS] 8. help output — all 8 new targets auto-documented via ## comments

Validation:
make test-unit: 59/59 PASS (no regressions)
make network: idempotent (first run: already exists → no error; second run: same)
make help: all 8 new targets documented
pre-commit run --all-files: 15/15 PASS

Blockers: None
