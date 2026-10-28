from __future__ import annotations

import argparse
import json
import logging
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)
RUNTIME = Path("D:/yige-personal-kb/.runtime/health")
ADB = Path("D:/yige-personal-kb/.runtime/android-tools/extracted/platform-tools/adb.exe")
POWERSHELL = Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
WSL = Path("C:/Windows/System32/wsl.exe")
SCHTASKS = Path("C:/Windows/System32/schtasks.exe")
PHONE_LOG = Path("D:/yige-personal-kb/.runtime/phone-agent/phone-agent.log")
AUTONOMY_HEARTBEAT = Path("D:/yige-personal-kb/.runtime/autonomy/last_run.json")
PROACTIVE_HEARTBEAT = Path("D:/yige-personal-kb/.runtime/proactive/last_run.json")
TASKS = (
    "XiaoJuJu-Agent-Stack",
    "XiaoJuJu-Agent-API",
    "XiaoJuJu-Memory-Worker",
    "XiaoJuJu-Phone-Agent",
    "XiaoJuJu-Autonomy",
    "XiaoJuJu-Proactive-Chat",
    "XiaoJuJu-Brain-Gateway",
)


def command(args: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return result.returncode, (result.stdout or result.stderr or "").strip()
    except Exception as exc:  # noqa: BLE001 - health checks record failures
        return 1, repr(exc)


def http_check(url: str, *, body: bool = True) -> dict[str, Any]:
    try:
        response = httpx.get(url, timeout=15)
        result = {"ok": response.status_code == 200, "status": response.status_code}
        if body:
            result["body"] = response.text[:1000]
        return result
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": repr(exc)}


def process_check() -> dict[str, Any]:
    script = (
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' "
        "-and ($_.CommandLine -match 'run_agent_api|run_memory_worker|phone_agent.py') } "
        "| Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    code, text = command([str(POWERSHELL), "-NoProfile", "-Command", script], timeout=20)
    return {"ok": code == 0, "output": text[-2000:]}


def postgres_check(settings) -> dict[str, Any]:
    try:
        with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
            row = conn.execute(
                "SELECT "
                "COUNT(*) FILTER (WHERE status='failed') AS failed, "
                "COUNT(*) FILTER (WHERE status='processing') AS processing "
                "FROM app_memory_candidates"
            ).fetchone()
            outbox = conn.execute(
                "SELECT COUNT(*) FROM app_outbox WHERE status IN ('queued','sending')"
            ).fetchone()[0]
            events = conn.execute(
                "SELECT COUNT(*) FROM app_events WHERE status='failed'"
            ).fetchone()[0]
        return {
            "ok": int(row[0] or 0) == 0 and int(row[1] or 0) < 20,
            "memory_failed": int(row[0] or 0),
            "memory_processing": int(row[1] or 0),
            "outbox_pending": int(outbox or 0),
            "events_failed": int(events or 0),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": repr(exc)}


def neo4j_check(settings) -> dict[str, Any]:
    password = settings.neo4j_password.get_secret_value() if settings.neo4j_password else ""
    try:
        driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, password))
        try:
            with driver.session() as session:
                count = session.run("MATCH (e:Episodic) RETURN count(e) AS n").single()["n"]
            return {"ok": True, "episodes": int(count)}
        finally:
            driver.close()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": repr(exc)}


def docker_check() -> dict[str, Any]:
    code, text = command(
        [str(WSL), "-d", "UbuntuAgent", "-u", "root", "--", "bash", "-lc", "docker ps --format '{{.Names}} {{.Status}}'"],
        timeout=30,
    )
    names = {"xiaojuju-agent-postgres-1", "xiaojuju-agent-neo4j-1", "xiaojuju-agent-valkey-1", "xiaojuju-agent-opa-1"}
    healthy = all(name in text and "healthy" in text for name in names)
    return {
        "ok": bool(healthy) if code == 0 else True,
        "critical": False,
        "skipped": code != 0,
        "output": text[-2000:] if code == 0 else "",
        "reason": "wsl child process unavailable; service ports are checked independently"
        if code != 0
        else "",
    }


def phone_check() -> dict[str, Any]:
    code, text = command([str(ADB), "devices"], timeout=20)
    connected = code == 0 and any(line.strip().endswith("device") for line in text.splitlines()[1:])
    log_age = None
    if PHONE_LOG.exists():
        log_age = round(time.time() - PHONE_LOG.stat().st_mtime, 1)
    return {"ok": connected and log_age is not None and log_age < 900, "adb": text[-1000:], "log_age_seconds": log_age}


def heartbeat_check(path: Path, max_age_seconds: int) -> dict[str, Any]:
    if not path.is_file():
        return {"ok": False, "path": str(path), "reason": "missing"}
    age = round(time.time() - path.stat().st_mtime, 1)
    return {"ok": age <= max_age_seconds, "path": str(path), "age_seconds": age, "max_age_seconds": max_age_seconds}


def repair(tasks: list[str]) -> None:
    cooldown = RUNTIME / "last_repair.txt"
    now = time.time()
    if cooldown.exists():
        try:
            if now - float(cooldown.read_text(encoding="utf-8")) < 60:
                return
        except ValueError:
            pass
    RUNTIME.mkdir(parents=True, exist_ok=True)
    cooldown.write_text(str(now), encoding="utf-8")
    for task in tasks:
        command([str(SCHTASKS), "/Run", "/TN", task], timeout=20)


def notify(settings, checks: dict[str, Any]) -> None:
    failures = [name for name, value in checks.items() if not value.get("ok")]
    if not failures:
        return
    message_id = "health:" + datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    text = "小居居健康告警：" + ", ".join(failures) + "。详细状态见 runtime/health/latest.json。"
    try:
        with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
            conn.execute(
                "INSERT INTO app_outbox(message_id, contact_id, text, kind, status) "
                "VALUES (%s, 'owner', %s, 'health_alert', 'queued') ON CONFLICT DO NOTHING",
                (message_id, text),
            )
    except Exception as exc:  # noqa: BLE001 - alert delivery is best effort
        logger.warning("health alert could not be queued: %s", exc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--notify", action="store_true")
    args = parser.parse_args()
    from xiaojuju_agent.settings import Settings

    settings = Settings.from_env()
    checks = {
        "api": http_check("http://127.0.0.1:12402/readyz"),
        "processes": process_check(),
        "postgres": postgres_check(settings),
        "neo4j": neo4j_check(settings),
        "docker": docker_check(),
        "phone": phone_check(),
        "autonomy": heartbeat_check(AUTONOMY_HEARTBEAT, 1800),
        "proactive": heartbeat_check(PROACTIVE_HEARTBEAT, 7200),
    }
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": all(value.get("ok") for value in checks.values()),
        "checks": checks,
    }
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (RUNTIME / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False) + "\n")
    if not report["ok"] and args.repair:
        repair(list(TASKS))
    if not report["ok"] and args.notify:
        notify(settings, checks)
    print(json.dumps(report, ensure_ascii=True))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()