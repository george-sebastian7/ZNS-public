const chatArea = document.getElementById("chat-area");
const form = document.getElementById("prompt-form");
const input = document.getElementById("prompt-input");
const modeSelect = document.getElementById("mode-select");
const providerSelect = document.getElementById("provider-select");
const sendBtn = document.getElementById("send-btn");

function getProviderName() {
    return providerSelect.value === "claude" ? "Claude" : "Gemini";
}

function showTyping() {
    const div = document.createElement("div");
    div.className = "message bot typing-indicator";
    div.innerHTML = '<span class="label">' + getProviderName() + '</span><div class="dots"><span></span><span></span><span></span></div>';
    chatArea.appendChild(div);
    chatArea.scrollTop = chatArea.scrollHeight;
    return div;
}

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const prompt = input.value.trim();
    if (!prompt) return;

    const mode = modeSelect.value;
    const provider = providerSelect.value;

    appendMessage("user", prompt);
    input.value = "";
    sendBtn.disabled = true;
    sendBtn.textContent = "...";

    const typing = showTyping();

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt, mode, provider }),
        });

        const data = await res.json();
        typing.remove();

        if (data.error) {
            appendMessage("error", data.error);
            return;
        }

        if (data.type === "answer") {
            appendMessage("bot", data.response, data.provider);
        } else if (data.type === "code") {
            appendCodeMessage(data);
        }
    } catch (err) {
        typing.remove();
        appendMessage("error", "Chyba pripojeni: " + err.message);
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = "Odeslat";
    }
});

function appendMessage(role, text, provider) {
    const div = document.createElement("div");
    div.className = "message " + role;

    const label = document.createElement("span");
    label.className = "label";
    if (role === "user") {
        label.textContent = "Ty";
    } else if (role === "bot") {
        const name = provider === "claude" ? "Claude" : "Gemini";
        label.textContent = name;
    } else {
        label.textContent = "Chyba";
    }

    const content = document.createElement("div");
    content.className = "content";
    content.textContent = text;

    div.appendChild(label);
    div.appendChild(content);
    chatArea.appendChild(div);
    chatArea.scrollTop = chatArea.scrollHeight;
}

function appendCodeMessage(data) {
    const div = document.createElement("div");
    div.className = "message bot";

    const name = data.provider === "claude" ? "Claude" : "Gemini";
    const label = document.createElement("span");
    label.className = "label";
    label.textContent = name + " (kod)";

    const info = document.createElement("div");
    info.className = "content";

    const status = data.run_success ? "uspesne spusten" : "chyba pri spusteni";
    info.textContent = "Soubor " + data.filename + " ulozen a " + status + ".";

    const runResult = document.createElement("div");
    runResult.className = "run-result " + (data.run_success ? "success" : "failure");

    const runLabel = document.createElement("strong");
    runLabel.textContent = data.run_success ? "Vystup:" : "Chyba:";
    const runOutput = document.createElement("pre");
    runOutput.textContent = data.run_output;

    runResult.appendChild(runLabel);
    runResult.appendChild(runOutput);

    div.appendChild(label);
    div.appendChild(info);
    div.appendChild(runResult);
    chatArea.appendChild(div);
    chatArea.scrollTop = chatArea.scrollHeight;
}
