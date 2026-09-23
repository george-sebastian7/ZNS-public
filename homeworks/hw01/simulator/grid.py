import random
from collections import deque

from .rules import DROPOFF_SIZE


class Grid:
    def __init__(self, width: int = 20, height: int = 20, wall_density: float = 0.2):
        self.width = width
        self.height = height
        self.cells = [["free"] * width for _ in range(height)]
        self.energy_map = [["low"] * width for _ in range(height)]
        self._generate(wall_density)

    def _generate(self, wall_density: float):
        for r in range(self.height):
            for c in range(self.width):
                if r < DROPOFF_SIZE and c < DROPOFF_SIZE:
                    self.cells[r][c] = "free"
                    self.energy_map[r][c] = "low"
                    continue

                if random.random() < wall_density:
                    self.cells[r][c] = "wall"
                else:
                    self.cells[r][c] = "free"
                    roll = random.random()
                    if roll < 0.5:
                        self.energy_map[r][c] = "low"
                    elif roll < 0.8:
                        self.energy_map[r][c] = "medium"
                    else:
                        self.energy_map[r][c] = "high"

        self._ensure_connectivity()

    def _ensure_connectivity(self):
        """Remove walls that would disconnect walkable areas."""
        free_cells = set()
        for r in range(self.height):
            for c in range(self.width):
                if self.cells[r][c] != "wall":
                    free_cells.add((r, c))

        if not free_cells:
            return

        start = next(iter(free_cells))
        visited = self._bfs(start)

        unreachable = free_cells - visited
        for r, c in unreachable:
            path = self._carve_path_to(r, c, visited)
            for pr, pc in path:
                if self.cells[pr][pc] == "wall":
                    self.cells[pr][pc] = "free"
                    self.energy_map[pr][pc] = "medium"
                    visited.add((pr, pc))

    def _bfs(self, start: tuple[int, int]) -> set:
        visited = {start}
        queue = deque([start])
        while queue:
            r, c = queue.popleft()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.height and 0 <= nc < self.width:
                    if (nr, nc) not in visited and self.cells[nr][nc] != "wall":
                        visited.add((nr, nc))
                        queue.append((nr, nc))
        return visited

    def _carve_path_to(self, target_r, target_c, reachable):
        """Carve a path from target to the nearest reachable cell."""
        visited = {(target_r, target_c)}
        queue = deque([(target_r, target_c, [(target_r, target_c)])])
        while queue:
            r, c, path = queue.popleft()
            if (r, c) in reachable:
                return path
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.height and 0 <= nc < self.width:
                    if (nr, nc) not in visited:
                        visited.add((nr, nc))
                        queue.append((nr, nc, path + [(nr, nc)]))
        return []

    def is_walkable(self, row: int, col: int) -> bool:
        if 0 <= row < self.height and 0 <= col < self.width:
            return self.cells[row][col] != "wall"
        return False

    def is_dropoff(self, row: int, col: int) -> bool:
        return row < DROPOFF_SIZE and col < DROPOFF_SIZE

    def get_energy_cost(self, row: int, col: int) -> str:
        if 0 <= row < self.height and 0 <= col < self.width:
            return self.energy_map[row][col]
        return "high"

    def to_dict(self):
        result = []
        for r in range(self.height):
            row = []
            for c in range(self.width):
                row.append({
                    "type": self.cells[r][c],
                    "energy_cost": self.energy_map[r][c],
                    "drop_off": self.is_dropoff(r, c),
                })
            result.append(row)
        return result
