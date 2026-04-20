from __future__ import annotations

import os

from app.services.parsers._dependency_utils import ensure_executable_on_path, find_executable, has_executable


class TestDependencyUtils:
    def test_find_executable_tries_windows_suffix(self, monkeypatch):
        seen: list[str] = []

        def fake_which(name: str):
            seen.append(name)
            return "/fake/java.exe" if name == "java.exe" else None

        monkeypatch.setattr("shutil.which", fake_which)

        assert find_executable("java") == "/fake/java.exe"
        assert seen == ["java", "java.exe"]

    def test_has_executable_accepts_existing_windows_name(self, monkeypatch):
        def fake_which(name: str):
            return "/fake/gswin64c.exe" if name == "gswin64c.exe" else None

        monkeypatch.setattr("shutil.which", fake_which)

        assert has_executable("gs", "gswin64c", "gswin32c") is True

    def test_find_executable_checks_common_install_locations(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _name: None)
        monkeypatch.setattr("glob.glob", lambda pattern: ["C:/Program Files/Tesseract-OCR/tesseract.exe"] if "Tesseract-OCR" in pattern else [])
        monkeypatch.setattr("os.path.isfile", lambda path: path == "C:/Program Files/Tesseract-OCR/tesseract.exe")

        assert find_executable("tesseract") == "C:/Program Files/Tesseract-OCR/tesseract.exe"

    def test_ensure_executable_on_path_prepends_bin_dir(self, monkeypatch):
        monkeypatch.setattr("app.services.parsers._dependency_utils.find_executable", lambda *_names: "C:/Tools/Tesseract/tesseract.exe")
        monkeypatch.setenv("PATH", os.pathsep.join(["C:/Windows/System32", "C:/Tools/Other"]))

        resolved = ensure_executable_on_path("tesseract")

        assert resolved == "C:/Tools/Tesseract/tesseract.exe"
        assert os.environ["PATH"].split(os.pathsep)[0] == "C:/Tools/Tesseract"
