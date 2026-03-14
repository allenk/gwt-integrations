# gwt Codex Skill

> Codex-like skill entrypoint for [GeminiWatermarkTool](https://github.com/allenk/GeminiWatermarkTool), plus access to the shared MCP server

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/) [![Codex](https://img.shields.io/badge/OpenAI-Codex-black.svg)](https://openai.com/) [![MCP](https://img.shields.io/badge/Protocol-MCP-blue.svg)](https://modelcontextprotocol.io) [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

This directory is the Codex-oriented skill payload from the `gwt-integrations` repository.

## What This Directory Is For

- `SKILL.md`: Codex-like prompt and usage guidance
- `install.py`: installs the binary to `~/.codex/skills/gwt/bin/` by default

This directory is meant to be installed directly by Codex-style GitHub skill installers.

## Install for Codex

Use this directory as the skill path:

```bash
python install-skill-from-github.py --repo allenk/gwt-integrations --path skills/gwt
```

After installation, Codex will load the skill from `~/.codex/skills/gwt/`.

## Install the GWT Binary

When the binary is missing, Codex can run `install.py` automatically. You can also run it manually:

```bash
python ~/.codex/skills/gwt/install.py
```

Default install location:

```text
~/.codex/skills/gwt/bin/
```

## Local Validation

To keep this directory self-contained during validation:

```bash
python ./install.py --dir ./bin
```

## Shared MCP Server

The MCP server is shared across agent families and lives at the repository root:

```text
/mcp
```

Examples:

- Codex CLI: `codex --mcp-server "python /path/to/gwt-integrations/mcp/server.py"`
- Cursor: configure the same `mcp/server.py`
- Claude Code: configure the same `mcp/server.py`

## Troubleshooting

If SmartScreen blocks the binary on Windows:

```powershell
Unblock-File $env:USERPROFILE\.codex\skills\gwt\bin\GeminiWatermarkTool.exe
```

If Gatekeeper blocks the binary on macOS:

```bash
xattr -dr com.apple.quarantine ~/.codex/skills/gwt/bin/GeminiWatermarkTool
```
