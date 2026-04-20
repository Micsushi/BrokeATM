from __future__ import annotations

import glob
import os
import shutil


def _extra_path_patterns(name: str) -> list[str]:
    normalized = name.lower()
    if normalized.endswith(".exe"):
        normalized = normalized[:-4]

    if normalized == "java":
        return [
            "C:/Program Files/Common Files/Oracle/Java/javapath/java.exe",
            "C:/Program Files/Java/*/bin/java.exe",
            "/mnt/c/Program Files/Common Files/Oracle/Java/javapath/java.exe",
            "/mnt/c/Program Files/Java/*/bin/java.exe",
        ]

    if normalized == "tesseract":
        return [
            "C:/Program Files/Tesseract-OCR/tesseract.exe",
            "/mnt/c/Program Files/Tesseract-OCR/tesseract.exe",
        ]

    if normalized in {"gs", "gswin64c", "gswin32c"}:
        return [
            "C:/Program Files/gs/*/bin/gswin64c.exe",
            "C:/Program Files/gs/*/bin/gswin32c.exe",
            "C:/Program Files (x86)/gs/*/bin/gswin32c.exe",
            "/mnt/c/Program Files/gs/*/bin/gswin64c.exe",
            "/mnt/c/Program Files/gs/*/bin/gswin32c.exe",
            "/mnt/c/Program Files (x86)/gs/*/bin/gswin32c.exe",
        ]

    return []


def _find_common_install_path(*names: str) -> str | None:
    for name in names:
        for pattern in _extra_path_patterns(name):
            for match in sorted(glob.glob(pattern), reverse=True):
                if os.path.isfile(match):
                    return match
    return None


def find_executable(*names: str) -> str | None:
    """Return the first matching executable visible to this runtime.

    WSL and some Windows-backed shells may expose tools as `name.exe` even
    when callers ask for `name`, so we probe both forms.
    """

    for name in names:
        candidates = [name]
        if not name.lower().endswith(".exe"):
            candidates.append(f"{name}.exe")
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
    return _find_common_install_path(*names)


def ensure_executable_on_path(*names: str) -> str | None:
    resolved = find_executable(*names)
    if not resolved:
        return None

    bin_dir = os.path.dirname(resolved)
    path_parts = os.environ.get("PATH", "").split(os.pathsep) if os.environ.get("PATH") else []
    if bin_dir and bin_dir not in path_parts:
        os.environ["PATH"] = os.pathsep.join([bin_dir, *path_parts]) if path_parts else bin_dir
    return resolved


def has_executable(*names: str) -> bool:
    return find_executable(*names) is not None
