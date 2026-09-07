const state = {
  datasetId: null,
  metadata: null,
  mainChart: null,
  secondaryChart: null,
  debounce: null,
  user: null,
  authMode: "login",
};

const $ = (id) => document.getElementById(id);

function status(message, error = false) {
  $("status").textContent = message;
  $("status").className = error
    ? "mt-3 text-sm text-red-400"
    : "mt-3 text-sm text-slate-400";
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || "Request failed.");
  return body;
}

function option(select, value, text = value) {
  const element = document.createElement("option");
  element.value = value;
  element.textContent = text;
  select.appendChild(element);
}

function setAuthenticated(user) {
  state.user = user;
  $("auth-modal").classList.add("hidden");
  $("workspace").classList.remove("pointer-events-none", "opacity-40");
  $("workspace-controls").classList.remove("pointer-events-none", "opacity-40");
  $("logout-btn").classList.remove("hidden");
  renderUser(user);
}

function setUnauthenticated() {
  state.user = null;
  state.datasetId = null;
  state.metadata = null;
  $("profile").textContent = "Create an account or sign in";
  $("tier-card").innerHTML = '<span class="font-semibold text-cyan-300">Free plan available</span><br><span class="text-sm text-slate-400">Create an account to start.</span>';
  $("auth-modal").classList.remove("hidden");
  $("workspace").classList.add("pointer-events-none", "opacity-40");
  $("workspace-controls").classList.add("pointer-events-none", "opacity-40");
  $("logout-btn").classList.add("hidden");
}

function renderUser(user) {
  $("profile").innerHTML =
    '<div class="font-medium truncate">' + escapeHtml(user.email) + '</div>' +
    '<div class="mt-1 text-xs text-slate-400">Personal workspace</div>';

  const plan = user.plan || {};
  const limits = plan.limits || {};
  $("tier-card").innerHTML =
    '<div class="font-semibold text-cyan-300">' + escapeHtml(plan.name || user.tier || "Free") + '</div>' +
    '<div class="mt-1 text-xs text-slate-300">' +
    'Up to ' + Number(limits.max_rows_per_dataset || 0).toLocaleString() +
    ' rows per dataset · ' + Number(limits.max_datasets || 0).toLocaleString() +
    ' datasets</div>';
}

function renderMetadata(metadata) {
  state.metadata = metadata;
  const metric = $("metric-select");
  const group = $("group-select");

  metric.innerHTML = "";
  group.innerHTML = "";

  metadata.metrics.forEach((value) => option(metric, value));
  [...metadata.dimensions, ...metadata.dates].forEach((value) => option(group, value));

  const host = $("dynamic-filters");
  host.innerHTML = "";

  metadata.dimensions.forEach((field) => {
    const wrapper = document.createElement("details");
    wrapper.className = "relative bg-slate-900 border border-slate-700 rounded-xl px-3 py-2";

    const summary = document.createElement("summary");
    summary.className = "cursor-pointer select-none";
    summary.textContent = field;

    const box = document.createElement("div");
    box.className = "absolute z-20 mt-3 left-0 max-h-64 overflow-auto min-w-56 p-3 bg-slate-800 border border-slate-600 rounded-xl shadow-xl";

    (metadata.categorical_values[field] || []).forEach((value) => {
      const label = document.createElement("label");
      label.className = "flex gap-2 py-1 text-sm";

      const input = document.createElement("input");
      input.type = "checkbox";
      input.dataset.field = field;
      input.value = value;
      input.addEventListener("change", scheduleQuery);

      label.append(input, document.createTextNode(value));
      box.appendChild(label);
    });

    wrapper.append(summary, box);
    host.appendChild(wrapper);
  });
}

function selectedFilters() {
  const result = {};
  document.querySelectorAll("#dynamic-filters input:checked").forEach((element) => {
    if (!result[element.dataset.field]) result[element.dataset.field] = [];
    result[element.dataset.field].push(element.value);
  });
  return result;
}

function chartData(rows) {
  return {
    labels: rows.map((row) => row.label),
    datasets: [{ label: "Analysis", data: rows.map((row) => row.value) }],
  };
}

function drawCharts(rows) {
  const type = $("chart-type").value;
  const data = chartData(rows);

  if (state.mainChart) state.mainChart.destroy();
  if (state.secondaryChart) state.secondaryChart.destroy();

  state.mainChart = new Chart($("main-chart"), {
    type,
    data,
    options: { responsive: true, plugins: { legend: { labels: { color: "#e2e8f0" } } } },
  });

  state.secondaryChart = new Chart($("secondary-chart"), {
    type: "doughnut",
    data,
    options: { responsive: true, plugins: { legend: { position: "bottom", labels: { color: "#e2e8f0" } } } },
  });
}

function renderTable(records) {
  const table = $("raw-table");
  table.innerHTML = "";

  if (!records.length) {
    table.textContent = "No matching records.";
    return;
  }

  const columns = Object.keys(records[0]);
  const head = document.createElement("thead");
  const row = document.createElement("tr");

  columns.forEach((column) => {
    const th = document.createElement("th");
    th.className = "p-2 border-b border-slate-700";
    th.textContent = column;
    row.appendChild(th);
  });

  head.appendChild(row);
  table.appendChild(head);

  const body = document.createElement("tbody");
  records.forEach((record) => {
    const rowElement = document.createElement("tr");
    columns.forEach((column) => {
      const td = document.createElement("td");
      td.className = "p-2 border-b border-slate-800";
      td.textContent = record[column] ?? "";
      rowElement.appendChild(td);
    });
    body.appendChild(rowElement);
  });
  table.appendChild(body);
}

async function runQuery() {
  if (!state.user || !state.datasetId || !state.metadata) return;

  try {
    status("Calculating…");
    const data = await api("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: state.datasetId,
        search: $("global-search").value,
        filters: selectedFilters(),
        aggregation: $("aggregation").value,
        metric: $("metric-select").value,
        group_by: $("group-select").value,
      }),
    });

    drawCharts(data.rows);
    renderTable(data.raw_records);
    $("insights").innerHTML = data.insights
      .map((item) => '<li class="border-l-2 border-cyan-400 pl-3">' + escapeHtml(item) + "</li>")
      .join("");

    status("Analysis updated.");
  } catch (error) {
    status(error.message, true);
  }
}

function scheduleQuery() {
  clearTimeout(state.debounce);
  state.debounce = setTimeout(runQuery, 300);
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = value;
  return element.innerHTML;
}

async function loadDatasets() {
  if (!state.user) return;

  try {
    const data = await api("/api/datasets");
    const host = $("dataset-list");
    host.innerHTML = "";

    data.datasets.forEach((dataset) => {
      const button = document.createElement("button");
      button.className = "block w-full text-left p-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm";
      button.textContent = dataset.filename + " · " + Number(dataset.row_count).toLocaleString() + " rows";
      button.onclick = () => {
        state.datasetId = dataset._id;
        renderMetadata(dataset.schema);
        runQuery();
      };
      host.appendChild(button);
    });
  } catch (error) {
    if (error.message !== "Authentication required.") status(error.message, true);
  }
}

async function loadUser() {
  try {
    const data = await api("/api/auth/me");
    setAuthenticated(data.user);
    await loadDatasets();
  } catch (_) {
    setUnauthenticated();
  }
}

function setAuthMode(mode) {
  state.authMode = mode;
  const signup = mode === "signup";

  $("auth-description").textContent = signup
    ? "Create your free account and start analyzing your data."
    : "Sign in to continue to your analytics workspace.";
  $("auth-submit").textContent = signup ? "Create free account" : "Sign in";
  $("auth-password").autocomplete = signup ? "new-password" : "current-password";

  $("show-login").className = "auth-tab rounded-md py-2 text-sm font-medium " + (!signup ? "bg-cyan-500 text-slate-950" : "text-slate-400");
  $("show-signup").className = "auth-tab rounded-md py-2 text-sm font-medium " + (signup ? "bg-cyan-500 text-slate-950" : "text-slate-400");
  $("auth-error").classList.add("hidden");
}

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = $("auth-error");
  error.classList.add("hidden");

  try {
    const endpoint = state.authMode === "signup" ? "/api/auth/signup" : "/api/auth/login";
    const data = await api(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: $("auth-email").value.trim(),
        password: $("auth-password").value,
      }),
    });

    setAuthenticated(data.user);
    await loadDatasets();
    status(state.authMode === "signup" ? "Account created successfully." : "Welcome back.");
  } catch (requestError) {
    error.textContent = requestError.message;
    error.classList.remove("hidden");
  }
});

$("show-login").addEventListener("click", () => setAuthMode("login"));
$("show-signup").addEventListener("click", () => setAuthMode("signup"));

$("logout-btn").addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } finally {
    setUnauthenticated();
  }
});

$("upload-btn").addEventListener("click", async () => {
  const file = $("file-input").files[0];
  if (!file) {
    status("Choose a CSV or XLSX file.", true);
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  try {
    $("upload-btn").disabled = true;
    status("Inspecting, cleaning and importing data…");
    const data = await api("/api/upload", { method: "POST", body: formData });
    state.datasetId = data.dataset._id;
    renderMetadata(data.metadata);
    await loadDatasets();
    await runQuery();
    status("Dataset imported successfully.");
  } catch (error) {
    status(error.message, true);
  } finally {
    $("upload-btn").disabled = false;
  }
});

["global-search", "aggregation", "metric-select", "group-select", "chart-type"].forEach((id) => {
  $(id).addEventListener(id === "global-search" ? "input" : "change", scheduleQuery);
});

setAuthMode("login");
loadUser();
