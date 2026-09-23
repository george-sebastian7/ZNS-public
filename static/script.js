const chatArea = document.getElementById("chat-area");
const form = document.getElementById("prompt-form");
const input = document.getElementById("prompt-input");
const modeSelect = document.getElementById("mode-select");
const sendBtn = document.getElementById("send-btn");

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const prompt = input.value.trim();
    if (!prompt) return;

    const mode = modeSelect.value;

    appendMessage("user", prompt);
    input.value = "";
    sendBtn.disabled = true;
    sendBtn.textContent = "...";

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt, mode }),
        });

        const data = await res.json();

        if (data.error) {
            appendMessage("error", data.error);
            return;
        }

        if (data.type === "answer") {
            appendMessage("bot", data.response);
        } else if (data.type === "code") {
            appendCodeMessage(data);
        }
    } catch (err) {
        appendMessage("error", "Chyba připojení: " + err.message);
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = "Odeslat";
    }
});

function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = "message " + role;

    const label = document.createElement("span");
    label.className = "label";
    if (role === "user") label.textContent = "Ty";
    else if (role === "bot") label.textContent = "Gemini";
    else label.textContent = "Chyba";

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

    const label = document.createElement("span");
    label.className = "label";
    label.textContent = "Gemini (kód)";

    const fileInfo = document.createElement("div");
    fileInfo.className = "file-info";
    fileInfo.textContent = "Soubor: " + data.filename;

    const codeBlock = document.createElement("pre");
    const codeEl = document.createElement("code");
    codeEl.textContent = data.code;
    codeBlock.appendChild(codeEl);

    const runResult = document.createElement("div");
    runResult.className = "run-result " + (data.run_success ? "success" : "failure");

    const runLabel = document.createElement("strong");
    runLabel.textContent = data.run_success ? "Výstup:" : "Chyba při spuštění:";
    const runOutput = document.createElement("pre");
    runOutput.textContent = data.run_output;

    runResult.appendChild(runLabel);
    runResult.appendChild(runOutput);

    div.appendChild(label);
    div.appendChild(fileInfo);
    div.appendChild(codeBlock);
    div.appendChild(runResult);
    chatArea.appendChild(div);
    chatArea.scrollTop = chatArea.scrollHeight;
}
