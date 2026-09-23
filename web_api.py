import os
import subprocess
import tempfile
import re
import uuid
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from google import genai

app = Flask(__name__, template_folder="templates", static_folder="static")

client = None

def get_client():
    global client
    if client is None:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return client

OUTPUT_DIR = Path(__file__).parent / "generated_code"
OUTPUT_DIR.mkdir(exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    prompt = data.get("prompt", "").strip()
    mode = data.get("mode", "answer")

    if not prompt:
        return jsonify({"error": "Prompt is empty."}), 400

    try:
        if mode == "answer":
            return _handle_answer(prompt)
        elif mode == "code":
            return _handle_code(prompt)
        else:
            return jsonify({"error": f"Unknown mode: {mode}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _handle_answer(prompt: str):
    c = get_client()
    response = c.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return jsonify({"type": "answer", "response": response.text})


def _handle_code(prompt: str):
    c = get_client()
    system_prompt = (
        "You are a code generator. The user will describe what they want. "
        "Respond ONLY with the code, no explanations, no markdown fences. "
        "Also include a comment on the first line: # filename: <suggested_filename> "
        "Choose an appropriate filename with the correct extension for the language."
    )
    response = c.models.generate_content(
        model="gemini-2.0-flash",
        contents=[system_prompt, prompt],
    )
    code = response.text.strip()

    # strip markdown fences if present
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
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
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
