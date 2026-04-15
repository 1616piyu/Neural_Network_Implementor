async function sendMessage() {
    let inputBox = document.getElementById("userInput");
    let input = inputBox.value;

    if (input.trim() === "") return;

    let chatbox = document.getElementById("chatbox");

    // Show user message
    chatbox.innerHTML += `<p><b>You:</b> ${input}</p>`;

    // Clear input box
    inputBox.value = "";

    // Send request
    let response = await fetch('/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message: input })
    });

    let data = await response.json();

    // Show bot response with confidence
    chatbox.innerHTML += `
        <p><b>Bot:</b> ${data.response}</p>
        <p style="color:gray;">Confidence: ${data.confidence?.toFixed(2)}</p>
    `;

    // Auto scroll
    chatbox.scrollTop = chatbox.scrollHeight;
}