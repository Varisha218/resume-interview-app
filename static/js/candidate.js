// Candidate side: My Resume form, Jobs board, Apply button, My Applications.
// Talks to /api/candidate/*. Login/signup/logout are handled by auth.js.
// Loaded after app.js and auth.js (uses their globals: App, goToScreen).

(function () {
  const CAND_SCREENS = ["resume", "jobs"];

  // ---------- helpers ----------

  const $ = (id) => document.getElementById(id);

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function showCandScreen(name) {
    if (!window.App || !App.user) {
      goToScreen("auth");
      return false;
    }
    document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
    $(`screen-${name}`).classList.add("active");
    document.querySelectorAll(".step").forEach((el) => el.classList.remove("active", "done"));
    window.scrollTo({ top: 0, behavior: "smooth" });
    return true;
  }

  // app.js's goToScreen only knows its own screens, so make sure a candidate
  // screen is hidden whenever the app navigates somewhere else.
  const originalGoToScreen = window.goToScreen;
  window.goToScreen = function (name) {
    CAND_SCREENS.forEach((s) => $(`screen-${s}`)?.classList.remove("active"));
    return originalGoToScreen.apply(this, arguments);
  };

  async function api(path, options = {}) {
    const resp = await fetch(`/api/candidate${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    let data = {};
    try { data = await resp.json(); } catch (e) { /* non-JSON error body */ }
    if (resp.status === 401) {
      App.user = null;
      alert("Your session expired — please log in again.");
      goToScreen("auth");
      throw new Error("Not logged in.");
    }
    if (!resp.ok) {
      const err = new Error(data.error || "Something went wrong.");
      err.code = data.code;
      throw err;
    }
    return data;
  }

  function setStatus(el, text, kind) {
    el.textContent = text || "";
    el.className = `cand-status ${kind || ""}`;
  }

  // =====================================================================
  // MY RESUME
  // =====================================================================

  const FIELDS = {
    full_name: "resumeFullName",
    phone: "resumePhone",
    location: "resumeLocation",
    headline: "resumeHeadline",
    summary: "resumeSummary",
    skills: "resumeSkills",
    education: "resumeEducation",
    experience: "resumeExperience",
    resume_text: "resumeFullText",
  };

  function fillResumeForm(profile) {
    Object.entries(FIELDS).forEach(([key, id]) => {
      let value = profile ? profile[key] : "";
      if (key === "skills") value = (value || []).join(", ");
      $(id).value = value || "";
    });
  }

  function readResumeForm() {
    const out = {};
    Object.entries(FIELDS).forEach(([key, id]) => { out[key] = $(id).value; });
    return out;
  }

  async function openResume() {
    if (!showCandScreen("resume")) return;
    const status = $("resumeStatus");
    setStatus(status, "Loading...", "");
    try {
      const data = await api("/profile");
      fillResumeForm(data.profile);
      setStatus(status, data.profile ? "" : "No resume saved yet — fill in the form and save.", "");
    } catch (e) {
      setStatus(status, e.message, "err");
    }
  }

  $("resumeForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = $("resumeStatus");
    const btn = $("resumeSaveBtn");
    btn.disabled = true;
    setStatus(status, "Saving...", "");
    try {
      const data = await api("/profile", { method: "PUT", body: JSON.stringify(readResumeForm()) });
      fillResumeForm(data.profile);
      setStatus(status, "Resume saved ✓", "ok");
    } catch (err) {
      setStatus(status, err.message, "err");
    } finally {
      btn.disabled = false;
    }
  });

  // Optional: fill the "full resume text" box from a PDF/DOCX/TXT using the
  // existing /api/upload_resume parser.
  $("resumeImportFile").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const status = $("resumeStatus");
    setStatus(status, "Reading file...", "");
    try {
      const formData = new FormData();
      formData.append("resume", file);
      const resp = await fetch("/api/upload_resume", { method: "POST", body: formData });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Could not read that file.");
      $("resumeFullText").value = data.resume_text;
      setStatus(status, "File imported — review it, then click Save.", "ok");
    } catch (err) {
      setStatus(status, err.message, "err");
    } finally {
      e.target.value = "";
    }
  });

  $("resumeToJobsBtn").addEventListener("click", openJobs);
  $("resumeBackBtn").addEventListener("click", backToProfile);

  // =====================================================================
  // JOBS BOARD
  // =====================================================================

  let jobsCache = [];

  function jobCardHtml(job) {
    const meta = [job.company, job.location, job.job_type].filter(Boolean).map(esc).join(" · ");
    const skills = (job.skills || []).map((s) => `<span class="chip">${esc(s)}</span>`).join("");
    const long = (job.description || "").length > 220;
    const action = job.applied
      ? `<span class="job-applied">✓ Applied</span>`
      : `<button class="btn primary small" data-act="open-apply">Apply</button>`;
    return `
      <div class="card job-card" data-job-id="${job.id}">
        <h3>${esc(job.title)}</h3>
        <p class="job-meta">${meta}</p>
        <div class="chip-list">${skills}</div>
        <div class="job-desc ${long ? "clamped" : ""}">${esc(job.description)}</div>
        ${long ? `<button class="job-link" data-act="toggle-desc">Show more</button>` : ""}
        <div class="job-actions">${action}</div>
        <div class="job-apply-box hidden">
          <label class="field-label">Cover note (optional)</label>
          <textarea rows="3" maxlength="2000" placeholder="Why are you a good fit?"></textarea>
          <div class="job-actions">
            <button class="btn primary small" data-act="submit-apply">Submit Application</button>
            <button class="btn secondary small" data-act="cancel-apply">Cancel</button>
            <span class="cand-status err"></span>
          </div>
        </div>
      </div>`;
  }

  function renderJobs(jobs) {
    jobsCache = jobs;
    const list = $("jobsList");
    list.innerHTML = jobs.length
      ? jobs.map(jobCardHtml).join("")
      : `<div class="card"><p class="detail-text">No open jobs found.</p></div>`;
  }

  async function loadJobs() {
    const q = $("jobSearch").value.trim();
    const status = $("jobsStatus");
    setStatus(status, "Loading jobs...", "");
    try {
      const data = await api(`/jobs${q ? `?q=${encodeURIComponent(q)}` : ""}`);
      renderJobs(data.jobs);
      setStatus(status, "", "");
    } catch (e) {
      setStatus(status, e.message, "err");
    }
  }

  function renderApplications(apps) {
    const el = $("applicationsList");
    el.innerHTML = apps.length
      ? apps.map((a) => `
          <li>
            <span><strong>${esc(a.title)}</strong> — ${esc(a.company)}</span>
            <span>${new Date(a.created_at * 1000).toLocaleDateString()} · <span class="app-status">${esc(a.status)}</span></span>
          </li>`).join("")
      : `<li class="detail-text">You haven't applied to any jobs yet.</li>`;
  }

  async function loadApplications() {
    try {
      const data = await api("/applications");
      renderApplications(data.applications);
    } catch (e) {
      $("applicationsList").innerHTML = `<li class="error-text">${esc(e.message)}</li>`;
    }
  }

  async function openJobs() {
    if (!showCandScreen("jobs")) return;
    await Promise.all([loadJobs(), loadApplications()]);
  }

  // One click handler for every job card (Apply / Show more / Submit / Cancel).
  $("jobsList").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const card = btn.closest(".job-card");
    const box = card.querySelector(".job-apply-box");
    const errEl = box.querySelector(".cand-status");

    switch (btn.dataset.act) {
      case "toggle-desc": {
        const desc = card.querySelector(".job-desc");
        const clamped = desc.classList.toggle("clamped");
        btn.textContent = clamped ? "Show more" : "Show less";
        break;
      }
      case "open-apply":
        box.classList.remove("hidden");
        btn.classList.add("hidden");
        break;
      case "cancel-apply":
        box.classList.add("hidden");
        card.querySelector('[data-act="open-apply"]')?.classList.remove("hidden");
        errEl.textContent = "";
        break;
      case "submit-apply": {
        errEl.textContent = "";
        btn.disabled = true;
        try {
          await api(`/jobs/${card.dataset.jobId}/apply`, {
            method: "POST",
            body: JSON.stringify({ cover_note: box.querySelector("textarea").value }),
          });
          const job = jobsCache.find((j) => String(j.id) === card.dataset.jobId);
          if (job) job.applied = true;
          card.outerHTML = jobCardHtml(job || { id: card.dataset.jobId, applied: true, title: "", description: "" });
          loadApplications();
        } catch (err) {
          errEl.textContent = err.message;
          if (err.code === "resume_required") {
            errEl.innerHTML = `${esc(err.message)} <button class="job-link" data-act="go-resume">Go to My Resume</button>`;
          }
        } finally {
          btn.disabled = false;
        }
        break;
      }
      case "go-resume":
        openResume();
        break;
    }
  });

  $("jobSearchBtn").addEventListener("click", loadJobs);
  $("jobSearch").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); loadJobs(); }
  });
  $("jobsToResumeBtn").addEventListener("click", openResume);
  $("jobsBackBtn").addEventListener("click", backToProfile);

  // =====================================================================
  // navigation
  // =====================================================================

  function backToProfile() {
    if (typeof window.refreshProfile === "function") window.refreshProfile();
    goToScreen("profile");
  }

  $("openResumeBtn").addEventListener("click", openResume);
  $("openJobsBtn").addEventListener("click", openJobs);
})();
