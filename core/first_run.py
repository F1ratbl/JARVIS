"""First-run environment checks for JARVIS."""

from __future__ import annotations

import importlib.util
import platform
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class SetupCheck:
    name: str
    ok: bool
    detail: str
    fix: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "fix": self.fix,
        }


def _module_check(module_name: str, package_hint: str | None = None) -> SetupCheck:
    ok = importlib.util.find_spec(module_name) is not None
    return SetupCheck(
        name=f"python:{module_name}",
        ok=ok,
        detail="Python paketi bulundu." if ok else "Python paketi bulunamadı.",
        fix="" if ok else f"pip install {package_hint or module_name}",
    )


def _command_check(command: str, fix: str = "") -> SetupCheck:
    path = shutil.which(command)
    return SetupCheck(
        name=f"cmd:{command}",
        ok=path is not None,
        detail=path or "Komut PATH içinde bulunamadı.",
        fix=fix,
    )


def run_checks() -> list[SetupCheck]:
    """Return non-invasive first-run checks without installing anything."""
    checks = [
        SetupCheck(
            name="platform:macos",
            ok=platform.system() == "Darwin",
            detail=f"Algılanan platform: {platform.system()}",
            fix="Bu proje AppleScript nedeniyle macOS hedefler.",
        ),
        _command_check("say", "macOS say komutu sistemle birlikte gelmelidir."),
        _command_check("osascript", "macOS AppleScript desteğini kontrol edin."),
        _command_check("ollama", "https://ollama.com üzerinden Ollama kurun."),
        _module_check("faster_whisper", "faster-whisper"),
        _module_check("sounddevice"),
        _module_check("numpy"),
        _module_check("scipy"),
        _module_check("ddgs"),
        _module_check("openwakeword"),
        _module_check("pyaudio"),
    ]
    return checks


def report() -> str:
    """Return a readable setup report."""
    lines = ["JARVIS first-run kontrol raporu:"]
    for check in run_checks():
        status = "OK" if check.ok else "EKSIK"
        lines.append(f"- [{status}] {check.name}: {check.detail}")
        if not check.ok and check.fix:
            lines.append(f"  Cozum: {check.fix}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())

