# gwt-integrations

> AI agent integrations for [GeminiWatermarkTool](https://github.com/allenk/GeminiWatermarkTool) — Claude Code Skill and MCP Server

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/) [![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-purple.svg)](https://www.anthropic.com/news/skills) [![MCP](https://img.shields.io/badge/Protocol-MCP-blue.svg)](https://modelcontextprotocol.io) [![Based on](https://img.shields.io/badge/Based%20on-GeminiWatermarkTool-orange.svg)](https://github.com/allenk/GeminiWatermarkTool) [![Built with](https://img.shields.io/badge/Built%20with-skill--creator-blueviolet.svg)](https://github.com/anthropics/skills/tree/main/skills/skill-creator) [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![GitHub Stars](https://img.shields.io/github/stars/allenk/gwt-integrations?style=social)](https://github.com/allenk/gwt-integrations)

This repo provides two independent ways to let AI agents invoke GeminiWatermarkTool automatically.

| Integration | Works with | How agent invokes GWT |
|-------------|-----------|----------------------|
| **Claude Code Skill** | Claude Code | Reads SKILL.md → builds CLI args → calls binary directly |
| **MCP Server** | Claude Code, Cursor, Zed, OpenAI Codex, any MCP client | Calls MCP tools → server.py → binary |

Both share the same GWT binary. `install.py` at the repo root handles installation for both paths.

---

## Repository Structure

```
gwt-integrations/
├── SKILL.md           ← Claude Code Skill (auto-discovered at repo root)
├── install.py         ← GWT binary installer, shared by Skill and MCP
├── mcp/
│   ├── server.py      ← MCP server (4 tools)
│   └── pyproject.toml
└── LICENSE
```

> **Why SKILL.md is at the root:** Claude Code discovers skills by looking for
> `SKILL.md` at the root of each directory under `~/.claude/skills/`. It must
> be at the top level — subdirectories are not scanned.

---

## How the Two Paths Work

```
                    ┌─────────────────┐
                    │   install.py    │  Downloads GWT binary
                    └────────┬────────┘  to ~/.claude/skills/gwt/bin/
                             │
              ┌──────────────┴──────────────┐
              │                             │
   ┌──────────▼──────────┐      ┌──────────▼──────────┐
   │   Claude Code Skill │      │      MCP Server      │
   │      SKILL.md       │      │   mcp/server.py      │
   │                     │      │                      │
   │  Agent reads docs,  │      │  Agent calls tools,  │
   │  builds CLI args,   │      │  server builds args, │
   │  execs binary       │      │  execs binary        │
   └─────────────────────┘      └─────────────────────┘
       Claude Code only            Any MCP client
```

Binary discovery order (identical in both paths):
1. `GWT_BINARY_PATH` environment variable
2. System `PATH`
3. `~/.claude/skills/gwt/bin/` ← where `install.py` installs to
4. `./bin/` relative to `server.py`

If the binary is missing, both paths resolve it the same way:
the agent runs `install.py` automatically.

---

## Claude Code Skill

### Install

```bash
cd ~/.claude/skills
git clone https://github.com/allenk/gwt-integrations gwt
```

Claude Code finds `SKILL.md` at `~/.claude/skills/gwt/SKILL.md` automatically.

### Install GWT binary

The skill tells Claude Code where `install.py` is. When the binary is missing,
the agent runs it automatically:

```bash
# or run manually
python ~/.claude/skills/gwt/install.py
```

### Verify

Open Claude Code and ask: `"What skills do you have?"`

### Example prompts

```
去掉這張圖的 Gemini 浮水印
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
pip install -e mcp/
```

The MCP server will detect a missing binary on first use and return an
`install_command` the agent can execute immediately:

```json
{
  "found": false,
  "install_command": "python /path/to/gwt-integrations/install.py"
}
```

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
xattr -dr com.apple.quarantine ~/.claude/skills/gwt/bin/GeminiWatermarkTool
```

**Windows SmartScreen:**
```powershell
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
