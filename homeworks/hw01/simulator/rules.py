import random

ENERGY_COSTS = {"low": 1, "medium": 3, "high": 5}

BOX_CREDITS = {"red": 10, "blue": 5, "yellow": 0, "green": 0, "orange": 0, "purple": 0}

BOX_COLORS = ["red", "blue", "yellow", "green", "orange", "purple"]

MUTATION_DELAY = 5
GREEN_RED_SPAWN_PROBABILITY = 0.9
GREEN_RED_SPAWN_DELAY = 8
GREEN_RED_SPAWN_RADIUS = 3

STARTING_ENERGY = 500
DROPOFF_SIZE = 4
SENSOR_RANGE = 4


def apply_box_mutations(boxes: dict, tick: int, grid) -> list[dict]:
    """Apply box color mutation rules. Returns list of events."""
    events = []
    positions = {(b.row, b.col): b for b in boxes.values()}
    to_remove = []
    to_add = []

    for key, box in list(boxes.items()):
        if box.color == "red":
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                neighbor = positions.get((box.row + dr, box.col + dc))
                if neighbor and neighbor.color == "yellow":
                    if box.age >= MUTATION_DELAY:
                        box.color = "orange"
                        events.append({
                            "type": "mutation",
                            "tick": tick,
                            "position": [box.row, box.col],
                            "from": "red",
                            "to": "orange",
                        })
                    break

        if box.color == "green" and box.age == GREEN_RED_SPAWN_DELAY:
            if random.random() < GREEN_RED_SPAWN_PROBABILITY:
                spawn_pos = _find_spawn_position(
                    box.row, box.col, GREEN_RED_SPAWN_RADIUS, positions, grid
                )
                if spawn_pos:
                    to_add.append(spawn_pos)
                    events.append({
                        "type": "spawn",
                        "tick": tick,
                        "position": list(spawn_pos),
                        "color": "red",
                        "cause": "green",
                    })

        box.age += 1

    for r, c in to_add:
        from .entities import Box as BoxClass
        new_box = BoxClass(row=r, col=c, color="red")
        boxes[(r, c)] = new_box

    return events


def _find_spawn_position(row, col, radius, occupied, grid):
    candidates = []
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr == 0 and dc == 0:
                continue
            r, c = row + dr, col + dc
            if 0 <= r < grid.height and 0 <= c < grid.width:
                if grid.cells[r][c] != "wall" and (r, c) not in occupied:
                    candidates.append((r, c))
    if candidates:
        return random.choice(candidates)
    return None
