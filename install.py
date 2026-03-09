#!/usr/bin/env python3
"""
GeminiWatermarkTool — Cross-platform binary installer

Downloads the appropriate GWT binary from GitHub Releases and installs
it to ~/.claude/skills/gwt/bin/ by default.

Usage:
    python install.py
    python install.py --version v0.2.5
    python install.py --dir /custom/path
"""

import argparse
import hashlib
import os
import platform
import stat
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

GITHUB_REPO = "allenk/GeminiWatermarkTool"
RELEASES_BASE = f"https://github.com/{GITHUB_REPO}/releases"

# (zip filename on GitHub Releases, binary name inside the zip)
BINARIES = {
    "Windows": ("GeminiWatermarkTool-Windows-x64.zip",     "GeminiWatermarkTool.exe"),
    "Linux":   ("GeminiWatermarkTool-Linux-x64.zip",       "GeminiWatermarkTool"),
    "Darwin":  ("GeminiWatermarkTool-macOS-Universal.zip", "GeminiWatermarkTool"),
}

# SHA256 checksums for known releases — keyed by (version_tag, platform).
# Only verified when --version is explicitly given (latest has no pinned hash).
# Update this table when new releases are published.
KNOWN_SHA256: dict[tuple[str, str], str] = {
    ("v0.2.5", "Windows"): "c480fd318a0ee2cd0267973e93f4045c71de79ccd11b7329e0aaed76d5e48d25",
    ("v0.2.5", "Linux"):   "ccf1c06b87a77193569f62893f5dd5fa9cc1ce69eccc96763d5b51cc813177c2",
    ("v0.2.5", "Darwin"):  "ffe22dc7d9890c7bb5210070eefe820c9539bea47dfeb7b9c51f0912758599a9",
}

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_INSTALL_DIRS = {
    "Windows": Path(os.environ.get("USERPROFILE", Path.home())) / ".claude" / "skills" / "gwt" / "bin",
    "Linux":   Path.home() / ".claude" / "skills" / "gwt" / "bin",
    "Darwin":  Path.home() / ".claude" / "skills" / "gwt" / "bin",
}


def resolve_install_dir(system: str, custom_dir: str | None) -> Path:
    if custom_dir:
        return Path(custom_dir).expanduser().resolve()

    env_dir = os.environ.get("GWT_INSTALL_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    return DEFAULT_INSTALL_DIRS[system]


def make_progress_hook(filename: str):
    bar_width = 40

    def hook(count, block_size, total_size):
        if total_size <= 0:
            downloaded = count * block_size
            print(f"\r  Downloading {filename}: {downloaded // 1024} KB", end="", flush=True)
            return
        downloaded = min(count * block_size, total_size)
        percent = downloaded / total_size
        filled = int(bar_width * percent)
        bar = "█" * filled + "░" * (bar_width - filled)
        mb_done = downloaded / 1_048_576
        mb_total = total_size / 1_048_576
        print(f"\r  [{bar}] {mb_done:.1f} / {mb_total:.1f} MB", end="", flush=True)

    return hook


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(
        description="Install GeminiWatermarkTool binary for Claude Code Skill or local validation"
    )
    parser.add_argument("--version", default="latest",
                        help="Release version (e.g. v0.2.5). Default: latest")
    parser.add_argument("--dir", default=None,
                        help="Custom install directory")
    args = parser.parse_args()

    system = platform.system()
    if system not in BINARIES:
        print(f"ERROR: Unsupported platform: {system}", file=sys.stderr)
        print("Supported: Windows, Linux, macOS (Darwin)", file=sys.stderr)
        sys.exit(1)

    zip_filename, binary_name = BINARIES[system]

    # Normalise version tag
    if args.version != "latest":
        version_tag = args.version if args.version.startswith("v") else f"v{args.version}"
    else:
        version_tag = "latest"

    print(f"Platform: {system}")
    print(f"Version:  {version_tag}")
    print(f"Package:  {zip_filename}")
    print(f"Binary:   {binary_name}")

    if version_tag == "latest":
        url = f"{RELEASES_BASE}/latest/download/{zip_filename}"
    else:
        url = f"{RELEASES_BASE}/download/{version_tag}/{zip_filename}"

    install_dir = resolve_install_dir(system, args.dir)
    install_dir.mkdir(parents=True, exist_ok=True)
    dest = install_dir / binary_name

    print(f"Target:   {dest}")
    print()

    # Download ZIP to a temp file
    print("Downloading from GitHub Releases...")
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        urllib.request.urlretrieve(url, tmp_path, reporthook=make_progress_hook(zip_filename))
    except urllib.error.HTTPError as e:
        print(f"\nERROR: HTTP {e.code} — {e.reason}", file=sys.stderr)
        if e.code == 404:
            print(f"  Version not found. Check: {RELEASES_BASE}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\nERROR: Network error — {e.reason}", file=sys.stderr)
        sys.exit(1)

    print()

    # SHA256 verification (only when a specific version with known hash is requested)
    expected_hash = KNOWN_SHA256.get((version_tag, system))
    if expected_hash:
        print("Verifying SHA256 ...", end=" ", flush=True)
        actual_hash = sha256_file(tmp_path)
        if actual_hash != expected_hash:
            print("FAILED", file=sys.stderr)
            print(f"  Expected: {expected_hash}", file=sys.stderr)
            print(f"  Got:      {actual_hash}", file=sys.stderr)
            tmp_path.unlink(missing_ok=True)
            sys.exit(1)
        print("OK")
    else:
        if version_tag != "latest":
            print(f"Note: No known checksum for {version_tag}/{system} — skipping verification.")

    # Extract binary from ZIP
    print(f"Extracting {binary_name} ...")
    try:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            # Find the binary inside the zip (may be in a subdirectory)
            matches = [n for n in zf.namelist() if Path(n).name == binary_name]
            if not matches:
                print(f"ERROR: '{binary_name}' not found in zip.", file=sys.stderr)
                print(f"  Contents: {zf.namelist()}", file=sys.stderr)
                sys.exit(1)

            # Extract to install_dir, stripping any subdirectory prefix
            with zf.open(matches[0]) as src, open(dest, "wb") as out:
                out.write(src.read())
    finally:
        if tmp_path:
            tmp_path.unlink(missing_ok=True)

    # Set executable permission on Unix
    if system in ("Linux", "Darwin"):
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("Executable permission set.")

    print()
    print(f"✅  GeminiWatermarkTool installed successfully!")
    print(f"    Location: {dest}")
    print()

    if system == "Darwin":
        print("macOS note: If blocked by Gatekeeper on first run:")
        print(f"  xattr -dr com.apple.quarantine '{dest}'")
        print()

    if system == "Windows":
        print("Windows note: If SmartScreen blocks the binary:")
        print(f"  Unblock-File '{dest}'")
        print()

    print("Set GWT_BINARY_PATH to this binary if your agent does not auto-discover it.")


if __name__ == "__main__":
    main()
