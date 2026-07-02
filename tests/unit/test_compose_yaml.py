"""Unit tests for compose.yaml and compose-standalone.yaml structure.

Parses each YAML file with pyyaml and validates:
  - All 7 expected service names present
  - fawkes-net declared as external network
  - defectdojo and infisical have healthcheck blocks
  - falco is the only service with privileged: true
  - No image tag is :latest except trivy-server
  - All secrets referenced in services are declared in top-level secrets
"""

from pathlib import Path

import pytest
import yaml

CORE_SERVICES = {
    "defectdojo",
    "defectdojo-nginx",
    "defectdojo-celery-beat",
    "defectdojo-celery-worker",
    "infisical",
    "trivy-server",
    "falco",
}

STANDALONE_EXTRA = {"postgres", "valkey"}

COMPOSE_FILES = [
    "compose.yaml",
    "compose-standalone.yaml",
]


@pytest.fixture(params=COMPOSE_FILES)
def compose_path(request, project_root):
    """Yield each compose file path, parameterized."""
    return project_root / request.param


@pytest.fixture
def compose_data(compose_path):
    """Parse compose.yaml / compose-standalone.yaml and return the dict."""
    assert compose_path.exists(), f"Missing compose file: {compose_path}"
    with open(compose_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def compose_filename(compose_path):
    """Return just the filename of the compose file."""
    return compose_path.name


# ── Service Name Coverage ─────────────────────────────────────────────────


class TestServiceNames:
    """All 7 core services must be present."""

    def test_all_core_services_present(self, compose_data):
        services = set(compose_data.get("services", {}).keys())
        missing = CORE_SERVICES - services
        assert not missing, (
            f"Missing expected core services: {missing}"
        )

    def test_no_unexpected_services(self, compose_data, compose_filename):
        """compose.yaml must only contain core services (standalone adds postgres+valkey)."""
        services = set(compose_data.get("services", {}).keys())
        if compose_filename == "compose-standalone.yaml":
            expected = CORE_SERVICES | STANDALONE_EXTRA
        else:
            expected = CORE_SERVICES
        extra = services - expected
        assert not extra, (
            f"Unexpected services found: {extra}"
        )


# ── Network Assertions ────────────────────────────────────────────────────


class TestNetwork:
    """fawkes-net must be declared as external."""

    def test_fawkes_net_is_external(self, compose_data):
        networks = compose_data.get("networks", {})
        assert "fawkes-net" in networks, "fawkes-net not declared in networks"
        fawkes = networks["fawkes-net"]
        assert fawkes.get("external") is True or fawkes.get("external") is True, (
            "fawkes-net must be declared as external: true"
        )

    def test_fawkes_net_has_name(self, compose_data):
        networks = compose_data.get("networks", {})
        fawkes = networks.get("fawkes-net", {})
        assert fawkes.get("name") == "fawkes-net", (
            "fawkes-net must have explicit name: fawkes-net"
        )

    def test_all_services_on_fawkes_net(self, compose_data):
        """Every service must be on the fawkes-net network."""
        services = compose_data.get("services", {})
        for svc_name, svc_config in services.items():
            svc_networks = svc_config.get("networks", [])
            if isinstance(svc_networks, list):
                assert "fawkes-net" in svc_networks, (
                    f"Service '{svc_name}' is not on fawkes-net"
                )
            elif isinstance(svc_networks, dict):
                assert "fawkes-net" in svc_networks, (
                    f"Service '{svc_name}' is not on fawkes-net"
                )


# ── Healthcheck Assertions ────────────────────────────────────────────────


class TestHealthchecks:
    """defectdojo and infisical must have healthcheck blocks."""

    def test_defectdojo_has_healthcheck(self, compose_data):
        svc = compose_data["services"].get("defectdojo", {})
        assert "healthcheck" in svc, "defectdojo is missing a healthcheck block"
        hc = svc["healthcheck"]
        assert "test" in hc, "defectdojo healthcheck has no test command"
        assert "interval" in hc, "defectdojo healthcheck has no interval"
        assert "retries" in hc, "defectdojo healthcheck has no retries"

    def test_infisical_has_healthcheck(self, compose_data):
        svc = compose_data["services"].get("infisical", {})
        assert "healthcheck" in svc, "infisical is missing a healthcheck block"
        hc = svc["healthcheck"]
        assert "test" in hc, "infisical healthcheck has no test command"
        assert "interval" in hc, "infisical healthcheck has no interval"
        assert "retries" in hc, "infisical healthcheck has no retries"

    def test_trivy_server_has_healthcheck(self, compose_data):
        svc = compose_data["services"].get("trivy-server", {})
        assert "healthcheck" in svc, "trivy-server is missing a healthcheck block"

    def test_defectdojo_nginx_has_healthcheck(self, compose_data):
        svc = compose_data["services"].get("defectdojo-nginx", {})
        assert "healthcheck" in svc, "defectdojo-nginx is missing a healthcheck block"

    def test_defectdojo_celery_worker_has_healthcheck(self, compose_data):
        svc = compose_data["services"].get("defectdojo-celery-worker", {})
        assert "healthcheck" in svc, (
            "defectdojo-celery-worker is missing a healthcheck block"
        )


# ── Privileged Assertions ─────────────────────────────────────────────────


class TestPrivileged:
    """falco is the only service with privileged: true."""

    def test_falco_is_privileged(self, compose_data):
        falco = compose_data["services"].get("falco", {})
        assert falco.get("privileged") is True, "falco must have privileged: true"

    def test_no_other_service_is_privileged(self, compose_data):
        services = compose_data.get("services", {})
        privileged_services = [
            name for name, config in services.items()
            if config.get("privileged") is True
        ]
        assert privileged_services == ["falco"], (
            f"Only falco should be privileged, but got: {privileged_services}"
        )


# ── Image Tag Assertions ──────────────────────────────────────────────────


class TestImageTags:
    """No :latest tags except trivy-server."""

    def test_trivy_server_is_latest(self, compose_data):
        trivy = compose_data["services"].get("trivy-server", {})
        image = trivy.get("image", "")
        assert "latest" in image, (
            f"trivy-server image must contain ':latest', got '{image}'"
        )

    def test_no_other_latest_tags(self, compose_data):
        services = compose_data.get("services", {})
        latest_services = []
        for name, config in services.items():
            if name == "trivy-server":
                continue
            image = config.get("image", "")
            if ":latest" in image:
                latest_services.append(name)
        assert not latest_services, (
            f"Services with :latest tag (excluding trivy-server): {latest_services}"
        )


# ── Secret Assertions ─────────────────────────────────────────────────────


class TestSecrets:
    """All service secrets must be declared in top-level secrets block."""

    def test_secrets_top_level_declared(self, compose_data):
        top_secrets = set(compose_data.get("secrets", {}).keys())
        used_secrets = set()
        services = compose_data.get("services", {})
        for svc_name, svc_config in services.items():
            svc_secrets = svc_config.get("secrets", [])
            if isinstance(svc_secrets, list):
                for s in svc_secrets:
                    if isinstance(s, str):
                        used_secrets.add(s)
                    elif isinstance(s, dict):
                        # secret reference with source/key format
                        used_secrets.update(s.values())
                        used_secrets.update(s.keys())
            elif isinstance(svc_secrets, dict):
                # dict format: secret_name: {...}
                used_secrets.update(svc_secrets.keys())
        undeclared = used_secrets - top_secrets
        assert not undeclared, (
            f"Secrets used in services but not declared in top-level 'secrets:': "
            f"{undeclared}"
        )

    def test_secrets_use_environment_source(self, compose_data):
        """All secrets should use the environment: injection syntax."""
        secrets = compose_data.get("secrets", {})
        for name, config in secrets.items():
            assert "environment" in config, (
                f"Secret '{name}' should use environment: source, got: {list(config.keys())}"
            )


# ── Standalone-Specific Assertions ────────────────────────────────────────


class TestExtraServicesStandalone:
    """compose-standalone.yaml includes postgres and valkey services."""

    def test_postgres_present_in_standalone(self):
        path = Path(__file__).parent.parent.parent / "compose-standalone.yaml"
        assert path.exists(), "compose-standalone.yaml not found"
        with open(path) as f:
            data = yaml.safe_load(f)
        services = data.get("services", {})
        assert "postgres" in services, "standalone compose must include postgres"
        assert "valkey" in services, "standalone compose must include valkey"
        assert "volumes" in data, "standalone compose must have volumes"
        vol_names = set(data["volumes"].keys())
        assert "postgres-data" in vol_names, "standalone compose needs postgres-data volume"
        assert "valkey-data" in vol_names, "standalone compose needs valkey-data volume"

    def test_postgres_healthcheck_in_standalone(self):
        path = Path(__file__).parent.parent.parent / "compose-standalone.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        for svc_name in ("postgres", "valkey"):
            svc = data["services"].get(svc_name, {})
            assert "healthcheck" in svc, (
                f"{svc_name} in standalone must have healthcheck"
            )

    def test_defectdojo_depends_in_standalone(self):
        """In standalone, defectdojo depends on postgres and valkey health."""
        path = Path(__file__).parent.parent.parent / "compose-standalone.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        svc = data["services"].get("defectdojo", {})
        depends = svc.get("depends_on", {})
        assert "postgres" in depends, (
            "standalone defectdojo must depend on postgres condition"
        )
        assert "valkey" in depends, (
            "standalone defectdojo must depend on valkey condition"
        )
        assert depends.get("postgres", {}).get("condition") == "service_healthy", (
            "standalone defectdojo must wait for postgres healthy"
        )
        assert depends.get("valkey", {}).get("condition") == "service_healthy", (
            "standalone defectdojo must wait for valkey healthy"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
