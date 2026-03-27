async function requestSession() {
    const response = await fetch("/auth/session", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
    });

    if (!response.ok) {
        throw new Error("Session konnte nicht geprueft werden.");
    }

    return response.json();
}

async function login(username, password) {
    const response = await fetch("/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
        },
        body: JSON.stringify({ username, password }),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.detail || "Anmeldung fehlgeschlagen.");
    }

    return payload;
}

function setMessage(message) {
    const messageNode = document.getElementById("login-message");
    messageNode.textContent = message;
}

window.addEventListener("DOMContentLoaded", async () => {
    const form = document.getElementById("login-form");
    const usernameInput = document.getElementById("username");
    const passwordInput = document.getElementById("password");
    const loginButton = document.getElementById("login-button");

    try {
        const session = await requestSession();
        if (session.authenticated) {
            window.location.replace("/admin");
            return;
        }
    } catch (error) {
        setMessage(error.message);
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        setMessage("");

        const username = usernameInput.value.trim();
        const password = passwordInput.value;
        if (!username || !password) {
            setMessage("Bitte Benutzername und Passwort eingeben.");
            return;
        }

        loginButton.disabled = true;
        loginButton.textContent = "Pruefe Zugang...";

        try {
            await login(username, password);
            window.location.replace("/admin");
        } catch (error) {
            setMessage(error.message);
            passwordInput.focus();
            passwordInput.select();
        } finally {
            loginButton.disabled = false;
            loginButton.textContent = "Anmelden";
        }
    });
});
