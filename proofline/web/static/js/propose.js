/**
 * Propose-change page: handles the form, color hint, new-code field
 * visibility, and fetch-based submission.
 *
 * No framework, no build step.  Plain ES2017.
 * MIT License.
 */
(function () {
  "use strict";

  const form          = document.getElementById("propose-form");
  const moduleInput   = document.getElementById("module-input");
  const colorHint     = document.getElementById("color-hint");
  const colorInd      = document.getElementById("color-indicator");
  const actionRadios  = document.querySelectorAll('input[name="action"]');
  const newCodeField  = document.getElementById("new-code-field");
  const submitBtn     = document.getElementById("submit-btn");
  const resultPanel   = document.getElementById("result-panel");
  const resultBody    = document.getElementById("result-body");
  const loadSourceBtn = document.getElementById("load-source-btn");
  const loadSourceErr = document.getElementById("load-source-error");
  const newCodeInput  = document.getElementById("new-code-input");
  const symbolInput   = document.getElementById("symbol-input");

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

  /* ── Show / hide new-code textarea and load-source button ──────────── */
  function updateNewCodeVisibility() {
    const action = document.querySelector('input[name="action"]:checked').value;
    const isRefactor = action === "refactor";
    newCodeField.style.display = isRefactor ? "block" : "none";
    updateLoadSourceButton();
  }

  function updateLoadSourceButton() {
    if (!loadSourceBtn) return;
    const action = document.querySelector('input[name="action"]:checked').value;
    const hasModule = moduleInput.value.trim() !== "";
    const hasSymbol = symbolInput.value.trim() !== "";
    const show = action === "refactor" && hasModule && hasSymbol;
    loadSourceBtn.style.display = show ? "inline-block" : "none";
  }

  actionRadios.forEach(function (r) {
    r.addEventListener("change", updateNewCodeVisibility);
  });
  moduleInput.addEventListener("change", updateLoadSourceButton);
  symbolInput.addEventListener("input", updateLoadSourceButton);
  updateNewCodeVisibility();

  /* ── Load current source ─────────────────────────────────────────── */
  if (loadSourceBtn) {
    loadSourceBtn.addEventListener("click", async function () {
      const mod = moduleInput.value.trim();
      const sym = symbolInput.value.trim();
      if (!mod || !sym) return;

      loadSourceBtn.disabled = true;
      loadSourceBtn.textContent = "Loading…";
      loadSourceErr.style.display = "none";
      loadSourceErr.textContent = "";

      try {
        const url = "/source?" + new URLSearchParams({ module: mod, symbol: sym });
        const resp = await fetch(url);
        const data = await resp.json();
        if (resp.ok && data.source !== undefined) {
          newCodeInput.value = data.source;
          newCodeInput.focus();
        } else {
          loadSourceErr.textContent = data.error || "Could not load source.";
          loadSourceErr.style.display = "block";
        }
      } catch (err) {
        loadSourceErr.textContent = "Request failed: " + String(err);
        loadSourceErr.style.display = "block";
      } finally {
        loadSourceBtn.disabled = false;
        loadSourceBtn.textContent = "Load current source";
      }
    });
  }

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
      // Attach the form's module/symbol to the response so buildExplanation
      // can use them – the server doesn't echo them back.
      data._form_module = payload.module || "";
      data._form_symbol = payload.symbol || "";
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

  /**
   * Build a single plain-English sentence explaining the verdict.
   * Always derived from the real response fields – never a canned string.
   */
  function buildExplanation(data) {
    const mod    = esc(data._form_module || data.module_path || data.module || "this module");
    const color  = esc(data.color || "");
    const v      = data.verdict || {};
    const branch = esc(data.branch || "");
    const reason = esc(data.reason || "");

    if (data.status === "blocked") {
      // Pull the complexity number from the reason field if scanner put it there.
      const complexityMatch = reason.match(/complexity=?(\d+)/i);
      const detail = complexityMatch
        ? ` (complexity ${complexityMatch[1]})`
        : "";
      const modLabel = mod !== "this module" ? `${mod} ` : "";
      return `Blocked: ${modLabel}is ${color}${detail}, so Proofline will not touch it automatically.`;
    }

    if (data.status === "applied") {
      const tests    = v.tests_after  != null ? v.tests_after  : "?";
      const edges    = v.new_edge_cases_run != null ? v.new_edge_cases_run : "?";
      const branchPart = branch ? `, so the change was committed on branch <code class="mono">${branch}</code>` : "";
      return `Applied: the adversary ran ${tests} test${tests !== 1 ? "s" : ""} and ${edges} edge case${edges !== 1 ? "s" : ""} before and after the change, all matched${branchPart}.`;
    }

    if (data.status === "needs_review" || data.status === "rejected") {
      const why = reason || (v.verdict ? `the adversary returned "${esc(v.verdict)}"` : "verification did not pass");
      return `Not applied: ${why}.`;
    }

    // Fallback for unexpected statuses (e.g. "error")
    return reason ? `Error: ${reason}.` : `Unexpected status: ${esc(data.status || "unknown")}.`;
  }

  function renderVerdict(data) {
    const [label, color] = statusLabel[data.status] || ["Unknown", "#64748b"];
    let html = `<div class="verdict-block">`;
    html += `<div class="verdict-status" style="color:${color}">${label}</div>`;
    // Plain-language explanation derived from the real response
    html += `<p class="verdict-explain">${buildExplanation(data)}</p>`;
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
