import json
import logging
import os
import sys
import threading
import time
import importlib.util

from flask import Flask, render_template, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator import SimulationEngine

app = Flask(__name__, template_folder="templates", static_folder="static")
logger = logging.getLogger("visualizer")

engine = None
engine_lock = threading.Lock()
sim_thread = None
sim_running = False
sim_speed = "realtime"
sim_step_event = threading.Event()

AGENT_TYPES = ["simple_reflex", "model_reflex", "goal_based", "utility_based", "learning"]


def load_agent_class(agent_type: str):
    agents_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")
    filepath = os.path.join(agents_dir, f"{agent_type}.py")
    if not os.path.exists(filepath):
        return None
    spec = importlib.util.spec_from_file_location(agent_type, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, type) and hasattr(obj, "decide") and attr != "BaseAgent":
            return obj
    return None


agent_instances = {}


def reset_engine(grid_size=20, num_boxes=15, selected_agents=None):
    global engine, agent_instances
    engine = SimulationEngine(grid_size=grid_size, num_boxes=num_boxes)
    agent_instances = {}

    if selected_agents is None:
        selected_agents = AGENT_TYPES

    for agent_type in selected_agents:
        cls = load_agent_class(agent_type)
        if cls is None:
            logger.warning("No generated code for agent type: %s", agent_type)
            continue
        agent_id = f"agent_{agent_type}"
        try:
            agent_instances[agent_id] = cls(agent_id=agent_id)
            engine.add_agent(agent_id, agent_type)
            logger.info("Loaded agent: %s (%s)", agent_id, agent_type)
        except Exception as e:
            logger.error("Failed to instantiate %s: %s", agent_type, e)


def simulation_loop():
    global sim_running
    tick = 0
    while sim_running:
        if engine is None:
            break

        if sim_speed == "step":
            sim_step_event.wait()
            sim_step_event.clear()
            if not sim_running:
                break

        with engine_lock:
            for agent_id, agent_obj in list(agent_instances.items()):
                if agent_id not in engine.agents or not engine.agents[agent_id].alive:
                    continue
                try:
                    sensor_data = engine.get_sensor_data(agent_id)
                    action = agent_obj.decide(sensor_data)
                    if isinstance(action, dict) and "action" in action:
                        engine.process_action(agent_id, action)
                except Exception as e:
                    logger.error("Agent %s error at tick %d: %s", agent_id, tick, e)

            engine.step()
            tick += 1

            if engine.all_agents_dead():
                logger.info("All agents dead at tick %d", tick)
                sim_running = False
                break

        if sim_speed == "realtime":
            time.sleep(0.3)
        elif sim_speed == "fast":
            time.sleep(0.05)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state", methods=["GET"])
def api_state():
    if engine is None:
        return jsonify({"error": "No simulation running"}), 400
    with engine_lock:
        raw = engine.get_full_state()

    walls = []
    grid_data = raw.get("grid", [])
    for r, row in enumerate(grid_data):
        for c, cell in enumerate(row):
            if cell["type"] == "wall":
                walls.append([r, c])

    boxes = list(raw.get("boxes", {}).values())

    result = {
        "tick": raw["tick"],
        "grid_size": raw["grid_size"],
        "walls": walls,
        "boxes": boxes,
        "agents": raw["agents"],
        "running": sim_running,
        "speed": sim_speed,
    }
    return jsonify(result)


@app.route("/api/start", methods=["POST"])
def api_start():
    global sim_thread, sim_running, sim_speed
    data = request.get_json() or {}
    grid_size = data.get("grid_size", 20)
    selected = data.get("agents", None)
    speed = data.get("speed", "realtime")

    if sim_running:
        return jsonify({"error": "Already running"}), 400

    sim_speed = speed
    reset_engine(grid_size=grid_size, selected_agents=selected)

    if not agent_instances:
        return jsonify({"error": "No agents loaded. Generate agents first."}), 400

    sim_running = True
    sim_thread = threading.Thread(target=simulation_loop, daemon=True)
    sim_thread.start()
    logger.info("Simulation started: grid=%d, agents=%s, speed=%s",
                grid_size, list(agent_instances.keys()), speed)
    return jsonify({"status": "started", "agents": list(agent_instances.keys())})


@app.route("/api/pause", methods=["POST"])
def api_pause():
    global sim_running
    sim_running = False
    return jsonify({"status": "paused"})


@app.route("/api/resume", methods=["POST"])
def api_resume():
    global sim_thread, sim_running
    if engine is None:
        return jsonify({"error": "No simulation to resume"}), 400
    if sim_running:
        return jsonify({"error": "Already running"}), 400
    sim_running = True
    sim_thread = threading.Thread(target=simulation_loop, daemon=True)
    sim_thread.start()
    return jsonify({"status": "resumed"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    global sim_running, engine
    sim_running = False
    sim_step_event.set()
    engine = None
    return jsonify({"status": "stopped"})


@app.route("/api/step", methods=["POST"])
def api_step():
    if engine is None:
        return jsonify({"error": "No simulation running"}), 400
    sim_step_event.set()
    return jsonify({"status": "stepped"})


@app.route("/api/speed", methods=["POST"])
def api_speed():
    global sim_speed
    data = request.get_json() or {}
    sim_speed = data.get("speed", "realtime")
    return jsonify({"speed": sim_speed})


@app.route("/api/agents/available", methods=["GET"])
def api_available_agents():
    available = []
    for at in AGENT_TYPES:
        cls = load_agent_class(at)
        available.append({"type": at, "loaded": cls is not None})
    return jsonify(available)
