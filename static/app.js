const statusContent = document.querySelector(".status-content");
const getStatusDot = () => document.querySelector(".status-dot");
const actions = document.querySelector(".actions");
const vaultInput = document.querySelector(".textbox");
const tableBody = document.querySelector("tbody");
const actionButtons = Array.from(document.querySelectorAll(".action-btn"));
let loadingTimer = null;
let isLoading = false;

const API = {
  health: "/api/health",
  scan: "/api/scan",
  sync: "/api/sync",
};

// Simulates a terminal-style progress bar using "#" ticks.
const startLoading = () => {
  isLoading = true;
  let ticks = 0;
  statusContent.textContent = "#";
  clearInterval(loadingTimer);
  loadingTimer = setInterval(() => {
    ticks = (ticks + 1) % 12;
    statusContent.textContent = "#".repeat(ticks + 1);
  }, 120);
};

// Stops the ticker and prints the final status message.
const stopLoading = (text) => {
  clearInterval(loadingTimer);
  statusContent.textContent = text;
  isLoading = false;
};

const setAnkiStatus = (online) => {
  const statusDot = getStatusDot();
  if (!statusDot) return;
  statusDot.classList.toggle("is-online", online);
};

const setStatus = (text) => {
  statusContent.textContent = text;
};

const setButtonsEnabled = (enabled) => {
  actionButtons.forEach((button) => {
    button.disabled = !enabled;
  });
};

const updateButtonState = () => {
  const value = vaultInput ? vaultInput.value.trim() : "";
  setButtonsEnabled(Boolean(value));
};

const renderCards = (cards) => {
  if (!tableBody) return;
  tableBody.innerHTML = "";
  if (!cards || cards.length === 0) {
    const row = document.createElement("tr");
    ["---", "---", "---"].forEach((text) => {
      const cell = document.createElement("td");
      cell.textContent = text;
      row.appendChild(cell);
    });
    tableBody.appendChild(row);
    return;
  }

  cards.forEach((card) => {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const frontCell = document.createElement("td");
    const backCell = document.createElement("td");
    nameCell.textContent = card.deck;
    frontCell.textContent = card.front;
    backCell.textContent = card.back;
    row.appendChild(nameCell);
    row.appendChild(frontCell);
    row.appendChild(backCell);
    tableBody.appendChild(row);
  });
};

const fetchHealth = async () => {
  try {
    const response = await fetch(API.health);
    if (!response.ok) {
      setAnkiStatus(false);
      return;
    }
    const data = await response.json();
    setAnkiStatus(Boolean(data.anki_online));
  } catch (error) {
    setAnkiStatus(false);
  }
};

const initStatus = () => {
  fetchHealth();
  setInterval(fetchHealth, 8000);
};

const buildPayload = () => {
  const vault = vaultInput ? vaultInput.value.trim() : "";
  return vault ? { vault } : {};
};

const handleScan = async () => {
  const response = await fetch(API.scan, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildPayload()),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "scan failed");
  }
  const data = await response.json();
  renderCards(data.cards);
  const suffix = data.truncated ? ` (showing ${data.returned_cards})` : "";
  return `new ${data.unique_cards}, dupes ${data.duplicate_cards}${suffix}`;
};

const handleSync = async (dryRun = false) => {
  const payload = buildPayload();
  if (dryRun) {
    payload.dry_run = true;
  }
  const response = await fetch(API.sync, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "sync failed");
  }
  const data = await response.json();
  const label = dryRun ? "dry-run" : "synced";
  return `${label}: ${data.added} add, ${data.updated} update`;
};

const actionHandlers = {
  scan: handleScan,
  sync: () => handleSync(false),
  "dry-run": () => handleSync(true),
};

// Single-flight handler: ignore new clicks while an action is running.
if (actions) {
  actions.addEventListener("click", async (event) => {
    const target = event.target;
    if (!target.classList.contains("action-btn")) return;
    if (isLoading) return;
    if (target.disabled) return;
    const action = target.dataset.action || target.textContent.trim();
    const handler = actionHandlers[action];
    if (!handler) return;
    startLoading();
    try {
      const message = await handler();
      stopLoading(message);
    } catch (error) {
      stopLoading(error.message || "error");
    }
  });
}

initStatus();
updateButtonState();
if (vaultInput) {
  vaultInput.addEventListener("input", updateButtonState);
}
