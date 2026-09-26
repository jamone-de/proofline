/**
 * Propose-change page: handles the form, color hint, new-code field
 * visibility, and fetch-based submission.
 *
 * No framework, no build step.  Plain ES2017.
 * MIT License.
 */
(function () {
  "use strict";

  const form        = document.getElementById("propose-form");
  const moduleInput = document.getElementById("module-input");
  const colorHint   = document.getElementById("color-hint");
  const colorInd    = document.getElementById("color-indicator");
  const actionRadios= document.querySelectorAll('input[name="action"]');
  const newCodeField= document.getElementById("new-code-field");
  const submitBtn   = document.getElementById("submit-btn");
  const resultPanel = document.getElementById("result-panel");
  const resultBody  = document.getElementById("result-body");

  /* ── Color hint when a module is selected ───────────────────────────── */
  const pillClass = { GREEN: "pill-green", YELLOW: "pill-yellow", RED: "pill-red" };

  moduleInput.addEventListener("change", function () {
    const opt = moduleInput.options[moduleInput.selectedIndex];
    const color = opt ? opt.dataset.color : "";
    if (color) {
      colorInd.innerHTML =
        `Module risk: <span class="pill ${pillClass[color] || ''}">${color}</span>`;
      colorHint.style.display = "block";
    } else {
      colorHint.style.display = "none";
    }
  });

  /* ── Show / hide new-code textarea based on action radio ───────────── */
  function updateNewCodeVisibility() {
    const action = document.querySelector('input[name="action"]:checked').value;
    newCodeField.style.display = action === "refactor" ? "block" : "none";
  }

  actionRadios.forEach(function (r) {
    r.addEventListener("change", updateNewCodeVisibility);
  });
  updateNewCodeVisibility();

  /* ── Fetch submission ───────────────────────────────────────────────── */
  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    submitBtn.disabled = true;
    submitBtn.textContent = "Running…";
    resultPanel.style.display = "none";

    const formData = new FormData(form);
    const payload = {
      module:   formData.get("module"),
      symbol:   formData.get("symbol"),
      action:   formData.get("action"),
      new_code: formData.get("new_code") || "",
    };

    try {
      const resp = await fetch("/propose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      renderVerdict(data);
    } catch (err) {
      renderError(String(err));
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit Proposal";
    }
  });

  /* ── Verdict rendering ──────────────────────────────────────────────── */
  const statusLabel = {
    applied:      ["&#10003; Applied",      "#16a34a"],
    blocked:      ["&#10007; Blocked",      "#dc2626"],
    needs_review: ["&#9888; Needs Review",  "#ca8a04"],
    rejected:     ["&#10007; Rejected",     "#dc2626"],
    error:        ["&#10007; Error",        "#dc2626"],
  };

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function renderVerdict(data) {
    const [label, color] = statusLabel[data.status] || ["Unknown", "#64748b"];
    let html = `<div class="verdict-block">`;
    html += `<div class="verdict-status" style="color:${color}">${label}</div>`;
    if (data.reason) {
      html += `<div class="verdict-row"><span class="verdict-key">Reason</span><span>${esc(data.reason)}</span></div>`;
    }
    if (data.color) {
      const pc = {"GREEN":"pill-green","YELLOW":"pill-yellow","RED":"pill-red"}[data.color]||"";
      html += `<div class="verdict-row"><span class="verdict-key">Module risk</span><span class="pill ${pc}">${esc(data.color)}</span></div>`;
    }
    if (data.branch) {
      html += `<div class="verdict-row"><span class="verdict-key">Branch</span><code class="mono">${esc(data.branch)}</code></div>`;
    }
    if (data.verdict) {
      const v = data.verdict;
      html += `<div class="verdict-row"><span class="verdict-key">Tests before/after</span><span class="tabnum">${esc(v.tests_before ?? "-")} / ${esc(v.tests_after ?? "-")}</span></div>`;
      html += `<div class="verdict-row"><span class="verdict-key">Coverage before/after</span><span class="tabnum">${esc(v.coverage_before ?? "-")} / ${esc(v.coverage_after ?? "-")}</span></div>`;
      html += `<div class="verdict-row"><span class="verdict-key">Edge cases run</span><span class="tabnum">${esc(v.new_edge_cases_run ?? "-")}</span></div>`;
      if (v.edge_cases_failed && v.edge_cases_failed.length > 0) {
        html += `<div class="verdict-key" style="margin-top:8px;">Failed edge cases</div>`;
        html += `<pre class="verdict-pre">${esc(JSON.stringify(v.edge_cases_failed, null, 2))}</pre>`;
      }
    }
    html += `<pre class="verdict-pre" style="margin-top:12px;">${esc(JSON.stringify(data, null, 2))}</pre>`;
    html += `</div>`;
    resultBody.innerHTML = html;
    resultPanel.style.display = "block";
  }

  function renderError(msg) {
    resultBody.innerHTML = `<div class="verdict-block"><div class="verdict-status" style="color:#dc2626">&#10007; Request failed</div><div>${esc(msg)}</div></div>`;
    resultPanel.style.display = "block";
  }
})();
