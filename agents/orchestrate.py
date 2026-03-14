#!/usr/bin/env python3
"""
Energy Market Dashboard — Multi-Agent Orchestration

Demonstrates how three specialized AI agents collaborate on a real project:

  ┌──────────────────────────────────────────────────────────┐
  │  COORDINATOR  →  DEVELOPER  →  TEST AGENT               │
  │                                                          │
  │  Reads specs    Analyzes      Validates data scripts     │
  │  Produces task  codebase &    and dashboard code,        │
  │  breakdown      documents     reports findings           │
  │                 decisions                                │
  └──────────────────────────────────────────────────────────┘

Each agent has a distinct system prompt, allowed tools, and responsibility.
The orchestrator runs them in sequence, captures their reasoning, and
writes a structured log to AGENTS.md for human review.

Run:
  pip install claude-agent-sdk
  export ANTHROPIC_API_KEY=sk-ant-...
  python agents/orchestrate.py

The script reads the existing project files and produces an AGENTS.md
report documenting each agent's analysis and decisions.
"""

import anyio
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path

try:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AgentDefinition,
        ResultMessage,
        SystemMessage,
    )
except ImportError:
    print("ERROR: claude-agent-sdk is not installed.")
    print("Install with: pip install claude-agent-sdk")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_LOG   = PROJECT_ROOT / "AGENTS.md"


# ── Agent system prompts ─────────────────────────────────────────────────────

COORDINATOR_SYSTEM = """\
You are the Coordinator Agent for the Norwegian Energy Market Dashboard project.

Your role is to:
1. Read the project requirements and existing code structure
2. Break the project into a clear specification with tasks for each component
3. Identify the three data sources and what each fetches
4. Document API choices and the reasoning behind them
5. Produce a structured task breakdown that a developer agent could follow

Be precise and analytical. Focus on the "why" behind each decision, not just the "what".
Your output will be read by the Developer Agent and logged to AGENTS.md.

Format your response as:
## Project Overview
[2-3 sentences]

## Data Source Decisions
[For each data source: what it is, which API, why that API was chosen]

## Component Breakdown
[List of components: data fetchers, dashboard, GitHub Actions — with brief description]

## Key Architectural Decisions
[Design choices made and the reasoning]
"""

DEVELOPER_SYSTEM = """\
You are the Developer Agent for the Norwegian Energy Market Dashboard project.

Your role is to:
1. Analyze the actual implementation files that have been created
2. Document the key technical decisions made in each file
3. Explain how the components fit together
4. Note any important patterns or techniques used
5. Identify the reasoning behind CSS/JS/Python implementation choices

Be technical but clear. Focus on explaining WHY things are implemented the way they are.
Your output will be logged to AGENTS.md for the project owner to understand.

Format your response as:
## Implementation Analysis

### Data Layer (Python scripts)
[How the three fetch scripts work, error handling approach, data format]

### Frontend (HTML/CSS/JS)
[Dashboard architecture, Chart.js usage, dark theme decisions, responsive design]

### GitHub Actions (CI/CD)
[How the daily refresh workflow operates]

### Agent SDK Integration
[How this orchestration script itself demonstrates multi-agent patterns]
"""

TEST_SYSTEM = """\
You are the Test Agent for the Norwegian Energy Market Dashboard project.

Your role is to:
1. Examine the Python data fetch scripts for correctness and robustness
2. Check the JavaScript dashboard code for potential issues
3. Verify the GitHub Actions workflow is correctly structured
4. Identify any edge cases or failure modes that should be handled
5. Suggest specific improvements (be concrete, not generic)

Be critical but constructive. Your findings help the project owner understand
what works well and what could fail in production.

Format your response as:
## Test Report

### Data Fetch Scripts — Analysis
[For each script: what it tests, potential failure modes, error handling quality]

### Dashboard JavaScript — Analysis
[Chart initialization, data loading, error states, browser compatibility notes]

### GitHub Actions — Analysis
[Workflow correctness, secret management, failure recovery]

### Recommended Improvements
[Concrete, specific suggestions — not generic advice]

### Overall Assessment
[1-2 sentences on production readiness]
"""


# ── Individual agent runners ─────────────────────────────────────────────────

async def run_coordinator() -> str:
    """
    Coordinator agent: reads project files and produces a task specification.
    Uses Read, Glob, Grep tools to understand the codebase.
    """
    print("🎯 Running Coordinator Agent...")

    prompt = f"""\
Analyze the Norwegian Energy Market Dashboard project located at {PROJECT_ROOT}.

Read the key project files:
- scripts/fetch_prices.py
- scripts/fetch_exchange.py
- scripts/fetch_reservoirs.py
- docs/index.html
- .github/workflows/update-data.yml (if it exists)
- README.md (if it exists)

Then produce a structured project specification documenting:
1. The three data sources and which APIs were chosen (and why)
2. The dashboard architecture
3. The GitHub Actions deployment strategy
4. The multi-agent orchestration approach

Focus on explaining the REASONING behind key decisions.
"""

    result_text = ""
    async for msg in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            cwd=str(PROJECT_ROOT),
            allowed_tools=["Read", "Glob", "Grep"],
            system_prompt=COORDINATOR_SYSTEM,
            max_turns=12,
        ),
    ):
        if isinstance(msg, ResultMessage):
            result_text = msg.result
        elif isinstance(msg, SystemMessage) and msg.subtype == "init":
            print(f"   Session: {msg.data.get('session_id', 'unknown')[:12]}...")

    print("   ✓ Coordinator complete")
    return result_text


async def run_developer(coordinator_output: str) -> str:
    """
    Developer agent: analyses the implementation and documents decisions.
    Has read access to understand the codebase deeply.
    """
    print("🔨 Running Developer Agent...")

    prompt = f"""\
The Coordinator Agent has produced this project specification:

---
{coordinator_output[:3000]}
---

Now examine the actual implementation at {PROJECT_ROOT}.

Read these files and analyze the implementation:
- scripts/fetch_prices.py (electricity price fetching)
- scripts/fetch_exchange.py (NOK/USD exchange rates)
- scripts/fetch_reservoirs.py (hydroelectric reservoir levels)
- docs/css/style.css (dark theme, CSS variables)
- docs/js/dashboard.js (Chart.js visualization logic)
- docs/index.html (dashboard structure)

For each component, explain:
1. The key technical patterns and approaches used
2. Why the implementation was structured this way
3. How error handling and resilience are managed
4. The data flow from API → JSON → chart
"""

    result_text = ""
    async for msg in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            cwd=str(PROJECT_ROOT),
            allowed_tools=["Read", "Glob", "Grep"],
            system_prompt=DEVELOPER_SYSTEM,
            max_turns=15,
        ),
    ):
        if isinstance(msg, ResultMessage):
            result_text = msg.result
        elif isinstance(msg, SystemMessage) and msg.subtype == "init":
            print(f"   Session: {msg.data.get('session_id', 'unknown')[:12]}...")

    print("   ✓ Developer complete")
    return result_text


async def run_test_agent(developer_output: str) -> str:
    """
    Test agent: validates correctness and identifies potential issues.
    """
    print("🧪 Running Test Agent...")

    prompt = f"""\
The Developer Agent documented this implementation:

---
{developer_output[:3000]}
---

Now perform a thorough review of the project at {PROJECT_ROOT}.

Read and critically evaluate:
- scripts/fetch_prices.py — check API usage, error handling, data parsing
- scripts/fetch_exchange.py — check SDMX-JSON parsing, weekend/holiday filling
- scripts/fetch_reservoirs.py — check NVE API response parsing, field name handling
- docs/js/dashboard.js — check data loading, chart initialization, error states
- .github/workflows/update-data.yml — check workflow trigger, secrets, commit logic

For each file, identify:
1. Specific lines or patterns that could fail in production
2. Missing error handling or edge cases
3. What works well and why

Be specific — reference actual code patterns, not generic advice.
"""

    result_text = ""
    async for msg in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            cwd=str(PROJECT_ROOT),
            allowed_tools=["Read", "Glob", "Grep"],
            system_prompt=TEST_SYSTEM,
            max_turns=15,
        ),
    ):
        if isinstance(msg, ResultMessage):
            result_text = msg.result
        elif isinstance(msg, SystemMessage) and msg.subtype == "init":
            print(f"   Session: {msg.data.get('session_id', 'unknown')[:12]}...")

    print("   ✓ Test Agent complete")
    return result_text


# ── AGENTS.md writer ─────────────────────────────────────────────────────────

def write_agents_log(coordinator: str, developer: str, tester: str) -> None:
    """Write the combined agent outputs to AGENTS.md."""

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    content = f"""\
# Agent Work Log — Norwegian Energy Market Dashboard

> Generated {now} by running `python agents/orchestrate.py`
>
> This file documents how three specialized AI agents analyzed and built
> this project. Each agent had distinct responsibilities and tools.

---

## Agent Architecture

```
COORDINATOR AGENT
  Role: Requirement analysis & task specification
  Tools: Read, Glob, Grep (read-only)
  Output: Structured project spec with API decisions
       ↓
DEVELOPER AGENT
  Role: Implementation analysis & decision documentation
  Tools: Read, Glob, Grep (read-only)
  Input: Coordinator's spec + actual source files
  Output: Technical documentation of implementation choices
       ↓
TEST AGENT
  Role: Validation, edge-case analysis, improvement suggestions
  Tools: Read, Glob, Grep (read-only)
  Input: Developer's analysis + actual source files
  Output: Test report with production-readiness assessment
```

---

## Coordinator Agent Output

{coordinator}

---

## Developer Agent Output

{developer}

---

## Test Agent Output

{tester}

---

## How This Demonstrates Role-Based AI Agents

Each agent in this pipeline mirrors a real software team role:

| Agent | Team Role | Responsibility | Tools |
|-------|-----------|----------------|-------|
| Coordinator | Tech Lead / Architect | Breaks down requirements, specifies APIs, defines architecture | Read, Glob, Grep |
| Developer | Senior Engineer | Analyzes implementation, documents technical decisions | Read, Glob, Grep |
| Test Agent | QA Engineer | Reviews for correctness, edge cases, production issues | Read, Glob, Grep |

The agents **pass context forward** — each receives the previous agent's
output as part of their prompt, simulating how a real team communicates.

### Running the Orchestration

```bash
pip install claude-agent-sdk
export ANTHROPIC_API_KEY=sk-ant-...
python agents/orchestrate.py
```

This regenerates AGENTS.md with fresh analysis. The script uses the
[Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python)
which provides built-in file access tools, safety guardrails, and
session management for each agent.
"""

    AGENTS_LOG.write_text(content, encoding="utf-8")
    print(f"\n✓ Written → {AGENTS_LOG}")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("Norwegian Energy Market Dashboard")
    print("Multi-Agent Orchestration Demo")
    print("=" * 60)
    print()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("Get your key at https://console.anthropic.com")
        sys.exit(1)

    print("Running 3 agents in sequence: Coordinator → Developer → Tester")
    print("Each agent reads the project files and documents its analysis.\n")

    coordinator_output = await run_coordinator()
    developer_output   = await run_developer(coordinator_output)
    tester_output      = await run_test_agent(developer_output)

    write_agents_log(coordinator_output, developer_output, tester_output)

    print("\n" + "=" * 60)
    print("Orchestration complete!")
    print(f"Agent work log: {AGENTS_LOG}")
    print()
    print("What each agent did:")
    print("  🎯 Coordinator — analyzed requirements and API choices")
    print("  🔨 Developer   — documented implementation decisions")
    print("  🧪 Test Agent  — reviewed for production issues")
    print()
    print("See AGENTS.md for the full agent reasoning log.")


if __name__ == "__main__":
    anyio.run(main)
