import hashlib
from dataclasses import dataclass
from pathlib import Path

IDENTITY_FILES = (
    "\u4eba\u683c\u5baa\u6cd5.md",
    "\u4eba\u683c\u6838\u5fc3.md",
    "\u5173\u7cfb\u89c4\u5219.md",
    "\u8eab\u4efd/AI\u6807\u8bc6\u89c4\u5219.md",
)


@dataclass(frozen=True)
class IdentityBundle:
    content: str
    sha256: str

    @property
    def text(self) -> str:
        return self.content

    @classmethod
    def load(cls, root: Path | str) -> "IdentityBundle":
        base = Path(root)
        chunks = []
        for relative in IDENTITY_FILES:
            path = base / relative
            if not path.is_file():
                raise RuntimeError(f"required identity file is missing: {relative}")
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                raise RuntimeError(f"required identity file is empty: {relative}")
            chunks.append(f"# {relative}\n{content}")
        optional_profile = base / "\u8eab\u4efd" / "\u7528\u6237\u753b\u50cf.md"
        if optional_profile.is_file():
            profile = optional_profile.read_text(encoding="utf-8").strip()
            if profile:
                chunks.append(f"# \u7528\u6237\u753b\u50cf\uff08\u8001\u5927\u81ea\u8ff0\uff0c\u672a\u72ec\u7acb\u9a8c\u8bc1\uff09\n{profile}")
        text = "\n\n".join(chunks)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return cls(content=text, sha256=digest)


IdentityPackage = IdentityBundle