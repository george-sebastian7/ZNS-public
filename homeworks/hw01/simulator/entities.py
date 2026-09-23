from dataclasses import dataclass, field


@dataclass
class Box:
    row: int
    col: int
    color: str
    age: int = 0

    def to_dict(self):
        return {"row": self.row, "col": self.col, "color": self.color}


@dataclass
class AgentState:
    agent_id: str
    agent_type: str
    row: int
    col: int
    energy: int = 500
    carrying: str | None = None
    credits: int = 0
    alive: bool = True

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "row": self.row,
            "col": self.col,
            "energy": self.energy,
            "carrying": self.carrying,
            "credits": self.credits,
            "alive": self.alive,
        }
