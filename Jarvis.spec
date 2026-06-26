# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


def safe_collect_submodules(package_name):
    try:
        return collect_submodules(package_name)
    except Exception:
        return []


datas = [
    ("frontend", "frontend"),
]
datas += collect_data_files("faster_whisper", includes=["assets/*"])
datas += collect_data_files("openwakeword", includes=["resources/models/*"])

hiddenimports = []
for package in (
    "app",
    "assistant",
    "core",
    "plugins",
    "memory_manager",
    "webview",
    "uvicorn",
    "websockets",
    "fastapi",
    "starlette",
    "ollama",
    "faster_whisper",
    "sounddevice",
    "openwakeword",
    "ddgs",
    "gtts",
):
    hiddenimports += safe_collect_submodules(package)

a = Analysis(
    ["app/desktop.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="JARVIS",
)

app = BUNDLE(
    coll,
    name="JARVIS.app",
    icon=None,
    bundle_identifier="local.jarvis.app",
    info_plist={
        "CFBundleDisplayName": "JARVIS",
        "NSMicrophoneUsageDescription": "JARVIS sesli komutlari dinlemek icin mikrofona erisir.",
        "NSAppleEventsUsageDescription": "JARVIS macOS uygulamalarini komutlarinizla yonetmek icin Apple Events kullanir.",
        "NSCalendarsUsageDescription": "JARVIS takvim etkinligi eklemek icin takviminize erisebilir.",
    },
)
