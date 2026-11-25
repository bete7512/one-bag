"""MCP server: the pipeline as tools a coding agent can call.

    pip install mcp            (written against mcp 2.3; 1.x works through the fallback import)
    python -m pipeline.mcp_server            (speaks MCP over stdio)

Point an MCP client at that command, with HERITAGE_ROOT set to the film's folder if it is not this
repository. The agent edits storyboard.json as a normal file and uses these tools to validate,
plan and run. There is deliberately no tool that records consent or confirms a line: those are
decisions for the person whose story it is.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path

try:  # mcp 2.x renamed FastMCP to MCPServer; both are supported here
    from mcp.server.mcpserver import MCPServer as Server
except ImportError:
    from mcp.server.fastmcp import FastMCP as Server

from . import cli
from .core import ROOT

server = Server("heritage-short")


def call(*argv: str, mock: bool = False) -> str:
    """Run a pipeline command and return what it printed."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            code = cli.main([*argv, *(["--mock"] if mock else [])])
        except SystemExit as stop:  # the argument parser leaves this way on a word it does not know: the caller gets its message as the answer
            code = stop.code if isinstance(stop.code, int) and stop.code else 2
    return out.getvalue() + f"\n(exit code {code})"


@server.tool()
def validate(strict: bool = False) -> str:
    """Check storyboard.json against the schema and the consent records. strict also refuses drafts and pending consent."""
    return call("validate", *(["--strict"] if strict else []))


@server.tool()
def plan(mock: bool = False) -> str:
    """Show which units would be regenerated and which input changed. Calls no model."""
    return call("plan", mock=mock)


@server.tool()
def run_stage(name: str, mock: bool = False) -> str:
    """Run one stage: script, narration, keyframes, shots, music or assemble."""
    return call("stage", name, mock=mock)


@server.tool()
def radio_cut(mock: bool = False) -> str:
    """Narration over placeholder music on a black screen, for the first audience test."""
    return call("radio", mock=mock)


@server.tool()
def make_film(mock: bool = False, strict: bool = False) -> str:
    """Run the whole pipeline and the final-cut check. Only changed units are regenerated."""
    return call("film", *(["--strict"] if strict else []), mock=mock)


@server.tool()
def final_check(mock: bool = False) -> str:
    """Measure the exported films: length, both ratios, loudness, subtitles, end card."""
    return call("qc", mock=mock)


@server.tool()
def costs(mock: bool = False) -> str:
    """Latency, GPU minutes and list-price equivalent per stage, from the run log."""
    return call("costs", mock=mock)


@server.tool()
def read_storyboard() -> str:
    """Return storyboard.json, the contract every stage reads."""
    root = Path(os.environ.get("HERITAGE_ROOT") or ROOT)
    return json.dumps(json.loads((root / "storyboard.json").read_text(encoding="utf-8")), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    server.run()
