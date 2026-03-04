// ── Live Clock ─────────────────────────────────────────────
function updateClock() {
    const el = document.getElementById("live-clock");
    if (el) {
        const now = new Date();
        el.textContent = now.toLocaleTimeString("en-IN", {
            hour: "2-digit", minute: "2-digit", second: "2-digit"
        }) + " — " + now.toLocaleDateString("en-IN", {
            weekday: "long", year: "numeric", month: "long", day: "numeric"
        });
    }
}
setInterval(updateClock, 1000);
updateClock();

// ── Session Polling ────────────────────────────────────────
let pollingInterval = null;

function startPolling() {
    pollingInterval = setInterval(fetchSessionStatus, 2000);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

function fetchSessionStatus() {
    fetch("/session_status")
        .then(r => r.json())
        .then(data => {
            updateLogBox(data.log);
            updateProgressBar(data.photo_count);

            if (!data.running) {
                stopPolling();
                enableButtons();
                document.getElementById("spinner").style.display = "none";

                if (data.status === "complete") {
                    setTimeout(() => location.reload(), 2000);
                }
            }
        })
        .catch(err => console.error("Polling error:", err));
}

// ── Log Box ────────────────────────────────────────────────
function updateLogBox(logs) {
    const box = document.getElementById("log-box");
    if (!box) return;
    box.innerHTML = logs.map(l => `<div>${l}</div>`).join("");
    box.scrollTop = box.scrollHeight;
}

// ── Progress Bar ───────────────────────────────────────────
function updateProgressBar(photoCount) {
    const bar  = document.getElementById("progress-bar");
    const text = document.getElementById("progress-text");
    if (!bar || !text) return;

    const pct = (photoCount / 5) * 100;
    bar.style.width  = pct + "%";
    text.textContent = `Photo ${photoCount} of 5`;
}

// ── Button State ───────────────────────────────────────────
function disableButtons() {
    const btns = ["btn-lecture", "btn-demo"];
    btns.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = true;
    });
}

function enableButtons() {
    const btns = ["btn-lecture", "btn-demo"];
    btns.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = false;
    });
}

// ── Start Demo Mode ────────────────────────────────────────
function startDemo() {
    if (!confirm("Start Demo Mode? This will take 5 photos in 20 seconds.")) return;

    showLogCard();
    disableButtons();
    updateLogBox(["[Starting] Demo mode initializing..."]);
    updateProgressBar(0);

    fetch("/start_demo", { method: "POST" })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                enableButtons();
                return;
            }
            startPolling();
        })
        .catch(err => {
            alert("Failed to start demo mode");
            enableButtons();
        });
}

// ── Start Lecture Mode ─────────────────────────────────────
function startLecture() {
    if (!confirm("Start Real Lecture Mode? This will run for the full lecture duration.")) return;

    showLogCard();
    disableButtons();
    updateLogBox(["[Starting] Lecture mode initializing..."]);
    updateProgressBar(0);

    fetch("/start_lecture", { method: "POST" })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                enableButtons();
                return;
            }
            startPolling();
        })
        .catch(err => {
            alert("Failed to start lecture mode");
            enableButtons();
        });
}

// ── Show Log Card ──────────────────────────────────────────
function showLogCard() {
    const card = document.getElementById("session-log-card");
    const spin = document.getElementById("spinner");
    if (card) card.style.display = "block";
    if (spin) spin.style.display = "inline-block";
    card.scrollIntoView({ behavior: "smooth" });
}