import "./style.css";

const apiBase = "/_/backend";

const newGameButton = document.querySelector("#newGame");
const scanButton = document.querySelector("#scan");
const refuelButton = document.querySelector("#refuel");
const repairButton = document.querySelector("#repair");
const statsEl = document.querySelector("#stats");
const mapEl = document.querySelector("#map");
const logEl = document.querySelector("#log");
const salvageEl = document.querySelector("#salvage");
const tradeEl = document.querySelector("#trade");
const encounterEl = document.querySelector("#encounter");
const statusMessageEl = document.querySelector("#statusMessage");
const travelButtons = document.querySelectorAll(".travel button[data-dir]");

let state = null;
let scanResults = [];

const formatStatus = (value, label) => `<div><span>${label}</span><strong>${value}</strong></div>`;

function renderStats() {
    if (!state) {
        statsEl.innerHTML = "<p>Start a new run to deploy your salvage rig.</p>";
        return;
    }

    statsEl.innerHTML = [
        formatStatus(state.turn, "Turn"),
        formatStatus(state.credits, "Credits"),
        formatStatus(state.fuel, "Fuel"),
        formatStatus(state.hull, "Hull"),
        formatStatus(`(${state.x}, ${state.y})`, "Sector"),
        formatStatus(state.status.toUpperCase(), "Status")
    ].join("");

    if (state.pendingEvent) {
        statusMessageEl.textContent = "Pirate ambush in progress. Resolve the encounter.";
    } else if (state.status === "won") {
        statusMessageEl.textContent = "Mission complete. Docked with a legendary haul.";
    } else if (state.status === "lost") {
        statusMessageEl.textContent = "Hull integrity lost. Salvage run terminated.";
    } else {
        statusMessageEl.textContent = "Goal: reach base with 120 credits.";
    }
}

function renderMap() {
    if (!state) {
        mapEl.innerHTML = "<p>Awaiting coordinates.</p>";
        return;
    }

    const size = state.mapSize;
    let html = "";
    for (let y = 0; y < size; y += 1) {
        for (let x = 0; x < size; x += 1) {
            const isBase = x === 0 && y === 0;
            const isCurrent = x === state.x && y === state.y;
            const classes = ["cell"];
            if (isBase) classes.push("base");
            if (isCurrent) classes.push("current");
            html += `<div class="${classes.join(" ")}">${isCurrent ? "YOU" : isBase ? "BASE" : ""}</div>`;
        }
    }
    mapEl.innerHTML = html;
}

function renderLog() {
    logEl.innerHTML = (state?.log || [])
        .slice()
        .reverse()
        .map((entry) => `<li>${entry}</li>`)
        .join("");
}

function renderSalvage() {
    if (!state) {
        salvageEl.innerHTML = "<p>No signals. Use scan to find targets.</p>";
        return;
    }

    if (!scanResults.length) {
        salvageEl.innerHTML = "<p>No salvage targets in this sector.</p>";
        return;
    }

    const disableActions = Boolean(state.pendingEvent);

    salvageEl.innerHTML = scanResults
        .map(
            (target) => `
                <div class="target">
                    <div>
                        <h3>${target.name}</h3>
                        <p>Value: ${target.value} cr | Risk: ${target.risk}</p>
                    </div>
                    <button data-salvage="${target.id}" ${disableActions ? "disabled" : ""}>Salvage</button>
                </div>
            `
        )
        .join("");

    salvageEl.querySelectorAll("button[data-salvage]").forEach((button) => {
        button.addEventListener("click", () => handleSalvage(button.dataset.salvage));
    });
}

function renderTrade() {
    if (!state) {
        tradeEl.innerHTML = "<p>No trade stations on comms.</p>";
        return;
    }

    const station = state.station;
    if (!station) {
        tradeEl.innerHTML = "<p>No trade station in this sector.</p>";
        return;
    }

    const disableActions = Boolean(state.pendingEvent);
    tradeEl.innerHTML = `
        <div class="station">
            <h3>${station.name}</h3>
            <p>Dock for supplies and upgrades.</p>
        </div>
        <div class="offers">
            ${station.offers
                .map(
                    (offer) => `
                        <div class="offer">
                            <span>${offer.label}</span>
                            <button data-trade="${offer.id}" ${disableActions ? "disabled" : ""}>
                                ${offer.price} cr
                            </button>
                        </div>
                    `
                )
                .join("")}
        </div>
    `;

    tradeEl.querySelectorAll("button[data-trade]").forEach((button) => {
        button.addEventListener("click", () => handleTrade(button.dataset.trade));
    });
}

function renderEncounter() {
    if (!state || !state.pendingEvent) {
        encounterEl.innerHTML = "<p>No active encounters.</p>";
        return;
    }

    const threat = state.pendingEvent.threat;
    encounterEl.innerHTML = `
        <div class="alert">Pirate ambush! Threat level ${threat}.</div>
        <div class="options">
            <button data-encounter="fight">Fight</button>
            <button data-encounter="bribe">Bribe</button>
            <button data-encounter="evade">Evade</button>
        </div>
        <p class="hint">Resolve the ambush to continue traveling.</p>
    `;

    encounterEl.querySelectorAll("button[data-encounter]").forEach((button) => {
        button.addEventListener("click", () => handleEncounter(button.dataset.encounter));
    });
}

function setBusy(isBusy) {
    const buttons = document.querySelectorAll("button");
    buttons.forEach((button) => {
        button.disabled = isBusy;
    });
}

async function request(path, payload) {
    const response = await fetch(`${apiBase}${path}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || "Request failed");
    }
    return response.json();
}

async function startGame() {
    setBusy(true);
    try {
        const response = await request("/new-game", {});
        state = response;
        scanResults = [];
        render();
    } catch (error) {
        alert(error.message);
    } finally {
        setBusy(false);
    }
}

async function handleScan() {
    if (!state) return;
    setBusy(true);
    try {
        const response = await request("/act", { game_id: state.id, action: "scan" });
        state = response;
        scanResults = response.nearby || [];
        render();
    } catch (error) {
        alert(error.message);
    } finally {
        setBusy(false);
    }
}

async function handleTravel(direction) {
    if (!state) return;
    setBusy(true);
    try {
        const response = await request("/act", {
            game_id: state.id,
            action: "travel",
            direction
        });
        state = response;
        scanResults = [];
        render();
    } catch (error) {
        alert(error.message);
    } finally {
        setBusy(false);
    }
}

async function handleSalvage(targetId) {
    if (!state) return;
    setBusy(true);
    try {
        const response = await request("/act", {
            game_id: state.id,
            action: "salvage",
            target_id: targetId
        });
        state = response;
        scanResults = scanResults.filter((item) => item.id !== targetId);
        render();
    } catch (error) {
        alert(error.message);
    } finally {
        setBusy(false);
    }
}

async function handleTrade(item) {
    if (!state) return;
    setBusy(true);
    try {
        const response = await request("/act", {
            game_id: state.id,
            action: "trade",
            item
        });
        state = response;
        render();
    } catch (error) {
        alert(error.message);
    } finally {
        setBusy(false);
    }
}

async function handleEncounter(action) {
    if (!state) return;
    setBusy(true);
    try {
        const response = await request("/act", {
            game_id: state.id,
            action
        });
        state = response;
        render();
    } catch (error) {
        alert(error.message);
    } finally {
        setBusy(false);
    }
}

async function handleRefuel() {
    if (!state) return;
    setBusy(true);
    try {
        const response = await request("/act", { game_id: state.id, action: "refuel" });
        state = response;
        render();
    } catch (error) {
        alert(error.message);
    } finally {
        setBusy(false);
    }
}

async function handleRepair() {
    if (!state) return;
    setBusy(true);
    try {
        const response = await request("/act", { game_id: state.id, action: "repair" });
        state = response;
        render();
    } catch (error) {
        alert(error.message);
    } finally {
        setBusy(false);
    }
}

function render() {
    renderStats();
    renderMap();
    renderLog();
    renderSalvage();
    renderTrade();
    renderEncounter();
    updateControls();
}

function updateControls() {
    const disableRegular = !state || Boolean(state.pendingEvent);
    scanButton.disabled = disableRegular;
    refuelButton.disabled = disableRegular;
    repairButton.disabled = disableRegular;
    travelButtons.forEach((button) => {
        button.disabled = disableRegular;
    });
}

newGameButton.addEventListener("click", startGame);
scanButton.addEventListener("click", handleScan);
refuelButton.addEventListener("click", handleRefuel);
repairButton.addEventListener("click", handleRepair);
travelButtons.forEach((button) => {
    button.addEventListener("click", () => handleTravel(button.dataset.dir));
});

render();
