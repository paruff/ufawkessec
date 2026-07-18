# TOKEN COST: This file loads on every Copilot/Claude Code/Cursor/opencode request.
# Every line is billed on every interaction. Keep it lean.
# Full details live in .agents/ — load on demand only.

# AGENTS — ufawkessec

## AI Policy
- AI writes; humans decide.
- Human review before merge.
- No secrets/PII.
- Follow repo docs/tests.
- Ask before risky changes.

## §1 Identity
- ufawkessec: uFawkes platform security scanning, policy enforcement, and compliance reporting.
- Owns: secret detection (Gitleaks), SAST (Semgrep, CodeQL), container vulnerability scanning, dependency governance, SBOM generation.
- Stack: Python 3.11, shell scripts, Docker, GitHub Actions, Trivy, Cosign.
- See `policy/` for policy-as-code definitions.

## §2 Where the Agents Live

```
  ┌─────────────┐     ┌──────────────┐     ┌────────────┐
  │   PIPE      │ ──► │     OBS      │ ──► │   GitOps   │
  │ (ufawkes    │     │ (ufawkesobs) │     │ (ufawkes-  │
  │  pipe)      │     │              │     │  gitops)   │
  └──────┬──────┘     └──────┬───────┘     └─────┬──────┘
         │                   │                    │
         ▼                   ▼                    ▼
  ┌──────────────┐   ┌──────────────┐    ┌──────────────┐
  │  ufawkessec  │   │  Fawkes CLI  │    │   ufawkes-   │
  │  (security)  │   │  (tooling)   │    │   config     │
  └──────────────┘   └──────────────┘    └──────────────┘
```

## §3 Context Files

| File | Why |
|---|---|
| `policy/` | policy-as-code definitions |
| `config/` | scanner configurations |
| `docs/policy-guide.md` | policy UX guidance |
| `docs/PR_STANDARD.md` | PR naming rules |
| `scripts/` | automation entrypoints |
| `Makefile` | dev commands |
| `.gitleaks.toml` | secret detection config |
| `compose.yaml` | local integration testing |

## §4 Architecture Rules
1. Policy definitions live in `policy/` — one file per scanner.
2. Scanner configs live in `config/` — separate from policy.
3. All secrets scanning uses `.gitleaks.toml` at repo root.
4. Every scanner must expose a CLI entrypoint in `scripts/`.
5. Policy changes require CI validation before merge.
6. Scanner output → SARIF format for GitHub integration.

## §5 PM-Agent Contract

### May Do
- Write/update scanner configs in `config/`.
- Update policy-as-code in `policy/`.
- Add/modify CI workflow steps.
- Update documentation in `docs/`.
- Bump dependencies in `requirements-test.txt` or pinned versions.
- Refactor scripts/ for clarity without changing behavior.

### Must Ask
- Changing scanner engines (e.g. Semgrep → another SAST tool).
- Adding new external dependencies or API integrations.
- Modifying `.gitleaks.toml` rules.
- Changing CI/CD pipeline structure beyond step additions.
- Any change to `Makefile` targets or compose files.
- Removing or renaming existing policy files.

### Must Never
- Commit secrets, tokens, or credentials.
- Disable or bypass security scanners.
- Lower default severity thresholds without documented exception.
- Upload SARIF results with sensitive data.
- Commit to `main` directly — always use branches + PR.
- Override CI failure without human review.
- Use uppercase in PR title first word after `type(scope):` (see docs/PR_STANDARD.md).

## §6 TDD Commit Order
1. Write/update test → commit with failing test
2. Implement feature/fix → commit with passing test
3. Refactor → commit
4. Update docs → commit

Exception: policy/config changes that are inherently untestable (e.g. tool config format) may skip step 1.

## §7 AI-Assisted Review Block
Every PR MUST include at least one commit authored by a human (not AI-generated). This is verified by checking author identity in the PR commits. Rationale: human accountability for security-critical changes.

AI-generated code and policy MUST be explicitly flagged in PR description with an `**AI-generated**` section listing what was AI-written and what was human-written.

## §8 GitOps / Trunk-Based Delivery Contract

### Branch & PR Discipline
- All work on feature branches off `main` (trunk-based, short-lived).
- Branch naming: `feat/<slug>`, `fix/<slug>`, `chore/<slug>`, `docs/<slug>`.
- Never commit directly to `main`.
- Every branch opens a PR through CI gates before merge.

### Deployment Lifecycle Gates
- `main-ci-guard.yml` verifies `ci-pipeline.yml` passes on `main` before allowing PR merge.
- Every workflow step logs `job-start` / `job-finish` timestamps for observability.
- Every merge to `main` is a deploy candidate.
- Broken `main` blocks all PRs — fix main CI before merging anything else.

### Observability Timestamps
Every inline job step MUST begin with:
```yaml
- name: job-start
  run: echo "job-start:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

And end with:
```yaml
- name: job-finish
  if: always()
  run: echo "job-finish:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

## §9 Known Limitations
- No SBOM generation in CI (planned for phase 2).
- Container scanning only runs on released images, not PR builds.
- No IaC scanning for Terraform/Kustomize (policy gap).
- No runtime security monitoring (beyond scan-on-release).
- SARIF upload is best-effort; GitHub Advanced Security license required for full UI.

## §10 Suite Integration

```
ufawkespipe      → CI/CD pipeline orchestrator
ufawkesobs       → observability + deployment
ufawkes-         → GitOps manifest repository
  gitops
fawkescli        → developer CLI tooling
ufawkesconfig    → shared configuration
```

- ufawkessec provides security scanning that reports into all PIPE workflows.
- Policy changes flow: ufawkessec → PIPE → OBS → GitOps overlay.
- Integration tests require `compose.yaml` from this repo plus ufawkespipe runners.
