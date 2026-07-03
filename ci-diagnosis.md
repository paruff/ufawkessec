Failure: Build & Validate (CI Pipeline stage 3)
Location: .github/workflows/ci-pipeline.yml line 61: fail-on-latest: true
This triggers reusable-build.yml@v1.1.0's grep step, which finds
aquasec/trivy:latest and fails unconditionally.
Evidence: grep -R "image: .*:latest" -n compose.yaml → 118: image: aquasec/trivy:latest
::error::Do not use :latest tags in compose.yaml
Process completed with exit code 1.
Cascading: Tests SKIPPED, Pipeline Complete FAILED.
Likely Cause: The design.md §3.2 explicitly specifies aquasec/trivy:latest for trivy-server
(needs current CVE database). The Rego policy no-latest-tag.rego has an allow-list
for this image. But the CI build step's fail-on-latest is a blunt grep with no
exception mechanism — it conflicts with the design and the Rego policy.
Confidence: HIGH
Proposed Fix: Set fail-on-latest: false in ci-pipeline.yml (line 61).
The Rego policy no-latest-tag.rego already enforces the no-latest-tag rule
with proper allow-listing. The grep is a redundant, conflicting duplicate
that should be disabled for this project.
