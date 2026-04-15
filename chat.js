const username = localStorage.getItem("username") || "guest";

// Show username
document.addEventListener("DOMContentLoaded", () => {
    const userDisplay = document.getElementById("usernameDisplay");
    if (userDisplay) userDisplay.innerText = username;

    loadHistory();

    // ENTER key support
    document.getElementById("userInput").addEventListener("keypress", function (e) {
        if (e.key === "Enter") sendMessage();
    });
});

// ---------------- SEND MESSAGE ----------------
async function sendMessage() {
    let inputBox = document.getElementById("userInput");
    let input = inputBox.value;

    if (input.trim() === "") return;

    let chatbox = document.getElementById("chatbox");

    // User message
    chatbox.innerHTML += `
        <div class="message user">
            <div class="bubble">${input}</div>
        </div>
    `;

    inputBox.value = "";

    // Loading animation
    chatbox.innerHTML += `
        <div class="message bot" id="loadingMsg">
            <div class="bubble">Typing...</div>
        </div>
    `;

    chatbox.scrollTop = chatbox.scrollHeight;

    try {
        let response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: input, username: username })
        });

        let data = await response.json();

        // Remove loading
        document.getElementById("loadingMsg").remove();

        // Bot response
        chatbox.innerHTML += `
            <div class="message bot">
                <div>
                    <div class="bubble">${data.response}</div>
                    <div class="confidence">
                        Confidence: ${data.confidence ? data.confidence.toFixed(2) : "N/A"}
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        document.getElementById("loadingMsg").remove();

        chatbox.innerHTML += `
            <div class="message bot">
                <div class="bubble">⚠️ Error: Unable to connect to server</div>
            </div>
        `;
    }

    chatbox.scrollTop = chatbox.scrollHeight;
}

// ---------------- LOAD HISTORY ----------------
async function loadHistory() {
    let chatbox = document.getElementById("chatbox");

    try {
        let response = await fetch(`/history/${username}`);
        let data = await response.json();

        chatbox.innerHTML = ""; // clear before loading

        data.forEach(chat => {
            chatbox.innerHTML += `
                <div class="message user">
                    <div class="bubble">${chat.message}</div>
                </div>
                <div class="message bot">
                    <div class="bubble">${chat.response}</div>
                </div>
            `;
        });

        chatbox.scrollTop = chatbox.scrollHeight;
    } catch (error) {
        console.log("History load error:", error);
    }
}

// ---------------- CLEAR CHAT ----------------
function clearChat() {
    document.getElementById("chatbox").innerHTML = "";
}

// ---------------- PDF UPLOAD ----------------
async function uploadPDF() {
    let fileInput = document.getElementById("pdfFile");

    if (!fileInput.files[0]) {
        alert("Please select a PDF file");
        return;
    }

    let formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        let response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        let data = await response.json();
        alert("✅ " + data.message);
    } catch (error) {
        alert("❌ Failed to upload PDF");
    }
}