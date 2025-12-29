const statusContent = document.querySelector(".status-content");
const statusDot = document.querySelector(".status-dot");
const actions = document.querySelector(".actions");
let loadingTimer = null;
let isLoading = false;

// Temporary default: show Anki as online until real status is wired up.
if (statusDot) {
  statusDot.classList.add("is-offline");
}

// Placeholder copy for each action; wire these to real responses later.
const messages = {
  scan: () => {
    const dupes = Math.floor(Math.random() * 6);
    const fresh = Math.floor(Math.random() * 12) + 1;
    return `dupes ${dupes}, new ${fresh}`;
  },
  sync: () => {
    const count = Math.floor(Math.random() * 30) + 1;
    return `succesfuly synced ${count} flashcards`;
  },
  "dry-run": () => (Math.random() > 0.5 ? "ready" : "not ready"),
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

// Single-flight handler: ignore new clicks while an action is running.
actions.addEventListener("click", (event) => {
  const target = event.target;
  if (!target.classList.contains("action-btn")) return;
  if (isLoading) return;
  const action = target.textContent.trim();
  startLoading();
  window.setTimeout(() => {
    const getMessage = messages[action];
    stopLoading(getMessage ? getMessage() : "idle");
  }, 1100);
});
