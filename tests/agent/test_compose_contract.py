from pathlib import Path

import yaml


def test_compose_uses_pinned_images_and_host_data_dir():
    path = Path("deploy/compose/compose.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    images = [service["image"] for service in data["services"].values()]
    assert all(":latest" not in image for image in images)
    assert any("postgres:17.11" in image for image in images)
    assert any("valkey/valkey:9.1.2" in image for image in images)
    assert any("neo4j:5.26-community" in image for image in images)
    assert any("openpolicyagent/opa:1.21.4" in image for image in images)
    text = path.read_text(encoding="utf-8")
    assert "postgres-data:/var/lib/postgresql/data" in text
    assert "volumes:" in text
    assert text.count("restart: unless-stopped") == 4
    assert "docker.m.daocloud.io/" in text
