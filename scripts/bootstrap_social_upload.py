from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_HOME = Path("D:/yige-personal-kb/.runtime/social-auto-upload")
DEFAULT_CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
DEPENDENCIES = (
    "loguru==0.7.3",
    "requests==2.32.3",
    "qrcode==8.2",
    "segno>=1.6.6",
    "tinycss2>=1.4.0,<2",
    "patchright==1.58.2",
    "opencv-python-headless==4.13.0.92",
)


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def patch_launch_fallbacks(home: Path, chrome: Path) -> None:
    helper = '''

def _build_launch_kwargs(headless: bool) -> dict:
    if LOCAL_CHROME_PATH:
        return {"headless": headless, "executable_path": LOCAL_CHROME_PATH}
    return {"headless": headless, "channel": "chromium"}
'''
    for relative in (
        "uploader/xiaohongshu_uploader/main.py",
        "uploader/douyin_uploader/main.py",
    ):
        path = home / relative
        text = path.read_text(encoding="utf-8")
        if "def _build_launch_kwargs" not in text:
            anchor = text.find("\n", text.find("logger"))
            if anchor < 0:
                raise RuntimeError(f"cannot find logger in {relative}")
            text = text[: anchor + 1] + helper + text[anchor + 1 :]
        text = text.replace(
            'playwright.chromium.launch(headless=self.headless, channel="chromium"',
            "playwright.chromium.launch(**_build_launch_kwargs(self.headless)",
        )
        text = text.replace(
            'playwright.chromium.launch(headless=headless, channel="chromium"',
            "playwright.chromium.launch(**_build_launch_kwargs(headless)",
        )
        text = text.replace(
            'playwright.chromium.launch(headless=True, channel="chromium"',
            "playwright.chromium.launch(**_build_launch_kwargs(True)",
        )
        path.write_text(text, encoding="utf-8")

    conf = home / "conf.py"
    conf_text = conf.read_text(encoding="utf-8")
    conf_text = re.sub(
        r'LOCAL_CHROME_PATH = ""',
        f'LOCAL_CHROME_PATH = r"{chrome.as_posix()}"',
        conf_text,
        count=1,
    )
    conf.write_text(conf_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, default=DEFAULT_HOME)
    parser.add_argument("--index-url", default="https://pypi.tuna.tsinghua.edu.cn/simple")
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()
    home = args.home.resolve()
    home.parent.mkdir(parents=True, exist_ok=True)
    if not home.exists():
        run(["git", "clone", "--depth", "1", "https://github.com/dreammis/social-auto-upload.git", str(home)])
    if not args.skip_install:
        run(["uv", "venv", str(home / ".venv")])
        python = home / ".venv" / "Scripts" / "python.exe"
        run(["uv", "pip", "install", "--python", str(python), "--no-deps", "-e", "."], cwd=home)
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--index-url",
                args.index_url,
                *DEPENDENCIES,
            ],
            cwd=home,
        )
    conf = home / "conf.py"
    if not conf.exists():
        shutil.copyfile(home / "conf.example.py", conf)
    patch_launch_fallbacks(home, DEFAULT_CHROME)
    print(f"social-auto-upload ready at {home}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc