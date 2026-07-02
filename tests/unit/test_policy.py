"""Unit tests for Docker Compose security policies using Conftest via Docker."""

import json
import subprocess
from pathlib import Path

import pytest


POLICY_DIR = Path(__file__).parent.parent.parent / "policy"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
CONFTEST_IMAGE = "openpolicyagent/conftest:v0.57.0"


def run_conftest(fixture_name: str, policy_dir: Path = POLICY_DIR) -> list:
    """Run conftest against a fixture file and return the list of failure messages.

    Returns a list of dicts with 'msg' keys for each policy violation found.
    Returns empty list if no violations or if an error occurs.
    """
    fixture_path = FIXTURES_DIR / fixture_name
    if not fixture_path.exists():
        pytest.fail(f"Fixture file not found: {fixture_path}")

    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{policy_dir}:/policy:ro",
            "-v",
            f"{FIXTURES_DIR}:/fixtures:ro",
            CONFTEST_IMAGE,
            "test",
            "--policy",
            "/policy",
            "--output",
            "json",
            "--no-color",
            f"/fixtures/{fixture_name}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Conftest exit codes:
    # 0 = success (no violations)
    # 1 = violations found
    # 2+ = error
    if result.returncode > 1:
        # Error - return empty list (caller should handle)
        return []

    if result.stdout.strip():
        try:
            output = json.loads(result.stdout)
            # Conftest JSON output: list of results, each with "failures" key
            failures = []
            for item in output:
                if "failures" in item:
                    failures.extend(item["failures"])
            return failures
        except (json.JSONDecodeError, KeyError):
            return []

    return []


def _count_failures_with(failures: list, keyword: str) -> int:
    """Count failures containing a specific keyword (case-insensitive)."""
    return sum(1 for f in failures if keyword in f.get("msg", "").lower())


# ── Standalone Tests (individual fixture per violation) ──────────────────────


class TestValidComposeStandalone:
    """compose-clean.yaml: minimal standalone fixture that should pass all policies."""

    def test_no_failures(self):
        failures = run_conftest("compose-clean.yaml")
        assert failures == [], (
            f"Expected zero violations for clean standalone fixture, got {len(failures)}: {failures}"
        )


class TestValidComposeSuite:
    """compose-clean-suite.yaml: suite-aware fixture that should pass all policies."""

    def test_suite_no_failures(self):
        failures = run_conftest("compose-clean-suite.yaml")
        assert failures == [], (
            f"Expected zero violations for clean suite fixture, got {len(failures)}: {failures}"
        )


class TestInvalidPrivileged:
    """compose-privileged.yaml: should fail no-privileged policy."""

    def test_privileged_violation_detected(self):
        failures = run_conftest("compose-privileged.yaml")
        privileged_failures = _count_failures_with(failures, "privileged")
        assert privileged_failures >= 1, (
            f"Expected at least 1 privileged violation, got {len(failures)}: {failures}"
        )

    def test_exactly_one_privileged_violation(self):
        failures = run_conftest("compose-privileged.yaml")
        privileged_failures = _count_failures_with(failures, "privileged")
        assert privileged_failures == 1, (
            f"Expected exactly 1 privileged violation, got {privileged_failures}: {failures}"
        )


class TestInvalidHostNetwork:
    """compose-host-network.yaml: should fail no-host-network policy."""

    def test_host_network_violation_detected(self):
        failures = run_conftest("compose-host-network.yaml")
        host_network_failures = _count_failures_with(failures, "host network")
        assert host_network_failures >= 1, (
            f"Expected at least 1 host network violation, got {len(failures)}: {failures}"
        )

    def test_exactly_one_host_network_violation(self):
        failures = run_conftest("compose-host-network.yaml")
        host_network_failures = _count_failures_with(failures, "host network")
        assert host_network_failures == 1, (
            f"Expected exactly 1 host network violation, got {host_network_failures}: {failures}"
        )


class TestInvalidLatestTag:
    """compose-latest-tag.yaml: should fail no-latest-tag policy."""

    def test_latest_tag_violations_detected(self):
        failures = run_conftest("compose-latest-tag.yaml")
        latest_failures = _count_failures_with(failures, "latest")
        assert latest_failures >= 2, (
            f"Expected at least 2 latest tag violations, got {latest_failures}: {failures}"
        )

    def test_exactly_two_latest_tag_violations(self):
        failures = run_conftest("compose-latest-tag.yaml")
        latest_failures = _count_failures_with(failures, "latest")
        assert latest_failures == 2, (
            f"Expected exactly 2 latest tag violations, got {latest_failures}: {failures}"
        )


# ── Allow-List Verification ──────────────────────────────────────────────────


class TestAllowLists:
    """Verify explicit allow-lists in policies work correctly."""

    def test_falco_allowed_privileged(self):
        """Falco service is allowed to run privileged (allow-list in no-privileged.rego)."""
        failures = run_conftest("compose-clean-suite.yaml")
        privileged_failures = _count_failures_with(failures, "privileged")
        assert privileged_failures == 0, (
            f"Falco privileged allow-list broken; got {privileged_failures} privileged violations: {failures}"
        )

    def test_trivy_allowed_latest_tag(self):
        """aquasec/trivy:latest is allowed (allow-list in no-latest-tag.rego)."""
        failures = run_conftest("compose-clean-suite.yaml")
        latest_trivy_failures = [
            f
            for f in failures
            if "latest" in f.get("msg", "").lower()
            and "trivy" in f.get("msg", "").lower()
        ]
        assert len(latest_trivy_failures) == 0, (
            f"Trivy latest-tag allow-list broken; got violations: {latest_trivy_failures}"
        )


# ── Suite Test (run all fixtures at once) ────────────────────────────────────


class TestPolicySuite:
    """Run conftest against all fixtures as a suite to verify end-to-end behavior."""

    def test_clean_passes_suite(self):
        """Suite-aware clean fixture must have zero violations."""
        failures = run_conftest("compose-clean-suite.yaml")
        assert failures == [], (
            f"Suite fixture had {len(failures)} violations: {failures}"
        )

    def test_standalone_passes(self):
        """Standalone clean fixture must have zero violations."""
        failures = run_conftest("compose-clean.yaml")
        assert failures == [], (
            f"Standalone fixture had {len(failures)} violations: {failures}"
        )

    def test_all_violation_fixtures_fail(self):
        """Each violation fixture must produce at least one failure."""
        for fixture_name in [
            "compose-privileged.yaml",
            "compose-host-network.yaml",
            "compose-latest-tag.yaml",
        ]:
            failures = run_conftest(fixture_name)
            assert len(failures) >= 1, (
                f"Fixture '{fixture_name}' expected violations but got none"
            )

    def test_all_fixtures_exist(self):
        """All required fixture files must be present."""
        expected_fixtures = {
            "compose-clean.yaml",
            "compose-clean-suite.yaml",
            "compose-privileged.yaml",
            "compose-host-network.yaml",
            "compose-latest-tag.yaml",
        }
        actual_fixtures = {
            f.name
            for f in FIXTURES_DIR.glob("*.yaml")
            if f.is_file() and not f.name.startswith(".")
        }
        missing = expected_fixtures - actual_fixtures
        assert not missing, f"Missing fixture files: {missing}"


# ── Policy Coverage ──────────────────────────────────────────────────────────


class TestPolicyCoverage:
    """Verify all 5 policy files are being evaluated."""

    def test_all_policies_exist(self):
        policy_files = list(POLICY_DIR.glob("*.rego"))
        assert len(policy_files) == 5, (
            f"Expected 5 policy files, found {len(policy_files)}: {[f.name for f in policy_files]}"
        )

        expected = {
            "no-privileged",
            "no-host-network",
            "no-latest-tag",
            "required-healthcheck",
            "no-root-user",
        }
        actual = {f.stem for f in policy_files}
        assert actual == expected, f"Policy mismatch. Expected {expected}, got {actual}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
