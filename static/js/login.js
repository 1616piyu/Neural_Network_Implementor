"use strict";

/* =========================================================
   DOCUMENT AI — LOGIN AND REGISTRATION
   Compatible with Flask /login and /register routes
========================================================= */

function showMessage(message, success = false) {
    const box = document.getElementById("message");

    if (!box) {
        alert(message);
        return;
    }

    box.textContent = message;
    box.style.display = "block";
    box.style.color = success ? "#176b45" : "#b42318";
    box.style.background = success ? "#eaf8f0" : "#fff0ee";
    box.setAttribute("role", success ? "status" : "alert");
}

function clearMessage() {
    const box = document.getElementById("message");

    if (!box) return;

    box.textContent = "";
    box.style.display = "none";
}

function getCredentials() {
    const fullName =
        document.getElementById("fullName")?.value.trim() || "";

    const email =
        document.getElementById("username")?.value.trim().toLowerCase() || "";

    const password =
        document.getElementById("password")?.value || "";

    const registering =
        document.getElementById("formTitle")?.textContent.trim() ===
        "Create your account";

    if (registering && fullName.length < 2) {
        showMessage("Please enter your full name.");
        return null;
    }

    if (!email) {
        showMessage("Please enter your email address.");
        return null;
    }

    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailPattern.test(email)) {
        showMessage("Please enter a valid email address.");
        return null;
    }

    if (!password) {
        showMessage("Please enter your password.");
        return null;
    }

    if (registering && password.length < 8) {
        showMessage("Your password must contain at least 8 characters.");
        return null;
    }

    return { fullName, email, password, registering };
}

/* =========================================================
   API REQUEST
========================================================= */

async function sendAuthRequest(endpoint, payload) {
    let response;

    try {
        response = await fetch(endpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify(payload)
        });
    } catch {
        throw new Error(
            "Unable to connect to the server. Check that Document AI is running."
        );
    }

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error("The server returned an invalid response.");
    }

    if (!response.ok) {
        throw new Error(
            data.message ||
            data.error ||
            "Request failed. Please try again."
        );
    }

    return data;
}

/* =========================================================
   BUTTON LOADING STATE
   Preserves nested icons and submitLabel markup.
========================================================= */

function setButtonLoading(button, loading, normalText, loadingText) {
    if (!button) return;

    const label = button.querySelector("#submitLabel");

    if (loading) {
        if (button.dataset.loading === "true") return;

        button.dataset.loading = "true";
        button.disabled = true;
        button.setAttribute("aria-busy", "true");

        if (label) {
            label.textContent = loadingText;
        } else {
            button.textContent = loadingText;
        }

        return;
    }

    button.disabled = false;
    button.removeAttribute("aria-busy");
    delete button.dataset.loading;

    if (label) {
        label.textContent = normalText;
    } else {
        button.textContent = normalText;
    }
}

function getSubmitLabel() {
    return (
        document.getElementById("submitLabel")?.textContent.trim() ||
        (document.getElementById("formTitle")?.textContent.trim() ===
            "Create your account"
            ? "Create account"
            : "Sign in")
    );
}

/* =========================================================
   LOGIN
========================================================= */

async function login() {
    clearMessage();

    const credentials = getCredentials();
    if (!credentials) return;

    const { email, password } = credentials;
    const button = document.getElementById("loginButton");
    const normalText = getSubmitLabel();

    if (button?.disabled) return;

    setButtonLoading(button, true, normalText, "Signing in...");

    try {
        const data = await sendAuthRequest("/login", {
            username: email,
            email,
            password
        });

        if (data.success !== true) {
            throw new Error(data.message || "Unable to log in.");
        }

        /*
         * Flask sets the session cookie in its response.
         * The browser stores and sends it automatically.
         * Do not use localStorage as proof of authentication.
         */
        showMessage("Login successful. Opening your workspace...", true);

        window.location.assign("/chat-page");
    } catch (error) {
        showMessage(error.message || "Unable to log in.");
    } finally {
        setButtonLoading(button, false, normalText, "Signing in...");
    }
}

/* =========================================================
   REGISTRATION
========================================================= */

async function register() {
    clearMessage();

    const credentials = getCredentials();
    if (!credentials) return;

    const { fullName, email, password } = credentials;
    const button = document.getElementById("loginButton");
    const normalText = getSubmitLabel();

    if (button?.disabled) return;

    setButtonLoading(button, true, normalText, "Creating account...");

    try {
        const data = await sendAuthRequest("/register", {
            username: email,
            email,
            full_name: fullName,
            name: fullName,
            password
        });

        if (data.success !== true) {
            throw new Error(
                data.message || "Unable to create your account."
            );
        }

        showMessage(
            data.message || "Account created successfully. Please sign in.",
            true
        );

        const emailInput = document.getElementById("username");
        const passwordInput = document.getElementById("password");

        if (emailInput) emailInput.value = email;
        if (passwordInput) passwordInput.value = "";

        if (typeof window.setAuthMode === "function") {
            window.setAuthMode("login");
        }
    } catch (error) {
        showMessage(error.message || "Unable to register.");
    } finally {
        setButtonLoading(button, false, normalText, "Creating account...");
    }
}

/* =========================================================
   GLOBAL FUNCTIONS
   Used by the existing login.html form.
========================================================= */

window.login = login;
window.register = register;
window.showMessage = showMessage;
window.clearMessage = clearMessage;