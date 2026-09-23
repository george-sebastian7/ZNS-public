import logging
import traceback

from simulator import SimulationEngine
from .validator import try_import

logger = logging.getLogger("generator")


def test_agent_in_simulator(code: str, agent_type: str, max_ticks: int = 20) -> dict:
    """
    Run the generated agent for a few ticks in a small simulator.
    Returns {"success": bool, "error": str|None, "ticks_completed": int, "credits": int}
    """
    agent_class, import_error = try_import(code, agent_type)
    if import_error:
        return {"success": False, "error": import_error, "ticks_completed": 0, "credits": 0}

    try:
        engine = SimulationEngine(grid_size=20, num_boxes=10)
        agent_obj = agent_class(agent_id="test_agent")
        engine.add_agent("test_agent", agent_type)

        for tick in range(max_ticks):
            sensor_data = engine.get_sensor_data("test_agent")
            action = agent_obj.decide(sensor_data)

            if not isinstance(action, dict) or "action" not in action:
                return {
                    "success": False,
                    "error": f"Tick {tick}: decide() returned invalid action: {action!r}",
                    "ticks_completed": tick,
                    "credits": engine.agents["test_agent"].credits,
                }

            engine.process_action("test_agent", action)
            engine.step()

            if not engine.agents["test_agent"].alive:
                break

        agent_state = engine.agents["test_agent"]
        logger.info("Test run: %d ticks, %d credits, energy=%d",
                    tick + 1, agent_state.credits, agent_state.energy)
        return {
            "success": True,
            "error": None,
            "ticks_completed": tick + 1,
            "credits": agent_state.credits,
        }

    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Agent test failed: %s\n%s", e, tb)
        return {"success": False, "error": f"{e}\n{tb}", "ticks_completed": 0, "credits": 0}
