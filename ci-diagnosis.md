Failure: markdownlint (MD001: heading-increment)
Location: docs/policy-guide.md
Evidence: Found 16 instances of `####` headings under `##` sections:

- Line 104: Example Fixture: `compose-clean.yaml`
- Line 114: Running Policy Tests
- Line 127: Test Output Interpretation
- Line 137: Pattern: Allow-List Approach
- Line 141: Example: Adding "infisical" to no-privileged Policy
- Line 170: Common Allow-Lists in Current Policies
- Line 177: Best Practices for Allow-Lists
- Line 292: Overview
- Line 296: Current Pattern (v0.2) - Option A
- Line 319: New Pattern (v0.3) - Option B
- Line 346: Migration Path
- Line 377: When to Upgrade
- Line 404: Common Issues and Solutions

Likely Cause: This is a policy rule (MD001) that requires heading levels to increment by one level only. All `####` headings under `##` sections were incorrectly used instead of `###`.

Confidence: HIGH

Proposed Fix: Replace all 16 instances of `####` with `###` in docs/policy-guide.md
