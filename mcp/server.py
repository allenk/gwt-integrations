#!/usr/bin/env python3
"""
GeminiWatermarkTool MCP Server

Exposes GWT CLI as MCP tools for Claude Code, Cursor, Zed, and any MCP client.

Usage:
    python server.py

Environment:
    GWT_BINARY_PATH  Override binary path (optional)
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
from typing import Optional

try:
    from fastmcp import FastMCP
except ImportError:
    print("ERROR: fastmcp not installed. Run: pip install fastmcp", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Binary discovery
# ---------------------------------------------------------------------------

def _repo_bin(binary_name: str) -> Path:
    return Path(__file__).resolve().parent.parent / "bin" / binary_name


def _local_validation_enabled() -> bool:
    return os.environ.get("GWT_LOCAL_VALIDATION", "").strip().lower() in {"1", "true", "yes", "on"}


def find_gwt_binary() -> Optional[str]:
    env_path = os.environ.get("GWT_BINARY_PATH")
    if env_path and Path(env_path).is_file():
        return env_path

    binary_name = "GeminiWatermarkTool.exe" if platform.system() == "Windows" else "GeminiWatermarkTool"

    in_path = shutil.which(binary_name) or shutil.which("GeminiWatermarkTool")
    if in_path:
        return in_path

    repo_bin = _repo_bin(binary_name)
    skill_bin = Path.home() / ".claude" / "skills" / "gwt" / "bin" / binary_name
    local_bin = Path(__file__).parent / "bin" / binary_name

    if _local_validation_enabled():
        # Local validation: prefer repo-local bin over skill bin
        for p in (repo_bin, skill_bin, local_bin):
            if p.is_file():
                return str(p)
    else:
        # Normal: prefer skill bin over repo-local bin
        for p in (skill_bin, repo_bin, local_bin):
            if p.is_file():
                return str(p)

    return None


def _installer_path() -> Path:
    """install.py lives at repo root — one level above mcp/."""
    return Path(__file__).parent.parent / "install.py"


def _default_install_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "bin"


def _install_command(installer: Path) -> str:
    if _local_validation_enabled():
        return f'python "{installer}" --dir "{_default_install_dir()}"'
    return f'python "{installer}"'


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="gwt",
    instructions=(
        "GeminiWatermarkTool: remove visible Gemini AI watermarks from images "
        "using reverse alpha blending + optional FDnCNN/NCNN AI denoising."
    ),
)


def _run_gwt(args: list[str], timeout: int = 120) -> dict:
    binary = find_gwt_binary()
    if not binary:
        installer = _installer_path()
        return {
            "success": False,
            "error": "GeminiWatermarkTool binary not found.",
            "install_command": _install_command(installer),
            "installer_path": str(installer),
            "expected_install_dir": str(_default_install_dir()) if _local_validation_enabled() else None,
            "hint": (
                "Run install_command to download the binary automatically, "
                "or set the GWT_BINARY_PATH environment variable. "
                f"Releases: https://github.com/allenk/GeminiWatermarkTool/releases"
            ),
        }

    cmd = [binary, "--no-banner"] + args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        output = "\n".join(filter(None, [stdout, stderr]))
        if proc.returncode == 0:
            return {"success": True, "output": output, "returncode": 0}
        else:
            return {
                "success": False,
                "error": output or f"GWT exited with code {proc.returncode}",
                "returncode": proc.returncode,
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"GWT timed out after {timeout} seconds"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Tool: remove_watermark
# ---------------------------------------------------------------------------

@mcp.tool()
def remove_watermark(
    input_path: str,
    output_path: str,
    # Detection
    force: bool = False,
    threshold: float = 0.25,
    force_small: bool = False,
    force_large: bool = False,
    # Region
    region: Optional[str] = None,
    fallback_region: Optional[str] = None,
    # Snap
    snap: bool = False,
    snap_max_size: int = 160,
    snap_threshold: float = 0.60,
    # Cleanup
    denoise: Optional[str] = None,
    sigma: Optional[float] = None,
    strength: Optional[float] = None,
    radius: Optional[int] = None,
    # Misc
    verbose: bool = False,
    quiet: bool = False,
) -> dict:
    """
    Remove a Gemini AI watermark from a single image file.

    PIPELINE SELECTION (automatic based on flag combination):
      No advanced flags          → standard 3-stage NCC detection
      fallback_region only       → standard detection, then fallback if not found
      fallback_region + snap     → SKIP standard detection, go directly to snap
      force=True                 → skip detection entirely

    Region spec formats:
      "x,y,w,h"         absolute pixel coordinates
      "br:mx,my,w,h"    bottom-right relative (margin_right, margin_bottom, w, h)
      "br:auto"         Gemini default position for this image size

    Recommended patterns:
      Standard image:
        remove_watermark(input, output)

      Resized/recompressed — snap skips standard detection:
        remove_watermark(input, output,
          fallback_region="br:64,64,500,500",
          snap=True, snap_max_size=320,
          denoise="ai", sigma=50, strength=120)

      Unknown image — standard first, fallback on failure:
        remove_watermark(input, output,
          fallback_region="br:64,64,500,500",
          denoise="ai", sigma=50, strength=120)
    """
    input_abs = str(Path(input_path).resolve())
    output_abs = str(Path(output_path).resolve())

    if not Path(input_abs).is_file():
        return {"success": False, "error": f"Input file not found: {input_abs}"}

    Path(output_abs).parent.mkdir(parents=True, exist_ok=True)

    args = ["-i", input_abs, "-o", output_abs]

    if force:
        args.append("--force")
    else:
        args += ["--threshold", str(threshold)]

    if force_small:
        args.append("--force-small")
    elif force_large:
        args.append("--force-large")

    if region:
        args += ["--region", region]
    if fallback_region:
        args += ["--fallback-region", fallback_region]

    if snap:
        args += ["--snap", "--snap-max-size", str(snap_max_size),
                 "--snap-threshold", str(snap_threshold)]

    if denoise and denoise.lower() not in ("off", "none", ""):
        args += ["--denoise", denoise]
        if denoise.lower() == "ai":
            if sigma is not None:
                args += ["--sigma", str(sigma)]
        else:
            if radius is not None:
                args += ["--radius", str(radius)]
        if strength is not None:
            args += ["--strength", str(strength)]

    if quiet:
        args.append("--quiet")
    elif verbose:
        args.append("--verbose")

    return _run_gwt(args)


# ---------------------------------------------------------------------------
# Tool: remove_watermark_snap
# ---------------------------------------------------------------------------

@mcp.tool()
def remove_watermark_snap(
    input_path: str,
    output_path: str,
    sigma: float = 50.0,
    strength: float = 120.0,
    snap_max_size: int = 320,
    snap_threshold: float = 0.60,
    fallback_region: str = "br:64,64,500,500",
) -> dict:
    """
    Snap-based removal for resized or recompressed images.

    Skips standard NCC detection entirely and goes directly to multi-scale
    snap search in the specified region, then applies AI denoising.

    Use when standard detection keeps returning [SKIP] on a watermarked image,
    or when you know the image was resized/recompressed after generation.
    """
    input_abs = str(Path(input_path).resolve())
    output_abs = str(Path(output_path).resolve())

    if not Path(input_abs).is_file():
        return {"success": False, "error": f"Input file not found: {input_abs}"}

    Path(output_abs).parent.mkdir(parents=True, exist_ok=True)

    # fallback_region + snap together = skip standard detection (by design in GWT)
    args = [
        "-i", input_abs, "-o", output_abs,
        "--fallback-region", fallback_region,
        "--snap",
        "--snap-max-size", str(snap_max_size),
        "--snap-threshold", str(snap_threshold),
        "--denoise", "ai",
        "--sigma", str(sigma),
        "--strength", str(strength),
    ]

    return _run_gwt(args)


# ---------------------------------------------------------------------------
# Tool: remove_watermark_batch
# ---------------------------------------------------------------------------

@mcp.tool()
def remove_watermark_batch(
    input_dir: str,
    output_dir: str,
    threshold: float = 0.25,
    denoise: Optional[str] = None,
    sigma: Optional[float] = None,
    strength: Optional[float] = None,
    radius: Optional[int] = None,
    fallback_region: Optional[str] = None,
    snap: bool = False,
    snap_max_size: int = 320,
    snap_threshold: float = 0.60,
) -> dict:
    """
    Remove Gemini watermarks from all images in a directory.

    Detection enabled by default — non-watermarked images are skipped safely.
    Output directory is created automatically if it does not exist.
    """
    input_abs = str(Path(input_dir).resolve())
    output_abs = str(Path(output_dir).resolve())

    if not Path(input_abs).is_dir():
        return {"success": False, "error": f"Input directory not found: {input_abs}"}

    Path(output_abs).mkdir(parents=True, exist_ok=True)

    args = ["-i", input_abs, "-o", output_abs, "--threshold", str(threshold)]

    if fallback_region:
        args += ["--fallback-region", fallback_region]
        if snap:
            args += ["--snap", "--snap-max-size", str(snap_max_size),
                     "--snap-threshold", str(snap_threshold)]

    if denoise and denoise.lower() not in ("off", "none", ""):
        args += ["--denoise", denoise]
        if denoise.lower() == "ai":
            if sigma is not None:
                args += ["--sigma", str(sigma)]
        else:
            if radius is not None:
                args += ["--radius", str(radius)]
        if strength is not None:
            args += ["--strength", str(strength)]

    return _run_gwt(args, timeout=600)


# ---------------------------------------------------------------------------
# Tool: get_gwt_info
# ---------------------------------------------------------------------------

@mcp.tool()
def get_gwt_info() -> dict:
    """
    Get GeminiWatermarkTool binary location and version.

    If the binary is not found, returns install_command which can be executed
    directly to download and install the binary automatically.

    Always call this first to verify the tool is ready before processing images.
    """
    binary = find_gwt_binary()
    installer = _installer_path()

    if not binary:
        return {
            "found": False,
            "install_command": _install_command(installer),
            "installer_path": str(installer),
            "expected_install_dir": str(_default_install_dir()) if _local_validation_enabled() else None,
            "installer_exists": installer.is_file(),
            "hint": (
                "Run install_command to download the binary. "
                "Releases: https://github.com/allenk/GeminiWatermarkTool/releases"
            ),
        }

    result = _run_gwt(["--version"])
    return {
        "found": True,
        "binary_path": binary,
        "version": result.get("output", "unknown").strip(),
        "platform": platform.system(),
        "installer_path": str(installer),
    }


def main():
    mcp.run()


if __name__ == "__main__":
    main()
