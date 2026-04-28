[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/allenk-gwt-integrations-badge.png)](https://mseep.ai/app/allenk-gwt-integrations)

# gwt-integrations

> AI agent integrations for [GeminiWatermarkTool](https://github.com/allenk/GeminiWatermarkTool) — Claude-like skill, Codex-like skill, and a shared MCP server

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/) [![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-purple.svg)](https://www.anthropic.com/news/skills) [![MCP](https://img.shields.io/badge/Protocol-MCP-blue.svg)](https://modelcontextprotocol.io) [![Based on](https://img.shields.io/badge/Based%20on-GeminiWatermarkTool-orange.svg)](https://github.com/allenk/GeminiWatermarkTool) [![Built with](https://img.shields.io/badge/Built%20with-skill--creator-blueviolet.svg)](https://github.com/anthropics/skills/tree/main/skills/skill-creator) [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![GitHub Stars](https://img.shields.io/github/stars/allenk/gwt-integrations?style=social)](https://github.com/allenk/gwt-integrations)

This repo provides specialized skill entrypoints for different agent families plus one shared MCP server.

| Integration | Works with | How agent invokes GWT |
|-------------|-----------|----------------------|
| **Root Skill** | Claude Code and Claude-like agents | Reads the root `SKILL.md` → builds CLI args → calls binary directly |
| **Codex Skill** | Codex and Codex-like agents | Installs from `skills/gwt/` → reads that `SKILL.md` → calls binary directly |
| **MCP Server** | Claude Code, Cursor, Zed, OpenAI Codex, any MCP client | Calls MCP tools → server.py → binary |

The skill entrypoints are intentionally specialized. The `mcp/` directory remains shared across all clients.

## Layout Strategy

This repo uses distinct skill entrypoints:

- Root skill layout: for Claude-like agents
- `skills/gwt/`: for Codex-like agents

This avoids forcing both agent families to share the exact same prompt wording and installer defaults.

## Install Destination Rules

| Integration path | Situation | Install location |
|------------------|-----------|------------------|
| Codex Skill | Normal use | `~/.codex/skills/gwt/bin/` |
| Claude-like Skill | Normal use | `~/.claude/skills/gwt/bin/` |
| MCP Server | Normal use | Shared server, independent of skill layout |
| MCP Server | Local validation with `GWT_LOCAL_VALIDATION=1` | `./bin/` at the repo root |
| Any path | Manual override with `python install.py --dir <path>` | The directory you specify |

In other words, the skill layer is split by agent family, while the MCP layer stays shared.

---

## Repository Structure

```
gwt-integrations/
├── SKILL.md           ← Claude-like skill entrypoint
├── install.py         ← Claude-like skill installer
├── skills/
│   └── gwt/           ← Codex-like skill entrypoint
├── mcp/
│   ├── server.py      ← Shared MCP server (4 tools)
│   └── pyproject.toml
└── LICENSE
```

> The root skill and `skills/gwt/` skill are intentionally different. They can
> be tuned for their respective agent families without splitting the MCP server.

---

## How the Two Paths Work

```
              ┌──────────────────┐
              │  install.py (x2) │  Each skill has its own installer
              └────────┬─────────┘  (Claude → ~/.claude, Codex → ~/.codex)
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
   ┌─▼───────────┐  ┌──▼──────────┐  ┌───▼─────────────────┐
   │ Claude-Like │  │ Codex-Like  │  │    MCP Server       │
   │  SKILL.md   │  │ skills/gwt/ │  │  mcp/server.py      │
   │  (root)     │  │  SKILL.md   │  │                     │
   │             │  │             │  │  Agent calls tools, │
   │ Agent reads │  │ Agent reads │  │  server builds args,│
   │ docs, execs │  │ docs, execs │  │  execs binary       │
   └─────────────┘  └─────────────┘  └─────────────────────┘
    Claude-like       Codex-like        Any MCP client
```

Binary discovery order (default behavior):
1. `GWT_BINARY_PATH` environment variable
2. System `PATH`
3. `~/.codex/skills/gwt/bin/`
4. `~/.claude/skills/gwt/bin/`
5. `./bin/` at the repo root (local validation / fallback)
6. `./mcp/bin/` relative to `server.py` (legacy fallback)

If the binary is missing, each skill entrypoint can invoke its own `install.py`
while the MCP server remains shared at the repo root.

---

## Claude-Like Skill

### Install

```bash
cd ~/.claude/skills
git clone https://github.com/allenk/gwt-integrations gwt
```

Claude Code finds `SKILL.md` at `~/.claude/skills/gwt/SKILL.md` automatically.

### Install GWT binary

When the binary is missing, the agent can run `install.py` automatically. In a
Claude-style install, this defaults to `~/.claude/skills/gwt/bin/`:

```bash
# or run manually
python ~/.claude/skills/gwt/install.py
```

### Verify

Open Claude Code and ask: `"What skills do you have?"`

## Codex-Like Skill

### Install

For Codex's GitHub skill installer, use the dedicated subdirectory:

```bash
python install-skill-from-github.py --repo allenk/gwt-integrations --path skills/gwt
```

After installation, Codex will load the skill from `~/.codex/skills/gwt/`, and the bundled `install.py` will default to `~/.codex/skills/gwt/bin/`.

### Verify

Open Codex and confirm that the `gwt` skill is available.

### Local validation only

To keep the repo self-contained during validation, install the binary locally
instead of an agent skill directory:

```bash
python ./install.py --dir ./bin
# then: export GWT_LOCAL_VALIDATION=1
```

### Example prompts

```
Remove the Gemini watermark from this image.
Remove the watermark from all images in ~/Downloads/
The bottom-right corner still has artifacts, fix it
The image keeps getting skipped, try snap search
```

---

## MCP Server

### Install

```bash
git clone https://github.com/allenk/gwt-integrations
cd gwt-integrations
pip install -e ./mcp
```

### Local validation only

```bash
pip install -e ./mcp
python ./install.py --dir ./bin
```

The MCP server will detect a missing binary on first use and return an
`install_command` the agent can execute immediately:

```json
{
  "found": false,
  "install_command": "python /path/to/gwt-integrations/install.py --dir /path/to/gwt-integrations/bin"
}
```

The MCP server is shared across agent families, so its `install_command` always
targets the repo-local `bin/` directory — it does not assume any particular
skill directory (`~/.claude/` or `~/.codex/`).

`GWT_LOCAL_VALIDATION=1` still controls the **search order** in
`find_gwt_binary()`: when set, the repo-local `bin/` is searched before the
skill directories.

### Configure clients

**Claude Code:**
```bash
claude mcp add gwt -- python /path/to/gwt-integrations/mcp/server.py
```

**Cursor** (`.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "gwt": {
      "command": "python",
      "args": ["/path/to/gwt-integrations/mcp/server.py"]
    }
  }
}
```

**Zed** (`~/.config/zed/settings.json`):
```json
{
  "context_servers": {
    "gwt": {
      "command": { "path": "python",
                   "args": ["/path/to/gwt-integrations/mcp/server.py"] }
    }
  }
}
```

**OpenAI Codex CLI:**
```bash
codex --mcp-server "python /path/to/gwt-integrations/mcp/server.py"
```

### MCP tools

| Tool | Purpose |
|------|---------|
| `get_gwt_info` | Check binary; returns `install_command` if missing |
| `remove_watermark` | Single file, full parameter control |
| `remove_watermark_snap` | Single file, resized/recompressed images |
| `remove_watermark_batch` | Entire directory |

---

## Usage Scenarios

This repo is most useful when the user does not want to manually build CLI
arguments. Instead, they describe the image problem in natural language, and
the agent maps that request to either the Skill path or the MCP tool path.

### Scenario 1: Standard Gemini watermark in the default corner

User says:

```text
Remove the Gemini watermark from this image.
Remove the Gemini watermark from the bottom-right corner of this image.
```

Agent behavior:
- Skill: runs standard GWT detection with no advanced flags
- MCP: calls `remove_watermark(input_path, output_path)`

Best for:
- Typical Gemini output
- Normal bottom-right watermark
- Images that were not resized after generation

### Scenario 2: Image was resized, recompressed, or screenshot

User says:

```text
This image keeps getting skipped. Try snap search.
This image was resized. Use snap search to find the watermark.
```

Agent behavior:
- Skill: adds `--fallback-region ... --snap`
- MCP: calls `remove_watermark_snap(...)`

Best for:
- JPEG recompression
- Social-media reposts
- Screenshots or edited exports
- Cases where standard detection returns `[SKIP]`

### Scenario 3: Watermark is still visible after one pass

User says:

```text
The watermark is mostly gone but the corner still looks dirty.
There are still artifacts in the bottom-right corner. Increase the strength a bit.
```

Agent behavior:
- Keeps the same detected/custom region
- Increases denoise settings, for example `sigma=75, strength=180`
- Escalates further only if needed, for example `sigma=100, strength=250`

Best for:
- Faint edge residue
- Partial removal
- Watermark halo or dirty corners

### Scenario 4: Non-standard watermark size or non-standard location

User says:

```text
The watermark is not in the normal bottom-right position.
Search the bottom-left 600x600 area with snap.
The watermark size looks unusual. Search the bottom-right 200x200 area.
```

Agent behavior:
- Uses region-constrained search instead of whole-image assumptions
- Skill: uses `--fallback-region br:...` or `bl:...` with `--snap`
- MCP: calls `remove_watermark(...)` with `fallback_region`, `snap`,
  `snap_max_size`, and `snap_threshold`

Best for:
- Cropped images
- Layout-shifted watermark positions
- Smaller or larger than expected watermark sizes

### Scenario 5: User knows the exact rectangle

User says:

```text
Use custom region 683,1297,52,52 and remove it directly.
Do not use snap. Use custom region 683,1297,52,52 directly.
```

Agent behavior:
- Skips broad search
- Applies GWT directly to the supplied region
- Useful when a human has already visually identified the watermark

Best for:
- Repeated images from the same source
- Fine-grained cleanup
- Cases where broad snap search drifts to a wrong candidate

### Scenario 6: Batch processing a folder

User says:

```text
Remove Gemini watermarks from every image in this folder.
Batch remove Gemini watermarks from every image in this folder.
```

Agent behavior:
- Skill: calls GWT in directory mode
- MCP: calls `remove_watermark_batch(input_dir, output_dir)`

Best for:
- Download folders
- Image exports from a single generation session
- Mixed folders where only some images contain a watermark

### How users should talk to the agent

The highest-signal instructions are:
- Describe whether the image is standard, resized, cropped, or recompressed
- Mention which corner to search: `bottom-right`, `bottom-left`, etc.
- Mention whether the watermark size looks normal, smaller, or larger
- If known, provide a region directly: `x,y,w,h`
- If artifacts remain, say whether you want a mild cleanup or stronger cleanup

Examples:

```text
Remove the Gemini watermark from this file.
Try snap search in the bottom-right 200x200 area.
Use custom region 683,1297,52,52.
The first pass worked, but increase strength slightly.
Process this whole folder and skip files with no watermark.
```

### Skill vs MCP in practice

- Use the Skill when you want the agent to infer the CLI flags from normal
  conversation in a skill-enabled agent.
- Use MCP when you want structured tool calls, explicit arguments, and easier
  integration with Cursor, Zed, Codex CLI, or any other MCP client.
- In both cases, the user-facing request can stay natural-language; the
  integration layer is what translates that request into GWT arguments.

---

## Region Syntax Reference

| Format | Meaning |
|--------|---------|
| `x,y,w,h` | Absolute pixel coordinates |
| `br:mx,my,w,h` | Bottom-right: margin_right, margin_bottom, width, height |
| `bl:mx,my,w,h` | Bottom-left relative |
| `tr:mx,my,w,h` | Top-right relative |
| `tl:mx,my,w,h` | Top-left / absolute |
| `br:auto` | Gemini default position for this image size |

---

## Troubleshooting

**Image keeps getting `[SKIP]`** — image was resized/recompressed after generation.
Tell the agent: *"try snap search"* or use `remove_watermark_snap`.

**Residual artifacts still visible** — tell the agent: *"increase the strength"*.
Escalation: `sigma=75, strength=180` → `sigma=100, strength=250`.

**macOS Gatekeeper:**
```bash
xattr -dr com.apple.quarantine ~/.codex/skills/gwt/bin/GeminiWatermarkTool
# or:
xattr -dr com.apple.quarantine ~/.claude/skills/gwt/bin/GeminiWatermarkTool
```

**Windows SmartScreen:**
```powershell
Unblock-File $env:USERPROFILE\.codex\skills\gwt\bin\GeminiWatermarkTool.exe
# or:
Unblock-File $env:USERPROFILE\.claude\skills\gwt\bin\GeminiWatermarkTool.exe
```

---

## Related

- **[GeminiWatermarkTool](https://github.com/allenk/GeminiWatermarkTool)** — core C++ tool
- **[Technical writeup on Medium](https://allenkuo.medium.com/removing-gemini-ai-watermarks-a-deep-dive-into-reverse-alpha-blending-bbbd83af2a3f)** — reverse alpha blending deep dive
- **[SynthID Research Report](https://allenkuo.medium.com/synthid-image-watermark-research-report-9b864b19f9cf)** — why Google's invisible watermark cannot be removed

---

## License

MIT — see [LICENSE](LICENSE)
