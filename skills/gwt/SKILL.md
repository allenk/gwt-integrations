---
name: gwt
description: >
  Remove Gemini AI watermarks from images using GeminiWatermarkTool (GWT).
  Use this skill whenever the user mentions: Gemini watermark, 浮水印, AI image
  cleanup, removing logos from Gemini-generated images, Google ImageFX cleanup,
  batch processing AI-generated photos, or anything about a semi-transparent logo
  in the bottom-right corner of an image — even if they don't say
  "GeminiWatermarkTool" explicitly. Also trigger for follow-up requests like
  "the corner still looks dirty" or "there's still residual artifacts" after a
  previous removal attempt.
---

# GeminiWatermarkTool Skill for Codex-Like Agents

## Overview

GeminiWatermarkTool (GWT) removes visible Gemini AI watermarks from images using
mathematically accurate reverse alpha blending, with optional AI denoising
(FDnCNN + NCNN Vulkan GPU) for residual cleanup.

Source: https://github.com/allenk/GeminiWatermarkTool

---

## Binary Location

Search in this order:

1. Environment variable: `GWT_BINARY_PATH`
2. System PATH: `GeminiWatermarkTool` (or `.exe` on Windows)
3. Codex skill bin directory:
   - Windows: `%USERPROFILE%\.codex\skills\gwt\bin\GeminiWatermarkTool.exe`
   - Linux/macOS: `~/.codex/skills/gwt/bin/GeminiWatermarkTool`
4. Repo-local bin directory (validation mode / fallback):
   - Windows: `.\bin\GeminiWatermarkTool.exe`
   - Linux/macOS: `./bin/GeminiWatermarkTool`

If not found, run the installer (located at repo root, same directory as this skill):
```
python ./install.py
```

Installed skill location:

- Codex-like agents: `%USERPROFILE%\.codex\skills\gwt\install.py`

For local validation inside this repo only:
```
python ./install.py --dir ./bin
```

**Always pass `--no-banner`** when calling GWT — suppresses ASCII art that wastes tokens.

---

## Decision Logic

### Pipeline selection (automatic, based on flags)

| Flags | Internal behavior |
|-------|-------------------|
| No advanced flags | Standard 3-stage NCC detection → process or skip |
| `--fallback-region` only | Standard detection first → if not found, apply to fallback region |
| `--fallback-region --snap` | **Skip standard detection entirely** → snap search directly |
| `--force` | Skip detection, process unconditionally |

### Case A — Standard image (not resized after generation)

```bash
GeminiWatermarkTool --no-banner -i input.jpg -o clean.jpg
```

Detection on by default (threshold 25%). Non-watermarked images are skipped safely.

### Case B — Image was resized or recompressed

`--fallback-region --snap` together skips standard detection and goes straight to
multi-scale snap search:

```bash
GeminiWatermarkTool --no-banner \
  -i input.jpg -o clean.jpg \
  --fallback-region br:64,64,500,500 \
  --snap --snap-max-size 320 --snap-threshold 0.60 \
  --denoise ai --sigma 50 --strength 120
```

### Case C — Unknown image (try standard first, fallback on failure)

Use `--fallback-region` **without** `--snap`. Standard detection runs first;
fallback region only activates if standard detection fails:

```bash
GeminiWatermarkTool --no-banner \
  -i input.jpg -o clean.jpg \
  --fallback-region br:64,64,500,500 \
  --denoise ai --sigma 50 --strength 120
```

---

## Full CLI Reference

### Core options

| Flag | Default | Description |
|------|---------|-------------|
| `-i, --input <path>` | — | Input file or directory |
| `-o, --output <path>` | — | Output file or directory |
| `-f, --force` | false | Skip detection, process unconditionally |
| `-t, --threshold <0.0-1.0>` | 0.25 | Detection confidence threshold |
| `--force-small` | — | Force 48×48 watermark size |
| `--force-large` | — | Force 96×96 watermark size |
| `-v, --verbose` | false | Detailed output |
| `-q, --quiet` | false | Suppress output except errors |
| `--no-banner` | — | Hide ASCII banner (always use in this skill) |

### Region options

| Flag | Description |
|------|-------------|
| `--region <spec>` | Explicit watermark region |
| `--fallback-region <spec>` | Search region when standard detection fails |

**Region spec formats:**

| Format | Meaning |
|--------|---------|
| `x,y,w,h` | Absolute pixel coordinates |
| `br:mx,my,w,h` | Bottom-right: margin_right, margin_bottom, width, height |
| `bl:mx,my,w,h` | Bottom-left relative |
| `tr:mx,my,w,h` | Top-right relative |
| `tl:mx,my,w,h` | Top-left / absolute |
| `br:auto` | Gemini default position for this image size |

### Snap engine

| Flag | Default | Description |
|------|---------|-------------|
| `--snap` | false | Multi-scale snap within region/fallback-region |
| `--snap-max-size <32-320>` | 160 | Maximum watermark size to search |
| `--snap-threshold <0.0-1.0>` | 0.60 | Minimum confidence to accept match |

### Denoise / inpaint

| Flag | Default | Description |
|------|---------|-------------|
| `--denoise <method>` | off | `ai` \| `ns` \| `telea` \| `soft` \| `off` |
| `--sigma <1-150>` | 50 | FDnCNN noise sigma (`ai` only) |
| `--strength <0-300>` | 120 (ai) / 85 (others) | Blend strength in percent |
| `--radius <1-25>` | 10 | Inpaint radius (`ns` / `telea` / `soft` only) |

---

## Watermark Size Auto-Detection

| Image dimensions | Watermark | Margin |
|-----------------|-----------|--------|
| W ≤ 1024 or H ≤ 1024 | 48×48 | 32px |
| W > 1024 and H > 1024 | 96×96 | 64px |

Override with `--force-small` or `--force-large`.

---

## Parameter Tuning Guide

| Situation | Action |
|-----------|--------|
| Faint residual | `--denoise ai --sigma 50 --strength 120` |
| Visible edge artifacts | `--sigma 75 --strength 180` |
| Strong residual (heavily resized) | `--sigma 100 --strength 250` |
| Detection keeps skipping | Lower `--threshold 0.15` or add `--fallback-region` |
| Snap finds nothing | Widen region, increase `--snap-max-size 320` |
| Snap confidence too low | Lower `--snap-threshold 0.40` |
| Wrong size detected | `--force-small` or `--force-large` |

---

## Important Notes

1. **AI denoise GPU fallback**: Vulkan GPU used when available, falls back to CPU
   automatically. If AI init fails entirely, GWT falls back to NS inpainting.
2. **SynthID cannot be removed**: Statistically embedded during generation,
   inseparable from image content.
3. **Supported formats**: jpg, jpeg, png, webp, bmp
4. **Batch mode**: `-i dir/ -o dir/` processes all images; non-watermarked files
   are skipped safely by default.
