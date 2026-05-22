#!/usr/bin/env python3
"""
GeminiWatermarkTool - cross-platform binary installer for Codex-like skills

Downloads the appropriate GWT binary from GitHub Releases and installs it to
the Codex-like skill bin directory by default.

Usage:
    python install.py
    python install.py --mini
    python install.py --full
    python install.py --version v0.3.0
    python install.py --version v0.3.0 --full
    python install.py --dir /custom/path
    python install.py --no-verify

Variants:
    mini (default)  CLI-only build, UPX-compressed on Windows/Linux,
                    about 5-12 MB depending on platform.
    --full          GUI + CLI build, about 18 MB on Windows.

Regardless of which variant is downloaded, the binary is installed under the
canonical name `GeminiWatermarkTool[.exe]`, so skill docs and MCP discovery
paths stay constant.
"""

import argparse
import hashlib
import os
import platform
import stat
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

GITHUB_REPO = "allenk/GeminiWatermarkTool"
RELEASES_BASE = f"https://github.com/{GITHUB_REPO}/releases"

BINARIES_FULL = {
    "Windows": ("GeminiWatermarkTool-Windows-x64.zip", "GeminiWatermarkTool.exe"),
    "Linux": ("GeminiWatermarkTool-Linux-x64.zip", "GeminiWatermarkTool"),
    "Darwin": ("GeminiWatermarkTool-macOS-Universal.zip", "GeminiWatermarkTool"),
}

BINARIES_MINI = {
    "Windows": ("gwt-mini-windows-x64.zip", "gwt-mini.exe"),
    "Linux": ("gwt-mini-linux-x64.zip", "gwt-mini"),
    "Darwin": ("gwt-mini-macos-universal.zip", "gwt-mini"),
}

INSTALL_NAMES = {
    "Windows": "GeminiWatermarkTool.exe",
    "Linux": "GeminiWatermarkTool",
    "Darwin": "GeminiWatermarkTool",
}

KNOWN_SHA256: dict[tuple[str, str], str] = {
    ("v0.2.5", "Windows"): "c480fd318a0ee2cd0267973e93f4045c71de79ccd11b7329e0aaed76d5e48d25",
    ("v0.2.5", "Linux"): "ccf1c06b87a77193569f62893f5dd5fa9cc1ce69eccc96763d5b51cc813177c2",
    ("v0.2.5", "Darwin"): "ffe22dc7d9890c7bb5210070eefe820c9539bea47dfeb7b9c51f0912758599a9",
}

REPO_ROOT = Path(__file__).resolve().parent


def _agent_skill_root(system: str, agent_dirname: str) -> Path:
    if system == "Windows":
        return Path(os.environ.get("USERPROFILE", Path.home())) / agent_dirname / "skills" / "gwt"
    return Path.home() / agent_dirname / "skills" / "gwt"


def default_install_dir(system: str) -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser().resolve() / "skills" / "gwt" / "bin"

    install_path = REPO_ROOT.resolve()
    install_parts = {part.lower() for part in install_path.parts}
    if ".codex" in install_parts:
        return install_path / "bin"
    return _agent_skill_root(system, ".codex") / "bin"


def resolve_install_dir(system: str, custom_dir: str | None) -> Path:
    if custom_dir:
        return Path(custom_dir).expanduser().resolve()

    env_dir = os.environ.get("GWT_INSTALL_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    return default_install_dir(system)


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
        bar = "#" * filled + "." * (bar_width - filled)
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


def fetch_sha256sums(version_tag: str) -> dict[str, str]:
    if version_tag == "latest":
        url = f"{RELEASES_BASE}/latest/download/SHA256SUMS.txt"
    else:
        url = f"{RELEASES_BASE}/download/{version_tag}/SHA256SUMS.txt"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "gwt-installer"})
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise

    sums: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts[0], parts[1].strip()
        if name.startswith("*"):
            name = name[1:]
        sums[name] = digest
    return sums


def main():
    parser = argparse.ArgumentParser(
        description="Install GeminiWatermarkTool binary for Codex-like skills or local validation"
    )
    parser.add_argument("--version", default="latest",
                        help="Release version (e.g. v0.3.0). Default: latest")
    parser.add_argument("--mini", action="store_true",
                        help="Install the gwt-mini build. This is the default.")
    parser.add_argument("--full", action="store_true",
                        help="Install the full GUI + CLI build instead of mini.")
    parser.add_argument("--dir", default=None,
                        help="Custom install directory")
    parser.add_argument("--no-verify", action="store_true",
                        help="Skip SHA256 verification")
    args = parser.parse_args()

    if args.mini and args.full:
        parser.error("--mini and --full are mutually exclusive")

    system = platform.system()
    if system not in BINARIES_FULL:
        print(f"ERROR: Unsupported platform: {system}", file=sys.stderr)
        print("Supported: Windows, Linux, macOS (Darwin)", file=sys.stderr)
        sys.exit(1)

    use_mini = not args.full
    binaries = BINARIES_MINI if use_mini else BINARIES_FULL
    build_label = "mini" if use_mini else "full"
    zip_filename, binary_in_zip = binaries[system]
    binary_install_name = INSTALL_NAMES[system]

    version_tag = args.version if args.version == "latest" or args.version.startswith("v") else f"v{args.version}"

    print(f"Platform: {system}")
    print(f"Version:  {version_tag}")
    print(f"Build:    {build_label}")
    print(f"Package:  {zip_filename}")
    if binary_in_zip != binary_install_name:
        print(f"Binary:   {binary_in_zip} -> {binary_install_name}")
    else:
        print(f"Binary:   {binary_install_name}")

    if version_tag == "latest":
        url = f"{RELEASES_BASE}/latest/download/{zip_filename}"
    else:
        url = f"{RELEASES_BASE}/download/{version_tag}/{zip_filename}"

    install_dir = resolve_install_dir(system, args.dir)
    install_dir.mkdir(parents=True, exist_ok=True)
    dest = install_dir / binary_install_name

    print(f"Target:   {dest}")
    print()

    print("Downloading from GitHub Releases...")
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        urllib.request.urlretrieve(url, tmp_path, reporthook=make_progress_hook(zip_filename))
    except urllib.error.HTTPError as e:
        print(f"\nERROR: HTTP {e.code} - {e.reason}", file=sys.stderr)
        if e.code == 404:
            print(f"  Asset not found at {url}", file=sys.stderr)
            if use_mini:
                print("  Note: gwt-mini was introduced in v0.2.7.", file=sys.stderr)
            else:
                print(f"  Check available releases: {RELEASES_BASE}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\nERROR: Network error - {e.reason}", file=sys.stderr)
        sys.exit(1)

    print()

    sums = fetch_sha256sums(version_tag)
    expected_hash = sums.get(zip_filename) or KNOWN_SHA256.get((version_tag, system))

    if args.no_verify:
        print("Skipping SHA256 verification (--no-verify)")
    elif expected_hash:
        source = "SHA256SUMS.txt" if zip_filename in sums else "legacy table"
        print(f"Verifying SHA256 (against {source}) ...", end=" ", flush=True)
        actual_hash = sha256_file(tmp_path)
        if actual_hash != expected_hash:
            print("FAILED", file=sys.stderr)
            print(f"  Expected: {expected_hash}", file=sys.stderr)
            print(f"  Got:      {actual_hash}", file=sys.stderr)
            tmp_path.unlink(missing_ok=True)
            sys.exit(1)
        print("OK")
    else:
        print(f"WARNING: no checksum available for {zip_filename}.")

    print(f"Extracting {binary_in_zip} ...")
    try:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            matches = [n for n in zf.namelist() if Path(n).name == binary_in_zip]
            if not matches:
                print(f"ERROR: '{binary_in_zip}' not found in zip.", file=sys.stderr)
                print(f"  Contents: {zf.namelist()}", file=sys.stderr)
                sys.exit(1)

            with zf.open(matches[0]) as src, open(dest, "wb") as out:
                out.write(src.read())
    finally:
        if tmp_path:
            tmp_path.unlink(missing_ok=True)

    if system in ("Linux", "Darwin"):
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("Executable permission set.")

    print()
    print(f"GeminiWatermarkTool ({build_label}) installed successfully!")
    print(f"    Location: {dest}")
    print()

    if system == "Windows":
        print("Windows note: If SmartScreen blocks the binary:")
        print(f"  Unblock-File '{dest}'")
        print()

    print("Set GWT_BINARY_PATH to this binary if your agent does not auto-discover it.")


if __name__ == "__main__":
    main()
