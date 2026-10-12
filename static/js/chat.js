
"use strict";

/* =========================================================
   DOCUMENT AI — FRONTEND
   Uses the Flask server session for authentication.
   Supports registered users and guest sessions.
========================================================= */

let username = "guest";
let displayNameFromSession = "";
let isGuest = false;
let guestQuestionsRemaining = null;
let guestQuestionLimit = 5;
let sessionReady = false;

let isSendingMessage = false;
let isUploadingFiles = false;

const MAX_UPLOAD_SIZE = 10 * 1024 * 1024;

/* =========================================================
   INITIALIZATION
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
    initializeTheme();
    initializeChatForm();
    initializeAccountMenu();

    getElement("refreshDocuments")?.addEventListener(
        "click",
        loadDocuments
    );

    getElement("themeToggle")?.addEventListener(
        "click",
        toggleTheme
    );

    // HTML already defines onclick handlers for these functions.
    // Do not attach duplicate handlers.

    getElement("chatbox")?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-prompt]");
        if (!button) return;

        const input = getElement("userInput");
        const prompt = button.getAttribute("data-prompt");

        if (!input || !prompt) return;

        if (isGuest && Number(guestQuestionsRemaining) <= 0) {
            showGuestLimitPrompt();
            return;
        }

        input.value = prompt;
        input.focus();
        resizeInput();
    });

    getElement("pdfFile")?.addEventListener("change", () => {
        const fileInput = getElement("pdfFile");
        const files = Array.from(fileInput?.files || []);

        if (files.length > 0) {
            setStatus(
                "uploadStatus",
                `${files.length} file(s) selected.`,
                false
            );
        } else {
            setStatus("uploadStatus", "");
        }
    });

    initializeSession();
});

/* =========================================================
   SERVER SESSION — REGISTERED USER OR GUEST
========================================================= */

async function initializeSession() {
    try {
        const response = await fetch("/session", {
            method: "GET",
            credentials: "same-origin",
            cache: "no-store"
        });

        if (!response.ok) {
            window.location.replace("/login");
            return;
        }

        const data = await response.json();

        username = data.username || "guest";
        displayNameFromSession =
            data.display_name || data.name || "";

        isGuest = data.is_guest === true;

        guestQuestionsRemaining = isGuest
            ? Number(data.questions_remaining ?? 5)
            : null;

        guestQuestionLimit = Number(data.question_limit ?? 5);
        sessionReady = true;

        initializeAccountDisplay();
        updateGuestControls();

        await loadHistory();
        await loadDocuments();

        if (isGuest && guestQuestionsRemaining <= 0) {
            showGuestLimitPrompt();
        }
    } catch (error) {
        console.error(
            "Could not verify the current session:",
            error
        );

        const chatbox = getElement("chatbox");

        if (chatbox) {
            chatbox.replaceChildren();

            addMessage(
                "assistant",
                "I couldn't verify your session. Please refresh the page or sign in again."
            );
        }
    }
}

function updateGuestControls() {
    const uploadButton = getElement("uploadButton");
    const fileInput = getElement("pdfFile");
    const refreshButton = getElement("refreshDocuments");
    const accountStatus = getElement("accountStatus");

    if (isGuest) {
        if (uploadButton) uploadButton.disabled = true;
        if (fileInput) fileInput.disabled = true;
        if (refreshButton) refreshButton.disabled = true;

        if (accountStatus) {
            accountStatus.textContent =
                `Guest workspace · ${guestQuestionsRemaining ?? 0} questions left`;
        }

        setStatus(
            "uploadStatus",
            "Document uploads are available after you create an account or sign in."
        );
    } else {
        if (uploadButton) uploadButton.disabled = false;
        if (fileInput) fileInput.disabled = false;
        if (refreshButton) refreshButton.disabled = false;

        setStatus("uploadStatus", "");
    }
}

function showGuestLimitPrompt() {
    const chatbox = getElement("chatbox");
    if (!chatbox) return;

    if (!chatbox.querySelector(".guest-limit-prompt")) {
        const prompt = document.createElement("div");
        prompt.className = "guest-limit-prompt";

        const heading = document.createElement("h3");
        heading.textContent = "You've used your free questions";

        const description = document.createElement("p");
        description.textContent =
            "Create an account or sign in to continue chatting and save your conversations.";

        const link = document.createElement("a");
        link.href = "/login";
        link.className = "guest-limit-link";
        link.textContent = "Register or sign in";

        prompt.append(heading, description, link);
        chatbox.appendChild(prompt);
        scrollChatToBottom();
    }

    const input = getElement("userInput");
    const sendButton = getElement("sendButton");

    if (input) {
        input.disabled = true;
        input.placeholder = "Sign in to continue chatting";
    }

    if (sendButton) {
        sendButton.disabled = true;
    }
}

/* =========================================================
   GENERAL UTILITIES
========================================================= */

function getElement(id) {
    return document.getElementById(id);
}

function setStatus(id, message, isError = false) {
    const element = getElement(id);
    if (!element) return;

    element.textContent = message;
    element.classList.toggle("error", isError);
    element.classList.toggle(
        "success",
        Boolean(message) && !isError
    );
}

function scrollChatToBottom() {
    const chatbox = getElement("chatbox");

    if (chatbox) {
        chatbox.scrollTop = chatbox.scrollHeight;
    }
}

function normalizeSources(sources) {
    if (Array.isArray(sources)) {
        return sources;
    }

    if (typeof sources === "string") {
        try {
            const parsed = JSON.parse(sources);
            return Array.isArray(parsed) ? parsed : [];
        } catch {
            return [];
        }
    }

    return [];
}

/* =========================================================
   ACCOUNT DISPLAY
========================================================= */

function getFriendlyName(value) {
    if (!value || value === "guest") {
        return "Guest";
    }

    let savedName = "";

    try {
        savedName =
            localStorage.getItem("displayName") ||
            localStorage.getItem("full_name") ||
            localStorage.getItem("name") ||
            "";
    } catch (error) {
        console.warn("Could not read account name.", error);
    }

    if (savedName.trim()) {
        return savedName.trim();
    }

    const localPart = value.includes("@")
        ? value.split("@")[0]
        : value;

    const cleaned = localPart
        .replace(/[._-]+/g, " ")
        .replace(/\d+/g, " ")
        .trim();

    if (!cleaned) {
        return "User";
    }

    return cleaned.replace(/\b\w/g, (letter) =>
        letter.toUpperCase()
    );
}

function initializeAccountDisplay() {
    const friendlyName = isGuest
        ? "Guest"
        : (
            displayNameFromSession.trim() ||
            getFriendlyName(username)
        );

    const profileName = getElement("profileName");
    const usernameDisplay = getElement("usernameDisplay");
    const userAvatar = getElement("userAvatar");
    const accountStatus = getElement("accountStatus");

    if (profileName) {
        profileName.textContent = friendlyName;
        profileName.title = friendlyName;
    }

    if (usernameDisplay) {
        usernameDisplay.textContent = friendlyName;
    }

    if (userAvatar) {
        const initials = friendlyName
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map((part) => part.charAt(0))
            .join("")
            .toUpperCase();

        userAvatar.textContent = initials || "G";
        userAvatar.setAttribute("aria-label", friendlyName);
    }

    if (accountStatus) {
        accountStatus.textContent = isGuest
            ? `Guest workspace · ${guestQuestionsRemaining ?? guestQuestionLimit} questions left`
            : "Personal workspace";
    }
}

/* =========================================================
   ACCOUNT MENU AND SERVER-SIDE LOGOUT
========================================================= */

function initializeAccountMenu() {
    const menuButton = getElement("accountMenuButton");
    const menu = getElement("accountMenu");
    const signOutButton = getElement("signOutButton");

    if (menuButton && menu) {
        menuButton.setAttribute("aria-expanded", "false");

        menuButton.addEventListener("click", (event) => {
            event.stopPropagation();

            menu.hidden = !menu.hidden;

            menuButton.setAttribute(
                "aria-expanded",
                String(!menu.hidden)
            );
        });

        document.addEventListener("click", (event) => {
            if (
                !menu.contains(event.target) &&
                !menuButton.contains(event.target)
            ) {
                menu.hidden = true;
                menuButton.setAttribute("aria-expanded", "false");
            }
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                menu.hidden = true;
                menuButton.setAttribute("aria-expanded", "false");
            }
        });
    }

    signOutButton?.addEventListener("click", signOut);
}

async function signOut() {
    const button = getElement("signOutButton");

    if (button) {
        button.disabled = true;
    }

    try {
        const response = await fetch("/logout", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                Accept: "application/json"
            }
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));

            throw new Error(
                data.message || "The server could not end your session."
            );
        }
    } catch (error) {
        console.error("Logout request failed:", error);

        if (button) {
            button.disabled = false;
        }

        alert(
            "Could not confirm logout with the server. Please try again."
        );

        return;
    }

    try {
        localStorage.removeItem("username");
        localStorage.removeItem("displayName");
        localStorage.removeItem("full_name");
        localStorage.removeItem("name");
    } catch (error) {
        console.warn("Could not clear old browser identity values.", error);
    }

    window.location.replace("/login");
}

/* =========================================================
   LIGHT / DARK THEME
========================================================= */

function initializeTheme() {
    let savedTheme = "light";

    try {
        const stored = localStorage.getItem("documentAITheme");

        if (stored === "light" || stored === "dark") {
            savedTheme = stored;
        }
    } catch (error) {
        console.warn("Could not read saved theme.", error);
    }

    applyTheme(savedTheme);
}

function applyTheme(theme) {
    const selectedTheme = theme === "dark" ? "dark" : "light";

    document.documentElement.dataset.theme = selectedTheme;

    const toggle = getElement("themeToggle");

    if (toggle) {
        const isDark = selectedTheme === "dark";

        const label = isDark
            ? "Switch to light theme"
            : "Switch to dark theme";

        toggle.setAttribute("aria-label", label);
        toggle.setAttribute("title", label);

        const sun = toggle.querySelector(".sun-icon");
        const moon = toggle.querySelector(".moon-icon");

        if (sun) sun.hidden = isDark;
        if (moon) moon.hidden = !isDark;
    }

    try {
        localStorage.setItem("documentAITheme", selectedTheme);
    } catch (error) {
        console.warn("Could not save theme preference.", error);
    }
}

function toggleTheme() {
    const current = document.documentElement.dataset.theme;

    applyTheme(current === "dark" ? "light" : "dark");
}

/* =========================================================
   CHAT FORM AND INPUT
========================================================= */

function initializeChatForm() {
    const form = getElement("chatForm");
    const input = getElement("userInput");

    form?.addEventListener("submit", (event) => {
        event.preventDefault();
        sendMessage();
    });

    input?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    });

    input?.addEventListener("input", resizeInput);
}

function resizeInput() {
    const input = getElement("userInput");
    if (!input) return;

    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
}

/* =========================================================
   WELCOME SCREEN
========================================================= */

function renderWelcomeScreen() {
    const chatbox = getElement("chatbox");
    if (!chatbox) return;

    chatbox.replaceChildren();

    const template = document.createElement("template");

    template.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                    <path
                        d="M12 3.5 14.3 9.7 20.5 12l-6.2 2.3L12 20.5l-2.3-6.2L3.5 12l6.2-2.3L12 3.5Z"
                        stroke="currentColor"
                        stroke-width="1.5"
                        stroke-linejoin="round"
                    />
                </svg>
            </div>

            <p class="welcome-eyebrow">WELCOME TO DOCUMENT AI</p>

            <h2>What would you like to discover?</h2>

            <p class="welcome-description">
                Ask a question, explore a document, or connect the dots
                across your knowledge base.
            </p>

            <div class="suggestion-grid">
                <button type="button" class="suggestion-card"
                    data-prompt="Summarize my uploaded documents.">
                    <span class="suggestion-icon" aria-hidden="true">▤</span>
                    <span>
                        <strong>Summarize my files</strong>
                        <small>Get the key takeaways</small>
                    </span>
                </button>

                <button type="button" class="suggestion-card"
                    data-prompt="What are the most important details in my documents?">
                    <span class="suggestion-icon" aria-hidden="true">⌕</span>
                    <span>
                        <strong>Find key information</strong>
                        <small>Surface useful details</small>
                    </span>
                </button>

                <button type="button" class="suggestion-card"
                    data-prompt="What topics are covered in my uploaded documents?">
                    <span class="suggestion-icon" aria-hidden="true">◇</span>
                    <span>
                        <strong>Explore a topic</strong>
                        <small>Understand what's covered</small>
                    </span>
                </button>

                <button type="button" class="suggestion-card"
                    data-prompt="Explain a concept from my documents in simple terms.">
                    <span class="suggestion-icon" aria-hidden="true">✳</span>
                    <span>
                        <strong>Explain something</strong>
                        <small>Make complex ideas clearer</small>
                    </span>
                </button>
            </div>
        </div>
    `;

    chatbox.appendChild(template.content.cloneNode(true));
}

function hideWelcomeMessage() {
    getElement("chatbox")
        ?.querySelector(".welcome-message")
        ?.remove();
}

function startNewChat() {
    if (isSendingMessage) return;

    if (isGuest && Number(guestQuestionsRemaining) <= 0) {
        showGuestLimitPrompt();
        return;
    }

    renderWelcomeScreen();

    const input = getElement("userInput");

    if (input) {
        input.value = "";
        input.style.height = "auto";
        input.focus();
    }

    // This clears the visible conversation only.
    // Saved chat history remains in the database.
}

/* =========================================================
   SAFE BASIC MARKDOWN RENDERING
========================================================= */

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => {
        const entities = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        };

        return entities[character];
    });
}

function renderFormattedText(value) {
    let text = escapeHTML(value);

    // Inline code.
    text = text.replace(/`([^`\n]+)`/g, "<code>$1</code>");

    // Bold.
    text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    // Italic.
    text = text.replace(
        /(^|[^*])\*([^*\n]+)\*/g,
        "$1<em>$2</em>"
    );

    // Basic headings.
    text = text.replace(/^### (.+)$/gm, "<strong>$1</strong>");
    text = text.replace(/^## (.+)$/gm, "<strong>$1</strong>");
    text = text.replace(/^# (.+)$/gm, "<strong>$1</strong>");

    // Preserve simple list markers and line breaks.
    text = text.replace(/^[•*-]\s+(.+)$/gm, "• $1");
    text = text.replace(/\n/g, "<br>");

    return text;
}

/* =========================================================
   CHAT MESSAGES
========================================================= */

function addMessage(role, content, sources = []) {
    const chatbox = getElement("chatbox");
    if (!chatbox) return null;

    hideWelcomeMessage();

    const normalizedRole = role === "user" ? "user" : "assistant";
    const messageElement = document.createElement("div");

    messageElement.className =
        `message ${normalizedRole}` +
        (normalizedRole === "assistant" ? " bot" : "");

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = renderFormattedText(content || "");

    messageElement.appendChild(bubble);

    if (
        normalizedRole === "assistant" &&
        Array.isArray(sources) &&
        sources.length > 0
    ) {
        const sourceElement = renderSources(sources);

        if (sourceElement) {
            messageElement.appendChild(sourceElement);
        }
    }

    chatbox.appendChild(messageElement);
    scrollChatToBottom();

    return messageElement;
}

/* =========================================================
   RETRIEVED SOURCE REFERENCES
========================================================= */

function renderSources(sources) {
    if (!Array.isArray(sources) || sources.length === 0) {
        return null;
    }

    const container = document.createElement("div");
    container.className = "source-list";

    const heading = document.createElement("div");
    heading.className = "source-heading";
    heading.textContent = `Sources (${sources.length})`;

    container.appendChild(heading);

    sources.forEach((source) => {
        const item = document.createElement("div");
        item.className = "source-item";

        const row = document.createElement("div");
        row.className = "source-row";

        const name = document.createElement("span");
        name.className = "source-name";

        const filename = source.filename || "Unknown document";
        const page = source.page;

        const validPage =
            page !== null &&
            page !== undefined &&
            page !== "" &&
            String(page).toLowerCase() !== "unknown";

        name.textContent = validPage
            ? `${filename} · Page ${page}`
            : filename;

        row.appendChild(name);

        const scoreValue = Number(source.score);

        if (
            source.score !== null &&
            source.score !== undefined &&
            source.score !== "" &&
            Number.isFinite(scoreValue)
        ) {
            const score = document.createElement("span");
            score.className = "source-score";

            const percentage = scoreValue <= 1
                ? scoreValue * 100
                : scoreValue;

            score.textContent = `${percentage.toFixed(1)}% match`;
            score.title =
                "Document retrieval similarity, not verified answer accuracy.";

            row.appendChild(score);
        }

        item.appendChild(row);

        const excerpt = source.excerpt || source.text || "";

        if (String(excerpt).trim()) {
            const details = document.createElement("details");
            details.className = "source-details";

            const summary = document.createElement("summary");
            summary.textContent = "View excerpt";

            const excerptElement = document.createElement("p");
            excerptElement.className = "source-excerpt";
            excerptElement.textContent = excerpt;

            details.append(summary, excerptElement);
            item.appendChild(details);
        }

        container.appendChild(item);
    });

    return container;
}

/* =========================================================
   LOADING INDICATOR
========================================================= */

function showLoading(message = "Thinking...") {
    const chatbox = getElement("chatbox");
    if (!chatbox) return null;

    hideWelcomeMessage();

    const loadingElement = document.createElement("div");
    loadingElement.className = "message assistant bot";
    loadingElement.id = "assistantLoading";

    const bubble = document.createElement("div");
    bubble.className = "bubble loading";
    bubble.textContent = message;

    loadingElement.appendChild(bubble);
    chatbox.appendChild(loadingElement);

    scrollChatToBottom();

    return loadingElement;
}

/* =========================================================
   GUEST QUESTION STATUS
========================================================= */

function updateGuestStatus() {
    if (!isGuest) return;

    const accountStatus = getElement("accountStatus");

    if (accountStatus) {
        accountStatus.textContent =
            `Guest workspace · ${guestQuestionsRemaining} questions left`;
    }

    let status = getElement("guestQuestionStatus");

    if (!status) {
        status = document.createElement("div");
        status.id = "guestQuestionStatus";
        status.className = "guest-question-status";
        status.setAttribute("role", "status");

        const chatbox = getElement("chatbox");

        if (chatbox?.parentElement) {
            chatbox.parentElement.insertBefore(status, chatbox);
        }
    }

    if (status) {
        status.textContent =
            `Guest mode: ${guestQuestionsRemaining} of ` +
            `${guestQuestionLimit} questions remaining.`;
    }
}

/* =========================================================
   SEND CHAT MESSAGE — POST /chat
========================================================= */

async function sendMessage() {
    if (isSendingMessage || !sessionReady) return;

    const input = getElement("userInput");
    const sendButton = getElement("sendButton");

    if (!input) return;

    if (isGuest && Number(guestQuestionsRemaining) <= 0) {
        showGuestLimitPrompt();
        return;
    }

    const messageText = input.value.trim();
    if (!messageText) return;

    isSendingMessage = true;

    addMessage("user", messageText);

    input.value = "";
    input.style.height = "auto";
    input.disabled = true;

    if (sendButton) {
        sendButton.disabled = true;
    }

    const loadingElement = showLoading("Thinking...");

    try {
        const response = await fetch("/chat", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json"
            },
            // The server identifies the user from the session cookie.
            body: JSON.stringify({
                message: messageText
            })
        });

        const data = await response.json().catch(() => ({}));

        if (response.status === 401) {
            window.location.replace("/login");
            return;
        }

        if (
            response.status === 429 ||
            data.limit_reached === true
        ) {
            loadingElement?.remove();

            if (isGuest) {
                guestQuestionsRemaining = 0;
                updateGuestStatus();
                showGuestLimitPrompt();
            } else {
                addMessage(
                    "assistant",
                    data.message ||
                    data.error ||
                    "The request limit has been reached. Please try again later."
                );
            }

            return;
        }

        if (!response.ok || data.success === false) {
            throw new Error(
                data.error ||
                data.message ||
                data.response ||
                `Chat request failed (${response.status}).`
            );
        }

        const answer =
            data.response ||
            data.answer ||
            data.message ||
            "I couldn't generate a response.";

        loadingElement?.remove();

        addMessage(
            "assistant",
            answer,
            normalizeSources(data.sources)
        );

        // Update the count from the server after a successful response.
        if (isGuest) {
            if (data.questions_remaining !== undefined) {
                guestQuestionsRemaining = Math.max(
                    0,
                    Number(data.questions_remaining) || 0
                );
            } else {
                // Fallback for a backend that does not return the count.
                guestQuestionsRemaining = Math.max(
                    0,
                    guestQuestionsRemaining - 1
                );
            }

            updateGuestStatus();

            if (
                guestQuestionsRemaining <= 0 ||
                data.limit_reached === true
            ) {
                showGuestLimitPrompt();
            }
        }
    } catch (error) {
        console.error("Chat request failed:", error);
        loadingElement?.remove();

        addMessage(
            "assistant",
            `Sorry, I couldn't complete your request. ${error.message}`
        );
    } finally {
        isSendingMessage = false;

        // Do not re-enable input after the guest has reached the limit.
        if (!(isGuest && Number(guestQuestionsRemaining) <= 0)) {
            input.disabled = false;

            if (sendButton) {
                sendButton.disabled = false;
            }

            input.focus();
        }
    }
}

/* =========================================================
   LOAD SAVED CHAT HISTORY
========================================================= */

async function loadHistory() {
    const chatbox = getElement("chatbox");
    if (!chatbox || !username || isGuest) {
        renderWelcomeScreen();
        return;
    }

    try {
        const response = await fetch(
            `/history/${encodeURIComponent(username)}`,
            {
                credentials: "same-origin",
                cache: "no-store"
            }
        );

        if (response.status === 401) {
            window.location.replace("/login");
            return;
        }

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(
                data.message ||
                `History request failed (${response.status}).`
            );
        }

        const history = Array.isArray(data)
            ? data
            : data.history;

        if (!Array.isArray(history)) {
            throw new Error(
                "Unexpected history response. Expected a history array."
            );
        }

        if (history.length === 0) {
            renderWelcomeScreen();
            return;
        }

        chatbox.replaceChildren();

        history.forEach((item) => {
            if (item.message) {
                addMessage("user", item.message);
            }

            if (item.response) {
                addMessage(
                    "assistant",
                    item.response,
                    normalizeSources(item.sources)
                );
            }
        });

        scrollChatToBottom();
    } catch (error) {
        console.error("Could not restore saved chat history:", error);

        chatbox.replaceChildren();

        addMessage(
            "assistant",
            "I couldn't load the saved conversation. Your saved database records have not been deleted. Please check the Flask terminal."
        );
    }
}

/* =========================================================
   LOAD SAVED DOCUMENTS
========================================================= */

async function loadDocuments() {
    const documentsList = getElement("documentsList");

    if (!documentsList) return;

    // Guests cannot access a registered user's documents.
    if (isGuest) {
        documentsList.replaceChildren();

        const empty = document.createElement("p");
        empty.className = "document-empty";
        empty.textContent =
            "Create an account or sign in to upload and manage documents.";

        documentsList.appendChild(empty);
        return;
    }

    if (!username || !sessionReady) return;

    documentsList.replaceChildren();

    const loadingText = document.createElement("p");
    loadingText.className = "document-empty";
    loadingText.textContent = "Loading documents...";

    documentsList.appendChild(loadingText);

    try {
        const response = await fetch(
            `/documents/${encodeURIComponent(username)}`,
            {
                credentials: "same-origin",
                cache: "no-store"
            }
        );

        if (response.status === 401) {
            window.location.replace("/login");
            return;
        }

        const data = await response.json().catch(() => ({}));

        if (!response.ok || data.success === false) {
            throw new Error(
                data.message ||
                `Document request failed (${response.status}).`
            );
        }

        const documents = Array.isArray(data)
            ? data
            : data.documents;

        if (!Array.isArray(documents)) {
            throw new Error(
                "Unexpected document response. Expected a documents array."
            );
        }

        documentsList.replaceChildren();

        if (documents.length === 0) {
            const empty = document.createElement("p");
            empty.className = "document-empty";
            empty.textContent = "No documents uploaded yet.";

            documentsList.appendChild(empty);
            return;
        }

        documents.forEach((doc) => {
            const item = document.createElement("div");
            item.className = "document-item";

            const name = document.createElement("div");
            name.className = "document-name";
            name.textContent = doc.filename || "Untitled document";

            const metadata = document.createElement("div");
            metadata.className = "document-meta";

            const filetype = String(
                doc.filetype || "document"
            ).toUpperCase();

            const chunks = Number(
                doc.chunks ?? doc.chunk_count ?? 0
            );

            metadata.textContent = `${filetype} · ${chunks} chunks`;

            item.append(name, metadata);

            if (doc.uploaded_at) {
                const date = document.createElement("div");
                date.className = "document-date";
                date.textContent = `Uploaded: ${doc.uploaded_at}`;

                item.appendChild(date);
            }

            documentsList.appendChild(item);
        });
    } catch (error) {
        console.error("Could not load saved documents:", error);

        documentsList.replaceChildren();

        const errorMessage = document.createElement("p");
        errorMessage.className = "document-empty";
        errorMessage.textContent =
            "Could not load documents. Check the browser console and Flask terminal.";

        documentsList.appendChild(errorMessage);
    }
}

/* =========================================================
   UPLOAD PDF / DOCX — POST /upload
========================================================= */

async function uploadPDF() {
    if (isUploadingFiles || !sessionReady) return;

    if (isGuest) {
        setStatus(
            "uploadStatus",
            "Please register or sign in before uploading documents.",
            true
        );
        return;
    }

    const fileInput = getElement("pdfFile");
    const uploadButton = getElement("uploadButton");

    if (!fileInput || !fileInput.files) {
        setStatus(
            "uploadStatus",
            "File input was not found.",
            true
        );
        return;
    }

    const files = Array.from(fileInput.files);

    if (files.length === 0) {
        setStatus(
            "uploadStatus",
            "Please select at least one PDF or DOCX file.",
            true
        );
        return;
    }

    const validFiles = [];
    const results = [];

    files.forEach((file) => {
        const extension = file.name
            .split(".")
            .pop()
            .toLowerCase();

        if (!["pdf", "docx"].includes(extension)) {
            results.push(
                `${file.name}: only PDF and DOCX files are supported.`
            );
        } else if (file.size > MAX_UPLOAD_SIZE) {
            results.push(
                `${file.name}: exceeds the 10 MB limit.`
            );
        } else {
            validFiles.push(file);
        }
    });

    if (validFiles.length === 0) {
        setStatus("uploadStatus", results.join("\n"), true);
        return;
    }

    isUploadingFiles = true;

    if (uploadButton) {
        uploadButton.disabled = true;
    }

    let uploadedCount = 0;
    let sessionExpired = false;

    try {
        for (const file of validFiles) {
            setStatus(
                "uploadStatus",
                `Uploading ${file.name}...`
            );

            const formData = new FormData();
            formData.append("file", file);

            try {
                const response = await fetch("/upload", {
                    method: "POST",
                    credentials: "same-origin",
                    body: formData
                });

                const data = await response.json().catch(() => ({}));

                if (response.status === 401) {
                    sessionExpired = true;
                    break;
                }

                if (!response.ok || data.success === false) {
                    throw new Error(
                        data.error ||
                        data.message ||
                        `Upload failed (${response.status}).`
                    );
                }

                uploadedCount++;

                const chunks =
                    data.chunks ??
                    data.chunks_indexed ??
                    "processed";

                results.push(
                    `${file.name}: uploaded successfully (${chunks} chunks).`
                );
            } catch (error) {
                console.error(
                    `Upload failed for ${file.name}:`,
                    error
                );

                results.push(`${file.name}: ${error.message}`);
            }
        }

        if (sessionExpired) {
            window.location.replace("/login");
            return;
        }

        if (uploadedCount > 0) {
            await loadDocuments();
        }

        setStatus(
            "uploadStatus",
            results.join("\n") ||
            `${uploadedCount} file(s) uploaded successfully.`,
            uploadedCount === 0
        );
    } catch (error) {
        console.error("Upload process failed:", error);

        setStatus(
            "uploadStatus",
            error.message || "The upload process failed.",
            true
        );
    } finally {
        isUploadingFiles = false;

        if (uploadButton) {
            uploadButton.disabled = isGuest;
        }

        fileInput.value = "";
    }
}

/* =========================================================
   CLEAR VISIBLE CONVERSATION
   Does not delete saved history from SQLite.
========================================================= */

function clearChat() {
    if (isSendingMessage) return;

    const chatbox = getElement("chatbox");
    if (!chatbox) return;

    chatbox.replaceChildren();

    if (isGuest && Number(guestQuestionsRemaining) <= 0) {
        showGuestLimitPrompt();
        return;
    }

    renderWelcomeScreen();
}

/* =========================================================
   OPTIONAL GLOBAL EXPORTS FOR EXISTING INLINE HTML
========================================================= */

window.startNewChat = startNewChat;
window.clearChat = clearChat;
window.uploadPDF = uploadPDF;
window.toggleTheme = toggleTheme;
window.sendMessage = sendMessage;
