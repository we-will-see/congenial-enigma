import os
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_compose_packages_api_database_health_and_persistent_documents() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert set(compose["services"]) == {"api", "postgres"}
    assert compose["services"]["api"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert "document_data:/app/data/documents" in compose["services"]["api"]["volumes"]
    assert compose["services"]["api"]["ports"] == ["${BIND_ADDRESS:-127.0.0.1}:${APP_PORT:-8000}:8000"]
    assert set(compose["volumes"]) == {"document_data", "postgres_data"}


def test_container_includes_ocr_and_runs_as_non_root() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "tesseract-ocr-eng" in dockerfile
    assert "USER enigma" in dockerfile
    assert 'ENTRYPOINT ["/usr/local/bin/enigma-entrypoint"]' in dockerfile


def test_vps_helpers_are_executable_and_safe_by_default() -> None:
    for name in ["entrypoint.sh", "vps-up.sh", "vps-down.sh"]:
        assert os.access(ROOT / "deploy" / name, os.X_OK)
    env_template = (ROOT / ".env.vps.example").read_text(encoding="utf-8")
    assert "BIND_ADDRESS=127.0.0.1" in env_template
    assert "POSTGRES_PASSWORD=CHANGE_ME" in env_template
