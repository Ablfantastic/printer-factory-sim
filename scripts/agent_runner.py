#!/usr/bin/env python3
"""Run one agent turn using Codex or Claude CLI and a skill file.

Uses the existing Claude Code authentication — NO separate ANTHROPIC_API_KEY needed.

The agent:
  1. Receives the skill file plus current state in the prompt
  2. Receives the current day + market signal as the user prompt
  3. Calls ./start_cli.sh commands via the Bash tool to inspect state and take actions
  4. Runs until it produces a final summary, then exits
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIN_AGENT_TURNS = 8
MAX_TURNS_RETRY_BONUS = 4
DEFAULT_BACKEND = "codex"
DEFAULT_CODEX_MODEL = "gpt-5.4-mini"
DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5-20251001"


def find_executable(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    if name == "codex":
        home = Path.home()
        candidates = sorted(
            (home / ".vscode" / "extensions").glob(
                "openai.chatgpt-*-win32-x64/bin/windows-x86_64/codex.exe"
            ),
            reverse=True,
        )
        if candidates:
            return str(candidates[0])
    return name


def reached_max_turns(output: str) -> bool:
    lowered = output.lower()
    return "reached max turns" in lowered or "max turns" in lowered


def run_claude_command(cmd: list[str], workdir: Path) -> str:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(workdir),
        timeout=300,
    )
    output = result.stdout.strip()
    if not output and result.stderr:
        output = result.stderr.strip()
    return output or "Agent turn complete (no output)."


def run_codex_command(prompt: str, workdir: Path, model: str) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".md",
        delete=False,
    ) as handle:
        output_path = Path(handle.name)

    cmd = [
        find_executable("codex"),
        "exec",
        "--model", model,
        "--cd", str(workdir),
        "--sandbox", "workspace-write",
        "--dangerously-bypass-approvals-and-sandbox",
        "--output-last-message", str(output_path),
        prompt,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(REPO_ROOT),
            timeout=300,
        )
        output = ""
        if output_path.exists():
            output = output_path.read_text(encoding="utf-8", errors="replace").strip()
        if not output:
            output = result.stdout.strip() or result.stderr.strip()
        return output or "Agent turn complete (no output)."
    finally:
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass


def run_agent(
    skill_name: str,
    workdir: Path,
    model: str = "",
    extra_context: str = "",
    max_turns: int = 15,
    backend: str = DEFAULT_BACKEND,
) -> str:
    """Run one agent turn via Codex CLI or Claude CLI.

    Args:
        skill_name:     Name of the skill file (without .md), e.g. "provider-manager".
        workdir:        Service working directory (e.g. REPO_ROOT/provider).
        model:          Optional model override.
        extra_context:  Optional text prepended to the user message (day, market signals).
        max_turns:      Maximum agentic turns (tool-call + response cycles).
                        The runner enforces a small floor because one Bash action
                        still needs room for the tool result and final summary.

    Returns:
        The agent's final text summary.
    """
    skill_path = REPO_ROOT / "skills" / f"{skill_name}.md"
    if not skill_path.exists():
        msg = f"Skill file not found: {skill_path}"
        print(f"ERROR: {msg}", file=sys.stderr)
        return msg

    skill_text = skill_path.read_text(encoding="utf-8")

    base_prompt = (
        "Execute your daily turn now. "
        "The current state and action hints are already provided above. "
        "Do not run assessment/list/catalog commands unless the pre-fetched state says it failed. "
        "Prefer zero or one Bash call: chain every required action with &&, then summarize. "
        "Follow the decision framework in your instructions exactly.\n\n"
        "End your turn with EXACTLY this summary block (fill in the brackets):\n"
        "## END-OF-DAY SUMMARY\n"
        "- Stock: [key stock levels after any changes]\n"
        "- Actions taken: [concrete actions taken, or 'none']\n"
        "- Risk: [one sentence]\n"
        "Do NOT use emojis. Use plain ASCII only."
    )
    user_message = (
        f"{extra_context}\n\n{base_prompt}".strip() if extra_context else base_prompt
    )
    effective_max_turns = max(max_turns, MIN_AGENT_TURNS)

    if backend == "codex":
        codex_model = model or DEFAULT_CODEX_MODEL
        prompt = (
            "You are running one autonomous supply-chain agent turn.\n\n"
            "ROLE SKILL:\n"
            f"{skill_text}\n\n"
            "TURN CONTEXT AND TASK:\n"
            f"{user_message}\n\n"
            "Important: do not edit files. Use shell commands only for service CLI actions. "
            "Return only the final operational summary."
        )
        try:
            return run_codex_command(prompt, workdir, codex_model)
        except subprocess.TimeoutExpired:
            return "Agent turn timed out after 5 minutes."
        except FileNotFoundError:
            return (
                "ERROR: 'codex' CLI not found in PATH. "
                "Install or expose Codex CLI, or run with --backend claude."
            )
        except Exception as exc:
            return f"Agent turn error: {exc}"

    cmd = [
        "claude",
        "--print",                          # non-interactive: run and exit
        "--dangerously-skip-permissions",   # no "allow Bash?" prompts during automated runs
        "--allowedTools", "Bash",           # agent can run ./start_cli.sh commands
        "--append-system-prompt", skill_text,  # add skill to end of Claude's system prompt
        "--max-turns", str(effective_max_turns),  # cap tool-use iterations for speed
    ]
    if model:
        cmd += ["--model", model]
    cmd.append(user_message)

    try:
        output = run_claude_command(cmd, workdir)
        if reached_max_turns(output):
            retry_turns = effective_max_turns + MAX_TURNS_RETRY_BONUS
            retry_cmd = list(cmd)
            turn_arg_index = retry_cmd.index("--max-turns") + 1
            retry_cmd[turn_arg_index] = str(retry_turns)
            retry_cmd[-1] = (
                f"{user_message}\n\n"
                "Previous attempt hit the max-turn limit. "
                "Do not reassess. Execute the ACTION HINT immediately if needed, then write the final summary."
            )
            retry_output = run_claude_command(retry_cmd, workdir)
            return retry_output or output
        return output

    except subprocess.TimeoutExpired:
        return "Agent turn timed out after 5 minutes."
    except FileNotFoundError:
        return (
            "ERROR: 'claude' CLI not found in PATH. "
            "Make sure Claude Code is installed and in PATH."
        )
    except Exception as exc:
        return f"Agent turn error: {exc}"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",    # force UTF-8 on Windows (prevents â€" garbling)
            errors="replace",    # replace undecodable chars instead of crashing
            cwd=str(workdir),   # agent runs ./start_cli.sh from the service directory
            timeout=300,         # 5-minute timeout per agent turn
        )
        output = result.stdout.strip()
        if not output and result.stderr:
            output = result.stderr.strip()
        return output or "Agent turn complete (no output)."

    except subprocess.TimeoutExpired:
        return "Agent turn timed out after 5 minutes."
    except FileNotFoundError:
        return (
            "ERROR: 'claude' CLI not found in PATH. "
            "Make sure Claude Code is installed and in PATH."
        )
    except Exception as exc:
        return f"Agent turn error: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one supply-chain agent turn via Codex or Claude CLI."
    )
    parser.add_argument("--skill", required=True,
                        help="Skill name (e.g. provider-manager)")
    parser.add_argument("--workdir", required=True, type=Path,
                        help="Service working directory")
    parser.add_argument("--backend", choices=("codex", "claude"), default=DEFAULT_BACKEND,
                        help=f"Agent CLI backend (default: {DEFAULT_BACKEND})")
    parser.add_argument("--model", default="",
                        help=f"Model override (defaults: codex={DEFAULT_CODEX_MODEL}, claude={DEFAULT_CLAUDE_MODEL})")
    parser.add_argument("--context", default="",
                        help="Optional extra context (day number, market signal)")
    args = parser.parse_args()

    summary = run_agent(
        args.skill,
        args.workdir.resolve(),
        model=args.model,
        extra_context=args.context,
        backend=args.backend,
    )
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
