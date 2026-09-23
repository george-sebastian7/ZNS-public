# HW01 — Grid Maze Agent System: Design Document

## Overview

Two web interfaces + Python backend using Claude API to generate agent code.

- **Chat UI** (port 8080) — prompt Claude to generate/debug agent code
- **Visualizer** (port 8081) — grid simulation with controls and live agent visualization
- **Backend** — simulator engine, agent runner, Claude-powered agent generator

Everything lives in `homeworks/hw01/`. Requires `CLAUDE_API_KEY` env var.

---

## Architecture

```
hw01/
├── main_chat.py              # Entry point for chat UI (port 8080)
├── main_visualizer.py         # Entry point for visualizer (port 8081)
├── requirements.txt
│
├── chat/                      # Chat UI (reused from project root)
│   ├── app.py                 # Flask routes for chat
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── script.js
│       └── styles.css
│
├── visualizer/                # Grid visualizer UI
│   ├── app.py                 # Flask routes + WebSocket for live updates
│   ├── templates/
│   │   └── index.html         # Canvas-based grid renderer
│   └── static/
│       ├── grid.js            # Grid rendering, animation, controls
│       └── styles.css
│
├── simulator/                 # Core simulation engine
│   ├── __init__.py
│   ├── grid.py                # Grid/maze generation, connectivity check
│   ├── engine.py              # Simulation loop, tick processing
│   ├── entities.py            # Box, Agent data classes
│   └── rules.py               # Box mutation rules, energy costs, scoring
│
├── agents/                    # Agent framework
│   ├── __init__.py
│   ├── base.py                # Abstract base agent class
│   ├── simple_reflex.py       # Generated: simple reflex agent
│   ├── model_reflex.py        # Generated: model-based reflex agent
│   ├── goal_based.py          # Generated: goal-based agent
│   ├── utility_based.py       # Generated: utility-based agent
│   └── learning.py            # Generated: learning agent
│
├── generator/                 # Claude API agent generator
│   ├── __init__.py
│   ├── generator.py           # Prompts Claude, receives code, writes agent files
│   ├── debugger.py            # Runs generated agent, sends errors back to Claude
│   ├── prompts.py             # Prompt templates per agent type
│   └── validator.py           # Validates generated code structure
│
├── logs/                      # Runtime logs
│   ├── generator.log          # Agent generation + debugging log
│   ├── simulator.log          # Simulation events log
│   └── agents.log             # Per-agent decision log
│
└── generated/                 # Raw generated code snapshots (versioned)
    └── .gitkeep
```

---

## Simulator Design

### Grid

- Switchable sizes: 20x20, 30x30, 40x40
- 4x4 drop-off zone in top-left corner (rows 0-3, cols 0-3)
- Random maze generation with guaranteed connectivity (all walkable cells reachable)
- Regenerate button creates a fresh grid

### Cell types

| Type  | Visual   | Description                        |
|-------|----------|------------------------------------|
| free  | white    | Walkable, empty                    |
| wall  | black    | Impassable                         |
| box   | colored  | Walkable, contains a box           |
| agent | marker   | Walkable, occupied by an agent     |
| drop  | gray     | Drop-off zone (top-left 4x4)       |

### Energy costs

| Level  | Cost | Visual hint       |
|--------|------|--------------------|
| low    | 1    | Light background   |
| medium | 3    | Medium background  |
| high   | 5    | Dark background    |

### Box colors and scoring

| Color   | Credits | Notes                                        |
|---------|---------|----------------------------------------------|
| red     | 10      | High value target                            |
| blue    | 5       | Medium value target                          |
| yellow  | 0       | Catalyst — turns adjacent red into orange    |
| green   | 0       | Predictor — 90% chance red spawns nearby     |
| orange  | 0       | Result of red+yellow adjacency               |
| purple  | 0       | No special behavior                          |

### Box mutation rules

1. Yellow placed adjacent to red -> after N ticks, red becomes orange (value lost!)
2. Green appears anywhere -> 90% probability red spawns within radius R after M ticks

### Sensor data format (JSON, per tick)

```json
{
  "grid": [
    [
      {
        "type": "free|wall|box|agent",
        "energy_cost": "low|medium|high",
        "drop_off": true|false,
        "box_color": null|"red"|"blue"|...,
        "agent_id": null|"agent_1"|...
      }
    ]
  ],
  "self": {
    "position": [row, col],
    "energy": 500,
    "carrying": null|"red"|"blue"|...,
    "credits": 0
  }
}
```

Grid is always 9x9, agent at center [4,4]. Out-of-bounds cells reported as walls.

### Agent actions

| Action | Params    | Preconditions                                  |
|--------|-----------|------------------------------------------------|
| move   | direction | Target cell is walkable and not occupied by agent |
| pickup | —         | On a box cell, not already carrying            |
| drop   | —         | Carrying a box, current cell has no box        |

Direction: "up", "down", "left", "right"

---

## Agent Types — Descriptions & Implementation Guidance

### Base Agent Interface

Every agent implements:

```python
class BaseAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.energy = 500          # starting energy
        self.carrying = None       # box color or None
        self.credits = 0
        self.position = None       # set by simulator

    def decide(self, sensor_data: dict) -> dict:
        """
        Receives sensor JSON, returns action dict.
        Returns: {"action": "move", "direction": "up"}
                 {"action": "pickup"}
                 {"action": "drop"}
                 {"action": "noop"}
        """
        raise NotImplementedError
```

---

### 1. Simple Reflex Agent

**Concept:** Pure condition-action rules on current percept. No memory, no model,
no planning. Reacts only to what it sees right now.

**Architecture:**
```
Sensors -> Condition-Action Rules -> Action
```

**Key rules (examples):**
- IF on a red/blue box AND not carrying THEN pickup
- IF carrying AND on drop-off cell THEN drop
- IF carrying THEN move toward top-left (simple heuristic: prefer up/left)
- IF see red/blue box in sensor range THEN move toward it
- IF nothing interesting THEN move randomly (avoid walls)

**What makes it "simple":**
- No memory of past percepts
- No world model
- No pathfinding — just greedy direction choice
- Gets stuck in dead ends, can't navigate complex mazes
- Doesn't know where it's been

**Generation requirement:** Full agent code generated by Claude API,
including the debugging loop ("program debugs program").

**Example decision logic:**
```python
def decide(self, sensor_data):
    grid = sensor_data["grid"]
    me = sensor_data["self"]

    # Rule 1: Drop if carrying and on drop-off
    center = grid[4][4]
    if me["carrying"] and center["drop_off"]:
        return {"action": "drop"}

    # Rule 2: Pick up valuable box
    if not me["carrying"] and center["type"] == "box":
        if center["box_color"] in ("red", "blue"):
            return {"action": "pickup"}

    # Rule 3: If carrying, move toward top-left
    if me["carrying"]:
        return self._move_toward_dropoff(grid)

    # Rule 4: If see valuable box, move toward it
    box_dir = self._find_nearest_valuable_box(grid)
    if box_dir:
        return {"action": "move", "direction": box_dir}

    # Rule 5: Random walk
    return {"action": "move", "direction": self._random_free_direction(grid)}
```

---

### 2. Model-based Reflex Agent

**Concept:** Maintains an internal model of the world that persists across ticks.
Still uses condition-action rules, but informed by accumulated knowledge.

**Architecture:**
```
Sensors -> Update Model -> Condition-Action Rules (using Model) -> Action
```

**Internal state (the model):**
- Full explored map (cells seen so far, merged from all 9x9 snapshots)
- Known box locations (even outside current view)
- Visited cells tracking
- Drop-off zone location (known after first observation)

**What makes it different from simple reflex:**
- Remembers box locations seen earlier
- Can navigate back to a box it saw 50 ticks ago
- Knows which areas are unexplored
- Tracks box mutations (red disappeared = probably turned orange)

**Generation requirement:** Full agent code generated by Claude API,
including the debugging loop.

**Example additions over simple reflex:**
```python
class ModelReflexAgent(BaseAgent):
    def __init__(self, agent_id):
        super().__init__(agent_id)
        self.world_map = {}        # (row, col) -> cell info
        self.known_boxes = {}      # (row, col) -> box_color
        self.visited = set()
        self.drop_off_cells = set()

    def decide(self, sensor_data):
        self._update_model(sensor_data)

        # Same rules as simple reflex, but can use self.known_boxes
        # to target boxes outside current 9x9 view

    def _update_model(self, sensor_data):
        # Merge current 9x9 view into world_map
        # Update known_boxes, remove boxes that disappeared
        # Mark cells as visited
        ...
```

---

### 3. Goal-based Agent

**Concept:** Has explicit goals and plans sequences of actions to achieve them.
Uses pathfinding (A*) to navigate efficiently.

**Architecture:**
```
Sensors -> Update Model -> Goal Formulation -> Planning (A*) -> Action
```

**Goals (prioritized):**
1. If carrying a box -> deliver to drop-off (plan path to nearest drop-off cell)
2. If not carrying -> go to nearest valuable box (plan path using A*)
3. If no known boxes -> explore unknown areas

**What makes it different from model-based reflex:**
- Explicit goal stack, not just rules
- Uses A* pathfinding with energy costs as weights
- Can plan multi-step routes around walls
- Replans when situation changes (box disappears, path blocked)

**Key components to generate:**
- A* pathfinding on the known world map
- Goal selection logic (which box to target)
- Replanning trigger (when current plan becomes invalid)

**Example:**
```python
class GoalBasedAgent(BaseAgent):
    def __init__(self, agent_id):
        super().__init__(agent_id)
        self.world_map = {}
        self.known_boxes = {}
        self.current_goal = None   # ("deliver",) or ("fetch", row, col) or ("explore",)
        self.current_path = []     # list of (row, col) to follow

    def decide(self, sensor_data):
        self._update_model(sensor_data)
        self._check_goal_validity()

        if not self.current_goal:
            self._select_goal()

        if not self.current_path:
            self._plan_path()

        return self._follow_path()

    def _select_goal(self):
        if self.carrying:
            self.current_goal = ("deliver",)
        elif self.known_boxes:
            nearest = self._nearest_valuable_box()
            if nearest:
                self.current_goal = ("fetch", *nearest)
        else:
            self.current_goal = ("explore",)

    def _plan_path(self):
        # A* from current position to goal target
        ...
```

**LLM generation note:** Claude generates the A* function, goal selection,
and replanning logic. Human may wire them together.

---

### 4. Utility-based Agent

**Concept:** Evaluates all possible actions/targets by a utility function
and chooses the one with highest expected utility. Makes optimal decisions
under uncertainty.

**Architecture:**
```
Sensors -> Update Model -> Evaluate Utilities -> Best Action -> Action
```

**Utility function considers:**
- Box credit value (red=10, blue=5)
- Energy cost to reach the box (A* path cost)
- Energy cost to deliver box from its location to drop-off
- Remaining energy (can I make the round trip?)
- Box mutation risk (is yellow nearby? red might become orange=0)
- Green box opportunity (green nearby = potential red spawn = future value)
- Distance to unexplored areas (exploration value)

**Formula example:**
```
utility(box) = credit_value / (energy_to_box + energy_to_dropoff + 1)
             * feasibility_factor   # 0 if not enough energy for round trip
             * mutation_risk        # discount if yellow is adjacent
```

**What makes it different from goal-based:**
- Doesn't just pick the nearest box — picks the BEST box
- Considers energy budget for the entire trip
- Accounts for risk (mutation) and opportunity (green->red)
- Can decide to skip a nearby blue (5pts) for a farther red (10pts)
  if the utility calculation favors it

**Example:**
```python
class UtilityBasedAgent(BaseAgent):
    def __init__(self, agent_id):
        super().__init__(agent_id)
        self.world_map = {}
        self.known_boxes = {}

    def decide(self, sensor_data):
        self._update_model(sensor_data)

        if self.carrying:
            return self._navigate_to_dropoff()

        # Evaluate all known valuable boxes
        candidates = []
        for pos, color in self.known_boxes.items():
            if color not in ("red", "blue"):
                continue
            u = self._compute_utility(pos, color)
            if u > 0:
                candidates.append((u, pos))

        if not candidates:
            return self._explore()

        candidates.sort(reverse=True)
        best_pos = candidates[0][1]
        return self._navigate_to(best_pos)

    def _compute_utility(self, box_pos, color):
        credit = {"red": 10, "blue": 5}.get(color, 0)
        cost_to_box = self._path_energy_cost(self.position, box_pos)
        cost_to_drop = self._path_energy_cost(box_pos, self._nearest_dropoff())
        total_cost = cost_to_box + cost_to_drop

        if total_cost > self.energy:
            return 0  # can't make the trip

        mutation_risk = self._check_yellow_adjacency(box_pos)
        return (credit / (total_cost + 1)) * mutation_risk
```

**LLM generation note:** Claude generates the utility function and
pathfinding. Human may tune weights and assemble.

---

### 5. Learning Agent

**Concept:** Learns from experience. Discovers patterns (box spawn rules,
optimal routes) and improves its policy over time.

**Architecture:**
```
                    +-----------+
Sensors -> Model -> | Performance |
                    | Element     | -> Action
                    +-----------+
                         ^
                    +-----------+
                    | Learning  |
                    | Element   |
                    +-----------+
                         ^
                    +-----------+
                    | Critic    |
                    +-----------+
```

**What it learns:**
- Box spawn patterns: green -> red correlation (discovers the 90% rule)
- Optimal routes through the maze (energy-efficient paths)
- Which areas tend to have more valuable boxes
- Mutation timing (how many ticks before red+yellow -> orange)

**Learning mechanisms (options):**
- **Q-learning:** state = (region, carrying, energy_bucket), action = direction/pickup/drop
- **Pattern tracker:** records green appearances, checks if red follows nearby
- **Route memory:** remembers energy-efficient paths between key locations
- **Spawn heatmap:** tracks where boxes appear most frequently

**What makes it different from utility-based:**
- Starts with no knowledge of box mutation rules
- Discovers the green->red correlation through observation
- Can improve its utility function weights over time
- Gets better the longer it runs (across episodes)

**Example:**
```python
class LearningAgent(BaseAgent):
    def __init__(self, agent_id):
        super().__init__(agent_id)
        self.world_map = {}
        self.known_boxes = {}
        # Learning state
        self.green_observations = []   # [(tick, position)]
        self.red_spawns = []           # [(tick, position)]
        self.spawn_correlation = 0.0   # learned P(red | green nearby)
        self.area_values = {}          # region -> average credits earned
        self.episode_history = []      # for post-episode analysis

    def decide(self, sensor_data):
        self._update_model(sensor_data)
        self._learn_from_observation(sensor_data)

        # Use learned knowledge in decisions
        if self.carrying:
            return self._navigate_to_dropoff()

        # If we learned green->red correlation, wait near green boxes
        if self.spawn_correlation > 0.7:
            green_pos = self._find_nearby_green()
            if green_pos and not self.known_boxes_valuable():
                return self._navigate_to(green_pos)  # wait for red spawn

        return self._utility_decision()  # fallback to utility-based

    def _learn_from_observation(self, sensor_data):
        # Track green box appearances
        # Track red box appearances
        # Correlate: did red appear near a recent green?
        # Update spawn_correlation
        ...

    def end_episode(self):
        # Post-episode learning
        # Update area_values based on where credits were earned
        # Refine spawn_correlation with full episode data
        ...
```

**LLM generation note:** Claude generates the learning components
(pattern tracker, correlation calculator). Human may assemble the
full agent and tune the learning parameters.

---

## Visualizer UI Design

### Layout

```
+-------------------------------------------------------+
|  HW01 Grid Maze Simulator           [20x20 ▼] [⟳]    |
+-------------------------------------------------------+
|                                                         |
|  +-------------------------------------------+  Stats  |
|  |                                           |  Panel  |
|  |            Grid Canvas                    |         |
|  |         (color-coded cells)               | Agent 1 |
|  |                                           | E: 450  |
|  |         Agents shown as markers           | C: 10   |
|  |         Boxes shown as colored squares    | Carry:- |
|  |         Drop-off zone shaded gray         |         |
|  |         Energy cost = cell shade          | Agent 2 |
|  |                                           | E: 300  |
|  +-------------------------------------------+ C: 5   |
|                                                         |
|  [▶ Start] [⏸ Pause] [⏹ Stop] [☠ Kill]               |
|  [Speed: ▼ Realtime / Fast / Step]                     |
|  [Agents: ☑SR ☑MR ☑GB ☑UB ☑LA]                       |
|                                                         |
|  Log output (scrollable)                                |
|  > Agent 1 (SimpleReflex): moved UP, energy 499        |
|  > Agent 2 (GoalBased): picked up RED box              |
+-------------------------------------------------------+
```

### Controls

- **Grid size dropdown**: 20x20, 30x30, 40x40 — regenerates field
- **Regenerate button**: new random maze, same size
- **Start**: begin simulation with selected agents
- **Pause/Continue**: freeze/resume simulation
- **Stop**: end simulation, show final scores
- **Kill**: immediately terminate all agents
- **Speed**: Realtime (200ms/tick), Fast (no delay), Step (manual tick)
- **Agent checkboxes**: select which agent types to deploy

### Color scheme

- Background: black
- Walls: dark gray
- Free cells: white (shade by energy cost)
- Drop-off zone: light gray with border
- Boxes: their actual color (red, blue, yellow, green, orange, purple)
- Agents: distinct markers (numbered circles, contrasting colors)

---

## Chat UI (port 8080)

Reused from the project root with modifications:
- Only Claude provider (no Gemini needed here)
- Mode: "generate agent" instead of generic code mode
- Dropdown to select which agent type to generate
- Shows generation log + debugging iterations
- Generated code is saved to `agents/` directory

---

## Logging

All logging uses Python `logging` module with file + console handlers.

| Log file          | Contents                                           |
|-------------------|----------------------------------------------------|
| logs/generator.log | Claude API calls, prompts sent, code received, validation errors, debug iterations |
| logs/simulator.log | Tick events, box mutations, agent actions, energy changes, scoring |
| logs/agents.log    | Per-agent decisions, sensor data summaries, internal state changes |

Log format: `[timestamp] [level] [component] message`

---

## Communication Flow

```
Chat UI (8080)                    Visualizer (8081)
    |                                  |
    | 1. User selects agent type       |
    | 2. Claude generates code         |
    | 3. Code saved to agents/         |
    |                                  |
    |    -------- agents/ dir -------> |
    |                                  |
    |                  4. User clicks Start
    |                  5. Simulator loads agent from agents/
    |                  6. Simulation runs, grid updates via WebSocket
    |                  7. Real-time visualization
    |                                  |
    | <-- logs visible in both UIs --> |
```

Both UIs read from the same `agents/` directory. The chat UI writes
generated agent files there; the visualizer loads and runs them.

---

## Requirements

```
flask
anthropic
```

Minimal dependencies. The visualizer uses vanilla JS canvas rendering,
no frontend frameworks.
