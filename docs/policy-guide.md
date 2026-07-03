# uFawkesSec Policy Guide — v0.2

This guide explains how to author, test, and maintain Rego policies for validating Docker Compose specifications in uFawkesSec.

---

## 1. The `deny[msg]` Pattern

The core pattern in uFawkesSec policies follows a simple rule: **`deny contains msg if { ... }`**

- When the condition evaluates to `true`, the rule is "violated"
- `msg` contains the human-readable error message explaining the violation
- Multiple `deny` rules can exist within a single policy file

### Worked Example: `no-privileged.rego`

```rego
package main
import rego.v1

# DENY: Services must not run in privileged mode
# Allow-list exception: falco is permitted to run privileged

deny contains msg if {
 some service in object.keys(input.services)
 input.services[service].privileged == true
 service != "falco"
 msg := sprintf("Service '%s' must not run in privileged mode", [service])
}
```

**Breaking down the example:**

1. `package main` — Declares this is a policy for uFawkesSec
2. `import rego.v1` — Import Rego language features
3. `deny contains msg if {` — Rule definition starts here
4. `some service in object.keys(input.services)` — Iterate over all services in the Compose YAML
5. `input.services[service].privileged == true` — Check if the service has privileged mode enabled
6. `service != "falco"` — Exception: skip violation check for the "falco" service
7. `msg := sprintf(...)` — Error message explaining the violation

**Key Pattern:**

- **Deny first, allow second** — Define violations first, then create allow-lists
- **Use `sprintf()` for messages** — Provides consistent error formatting
- **Check service membership** — `object.keys(input.services)` gives a list of service names from the YAML

---

## 2. Conftest Input Object Structure

When Conftest loads a Compose YAML file, it creates a nested object:

```yaml
# compose.yaml input structure for Conftest
input:
  services:
    service_name:
      image: "postgres:15-alpine"
      ports: ["5432:5432"]
      user: "999:999"
      privileged: true
      network_mode: "bridge"
      healthcheck:
        test: ["CMD", "pg_isready", "-U", "postgres"]
        interval: 10s
        timeout: 5s
        retries: 5
```

### Available Input Fields

| Field                                  | Type    | Example                         | Description                                |
| -------------------------------------- | ------- | ------------------------------- | ------------------------------------------ |
| `input.services[service].image`        | string  | `"postgres:15-alpine"`          | Docker image reference                     |
| `input.services[service].ports`        | array   | `["5432:5432"]`                 | Published port mappings                    |
| `input.services[service].user`         | string  | `"999:999"`                     | User:group specification (UID:GID) or name |
| `input.services[service].privileged`   | boolean | `true` or `false`               | Privileged mode flag                       |
| `input.services[service].network_mode` | string  | `"bridge"` or `"host"`          | Docker network mode                        |
| `input.services[service].healthcheck`  | object  | see healthcheck structure below | Health check configuration                 |

### Healthcheck Structure

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

---

## 3. Testing Policies Locally

### Basic Testing Command

Run Conftest against a fixture YAML file:

```bash
conftest test --policy policy/ tests/fixtures/compose-clean.yaml
```

### Example Fixture: `compose-clean.yaml`

The uFawkesSec policy test suite includes 5 fixture files:

1. **`compose-clean.yaml`** — Compliant with all policies
2. **`compose-privileged.yaml`** — Violates no-privileged policy (has a privileged service named "custom-privileged")
3. **`compose-host-network.yaml`** — Violates no-host-network policy
4. **`compose-latest-tag.yaml`** — Violates no-latest-tag policy (has multiple :latest images)
5. **`compose-clean-suite.yaml`** — Suite containing all compliant services

### Running Policy Tests

```bash
# Run all policy tests in unit test suite
pytest tests/unit/test_policy.py -v

# Or run specific test class
pytest tests/unit/test_policy.py::TestValidComposeStandalone

# Run conftest directly for debugging
conftest test --policy policy/ tests/fixtures/compose-clean.yaml
```

### Test Output Interpretation

- **Exit Code 0** — All policies passed (success)
- **Exit Code 1** — One or more policies violated (expected for negative test fixtures)
- **Exit Code 2+** — Error in policy files or fixtures

---

## 4. Adding Exceptions to Policies

### Pattern: Allow-List Approach

Instead of denying all violations, uFawkesSec policies use an allow-list approach for specific exceptions.

### Example: Adding "infisical" to no-privileged Policy

Original policy:

```rego
package main

deny contains msg if {
  some service in object.keys(input.services)
  input.services[service].privileged == true
  service != "falco"  # Only falco is allowed
  msg := sprintf("Service '%s' must not run in privileged mode", [service])
}
```

Enhanced policy with additional exception:

```rego
package main

deny contains msg if {
  some service in object.keys(input.services)
  input.services[service].privileged == true
  service != "falco"     # Falco is always allowed
  service != "infisical" # Infisical is also allowed (e.g., for database containers)
  msg := sprintf("Service '%s' must not run in privileged mode", [service])
}
```

### Common Allow-Lists in Current Policies

| Policy               | Allowed Items            | Rationale                                             |
| -------------------- | ------------------------ | ----------------------------------------------------- |
| `no-privileged.rego` | `"falco"`                | Required for eBPF security monitoring                 |
| `no-latest-tag.rego` | `"aquasec/trivy:latest"` | Trivy needs the latest image for current CVE database |

### Best Practices for Allow-Lists

1. **Document exceptions** — Add comments explaining why exceptions exist
2. **Keep the list minimal** — Allow only what's absolutely required
3. **Review periodically** — Re-evaluate exceptions when requirements change

---

## 5. Reference: All 5 Current Policies

Below are the descriptions, enforcement details, and exceptions for each policy:

### `policy/no-privileged.rego`

**Purpose:** Ensures services don't run in privileged mode unless explicitly allowed.

**Enforcement:**

- Denies any service with `privileged: true`
- Service must not be in the allow-list

**Allow-list:**

- `"falco"` — Required for eBPF probe loading

**Example Violation:** A Compose YAML with `nginx: privileged: true`

**Error Message:** `"Service 'nginx' must not run in privileged mode"`

### `policy/no-host-network.rego`

**Purpose:** Prevents containers from using the host network stack for security reasons.

**Enforcement:**

- Denies services with `network_mode: "host"`

**Allow-list:** None

**Example Violation:** A Compose YAML with `database: network_mode: "host"`

**Error Message:** `"Service 'database' must not use host network mode"`

### `policy/no-latest-tag.rego`

**Purpose:** Ensures all Docker images use explicit version tags for reproducibility.

**Enforcement:**

1. Denies services with `:latest` tags that aren't in the allow-list
2. Denies services without any tag (defaults to `:latest`)

**Allow-list:**

- `"aquasec/trivy:latest"` — Trivy needs the latest image for current CVE database

**Examples:**

- `"myapp:latest"` → Violation
- `"myapp:1.2.3"` → Allowed
- `"myapp"` → Violation (assumes `:latest`)

**Error Messages:**

- `"Service 'myapp' uses ':latest' tag in image 'myapp:latest' - use explicit version tags"`
- `"Service 'myapp' uses image 'myapp' without explicit tag (defaults to ':latest')"`

### `policy/no-root-user.rego`

**Purpose:** Prevents containers from running as root user for security.

**Enforcement:**

- Denies services running as root user (`"root"`, `"0"`, or `"0:0"`)

**Allow-list:** None

**Examples:**

- `"user: "root"` → Violation
- `"user: "0"` → Violation (UID 0)
- `"user: "0:0"` → Violation (UID 0, GID 0)
- `"user: "1000:1001"` → Allowed

**Error Messages:**

- `"Service 'app' must not run as root user"`
- `"Service 'app' must not run as root user (UID 0)"`
- `"Service 'app' must not run as root user (UID 0:GID 0)"`

### `policy/required-healthcheck.rego`

**Purpose:** Ensures services have health checks defined for operational monitoring.

**Enforcement:**

1. Denies services without any `healthcheck` block
2. Denies healthchecks missing a `test` command

**Allow-list:** None

**Examples:**

- No `healthcheck:` block → Violation
- `healthcheck:` present but no `test:` → Violation

**Error Messages:**

- `"Service 'cache' must define a healthcheck configuration"`
- `"Service 'cache' healthcheck must specify a 'test' command"`

---

## 6. Upgrading to OCI Policy Bundle (v0.3)

### Overview

uFawkesSec v0.3 introduces a new policy distribution pattern using OCI artifacts, replacing the current Git clone approach.

### Current Pattern (v0.2) - Option A

```yaml
- name: policy-check
  image: openpolicyagent/conftest:v0.57.0
  commands:
    - apk add --no-cache git
    - git clone --depth 1 https://github.com/paruff/uFawkesSec /tmp/sec
    - conftest test --policy /tmp/sec/policy/ compose.yaml .pipeline.yml
```

**Pros:**

- Simple implementation
- No artifact publishing required
- Relies on GitHub availability (~10s additional time)

**Cons:**

- External service dependency
- Potential rate limiting or downtime impacts
- Less robust for production CI/CD

### New Pattern (v0.3) - Option B

```yaml
- name: pull-policy-bundle
  image: openpolicyagent/conftest:v0.57.0
  commands:
    - conftest pull oci://internal-registry.example.com/uFawkesSec/policies:latest

- name: policy-check
  image: openpolicyagent/conftest:v0.57.0
  commands:
    - conftest test --policy /tmp/policies compose.yaml .pipeline.yml
```

**Pros:**

- Internal registry control
- Elimination of GitHub external dependencies
- More robust and reliable
- Better caching and layer reuse

**Cons:**

- Requires registry setup
- Additional pipeline complexity
- Need for proper access controls

### Migration Path

**Step 1: Build and Push OCI Bundle**

```bash
# Create policy bundle
conftest push oci://internal-registry.example.com/uFawkesSec/policies:latest policy/

# Verify bundle contents
cosign verify --type sbom oci://internal-registry.example.com/uFawkesSec/policies:latest
```

**Step 2: Update Pipeline**

Replace Git clone with OCI pull:

```yaml
- name: policy-check
  image: openpolicyagent/conftest:v0.57.0
  commands:
    - conftest pull oci://internal-registry.example.com/uFawkesSec/policies:latest
    - conftest test --policy /tmp/policies compose.yaml .pipeline.yml
```

**Step 3: Security Considerations**

- The OCI bundle contains the policy code (`policy/` directory)
- Cosign signatures can be used to verify bundle integrity
- Registry access controls ensure only authorized pipelines can retrieve policies
- Signed policies prevent tampering during CI/CD

### When to Upgrade

**Choose Option B (OCI) if:**

- Your organization has an internal registry
- You need improved reliability over simplicity
- You're concerned about external service dependencies

**Choose Option A (Git clone) if:**

- Simplicity is preferred
- You have limited infrastructure setup
- External service usage is acceptable for this use case

---

## References and Further Reading

1. **Conftest Documentation:** `https://www.openpolicyagent.org/docs/latest/conftest/`
2. **uFawkesPipe CI Pipelines:** Review for concrete implementation examples
3. **Conftest CLI Reference:** `conftest test --help` for all available options
4. **OCI Distribution Specs:** Docker Registry API and OCI Distribution Specification

---

## Troubleshooting

### Common Issues and Solutions

**Issue: "command not found: conftest"**
Solution: Verify Conftest is installed in the pipeline image:

```yaml
image: openpolicyagent/conftest:v0.57.0
```

**Issue: Policy test fails with "bundle not found"**
Solution: Check OCI registry credentials and ensure the bundle exists.

**Issue: "permission denied" when pulling from OCI registry**
Solution: Verify pipeline service account has appropriate permissions.

---

## Conclusion

This policy guide provides the foundation for writing, testing, and maintaining Rego policies in uFawkesSec. The allow-list approach allows for exceptions while maintaining security standards, and the upcoming OCI distribution pattern will provide more robust and reliable policy management.

The current v0.2 implementation is simple, effective, and well-tested. The v0.3 upgrade path provides a clear migration strategy for organizations ready to adopt more sophisticated artifact management and internal registry usage.
