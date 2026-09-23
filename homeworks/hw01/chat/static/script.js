const agentSelect = document.getElementById("agent-select");
const generateBtn = document.getElementById("generate-btn");
const generateAllBtn = document.getElementById("generate-all-btn");
const statusBar = document.getElementById("status-bar");
const outputArea = document.getElementById("output-area");

generateBtn.addEventListener("click", () => {
    const agentType = agentSelect.value;
    generateAgent(agentType);
});

generateAllBtn.addEventListener("click", async () => {
    const options = agentSelect.options;
    generateAllBtn.disabled = true;
    generateBtn.disabled = true;
    for (let i = 0; i < options.length; i++) {
        await generateAgent(options[i].value);
    }
    generateAllBtn.disabled = false;
    generateBtn.disabled = false;
});

async function generateAgent(agentType) {
    setStatus("Generating " + agentType + "...", "loading");
    generateBtn.disabled = true;

    try {
        const res = await fetch("/api/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ agent_type: agentType }),
        });
        const data = await res.json();

        if (data.error && !data.success) {
            setStatus("Failed: " + data.error, "error");
            appendResult(agentType, data, false);
        } else if (data.success) {
            const testOk = data.test && data.test.success;
            setStatus(
                agentType + " generated (" + data.iterations + " iterations)" +
                (testOk ? " — test passed" : " — test failed"),
                testOk ? "success" : "warning"
            );
            appendResult(agentType, data, true);
        }
    } catch (err) {
        setStatus("Error: " + err.message, "error");
    } finally {
        generateBtn.disabled = false;
    }
}

function setStatus(text, type) {
    statusBar.textContent = text;
    statusBar.className = type;
}

function appendResult(agentType, data, success) {
    const div = document.createElement("div");
    div.className = "result " + (success ? "success" : "failure");

    let html = '<div class="result-header">' +
        '<strong>' + agentType.replace(/_/g, " ") + '</strong>' +
        '<span class="badge">' + (success ? "OK" : "FAIL") + '</span>' +
        '</div>';

    html += '<div class="result-meta">';
    html += 'Iterations: ' + (data.iterations || 0);
    if (data.filepath) html += ' | File: ' + data.filepath;
    if (data.test) {
        html += ' | Test ticks: ' + data.test.ticks_completed;
        html += ' | Credits: ' + data.test.credits;
    }
    html += '</div>';

    if (data.error) {
        html += '<pre class="error-text">' + escapeHtml(data.error) + '</pre>';
    }

    if (data.test && data.test.error) {
        html += '<pre class="error-text">Test: ' + escapeHtml(data.test.error) + '</pre>';
    }

    if (data.code) {
        html += '<details><summary>Show code</summary>';
        html += '<pre><code>' + escapeHtml(data.code) + '</code></pre>';
        html += '</details>';
    }

    div.innerHTML = html;
    outputArea.prepend(div);
}

function escapeHtml(text) {
    const d = document.createElement("div");
    d.textContent = text;
    return d.innerHTML;
}
