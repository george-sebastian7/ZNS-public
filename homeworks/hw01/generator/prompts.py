BASE_CONTEXT = """\
You are generating Python agent code for a grid maze simulator.

## Environment rules
- Grid maze with walkable cells and walls.
- 4x4 drop-off zone in the top-left corner (rows 0-3, cols 0-3).
- Boxes have colors: red (10 credits), blue (5 credits), yellow, green, orange, purple (0 credits).
- Agent carries at most 1 box at a time.
- Agent sensors see a 9x9 area centered on the agent (sees through walls).
- Each cell has energy cost: low=1, medium=3, high=5. Agent has limited energy (500 starting).
- Box mutations: yellow adjacent to red -> red becomes orange over time.
  Green box -> 90% chance a red box spawns nearby after some ticks.
- Credits are earned only when a box is dropped on a drop-off cell.

## Agent base class
```python
class BaseAgent:
    AGENT_TYPE = "base"
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
    def decide(self, sensor_data: dict) -> dict:
        raise NotImplementedError
```

## sensor_data format
```json
{
  "grid": [[cell, ...], ...],  // 9x9, agent at [4][4]
  "self": {
    "position": [row, col],
    "energy": 500,
    "carrying": null,
    "credits": 0
  }
}
```

Each cell:
```json
{
  "type": "free|wall|box|agent",
  "energy_cost": "low|medium|high",
  "drop_off": true|false,
  "box_color": null|"red"|"blue"|...,
  "agent_id": null|"agent_1"|...
}
```

## Return value from decide()
One of:
- {"action": "move", "direction": "up"|"down"|"left"|"right"}
- {"action": "pickup"}
- {"action": "drop"}
- {"action": "noop"}

## Important
- The agent can enter a cell with a box (to pick it up).
- Moving onto a wall or another agent is invalid.
- Output ONLY valid Python code, no markdown fences, no explanations.
- The class must inherit from BaseAgent and set AGENT_TYPE.
- Import BaseAgent with: from agents.base import BaseAgent
"""

AGENT_PROMPTS = {
    "simple_reflex": BASE_CONTEXT + """
## Task: Simple Reflex Agent
Generate a SimpleReflexAgent class. It uses ONLY condition-action rules
based on the current percept. NO memory, NO internal state beyond what
BaseAgent provides.

Rules to implement:
1. If on a drop-off cell and carrying a box -> drop
2. If on a red or blue box and not carrying -> pickup
3. If carrying a box -> move toward top-left (prefer up, then left)
4. If a red or blue box is visible in the 9x9 grid -> move toward it
   (pick the closest one, prefer red over blue if equidistant)
5. Otherwise -> move in a random valid direction (avoid walls and other agents)

Set AGENT_TYPE = "simple_reflex"
""",

    "model_reflex": BASE_CONTEXT + """
## Task: Model-based Reflex Agent
Generate a ModelReflexAgent class. It maintains an internal world model
that accumulates knowledge across ticks.

Internal state to maintain:
- world_map: dict mapping (row, col) to cell info from past observations
- known_boxes: dict mapping (row, col) to box color
- visited: set of visited positions
- drop_off_cells: set of known drop-off positions

On each decide():
1. Merge current 9x9 sensor data into world_map (using agent position offset)
2. Update known_boxes (add new, remove disappeared ones from current view)
3. Mark current position as visited

Decision rules (using accumulated model):
1. If on drop-off and carrying -> drop
2. If on valuable box (red/blue) and not carrying -> pickup
3. If carrying -> navigate toward nearest known drop-off cell
4. If known valuable box exists (even outside current view) -> move toward nearest
5. If unexplored areas exist -> move toward nearest unvisited cell
6. Otherwise -> random valid move

For navigation, use simple greedy movement (move in the direction that
reduces Manhattan distance to target), falling back to random if blocked.

Set AGENT_TYPE = "model_reflex"
""",

    "goal_based": BASE_CONTEXT + """
## Task: Goal-based Agent
Generate a GoalBasedAgent class. It maintains a world model AND uses
A* pathfinding to plan routes to goals.

Internal state:
- world_map, known_boxes, visited (same as model-based)
- current_goal: tuple describing current goal or None
- current_path: list of (row, col) waypoints to follow

Goals (priority order):
1. ("deliver",) - deliver carried box to drop-off
2. ("fetch", row, col) - go pick up a specific box
3. ("explore",) - explore unknown areas

On each decide():
1. Update world model from sensors
2. Check if current goal is still valid (box still there, path not blocked)
3. If no goal or goal invalid -> select new goal by priority
4. Plan path using A* on known world map (energy cost as edge weight)
5. Follow path one step at a time
6. Pick up / drop when on target

A* implementation:
- Use a priority queue (heapq)
- Nodes: (row, col)
- Edge cost: energy cost of target cell (low=1, medium=3, high=5)
- Heuristic: Manhattan distance * 1 (admissible since min cost is 1)
- Only traverse cells known to be walkable in world_map
- Treat unknown cells as walkable (optimistic)

Set AGENT_TYPE = "goal_based"
""",

    "utility_based": BASE_CONTEXT + """
## Task: Utility-based Agent
Generate a UtilityBasedAgent class. It evaluates all known boxes by a
utility function and always pursues the highest-utility target.

Internal state:
- world_map, known_boxes, visited (same as model-based)
- Uses A* pathfinding (same as goal-based)

Utility function for each known valuable box:
```
credit_value = 10 for red, 5 for blue
path_cost_to_box = A* cost from current position to box
path_cost_to_dropoff = A* cost from box to nearest drop-off cell
total_cost = path_cost_to_box + path_cost_to_dropoff

if total_cost > remaining_energy:
    utility = 0  # can't complete the trip
else:
    utility = credit_value / (total_cost + 1)

# Mutation risk: if yellow box adjacent to a red box, discount red's utility
if color == "red" and yellow_adjacent:
    utility *= 0.3

# Green opportunity: if green box nearby, boost area utility
# (red may spawn near green)
```

On each decide():
1. Update world model
2. If carrying -> navigate to nearest drop-off (A*)
3. If not carrying -> compute utility for all known red/blue boxes
4. Pursue highest utility box
5. If no valuable boxes known -> explore

Set AGENT_TYPE = "utility_based"
""",

    "learning": BASE_CONTEXT + """
## Task: Learning Agent
Generate a LearningAgent class. It learns from experience across ticks,
discovering patterns like box spawn rules and optimal areas.

Internal state:
- world_map, known_boxes, visited (same as model-based)
- A* pathfinding (same as goal-based)
- green_sightings: list of (tick, row, col) when green boxes were first seen
- red_spawns: list of (tick, row, col) when new red boxes appeared
- learned_green_red_correlation: float, starts at 0.0
- area_visit_count: dict mapping region to visit count
- area_credit_earned: dict mapping region to total credits earned there
- tick_counter: int

Learning mechanisms:
1. Track when green boxes appear and when red boxes appear nearby later
2. After enough observations, update learned_green_red_correlation
3. Track which areas of the map yield more credits (divide map into regions)
4. Use learned knowledge in decisions:
   - If high green-red correlation learned AND green box visible AND no
     immediate valuable box -> wait near green box for red spawn
   - Prefer exploring high-yield areas over low-yield ones

Decision logic:
1. Update model + learning state
2. If carrying -> deliver (A*)
3. If valuable box nearby -> fetch it (utility-based ranking)
4. If learned correlation > 0.5 and green box known -> move near green
5. Explore toward high-yield or unknown areas

Regions: divide map into 4x4 quadrants for area tracking.

Set AGENT_TYPE = "learning"
""",
}

DEBUG_PROMPT = """\
The following Python agent code has an error. Fix the code and return
the complete corrected file. Output ONLY the Python code, no explanations.

## Error
{error}

## Code
{code}
"""
