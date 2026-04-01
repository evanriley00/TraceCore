const STORAGE_KEY = "tracecore-control-room-state";
const SUPPORTED_UPLOAD_EXTENSIONS = new Set([
  "txt",
  "md",
  "markdown",
  "csv",
  "tsv",
  "json",
  "log",
  "html",
  "htm",
  "xml",
  "yaml",
  "yml",
  "rst",
]);

const defaultState = {
  accessToken: "",
  apiKey: "",
  user: null,
  sessionKey: "",
  lastRequestId: null,
  lastResult: null,
  lastDocument: null,
  runs: [],
  health: null,
  logs: [],
  authMode: "register",
};

const state = loadState();
const dom = {};
let toastTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  captureDom();
  bindEvents();
  applyState();
  refreshHealth();

  if (hasAuth()) {
    hydrateSession();
  } else {
    pushLog("Ready. Create an account or log in, then the UI will handle the auth headers for you.");
  }
});

function captureDom() {
  dom.authStatus = document.querySelector("#auth-status");
  dom.cacheStatus = document.querySelector("#cache-status");
  dom.sessionStatus = document.querySelector("#session-status");
  dom.activityLog = document.querySelector("#activity-log");
  dom.loadSample = document.querySelector("#load-sample");
  dom.refreshRuns = document.querySelector("#refresh-runs");
  dom.authRegisterTab = document.querySelector("#auth-register-tab");
  dom.authLoginTab = document.querySelector("#auth-login-tab");
  dom.registerForm = document.querySelector("#register-form");
  dom.loginForm = document.querySelector("#login-form");
  dom.authSummary = document.querySelector("#auth-summary");
  dom.signOut = document.querySelector("#sign-out");
  dom.identityCard = document.querySelector("#identity-card");
  dom.identityName = document.querySelector("#identity-name");
  dom.identityDetail = document.querySelector("#identity-detail");
  dom.authModeBadge = document.querySelector("#auth-mode-badge");
  dom.docTitle = document.querySelector("#doc-title");
  dom.docSource = document.querySelector("#doc-source");
  dom.docTags = document.querySelector("#doc-tags");
  dom.docFile = document.querySelector("#doc-file");
  dom.docFileMeta = document.querySelector("#doc-file-meta");
  dom.docContent = document.querySelector("#doc-content");
  dom.ingestForm = document.querySelector("#ingest-form");
  dom.ingestSummary = document.querySelector("#ingest-summary");
  dom.queryForm = document.querySelector("#query-form");
  dom.queryQuestion = document.querySelector("#query-question");
  dom.querySessionKey = document.querySelector("#query-session-key");
  dom.queryUseCache = document.querySelector("#query-use-cache");
  dom.resultMeta = document.querySelector("#result-meta");
  dom.resultEmpty = document.querySelector("#result-empty");
  dom.resultPanel = document.querySelector("#result-panel");
  dom.metricsGrid = document.querySelector("#metrics-grid");
  dom.answerText = document.querySelector("#answer-text");
  dom.evidenceList = document.querySelector("#evidence-list");
  dom.runsList = document.querySelector("#runs-list");
  dom.feedbackForm = document.querySelector("#feedback-form");
  dom.feedbackRequestId = document.querySelector("#feedback-request-id");
  dom.feedbackRating = document.querySelector("#feedback-rating");
  dom.feedbackComment = document.querySelector("#feedback-comment");
  dom.useLastRequest = document.querySelector("#use-last-request");
  dom.toast = document.querySelector("#toast");
}

function bindEvents() {
  dom.authRegisterTab.addEventListener("click", () => switchAuthMode("register"));
  dom.authLoginTab.addEventListener("click", () => switchAuthMode("login"));
  dom.signOut.addEventListener("click", handleSignOut);
  dom.loadSample.addEventListener("click", loadDemoContent);
  dom.refreshRuns.addEventListener("click", () => fetchRuns());
  dom.useLastRequest.addEventListener("click", () => {
    if (!state.lastRequestId) {
      return;
    }

    dom.feedbackRequestId.value = String(state.lastRequestId);
    showToast(`Loaded request #${state.lastRequestId} into the feedback form.`, "info");
  });

  dom.registerForm.addEventListener("submit", handleRegister);
  dom.loginForm.addEventListener("submit", handleLogin);
  dom.docFile.addEventListener("change", handleDocumentFileSelection);
  dom.ingestForm.addEventListener("submit", handleIngest);
  dom.queryForm.addEventListener("submit", handleQuery);
  dom.feedbackForm.addEventListener("submit", handleFeedback);
}

function applyState() {
  const authReady = Boolean(state.user || state.accessToken || state.apiKey);
  const userName = state.user?.full_name || state.user?.email || "Not connected";

  dom.authRegisterTab.classList.toggle("is-active", state.authMode === "register");
  dom.authLoginTab.classList.toggle("is-active", state.authMode === "login");
  dom.registerForm.classList.toggle("is-hidden", state.authMode !== "register");
  dom.loginForm.classList.toggle("is-hidden", state.authMode !== "login");
  dom.signOut.classList.toggle("is-hidden", !authReady);
  dom.identityCard.classList.toggle("is-hidden", !state.user);

  dom.authStatus.textContent = authReady ? userName : "Not connected";
  dom.authSummary.textContent = state.user
    ? "You are connected. The UI is now attaching auth headers automatically."
    : "Create a local account once and the UI will keep the token for you in this browser.";

  if (state.user) {
    dom.identityName.textContent = state.user.full_name || state.user.email;
    dom.identityDetail.textContent = `${state.user.email} | user #${state.user.id}`;
    dom.authModeBadge.textContent = activeAuthBadge();
  }

  dom.sessionStatus.textContent = state.sessionKey
    ? `Active ${shortId(state.sessionKey)}`
    : "No active session";

  dom.cacheStatus.textContent = state.health
    ? `${state.health.cache_backend} cache`
    : "Checking";

  dom.ingestSummary.textContent = state.lastDocument
    ? buildIngestSummary(state.lastDocument)
    : "No document ingested yet.";

  if (state.sessionKey) {
    if (!dom.querySessionKey.value.trim()) {
      dom.querySessionKey.value = state.sessionKey;
    }
  } else {
    dom.querySessionKey.value = "";
  }

  if (state.lastRequestId) {
    dom.feedbackRequestId.value = String(state.lastRequestId);
  }

  renderLogs();
  renderResult();
  renderRuns();
  saveState();
}

function renderLogs() {
  if (!state.logs.length) {
    dom.activityLog.innerHTML = '<div class="empty-inline">No activity yet. The panel will narrate the main steps here.</div>';
    return;
  }

  dom.activityLog.innerHTML = state.logs
    .map(
      (entry) => `
        <article class="log-entry">
          <small>${formatTimestamp(entry.time)}</small>
          <div>${escapeHtml(entry.message)}</div>
        </article>
      `,
    )
    .join("");
}

function renderResult() {
  if (!state.lastResult) {
    dom.resultEmpty.classList.remove("is-hidden");
    dom.resultPanel.classList.add("is-hidden");
    dom.resultMeta.textContent = "No run yet.";
    return;
  }

  const result = state.lastResult;
  dom.resultEmpty.classList.add("is-hidden");
  dom.resultPanel.classList.remove("is-hidden");
  dom.resultMeta.textContent = `Request #${result.request_id} | ${result.cached ? "cache hit" : "fresh run"} | session ${shortId(result.session_key)}`;

  const tiles = [
    { label: "Query Type", value: humanize(result.query_type) },
    { label: "Confidence", value: formatPercent(result.confidence) },
    { label: "Eval Score", value: formatPercent(result.evaluation?.overall_score) },
    { label: "Evidence Hits", value: String(result.evidence?.length || 0) },
  ];

  dom.metricsGrid.innerHTML = tiles
    .map(
      (tile) => `
        <article class="metric-tile">
          <span>${escapeHtml(tile.label)}</span>
          <strong>${escapeHtml(tile.value)}</strong>
        </article>
      `,
    )
    .join("");

  dom.answerText.textContent = result.answer;

  if (!result.evidence?.length) {
    dom.evidenceList.innerHTML = '<div class="empty-inline">No evidence was attached to this result.</div>';
  } else {
    dom.evidenceList.innerHTML = result.evidence
      .map(
        (item) => `
          <article class="evidence-item">
            <strong>${escapeHtml(item.source || "Unknown source")}</strong>
            <div>${escapeHtml(item.snippet || "")}</div>
            <div class="run-meta">
              <span>score ${formatPercent(item.score)}</span>
              ${item.document_id ? `<span>document #${item.document_id}</span>` : ""}
            </div>
          </article>
        `,
      )
      .join("");
  }
}

function renderRuns() {
  if (!state.runs?.length) {
    dom.runsList.innerHTML = '<div class="empty-inline">Sign in and run a query to see history here.</div>';
    return;
  }

  dom.runsList.innerHTML = state.runs
    .map(
      (run) => `
        <article class="run-item">
          <strong>${escapeHtml(run.question)}</strong>
          <div class="support-text">${escapeHtml(humanize(run.query_type || "pending"))}</div>
          <div class="run-meta">
            <span>${escapeHtml(run.status)}</span>
            <span>${run.cache_hit ? "cache hit" : "fresh run"}</span>
            <span>${formatPercent(run.overall_score)}</span>
            <span>${formatTimestamp(run.created_at)}</span>
          </div>
        </article>
      `,
    )
    .join("");
}

async function refreshHealth() {
  try {
    state.health = await apiRequest("/health", { auth: false });
    applyState();
  } catch (error) {
    pushLog(`Could not read /health: ${error.message}`);
  }
}

async function hydrateSession() {
  try {
    const user = await apiRequest("/auth/me");
    state.user = user;
    pushLog(`Welcome back, ${user.full_name || user.email}.`);
    applyState();
    await fetchRuns(true);
  } catch (error) {
    clearAuth(false);
    showToast(`Saved auth expired: ${error.message}`, "error");
    pushLog("Saved auth could not be reused, so the UI cleared it for safety.");
  }
}

async function handleRegister(event) {
  event.preventDefault();
  const submitter = event.submitter || dom.registerForm.querySelector('button[type="submit"]');

  await withBusy(submitter, "Creating Account...", async () => {
    const payload = {
      full_name: dom.registerForm.querySelector("#register-name").value.trim() || null,
      email: dom.registerForm.querySelector("#register-email").value.trim(),
      password: dom.registerForm.querySelector("#register-password").value,
    };

    const response = await apiRequest("/auth/register", {
      method: "POST",
      auth: false,
      body: payload,
    });

    state.accessToken = response.access_token;
    state.apiKey = response.api_key;
    state.user = response.user;
    pushLog(`Registered ${response.user.email}. Bearer token and API key are now stored in this browser.`);
    applyState();
    showToast("Account created. You can move straight to ingesting a document.", "success");
    dom.registerForm.reset();
  });
}

async function handleLogin(event) {
  event.preventDefault();
  const submitter = event.submitter || dom.loginForm.querySelector('button[type="submit"]');

  await withBusy(submitter, "Logging In...", async () => {
    const payload = {
      email: dom.loginForm.querySelector("#login-email").value.trim(),
      password: dom.loginForm.querySelector("#login-password").value,
    };

    const response = await apiRequest("/auth/login", {
      method: "POST",
      auth: false,
      body: payload,
    });

    state.accessToken = response.access_token;
    state.user = response.user;
    pushLog(`Logged in as ${response.user.email}.`);
    applyState();
    showToast("Logged in. The UI will handle the Authorization header from now on.", "success");
    dom.loginForm.reset();
    await fetchRuns(true);
  });
}

async function handleIngest(event) {
  event.preventDefault();
  const submitter = event.submitter || dom.ingestForm.querySelector('button[type="submit"]');

  await withBusy(submitter, "Ingesting...", async () => {
    const payload = {
      title: dom.docTitle.value.trim(),
      source: dom.docSource.value.trim() || null,
      tags: dom.docTags.value.split(",").map((item) => item.trim()).filter(Boolean),
      content: dom.docContent.value.trim(),
    };

    const response = await apiRequest("/v1/documents/ingest", {
      method: "POST",
      body: payload,
    });

    state.lastDocument = response;
    pushLog(`Document "${response.title}" was queued and is available for retrieval right away.`);
    applyState();
    showToast("Document ingested. You can ask a question now.", "success");
  });
}

async function handleDocumentFileSelection(event) {
  const [file] = event.target.files || [];

  if (!file) {
    setDocumentFileMeta(
      "No file selected yet. Choose a text-based file and TraceCore will load it into the content preview below.",
    );
    return;
  }

  if (!isSupportedUpload(file)) {
    dom.docFile.value = "";
    setDocumentFileMeta(
      "That file type is not supported here yet. Use a text-based file such as .txt, .md, .csv, .json, or .html.",
      "error",
    );
    showToast("Choose a text-based file for document ingest.", "error");
    return;
  }

  try {
    const content = await file.text();
    const trimmedContent = content.trim();

    if (!trimmedContent) {
      throw new Error("The selected file is empty.");
    }

    dom.docContent.value = trimmedContent;

    if (!dom.docTitle.value.trim()) {
      dom.docTitle.value = deriveTitleFromFilename(file.name);
    }

    if (!dom.docSource.value.trim()) {
      dom.docSource.value = file.name;
    }

    setDocumentFileMeta(
      `Loaded ${file.name} (${formatFileSize(file.size)}). You can review or edit the extracted text below.`,
      "success",
    );
    pushLog(`Loaded "${file.name}" into the document content preview.`);
    showToast(`Loaded ${file.name}.`, "success");
  } catch (error) {
    dom.docFile.value = "";
    setDocumentFileMeta(
      "TraceCore could not read that file. Try a UTF-8 text file or paste the content manually.",
      "error",
    );
    showToast(error.message || "That file could not be read.", "error");
  }
}

async function handleQuery(event) {
  event.preventDefault();
  const submitter = event.submitter || dom.queryForm.querySelector('button[type="submit"]');

  await withBusy(submitter, "Running Workflow...", async () => {
    const payload = {
      question: dom.queryQuestion.value.trim(),
      session_key: dom.querySessionKey.value.trim() || null,
      use_cache: dom.queryUseCache.checked,
    };

    const response = await apiRequest("/v1/query", {
      method: "POST",
      body: payload,
    });

    state.lastResult = response;
    state.sessionKey = response.session_key;
    state.lastRequestId = response.request_id;
    pushLog(`Request #${response.request_id} completed as ${humanize(response.query_type)}.`);
    applyState();
    showToast(response.cached ? "Query answered from cache." : "Decision workflow completed.", "success");
    await fetchRuns(true);
  });
}

async function handleFeedback(event) {
  event.preventDefault();
  const submitter = event.submitter || dom.feedbackForm.querySelector('button[type="submit"]');

  await withBusy(submitter, "Saving Feedback...", async () => {
    const payload = {
      request_id: Number(dom.feedbackRequestId.value),
      rating: Number(dom.feedbackRating.value),
      comment: dom.feedbackComment.value.trim() || null,
    };

    const response = await apiRequest("/v1/feedback", {
      method: "POST",
      body: payload,
    });

    pushLog(`Feedback saved for request #${response.request_id} with rating ${response.rating}.`);
    showToast("Feedback stored. This run is now part of the learning loop.", "success");
    dom.feedbackComment.value = "";
  });
}

async function fetchRuns(quiet = false) {
  if (!hasAuth()) {
    if (!quiet) {
      showToast("Sign in first so the UI can load your run history.", "info");
    }
    return;
  }

  try {
    state.runs = await apiRequest("/v1/runs");
    applyState();

    if (!quiet) {
      pushLog(`Loaded ${state.runs.length} recent runs.`);
      showToast("Run history refreshed.", "info");
    }
  } catch (error) {
    if (error.status === 401) {
      clearAuth(false);
    }

    showToast(error.message, "error");
  }
}

function handleSignOut() {
  clearAuth(true);
}

function clearAuth(announce = true) {
  state.accessToken = "";
  state.apiKey = "";
  state.user = null;
  state.sessionKey = "";
  state.lastRequestId = null;
  state.lastResult = null;
  state.runs = [];
  applyState();

  if (announce) {
    pushLog("Signed out locally. Tokens and cached UI session were cleared from this browser.");
    showToast("Signed out.", "info");
  }
}

function switchAuthMode(mode) {
  state.authMode = mode;
  applyState();
}

function loadDemoContent() {
  dom.docTitle.value = "Solar Energy Brief";
  dom.docSource.value = "internal_research";
  dom.docTags.value = "energy, solar, costs";
  dom.docFile.value = "";
  dom.docContent.value = "Solar energy reduces long-term electricity costs, improves grid resilience, and lowers carbon emissions when deployed at scale.";
  setDocumentFileMeta(
    "Demo content loaded directly into the preview. You can replace it by choosing a text-based file.",
    "success",
  );
  dom.queryQuestion.value = "Summarize solar energy and give evidence for the recommendation.";
  dom.queryUseCache.checked = true;
  pushLog("Loaded a demo document and sample question into the forms.");
  showToast("Demo content loaded.", "info");
}

async function apiRequest(path, { method = "GET", auth = true, body = null } = {}) {
  const headers = {};

  if (body !== null) {
    headers["Content-Type"] = "application/json";
  }

  if (auth) {
    Object.assign(headers, buildAuthHeaders());
  }

  const response = await fetch(path, {
    method,
    headers,
    body: body !== null ? JSON.stringify(body) : undefined,
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = typeof payload === "string"
      ? payload
      : payload?.detail || JSON.stringify(payload);
    const error = new Error(detail || `Request failed with ${response.status}`);
    error.status = response.status;
    throw error;
  }

  return payload;
}

function buildAuthHeaders() {
  if (state.accessToken) {
    return { Authorization: `Bearer ${state.accessToken}` };
  }

  if (state.apiKey) {
    return { "X-API-Key": state.apiKey };
  }

  const error = new Error("Sign in first so the UI can attach your request to a user.");
  error.status = 401;
  throw error;
}

async function withBusy(button, busyText, callback) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = busyText;

  try {
    await callback();
  } catch (error) {
    pushLog(error.message);
    showToast(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

function pushLog(message) {
  const lastMessage = state.logs[0]?.message;
  if (lastMessage === message) {
    return;
  }

  state.logs = [
    { time: new Date().toISOString(), message },
    ...state.logs,
  ].slice(0, 8);
  renderLogs();
  saveState();
}

function showToast(message, tone = "info") {
  dom.toast.textContent = message;
  dom.toast.className = `toast ${tone}`;
  dom.toast.classList.remove("is-hidden");

  if (toastTimer) {
    window.clearTimeout(toastTimer);
  }

  toastTimer = window.setTimeout(() => {
    dom.toast.classList.add("is-hidden");
  }, 3200);
}

function setDocumentFileMeta(message, tone = "info") {
  dom.docFileMeta.textContent = message;
  dom.docFileMeta.classList.toggle("is-success", tone === "success");
  dom.docFileMeta.classList.toggle("is-error", tone === "error");
}

function buildIngestSummary(document) {
  if (document.status === "queued") {
    return `Last document: "${document.title}" is queued and available for immediate queries.`;
  }

  return `Last document: "${document.title}" is ${document.status}.`;
}

function activeAuthBadge() {
  if (state.accessToken) {
    return "Bearer token ready";
  }

  if (state.apiKey) {
    return "API key ready";
  }

  return "No auth cached";
}

function hasAuth() {
  return Boolean(state.accessToken || state.apiKey);
}

function humanize(value) {
  if (!value) {
    return "Pending";
  }

  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortId(value) {
  if (!value) {
    return "Unknown";
  }

  return `${value.slice(0, 8)}...`;
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/a";
  }

  return `${Math.round(Number(value) * 100)}%`;
}

function formatTimestamp(value) {
  if (!value) {
    return "Just now";
  }

  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatFileSize(size) {
  if (!size) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];
  let value = size;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const roundedValue = value >= 10 || unitIndex === 0
    ? Math.round(value)
    : value.toFixed(1);

  return `${roundedValue} ${units[unitIndex]}`;
}

function deriveTitleFromFilename(filename) {
  const trimmedName = filename.trim();
  const extensionIndex = trimmedName.lastIndexOf(".");
  const baseName = extensionIndex > 0
    ? trimmedName.slice(0, extensionIndex)
    : trimmedName;

  return baseName.replace(/[_-]+/g, " ").trim() || "Uploaded Document";
}

function isSupportedUpload(file) {
  const normalizedName = file.name.trim().toLowerCase();
  const extension = normalizedName.includes(".")
    ? normalizedName.split(".").pop()
    : "";

  if (SUPPORTED_UPLOAD_EXTENSIONS.has(extension)) {
    return true;
  }

  return file.type.startsWith("text/") || file.type === "application/json" || file.type === "application/xml";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function loadState() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return cloneDefaultState();
    }

    return { ...cloneDefaultState(), ...JSON.parse(raw) };
  } catch {
    return cloneDefaultState();
  }
}

function saveState() {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...state }));
  } catch {
    return;
  }
}

function cloneDefaultState() {
  return JSON.parse(JSON.stringify(defaultState));
}
