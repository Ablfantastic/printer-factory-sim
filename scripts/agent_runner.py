#!/usr/bin/env python3
"""Run one Claude agent turn using a skill file and the service CLI."""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_venv_python() -> str:
    venv = REPO_ROOT / "venv"
    win = venv / "Scripts" / "python.exe"
    unix = venv / "bin" / "python"
    if win.exists():
        return str(win)
    if unix.exists():
        return str(unix)
    return sys.executable


def run_cli(workdir: Path, venv_python: str, raw_command: str) -> str:
    cmd = raw_command.strip()
    for prefix in ("./start_cli.sh", "bash start_cli.sh", "sh start_cli.sh"):
        if cmd.startswith(prefix):
            cmd = cmd[len(prefix):].strip()
            break
    try:
        args = shlex.split(cmd, posix=True)
    except ValueError:
        args = cmd.split()
    result = subprocess.run(
        [venv_python, "-m", "app.cli"] + args,
        capture_output=True,
        text=True,
        cwd=str(workdir),
    )
    return (result.stdout + result.stderr).strip() or "(no output)"


def run_agent(skill_name: str, workdir: Path, model: str) -> str:
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic not installed. Run: pip install anthropic", file=sys.stderr)
        sys.exit(1)

    skill_path = REPO_ROOT / "skills" / f"{skill_name}.md"
    if not skill_path.exists():
        print(f"ERROR: skill file not found: {skill_path}", file=sys.stderr)
        sys.exit(1)

    skill_text = skill_path.read_text(encoding="utf-8")
    venv_python = get_venv_python()
    client = anthropic.Anthropic()

    tools = [
        {
            "name": "run_command",
            "description": (
                "Run a CLI command for this service using the ./start_cli.sh syntax "
                "described in the skill instructions. Example: ./start_cli.sh day current"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "CLI command to run"}
                },
                "required": ["command"],
            },
        }
    ]

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                "Execute your daily turn now. "
                "Follow the decision framework in your instructions exactly."
            ),
        }
    ]

    for _ in range(30):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=skill_text,
            tools=tools,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                output = run_cli(workdir, venv_python, block.input.get("command", ""))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    }
                )

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    last = messages[-1]
    if last.get("role") == "assistant":
        for block in last.get("content", []):
            if hasattr(block, "text"):
                return block.text
    return "Agent turn complete."


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Claude agent turn.")
    parser.add_argument("--skill", required=True, help="Skill name (e.g. provider-manager)")
    parser.add_argument("--workdir", required=True, type=Path, help="Service working directory")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    args = parser.parse_args()

    summary = run_agent(args.skill, args.workdir.resolve(), args.model)
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
