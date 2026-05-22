#!/usr/bin/env python3
"""
GeminiWatermarkTool — cross-platform binary installer for Claude-like skills

Downloads the appropriate GWT binary from GitHub Releases and installs
it to the Claude-like skill bin directory by default.

Usage:
    python install.py
    python install.py --mini
    python install.py --full
    python install.py --version v0.3.0
    python install.py --version v0.3.0 --mini
    python install.py --version v0.3.0 --full
    python install.py --dir /custom/path
    python install.py --no-verify

Variants:
    mini (default)  CLI-only build, UPX-compressed on Windows/Linux,
                    ~5-12 MB depending on platform. Requires v0.2.7+.
    --full          GUI + CLI build, ~18 MB on Windows.

Regardless of which variant is downloaded, the binary is installed
under the canonical name `GeminiWatermarkTool[.exe]`, so SKILL.md /
.claude/settings.json / MCP server invocation paths stay constant.

Verification:
    Releases v0.2.9 and newer ship a SHA256SUMS.txt asset; the installer
    downloads it from the same release URL and verifies the binary
    against the published digest. For older releases the installer
    falls back to the small KNOWN_SHA256 table at the top of this file
    (legacy v0.2.5 entries kept for archaeological installs).
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

# (zip filename on GitHub Releases, binary name inside the zip)
# Two release variants since v0.2.7:
#   - full: BUILD_GUI=ON,  ENABLE_AI_DENOISE=ON  (about 18 MB on Win)
#   - mini: BUILD_GUI=OFF, ENABLE_AI_DENOISE=ON  (about 5 MB on Win, UPX)
BINARIES_FULL = {
    "Windows": ("GeminiWatermarkTool-Windows-x64.zip",     "GeminiWatermarkTool.exe"),
    "Linux":   ("GeminiWatermarkTool-Linux-x64.zip",       "GeminiWatermarkTool"),
    "Darwin":  ("GeminiWatermarkTool-macOS-Universal.zip", "GeminiWatermarkTool"),
}

BINARIES_MINI = {
    "Windows": ("gwt-mini-windows-x64.zip",         "gwt-mini.exe"),
    "Linux":   ("gwt-mini-linux-x64.zip",           "gwt-mini"),
    "Darwin":  ("gwt-mini-macos-universal.zip",     "gwt-mini"),
}

# The binary is always installed under the canonical name regardless of
# which variant is downloaded. This keeps SKILL.md / settings.json / MCP
# server paths invariant when a user switches between full and mini.
INSTALL_NAMES = {
    "Windows": "GeminiWatermarkTool.exe",
    "Linux":   "GeminiWatermarkTool",
    "Darwin":  "GeminiWatermarkTool",
}

# Legacy SHA256 hashes for releases that predate SHA256SUMS.txt (v0.2.9+).
# Only used when fetching SHA256SUMS.txt returns 404. Do not extend; new
# releases publish their digests as a release asset, not in this table.
KNOWN_SHA256: dict[tuple[str, str], str] = {
    ("v0.2.5", "Windows"): "c480fd318a0ee2cd0267973e93f4045c71de79ccd11b7329e0aaed76d5e48d25",
    ("v0.2.5", "Linux"):   "ccf1c06b87a77193569f62893f5dd5fa9cc1ce69eccc96763d5b51cc813177c2",
    ("v0.2.5", "Darwin"):  "ffe22dc7d9890c7bb5210070eefe820c9539bea47dfeb7b9c51f0912758599a9",
}

REPO_ROOT = Path(__file__).resolve().parent


def _agent_skill_root(system: str, agent_dirname: str) -> Path:
    if system == "Windows":
        return Path(os.environ.get("USERPROFILE", Path.home())) / agent_dirname / "skills" / "gwt"
    return Path.home() / agent_dirname / "skills" / "gwt"


def default_install_dir(system: str) -> Path:
    install_path = REPO_ROOT.resolve()
    install_parts = {part.lower() for part in install_path.parts}
    if ".claude" in install_parts:
        return install_path / "bin"
    return _agent_skill_root(system, ".claude") / "bin"


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


def fetch_sha256sums(version_tag: str) -> dict[str, str]:
    """Fetch and parse SHA256SUMS.txt from the release.

    Returns ``{filename: hex_digest}`` keyed by the bare zip filename.
    Returns an empty dict on HTTP 404, which means either the release
    predates v0.2.9 or the asset has not been uploaded yet. Other HTTP
    errors propagate.

    Accepts either GNU coreutils format ``<digest>  <filename>`` or the
    binary-mode variant ``<digest>  *<filename>`` (asterisk stripped).
    """
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
        # sha256sum binary-mode marker is a leading '*' on the filename
        if name.startswith("*"):
            name = name[1:]
        sums[name] = digest
    return sums


def main():
    parser = argparse.ArgumentParser(
        description="Install GeminiWatermarkTool binary for Claude-like skills or local validation"
    )
    parser.add_argument("--version", default="latest",
                        help="Release version (e.g. v0.3.0). Default: latest")
    parser.add_argument("--mini", action="store_true",
                        help="Install the gwt-mini build (CLI-only, smaller). This is the default.")
    parser.add_argument("--full", action="store_true",
                        help="Install the full GUI + CLI build instead of mini.")
    parser.add_argument("--dir", default=None,
                        help="Custom install directory")
    parser.add_argument("--no-verify", action="store_true",
                        help="Skip SHA256 verification (not recommended)")
    args = parser.parse_args()

    system = platform.system()
    if system not in BINARIES_FULL:
        print(f"ERROR: Unsupported platform: {system}", file=sys.stderr)
        print("Supported: Windows, Linux, macOS (Darwin)", file=sys.stderr)
        sys.exit(1)

    if args.mini and args.full:
        parser.error("--mini and --full are mutually exclusive")

    use_mini = not args.full
    binaries = BINARIES_MINI if use_mini else BINARIES_FULL
    build_label = "mini" if use_mini else "full"

    zip_filename, binary_in_zip = binaries[system]
    binary_install_name = INSTALL_NAMES[system]

    # Normalise version tag
    if args.version != "latest":
        version_tag = args.version if args.version.startswith("v") else f"v{args.version}"
    else:
        version_tag = "latest"

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
            print(f"  Asset not found at {url}", file=sys.stderr)
            if use_mini:
                print(f"  Note: gwt-mini was introduced in v0.2.7. Older versions only ship the full build.",
                      file=sys.stderr)
            else:
                print(f"  Check available releases: {RELEASES_BASE}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\nERROR: Network error — {e.reason}", file=sys.stderr)
        sys.exit(1)

    print()

    # SHA256 verification
    # Prefer SHA256SUMS.txt published with the release (v0.2.9+), fall back
    # to the legacy KNOWN_SHA256 table for older versions.
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
        print(f"  Releases v0.2.9+ ship a SHA256SUMS.txt asset; older releases do not.")
        print(f"  Use --no-verify to silence this notice.")

    # Extract binary from ZIP, renaming to the canonical install name
    print(f"Extracting {binary_in_zip} ...")
    try:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            # Find the binary inside the zip (may be in a subdirectory)
            matches = [n for n in zf.namelist() if Path(n).name == binary_in_zip]
            if not matches:
                print(f"ERROR: '{binary_in_zip}' not found in zip.", file=sys.stderr)
                print(f"  Contents: {zf.namelist()}", file=sys.stderr)
                sys.exit(1)

            # Extract to install_dir under the canonical install name,
            # stripping any subdirectory prefix.
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
    print(f"✅  GeminiWatermarkTool ({build_label}) installed successfully!")
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
