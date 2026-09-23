const canvas = document.getElementById("grid-canvas");
const ctx = canvas.getContext("2d");

let gridSize = 20;
let speed = "realtime";
let polling = null;
let state = null;

const COLORS = {
    wall: "#444",
    floor: "#111",
    dropoff: "#1a1a2e",
    red: "#cc3333",
    green: "#33cc33",
    blue: "#3366cc",
    yellow: "#cccc33",
    orange: "#cc8833",
    purple: "#9933cc",
};

const AGENT_COLORS = [
    "#00ffff", "#ff00ff", "#ffff00", "#00ff88", "#ff8800",
];

function resizeCanvas() {
    const area = document.querySelector(".canvas-area");
    const size = Math.min(area.clientWidth, area.clientHeight) - 20;
    canvas.width = size;
    canvas.height = size;
    if (state) drawGrid(state);
}

window.addEventListener("resize", resizeCanvas);
resizeCanvas();

function drawGrid(s) {
    const cellSize = canvas.width / s.grid_size;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const walls = s.walls || [];
    const wallSet = new Set(walls.map(w => w[0] + "," + w[1]));

    for (let r = 0; r < s.grid_size; r++) {
        for (let c = 0; c < s.grid_size; c++) {
            const x = c * cellSize;
            const y = r * cellSize;

            if (wallSet.has(r + "," + c)) {
                ctx.fillStyle = COLORS.wall;
            } else if (r < 4 && c < 4) {
                ctx.fillStyle = COLORS.dropoff;
            } else {
                ctx.fillStyle = COLORS.floor;
            }
            ctx.fillRect(x, y, cellSize, cellSize);
            ctx.strokeStyle = "#222";
            ctx.lineWidth = 0.5;
            ctx.strokeRect(x, y, cellSize, cellSize);
        }
    }

    const boxes = s.boxes || [];
    for (const box of boxes) {
        const x = box.col * cellSize;
        const y = box.row * cellSize;
        const pad = cellSize * 0.2;
        ctx.fillStyle = COLORS[box.color] || "#888";
        ctx.fillRect(x + pad, y + pad, cellSize - 2 * pad, cellSize - 2 * pad);
    }

    const agents = s.agents || {};
    let agentIdx = 0;
    for (const [id, agent] of Object.entries(agents)) {
        if (!agent.alive) continue;
        const x = agent.col * cellSize;
        const y = agent.row * cellSize;
        const cx = x + cellSize / 2;
        const cy = y + cellSize / 2;
        const radius = cellSize * 0.35;

        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fillStyle = AGENT_COLORS[agentIdx % AGENT_COLORS.length];
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        if (agent.carrying) {
            ctx.beginPath();
            ctx.arc(cx, cy, radius * 0.4, 0, Math.PI * 2);
            ctx.fillStyle = COLORS[agent.carrying] || "#888";
            ctx.fill();
        }

        agentIdx++;
    }

    const dropoffOutline = 4 * cellSize;
    ctx.strokeStyle = "#3355aa";
    ctx.lineWidth = 2;
    ctx.strokeRect(0, 0, dropoffOutline, dropoffOutline);
}

function updateStats(s) {
    const el = document.getElementById("stats-content");
    if (!s) { el.textContent = ""; return; }

    let html = "<div>Tick: " + (s.tick || 0) + "</div>";
    const agents = s.agents || {};
    for (const [id, a] of Object.entries(agents)) {
        const shortId = id.replace("agent_", "");
        html += '<div class="agent-stat">';
        html += "<strong>" + shortId + "</strong>";
        html += " E:" + a.energy;
        html += " C:" + a.credits;
        if (a.carrying) html += " [" + a.carrying + "]";
        if (!a.alive) html += " DEAD";
        html += "</div>";
    }
    el.innerHTML = html;
}

async function fetchState() {
    try {
        const res = await fetch("/api/state");
        if (!res.ok) return;
        state = await res.json();
        drawGrid(state);
        updateStats(state);

        if (!state.running && polling) {
            clearInterval(polling);
            polling = null;
            updateButtons(false);
        }
    } catch (e) {}
}

function startPolling() {
    if (polling) clearInterval(polling);
    const interval = speed === "fast" ? 60 : 300;
    polling = setInterval(fetchState, interval);
    fetchState();
}

function stopPolling() {
    if (polling) { clearInterval(polling); polling = null; }
}

function updateButtons(running) {
    document.getElementById("btn-start").disabled = running;
    document.getElementById("btn-pause").disabled = !running;
    document.getElementById("btn-stop").disabled = !running;
    document.getElementById("btn-step").disabled = speed !== "step" || !running;
}

function getSelectedAgents() {
    const checks = document.querySelectorAll("#agent-checks input:checked");
    return Array.from(checks).map(c => c.value);
}

async function loadAvailableAgents() {
    try {
        const res = await fetch("/api/agents/available");
        const agents = await res.json();
        const container = document.getElementById("agent-checks");
        container.innerHTML = "";
        for (const a of agents) {
            const label = document.createElement("label");
            label.className = "check-label" + (a.loaded ? "" : " disabled");
            const input = document.createElement("input");
            input.type = "checkbox";
            input.value = a.type;
            input.checked = a.loaded;
            input.disabled = !a.loaded;
            label.appendChild(input);
            label.appendChild(document.createTextNode(" " + a.type.replace(/_/g, " ")));
            container.appendChild(label);
        }
    } catch (e) {}
}

document.getElementById("btn-start").addEventListener("click", async () => {
    const agents = getSelectedAgents();
    if (agents.length === 0) { alert("No agents selected"); return; }
    const res = await fetch("/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ grid_size: gridSize, agents: agents, speed: speed }),
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    updateButtons(true);
    startPolling();
});

document.getElementById("btn-pause").addEventListener("click", async () => {
    await fetch("/api/pause", { method: "POST" });
    stopPolling();
    updateButtons(false);
});

document.getElementById("btn-stop").addEventListener("click", async () => {
    await fetch("/api/stop", { method: "POST" });
    stopPolling();
    state = null;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    updateStats(null);
    updateButtons(false);
});

document.getElementById("btn-step").addEventListener("click", async () => {
    await fetch("/api/step", { method: "POST" });
    fetchState();
});

document.getElementById("btn-regen").addEventListener("click", async () => {
    await fetch("/api/stop", { method: "POST" });
    stopPolling();
    state = null;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    updateStats(null);
    updateButtons(false);
});

document.querySelectorAll(".grid-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".grid-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        gridSize = parseInt(btn.dataset.size);
    });
});

document.querySelectorAll(".speed-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
        document.querySelectorAll(".speed-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        speed = btn.dataset.speed;
        document.getElementById("btn-step").disabled = speed !== "step";
        await fetch("/api/speed", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ speed: speed }),
        });
    });
});

loadAvailableAgents();
