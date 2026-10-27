from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_HOME = Path("D:/yige-personal-kb/.runtime/social-auto-upload")
RECEIPT_ROOT = Path("D:/yige-personal-kb/.runtime/social-publish")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("platform", choices=["xiaohongshu", "douyin", "tencent"])
    parser.add_argument("--account", default="xiaojuju")
    parser.add_argument("--home", type=Path, default=DEFAULT_HOME)
    parser.add_argument("--wait-seconds", type=float, default=30.0)
    args = parser.parse_args()
    home = args.home.resolve()
    python = home / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        raise SystemExit(f"social-auto-upload Python is missing: {python}")
    log_dir = RECEIPT_ROOT / "login"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{args.platform}-{args.account}.stdout.log"
    stderr_path = log_dir / f"{args.platform}-{args.account}.stderr.log"
    temp_dir = RECEIPT_ROOT / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"TMP": str(temp_dir), "TEMP": str(temp_dir), "PYTHONIOENCODING": "utf-8"})
    stdout = stdout_path.open("w", encoding="utf-8")
    stderr = stderr_path.open("w", encoding="utf-8")
    started_at = time.time()
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(
        [
            str(python),
            "-m",
            "sau_cli",
            args.platform,
            "login",
            "--account",
            args.account,
            "--headless",
        ],
        cwd=str(home),
        env=env,
        stdout=stdout,
        stderr=stderr,
        creationflags=flags,
    )
    stdout.close()
    stderr.close()
    cookies = home / "cookies"
    qr_path = None
    deadline = time.monotonic() + max(1.0, args.wait_seconds)
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        matches = sorted(
            (
                path
                for path in cookies.glob(f"*{args.account}*qrcode*.png")
                if path.stat().st_mtime >= started_at - 1
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if matches:
            qr_path = str(matches[0])
            break
        time.sleep(0.5)
    result = {
        "platform": args.platform,
        "account": args.account,
        "process_id": process.pid,
        "running": process.poll() is None,
        "qr_path": qr_path,
        "cookie_file": str(cookies / f"{args.platform}_{args.account}.json"),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()