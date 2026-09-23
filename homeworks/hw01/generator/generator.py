import logging
import os
from pathlib import Path

import anthropic

from .prompts import AGENT_PROMPTS, DEBUG_PROMPT
from .validator import clean_code, validate_syntax, validate_structure

logger = logging.getLogger("generator")

AGENTS_DIR = Path(__file__).parent.parent / "agents"
GENERATED_DIR = Path(__file__).parent.parent / "generated"

MAX_DEBUG_ITERATIONS = 5


def generate_agent(agent_type: str) -> dict:
    """
    Use Claude API to generate agent code.
    Returns {"success": bool, "code": str, "filepath": str, "iterations": int, "error": str|None}
    """
    if agent_type not in AGENT_PROMPTS:
        return {"success": False, "code": "", "filepath": "", "iterations": 0,
                "error": f"Unknown agent type: {agent_type}"}

    client = anthropic.Anthropic(api_key=os.environ["CLAUDE_API_KEY"])
    prompt = AGENT_PROMPTS[agent_type]

    logger.info("Generating %s agent...", agent_type)

    code = _call_claude(client, prompt)
    code = clean_code(code)

    _save_snapshot(agent_type, code, 0)

    for iteration in range(1, MAX_DEBUG_ITERATIONS + 1):
        error = validate_syntax(code)
        if error is None:
            error = validate_structure(code)
        if error is None:
            filepath = _save_agent(agent_type, code)
            logger.info("Agent %s generated successfully after %d iterations. Saved to %s",
                        agent_type, iteration, filepath)
            return {"success": True, "code": code, "filepath": str(filepath),
                    "iterations": iteration, "error": None}

        logger.warning("Agent %s iteration %d error: %s", agent_type, iteration, error)

        debug_prompt = DEBUG_PROMPT.format(error=error, code=code)
        code = _call_claude(client, debug_prompt)
        code = clean_code(code)
        _save_snapshot(agent_type, code, iteration)

    filepath = _save_agent(agent_type, code)
    final_error = validate_syntax(code) or validate_structure(code)
    logger.error("Agent %s failed after %d debug iterations. Last error: %s",
                 agent_type, MAX_DEBUG_ITERATIONS, final_error)
    return {"success": False, "code": code, "filepath": str(filepath),
            "iterations": MAX_DEBUG_ITERATIONS, "error": final_error}


def _call_claude(client: anthropic.Anthropic, prompt: str) -> str:
    model = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    response = client.messages.create(
        model=model,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    logger.debug("Claude response length: %d chars", len(text))
    return text


def _save_agent(agent_type: str, code: str) -> Path:
    filepath = AGENTS_DIR / f"{agent_type}.py"
    filepath.write_text(code, encoding="utf-8")
    return filepath


def _save_snapshot(agent_type: str, code: str, iteration: int):
    GENERATED_DIR.mkdir(exist_ok=True)
    path = GENERATED_DIR / f"{agent_type}_v{iteration}.py"
    path.write_text(code, encoding="utf-8")
    logger.debug("Snapshot saved: %s", path)
