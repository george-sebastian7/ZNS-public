import os
import subprocess
import re
import uuid
from pathlib import Path

from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder="templates", static_folder="static")

GEMINI_MODEL = "gemini-3.6-flash"
CLAUDE_MODEL = "claude-sonnet-4-5-20241022"

gemini_client = None
claude_client = None

OUTPUT_DIR = Path(__file__).parent / "generated_code"
OUTPUT_DIR.mkdir(exist_ok=True)


def get_gemini_client():
    global gemini_client
    if gemini_client is None:
        from google import genai
        gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return gemini_client


def get_claude_client():
    global claude_client
    if claude_client is None:
        import anthropic
        claude_client = anthropic.Anthropic(api_key=os.environ["CLAUDE_API_KEY"])
    return claude_client


@app.route("/")
def index():
    providers = []
    if os.environ.get("GEMINI_API_KEY"):
        providers.append("gemini")
    if os.environ.get("CLAUDE_API_KEY"):
        providers.append("claude")
    return render_template("index.html", providers=providers)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    prompt = data.get("prompt", "").strip()
    mode = data.get("mode", "answer")
    provider = data.get("provider", "gemini")

    if not prompt:
        return jsonify({"error": "Prompt is empty."}), 400

    try:
        if mode == "answer":
            return _handle_answer(prompt, provider)
        elif mode == "code":
            return _handle_code(prompt, provider)
        else:
            return jsonify({"error": f"Unknown mode: {mode}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _call_gemini(prompt: str, system: str | None = None) -> str:
    c = get_gemini_client()
    contents = [system, prompt] if system else prompt
    response = c.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
    )
    return response.text


def _call_claude(prompt: str, system: str | None = None) -> str:
    c = get_claude_client()
    kwargs = {
        "model": CLAUDE_MODEL,
        "max_tokens": 16000,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    response = c.messages.create(**kwargs)
    return next(
        (block.text for block in response.content if block.type == "text"), ""
    )


def _generate(prompt: str, provider: str, system: str | None = None) -> str:
    if provider == "claude":
        return _call_claude(prompt, system)
    return _call_gemini(prompt, system)


def _handle_answer(prompt: str, provider: str):
    text = _generate(prompt, provider)
    return jsonify({"type": "answer", "response": text, "provider": provider})


def _handle_code(prompt: str, provider: str):
    system_prompt = (
        "You are a code generator. The user will describe what they want. "
        "Respond ONLY with the code, no explanations, no markdown fences. "
        "Also include a comment on the first line: # filename: <suggested_filename> "
        "Choose an appropriate filename with the correct extension for the language."
    )
    code = _generate(prompt, provider, system=system_prompt).strip()

    code = re.sub(r"^```[a-zA-Z]*\n?", "", code)
    code = re.sub(r"\n?```$", "", code)
    code = code.strip()

    filename = _extract_filename(code)
    filepath = OUTPUT_DIR / filename
    filepath.write_text(code, encoding="utf-8")

    run_output, success = _try_run(filepath)

    return jsonify({
        "type": "code",
        "code": code,
        "filename": filename,
        "filepath": str(filepath),
        "run_output": run_output,
        "run_success": success,
        "provider": provider,
    })


def _extract_filename(code: str) -> str:
    first_line = code.split("\n", 1)[0]
    match = re.search(r"filename:\s*(\S+)", first_line, re.IGNORECASE)
    if match:
        name = match.group(1)
        name = re.sub(r"[^\w.\-]", "_", name)
        return name
    return f"script_{uuid.uuid4().hex[:8]}.py"


def _try_run(filepath: Path) -> tuple[str, bool]:
    ext = filepath.suffix.lower()
    runners = {
        ".py": ["python3", str(filepath)],
        ".js": ["node", str(filepath)],
        ".sh": ["bash", str(filepath)],
    }
    cmd = runners.get(ext)
    if cmd is None:
        return f"No runner configured for {ext} files. File saved to {filepath}.", False

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
            cwd=str(filepath.parent),
        )
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        output = output.strip()
        if not output:
            output = "(no output)"
        return output, result.returncode == 0
    except subprocess.TimeoutExpired:
        return "Execution timed out (15s limit).", False
    except Exception as e:
        return f"Failed to run: {e}", False
