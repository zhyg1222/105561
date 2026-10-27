from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOME = Path("D:/yige-personal-kb/xiaojuju/vendor/open-llm-vtuber")
PYTHON = HOME / ".venv" / "Scripts" / "python.exe"
RUNTIME = Path("D:/yige-personal-kb/.runtime/vtuber")


def ensure_config() -> None:
    path = HOME / "conf.yaml"
    text = path.read_text(encoding="utf-8")
    if "base_url: http://127.0.0.1:12402/v1" not in text:
        text = text.replace("base_url: http://127.0.0.1:12400/v1", "base_url: http://127.0.0.1:12402/v1")
        path.write_text(text, encoding="utf-8")


def main() -> int:
    ensure_config()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "TMP": "D:/yige-personal-kb/.runtime/tmp",
            "TEMP": "D:/yige-personal-kb/.runtime/tmp",
            "HF_HOME": str(HOME / "models"),
            "MODELSCOPE_CACHE": str(HOME / "models"),
        }
    )
    with (RUNTIME / "server.out.log").open("a", encoding="utf-8") as stdout, (
        RUNTIME / "server.err.log"
    ).open("a", encoding="utf-8") as stderr:
        return subprocess.call(
            [str(PYTHON), "run_server.py"],
            cwd=str(HOME),
            env=env,
            stdout=stdout,
            stderr=stderr,
        )


if __name__ == "__main__":
    sys.exit(main())