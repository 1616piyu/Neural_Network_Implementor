function login() {
    let username = document.getElementById("username").value;
    let password = document.getElementById("password").value;

    fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);

        if (data.message === "Login successful") {
            localStorage.setItem("username", username);
            window.location.href = "/chat-page";
        }
    });
}

function register() {
    let username = document.getElementById("username").value;
    let password = document.getElementById("password").value;

    fetch('/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    })
    .then(res => res.json())
    .then(data => alert(data.message));
}