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
  const element = $("status");
  element.textContent = message;
  element.className = error
    ? "mt-3 text-sm text-red-600"
    : "mt-3 text-sm text-slate-500";
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
  });
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
  $("profile").innerHTML =
    '<div class="font-semibold text-slate-700">Welcome to BengaAnalytics</div>' +
    '<div class="mt-1 text-xs text-slate-500">Create an account or sign in to continue.</div>';
  $("tier-card").innerHTML =
    '<div class="font-semibold text-teal-700">Free plan available</div>' +
    '<div class="mt-1 text-xs text-teal-700/80">Create an account to start analyzing your data.</div>';
  $("auth-modal").classList.remove("hidden");
  $("workspace").classList.add("pointer-events-none", "opacity-40");
  $("workspace-controls").classList.add("pointer-events-none", "opacity-40");
  $("logout-btn").classList.add("hidden");
}

function renderUser(user) {
  const name = user.display_name || user.email;
  $("profile").innerHTML =
    '<div class="font-semibold text-slate-800 truncate">' + escapeHtml(name) + '</div>' +
    '<div class="mt-1 truncate text-xs text-slate-500">' + escapeHtml(user.email) + '</div>' +
    '<div class="mt-2 text-xs font-medium text-teal-700">Personal workspace</div>';

  const plan = user.plan || {};
  const limits = plan.limits || {};
  $("tier-card").innerHTML =
    '<div class="font-semibold text-teal-700">' + escapeHtml(plan.name || user.tier || "Free") + '</div>' +
    '<div class="mt-1 text-xs leading-5 text-teal-800">' +
    'Up to ' + Number(limits.max_rows_per_dataset || 0).toLocaleString() +
    ' rows per dataset<br>' + Number(limits.max_datasets || 0).toLocaleString() +
    ' datasets in your workspace</div>';
}

function renderMetadata(metadata) {
  state.metadata = metadata;
  const metric = $("metric-select");
  const group = $("group-select");

  metric.innerHTML = "";
  group.innerHTML = "";

  if (metadata.metrics.length) {
    metadata.metrics.forEach((value) => option(metric, value));
  } else {
    option(metric, "", "No numerical metrics");
  }

  if (metadata.dimensions.length || metadata.dates.length) {
    [...metadata.dimensions, ...metadata.dates].forEach((value) => option(group, value));
  } else {
    option(group, "", "No grouping field");
  }

  const host = $("dynamic-filters");
  host.innerHTML = "";

  metadata.dimensions.forEach((field) => {
    const wrapper = document.createElement("details");
    wrapper.className = "relative rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 shadow-sm";

    const summary = document.createElement("summary");
    summary.className = "cursor-pointer select-none text-sm font-medium text-slate-700";
    summary.textContent = field;

    const box = document.createElement("div");
    box.className = "absolute left-0 z-20 mt-3 max-h-64 min-w-60 overflow-auto rounded-xl border border-slate-200 bg-white p-3 shadow-xl";

    (metadata.categorical_values[field] || []).forEach((value) => {
      const label = document.createElement("label");
      label.className = "flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-50";

      const input = document.createElement("input");
      input.type = "checkbox";
      input.className = "h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500";
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
    datasets: [{
      label: "Analysis",
      data: rows.map((row) => row.value),
      backgroundColor: [
        "rgba(20, 184, 166, 0.75)",
        "rgba(14, 165, 233, 0.70)",
        "rgba(99, 102, 241, 0.65)",
        "rgba(16, 185, 129, 0.65)",
        "rgba(245, 158, 11, 0.65)",
        "rgba(244, 114, 182, 0.60)",
      ],
      borderColor: "#0f766e",
      borderWidth: 2,
      tension: 0.35,
    }],
  };
}

function drawCharts(rows) {
  const type = $("chart-type").value;
  const data = chartData(rows);

  if (state.mainChart) state.mainChart.destroy();
  if (state.secondaryChart) state.secondaryChart.destroy();

  const shared = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: "#475569", usePointStyle: true } },
    },
  };

  state.mainChart = new Chart($("main-chart"), {
    type,
    data,
    options: {
      ...shared,
      scales: type === "pie" ? {} : {
        x: { ticks: { color: "#64748b" }, grid: { color: "#f1f5f9" } },
        y: { ticks: { color: "#64748b" }, grid: { color: "#e2e8f0" } },
      },
    },
  });

  state.secondaryChart = new Chart($("secondary-chart"), {
    type: "doughnut",
    data,
    options: {
      ...shared,
      plugins: {
        legend: { position: "bottom", labels: { color: "#475569", boxWidth: 12 } },
      },
    },
  });
}

function renderTable(records) {
  const table = $("raw-table");
  table.innerHTML = "";

  if (!records.length) {
    table.innerHTML = '<caption class="py-8 text-left text-slate-500">No matching records found.</caption>';
    return;
  }

  const columns = Object.keys(records[0]);
  const head = document.createElement("thead");
  const row = document.createElement("tr");
  row.className = "bg-slate-50";

  columns.forEach((column) => {
    const th = document.createElement("th");
    th.className = "whitespace-nowrap border-b border-slate-200 px-3 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500";
    th.textContent = column;
    row.appendChild(th);
  });

  head.appendChild(row);
  table.appendChild(head);

  const body = document.createElement("tbody");
  records.forEach((record) => {
    const rowElement = document.createElement("tr");
    rowElement.className = "hover:bg-slate-50";
    columns.forEach((column) => {
      const td = document.createElement("td");
      td.className = "whitespace-nowrap border-b border-slate-100 px-3 py-3 text-slate-600";
      td.textContent = record[column] ?? "";
      rowElement.appendChild(td);
    });
    body.appendChild(rowElement);
  });
  table.appendChild(body);
}

async function runQuery() {
  if (!state.user || !state.datasetId || !state.metadata) return;

  const aggregation = $("aggregation").value;
  const metric = $("metric-select").value;
  if (aggregation !== "count" && !metric) {
    status("This dataset has no numerical metric available for the selected calculation.", true);
    return;
  }

  try {
    status("Calculating…");
    const data = await api("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: state.datasetId,
        search: $("global-search").value,
        filters: selectedFilters(),
        aggregation,
        metric,
        group_by: $("group-select").value,
      }),
    });

    drawCharts(data.rows);
    renderTable(data.raw_records);
    $("insights").innerHTML = data.insights
      .map((item) => '<li class="border-l-2 border-teal-500 pl-3 leading-6">' + escapeHtml(item) + "</li>")
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
  element.textContent = value == null ? "" : String(value);
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
      button.type = "button";
      button.className = "block w-full rounded-xl border border-slate-200 bg-white p-3 text-left text-sm text-slate-600 shadow-sm transition hover:border-teal-200 hover:bg-teal-50";
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
    ? "Create your account to securely access your personal analytics workspace."
    : "Sign in to continue to your analytics workspace.";
  $("auth-submit").textContent = signup ? "Create account" : "Sign in";
  $("auth-footnote").textContent = signup
    ? "Your account starts on the Free plan. Paid plans can be added later without changing your workspace."
    : "Secure access to your personal analytics workspace.";

  $("signup-name-fields").classList.toggle("hidden", !signup);
  $("confirm-password-field").classList.toggle("hidden", !signup);
  $("terms-field").classList.toggle("hidden", !signup);
  $("terms-field").classList.toggle("flex", signup);

  $("auth-first-name").required = signup;
  $("auth-last-name").required = signup;
  $("auth-confirm-password").required = signup;
  $("accept-terms").required = signup;

  $("auth-password").autocomplete = signup ? "new-password" : "current-password";
  $("auth-confirm-password").autocomplete = "new-password";

  $("show-login").className = "auth-tab rounded-lg px-3 py-2.5 text-sm font-semibold transition " +
    (!signup ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700");
  $("show-signup").className = "auth-tab rounded-lg px-3 py-2.5 text-sm font-semibold transition " +
    (signup ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700");

  $("auth-error").classList.add("hidden");
  $("auth-error").textContent = "";
}

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();

  const form = event.currentTarget;
  const error = $("auth-error");
  error.classList.add("hidden");

  if (!form.reportValidity()) return;

  const password = $("auth-password").value;
  const confirmPassword = $("auth-confirm-password").value;

  if (state.authMode === "signup" && password !== confirmPassword) {
    error.textContent = "Passwords do not match.";
    error.classList.remove("hidden");
    $("auth-confirm-password").focus();
    return;
  }

  const button = $("auth-submit");
  button.disabled = true;
  const originalText = button.textContent;
  button.textContent = state.authMode === "signup" ? "Creating account…" : "Signing in…";

  try {
    const endpoint = state.authMode === "signup" ? "/api/auth/signup" : "/api/auth/login";
    const payload = {
      email: $("auth-email").value.trim(),
      password,
    };

    if (state.authMode === "signup") {
      payload.first_name = $("auth-first-name").value.trim();
      payload.last_name = $("auth-last-name").value.trim();
      payload.confirm_password = confirmPassword;
      payload.accepted_terms = $("accept-terms").checked;
    }

    const data = await api(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    setAuthenticated(data.user);
    $("auth-form").reset();
    await loadDatasets();
    status(state.authMode === "signup" ? "Account created successfully. Welcome to BengaAnalytics." : "Welcome back.");
  } catch (requestError) {
    error.textContent = requestError.message;
    error.classList.remove("hidden");
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
});

$("show-login").addEventListener("click", () => setAuthMode("login"));
$("show-signup").addEventListener("click", () => setAuthMode("signup"));

$("logout-btn").addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } finally {
    $("auth-form").reset();
    setAuthMode("login");
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
