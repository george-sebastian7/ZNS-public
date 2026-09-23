class BaseAgent:
    """Abstract base class that all generated agents must implement."""

    AGENT_TYPE = "base"

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    def decide(self, sensor_data: dict) -> dict:
        """
        Receives sensor JSON, returns an action dict.

        sensor_data format:
        {
            "grid": [[{cell}, ...], ...],   # 9x9 grid, agent at center [4][4]
            "self": {
                "position": [row, col],
                "energy": int,
                "carrying": null | "red" | "blue" | ...,
                "credits": int
            }
        }

        Each cell:
        {
            "type": "free" | "wall" | "box" | "agent",
            "energy_cost": "low" | "medium" | "high",
            "drop_off": bool,
            "box_color": null | "red" | "blue" | "yellow" | "green" | "orange" | "purple",
            "agent_id": null | str
        }

        Return one of:
            {"action": "move", "direction": "up"|"down"|"left"|"right"}
            {"action": "pickup"}
            {"action": "drop"}
            {"action": "noop"}
        """
        raise NotImplementedError

    def __repr__(self):
        return f"{self.__class__.__name__}({self.agent_id!r})"
