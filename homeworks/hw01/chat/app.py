import logging
import os
import sys

from flask import Flask, render_template, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator.generator import generate_agent
from generator.debugger import test_agent_in_simulator

app = Flask(__name__, template_folder="templates", static_folder="static")
logger = logging.getLogger("chat")

AGENT_TYPES = ["simple_reflex", "model_reflex", "goal_based", "utility_based", "learning"]


@app.route("/")
def index():
    return render_template("index.html", agent_types=AGENT_TYPES)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json()
    agent_type = data.get("agent_type", "")

    if agent_type not in AGENT_TYPES:
        return jsonify({"error": f"Unknown agent type: {agent_type}"}), 400

    logger.info("Generating agent: %s", agent_type)
    result = generate_agent(agent_type)

    if result["success"]:
        test_result = test_agent_in_simulator(result["code"], agent_type)
        result["test"] = test_result
        if not test_result["success"]:
            logger.warning("Generated agent failed test: %s", test_result["error"])

    return jsonify(result)


@app.route("/api/agents", methods=["GET"])
def api_list_agents():
    """List which agent files exist."""
    from pathlib import Path
    agents_dir = Path(__file__).parent.parent / "agents"
    available = []
    for at in AGENT_TYPES:
        filepath = agents_dir / f"{at}.py"
        available.append({"type": at, "exists": filepath.exists()})
    return jsonify(available)
