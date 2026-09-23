import logging
import random

from .grid import Grid
from .entities import Box, AgentState
from .rules import (
    ENERGY_COSTS, BOX_CREDITS, BOX_COLORS, DROPOFF_SIZE,
    SENSOR_RANGE, STARTING_ENERGY, apply_box_mutations,
)

logger = logging.getLogger("simulator")


class SimulationEngine:
    def __init__(self, grid_size: int = 20, num_boxes: int = 15):
        self.grid = Grid(grid_size, grid_size)
        self.agents: dict[str, AgentState] = {}
        self.boxes: dict[tuple[int, int], Box] = {}
        self.tick = 0
        self.running = False
        self.events: list[dict] = []
        self._place_boxes(num_boxes)

    def reset(self, grid_size: int = 20, num_boxes: int = 15):
        self.grid = Grid(grid_size, grid_size)
        self.agents.clear()
        self.boxes.clear()
        self.tick = 0
        self.running = False
        self.events.clear()
        self._place_boxes(num_boxes)
        logger.info("Simulation reset: grid=%dx%d, boxes=%d", grid_size, grid_size, num_boxes)

    def _place_boxes(self, count: int):
        placed = 0
        attempts = 0
        while placed < count and attempts < count * 10:
            r = random.randint(0, self.grid.height - 1)
            c = random.randint(0, self.grid.width - 1)
            attempts += 1
            if not self.grid.is_walkable(r, c):
                continue
            if self.grid.is_dropoff(r, c):
                continue
            if (r, c) in self.boxes:
                continue
            weights = [0.2, 0.3, 0.15, 0.15, 0.1, 0.1]
            color = random.choices(BOX_COLORS, weights=weights, k=1)[0]
            self.boxes[(r, c)] = Box(row=r, col=c, color=color)
            placed += 1

    def add_agent(self, agent_id: str, agent_type: str) -> AgentState:
        r, c = self._find_free_spawn()
        state = AgentState(
            agent_id=agent_id,
            agent_type=agent_type,
            row=r, col=c,
            energy=STARTING_ENERGY,
        )
        self.agents[agent_id] = state
        logger.info("Agent added: %s (%s) at (%d,%d)", agent_id, agent_type, r, c)
        return state

    def remove_agent(self, agent_id: str):
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info("Agent removed: %s", agent_id)

    def _find_free_spawn(self) -> tuple[int, int]:
        occupied = {(a.row, a.col) for a in self.agents.values()}
        box_positions = set(self.boxes.keys())
        for _ in range(1000):
            r = random.randint(DROPOFF_SIZE, self.grid.height - 1)
            c = random.randint(DROPOFF_SIZE, self.grid.width - 1)
            if self.grid.is_walkable(r, c) and (r, c) not in occupied and (r, c) not in box_positions:
                return (r, c)
        return (DROPOFF_SIZE, DROPOFF_SIZE)

    def get_sensor_data(self, agent_id: str) -> dict:
        agent = self.agents[agent_id]
        grid_view = []
        occupied_agents = {(a.row, a.col): a.agent_id for a in self.agents.values()}

        for dr in range(-SENSOR_RANGE, SENSOR_RANGE + 1):
            row_data = []
            for dc in range(-SENSOR_RANGE, SENSOR_RANGE + 1):
                r, c = agent.row + dr, agent.col + dc
                if not (0 <= r < self.grid.height and 0 <= c < self.grid.width):
                    row_data.append({
                        "type": "wall",
                        "energy_cost": "high",
                        "drop_off": False,
                        "box_color": None,
                        "agent_id": None,
                    })
                    continue

                cell = {
                    "type": self.grid.cells[r][c],
                    "energy_cost": self.grid.energy_map[r][c],
                    "drop_off": self.grid.is_dropoff(r, c),
                    "box_color": None,
                    "agent_id": None,
                }

                if (r, c) in self.boxes:
                    cell["type"] = "box"
                    cell["box_color"] = self.boxes[(r, c)].color
                elif (r, c) in occupied_agents and occupied_agents[(r, c)] != agent_id:
                    cell["type"] = "agent"
                    cell["agent_id"] = occupied_agents[(r, c)]

                row_data.append(cell)
            grid_view.append(row_data)

        return {
            "grid": grid_view,
            "self": {
                "position": [agent.row, agent.col],
                "energy": agent.energy,
                "carrying": agent.carrying,
                "credits": agent.credits,
            },
        }

    def process_action(self, agent_id: str, action: dict) -> dict:
        agent = self.agents.get(agent_id)
        if not agent or not agent.alive:
            return {"success": False, "reason": "agent_dead"}

        action_type = action.get("action", "noop")
        result = {"success": False, "reason": "unknown"}

        if action_type == "move":
            result = self._do_move(agent, action.get("direction", ""))
        elif action_type == "pickup":
            result = self._do_pickup(agent)
        elif action_type == "drop":
            result = self._do_drop(agent)
        elif action_type == "noop":
            result = {"success": True, "reason": "noop"}

        if agent.energy <= 0:
            agent.alive = False
            logger.info("Agent %s ran out of energy. Credits: %d", agent_id, agent.credits)

        return result

    def _do_move(self, agent: AgentState, direction: str) -> dict:
        deltas = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
        if direction not in deltas:
            return {"success": False, "reason": "invalid_direction"}

        dr, dc = deltas[direction]
        nr, nc = agent.row + dr, agent.col + dc

        if not self.grid.is_walkable(nr, nc):
            return {"success": False, "reason": "wall"}

        occupied = {(a.row, a.col) for aid, a in self.agents.items() if aid != agent.agent_id}
        if (nr, nc) in occupied:
            return {"success": False, "reason": "occupied_by_agent"}

        cost_level = self.grid.get_energy_cost(nr, nc)
        cost = ENERGY_COSTS[cost_level]
        agent.energy -= cost
        agent.row = nr
        agent.col = nc

        logger.debug("Agent %s moved %s to (%d,%d), energy=%d", agent.agent_id, direction, nr, nc, agent.energy)
        return {"success": True, "energy_spent": cost}

    def _do_pickup(self, agent: AgentState) -> dict:
        if agent.carrying is not None:
            return {"success": False, "reason": "already_carrying"}

        pos = (agent.row, agent.col)
        if pos not in self.boxes:
            return {"success": False, "reason": "no_box_here"}

        box = self.boxes.pop(pos)
        agent.carrying = box.color
        logger.info("Agent %s picked up %s box at (%d,%d)", agent.agent_id, box.color, agent.row, agent.col)
        return {"success": True, "box_color": box.color}

    def _do_drop(self, agent: AgentState) -> dict:
        if agent.carrying is None:
            return {"success": False, "reason": "not_carrying"}

        pos = (agent.row, agent.col)
        if pos in self.boxes:
            return {"success": False, "reason": "box_already_here"}

        color = agent.carrying
        agent.carrying = None

        if self.grid.is_dropoff(agent.row, agent.col):
            earned = BOX_CREDITS.get(color, 0)
            agent.credits += earned
            logger.info("Agent %s delivered %s box at dropoff (%d,%d), +%d credits (total: %d)",
                        agent.agent_id, color, agent.row, agent.col, earned, agent.credits)
            return {"success": True, "delivered": True, "credits_earned": earned}
        else:
            self.boxes[pos] = Box(row=agent.row, col=agent.col, color=color)
            logger.debug("Agent %s dropped %s box at (%d,%d)", agent.agent_id, color, agent.row, agent.col)
            return {"success": True, "delivered": False}

    def step(self) -> list[dict]:
        self.tick += 1
        mutation_events = apply_box_mutations(self.boxes, self.tick, self.grid)
        self.events.extend(mutation_events)
        return mutation_events

    def get_full_state(self) -> dict:
        return {
            "tick": self.tick,
            "grid_size": self.grid.width,
            "grid": self.grid.to_dict(),
            "boxes": {f"{r},{c}": b.to_dict() for (r, c), b in self.boxes.items()},
            "agents": {aid: a.to_dict() for aid, a in self.agents.items()},
            "running": self.running,
        }

    def all_agents_dead(self) -> bool:
        return all(not a.alive for a in self.agents.values()) if self.agents else False
