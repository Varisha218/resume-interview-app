// Global app state shared with interview.js and auth.js
window.App = {
  resumeText: "",
  jdText: "",
  analysis: null,
  mode: "practice",
  // Adaptive interview state (see /api/interview/*)
  pool: null,
  currentQuestion: null,
  difficulty: "medium",
  askedIds: [],
  maxQuestions: 6,
  answers: [], // filled in by interview.js: {evaluation, face_detect_ratio, emotion_counts, skip_reason, difficulty, question}
  // Auth state — populated by auth.js from /api/auth/me. Interview
  // progress (streaks, medals, history) is tied to this account server-side.
  user: null,
  profile: null,
};

const screens = ["auth", "profile", "upload", "results", "mode", "interview", "summary"];

function goToScreen(name) {
  screens.forEach((s) => {
    document.getElementById(`screen-${s}`).classList.toggle("active", s === name);
  });
  document.querySelectorAll(".step").forEach((el) => {
    const step = el.dataset.step;
    el.classList.remove("active", "done");
    if (step === name) el.classList.add("active");
    else if (screens.indexOf(step) < screens.indexOf(name)) el.classList.add("done");
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---------- STEP 1: Upload & Analyze ----------

document.getElementById("analyzeBtn").addEventListener("click", async () => {
  const errorEl = document.getElementById("uploadError");
  errorEl.textContent = "";
  const fileInput = document.getElementById("resumeFile");
  const pastedResume = document.getElementById("resumeText").value.trim();
  const jdText = document.getElementById("jdText").value.trim();

  if (!jdText) {
    errorEl.textContent = "Please paste the job description.";
    return;
  }
  if (!fileInput.files.length && !pastedResume) {
    errorEl.textContent = "Please upload a resume file or paste resume text.";
    return;
  }

  const btn = document.getElementById("analyzeBtn");
  btn.disabled = true;
  btn.textContent = "Analyzing...";

  try {
    let resumeText = pastedResume;

    if (fileInput.files.length) {
      const formData = new FormData();
      formData.append("resume", fileInput.files[0]);
      const uploadResp = await fetch("/api/upload_resume", { method: "POST", body: formData });
      const uploadData = await uploadResp.json();
      if (!uploadResp.ok) throw new Error(uploadData.error || "Failed to parse resume.");
      resumeText = uploadData.resume_text;
    }

    const analyzeResp = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_text: resumeText, jd_text: jdText }),
    });
    const analysisData = await analyzeResp.json();
    if (!analyzeResp.ok) throw new Error(analysisData.error || "Analysis failed.");

    App.resumeText = resumeText;
    App.jdText = jdText;
    App.analysis = analysisData;

    renderResults(analysisData);
    goToScreen("results");
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Analyze Match";
  }
});

function renderResults(data) {
  const circumference = 326.7;
  const offset = circumference - (circumference * data.overall_score) / 100;
  document.getElementById("scoreArc").style.strokeDashoffset = offset;
  document.getElementById("scoreNumber").textContent = `${Math.round(data.overall_score)}%`;

  // 1. Score Breakdown Formula
  const skillScore = Math.round(data.score_breakdown?.skill_match ?? 0);
  const semanticScore = Math.round(data.score_breakdown?.semantic_match ?? 0);

  document.getElementById("breakdownSkillScore").textContent = `${skillScore}%`;
  document.getElementById("breakdownSkillBar").style.width = `${skillScore}%`;
  
  document.getElementById("breakdownSemanticScore").textContent = `${semanticScore}%`;
  document.getElementById("breakdownSemanticBar").style.width = `${semanticScore}%`;

  // 3. Matched Skills Split
  const techEl = document.getElementById("matchedTechSkills");
  const techSkills = data.technical_matched || [];
  techEl.innerHTML = techSkills.length
    ? techSkills.map((s) => `<span class="chip matched">${s}</span>`).join("")
    : `<span class="chip">No technical skill overlap found</span>`;

  const softEl = document.getElementById("matchedSoftSkills");
  const softSkills = data.soft_matched || [];
  softEl.innerHTML = softSkills.length
    ? softSkills.map((s) => `<span class="chip matched">${s}</span>`).join("")
    : `<span class="chip">No soft skill overlap found</span>`;

  // 4. Prioritized Missing Skills
  const critEl = document.getElementById("criticalMissing");
  const critMissing = data.critical_missing || [];
  critEl.innerHTML = critMissing.length
    ? critMissing.map((s) => `<span class="chip missing">${s}</span>`).join("")
    : `<span class="chip matched">No critical gaps</span>`;

  const impEl = document.getElementById("importantMissing");
  const impMissing = data.important_missing || [];
  impEl.innerHTML = impMissing.length
    ? impMissing.map((s) => `<span class="chip missing">${s}</span>`).join("")
    : `<span class="chip matched">No important gaps</span>`;

  const clarifyEl = document.getElementById("worthClarifying");
  const worthClarifying = data.worth_clarifying || [];
  clarifyEl.innerHTML = worthClarifying.length
    ? worthClarifying.map((s) => `<span class="chip suggested">${s}</span>`).join("")
    : `<span class="chip matched">Nothing ambiguous found</span>`;

  const niceEl = document.getElementById("niceMissing");
  const niceMissing = data.nice_to_have_missing || [];
  niceEl.innerHTML = niceMissing.length
    ? niceMissing.map((s) => `<span class="chip missing">${s}</span>`).join("")
    : `<span class="chip matched">No nice-to-have gaps</span>`;

  // 5. Keyword Density Grid
  const densityEl = document.getElementById("keywordDensityGrid");
  const density = data.keyword_density || [];
  densityEl.innerHTML = density.length
    ? density.map((item) => `
        <div class="density-item">
          <span>${item.skill}</span>
          <span class="density-count">${item.count}x</span>
        </div>
      `).join("")
    : `<p class="detail-text" style="grid-column: 1/-1;">No keywords found to measure density.</p>`;

  // 6. ATS Readability & Compatibility Check
  const compScore = data.ats_compatibility?.score ?? 0;
  document.getElementById("atsCompatibilityScore").textContent = `${compScore}%`;
  if (compScore >= 80) {
    document.getElementById("atsCompatibilityScore").style.color = "var(--success)";
  } else if (compScore >= 50) {
    document.getElementById("atsCompatibilityScore").style.color = "var(--warning)";
  } else {
    document.getElementById("atsCompatibilityScore").style.color = "var(--danger)";
  }

  const checklist = data.ats_compatibility?.details || {};
  const setCheck = (id, passed) => {
    const el = document.getElementById(id);
    if (passed) {
      el.textContent = "✓";
      el.className = "check-icon pass";
    } else {
      el.textContent = "✗";
      el.className = "check-icon fail";
    }
  };

  setCheck("checkSearchable", checklist.searchable_text);
  setCheck("checkHeadings", checklist.standard_headings);
  setCheck("checkTables", checklist.no_complex_tables);
  setCheck("checkParagraphs", checklist.no_long_paragraphs);
  setCheck("checkLength", checklist.appropriate_length);

  // 7. General quality notes
  const notesEl = document.getElementById("qualityNotes");
  notesEl.innerHTML = data.quality_notes?.length
    ? data.quality_notes.map((n) => `<li>${n}</li>`).join("")
    : "<li>Your resume structure looks solid.</li>";
}

document.getElementById("goToModeBtn").addEventListener("click", () => goToScreen("mode"));

// ---------- STEP 3: Mode selection ----------

window.startInterviewFromMode = async function() {
  const resp = await fetch("/api/interview/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      matched_skills: App.analysis.matched_skills,
      missing_skills: App.analysis.missing_skills,
      resume_text: App.resumeText,
      jd_text: App.jdText,
      mode: App.mode,
    }),
  });
  const data = await resp.json();
  if (!resp.ok) {
    if (resp.status === 401) {
      alert("Your session expired — please log in again.");
      goToScreen("auth");
      return;
    }
    alert(data.error || "Could not start the interview.");
    return;
  }
  App.pool = data.pool;
  App.currentQuestion = data.question;
  App.difficulty = data.difficulty;
  App.askedIds = data.asked_ids;
  App.answers = [];
  goToScreen("interview");
  window.startInterview(); // defined in interview.js
};

document.querySelectorAll("[data-mode]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    App.mode = btn.dataset.mode;
    
    if (App.mode === "practice") {
      if (window.refreshProfile) window.refreshProfile();
      goToScreen("profile");
      App.pendingInterviewStart = true;
      document.getElementById("startNewInterviewBtn").textContent = "Begin Practice Interview →";
      return;
    }
    
    await window.startInterviewFromMode();
  });
});

// ---------- STEP 5: Restart / return to profile ----------

function resetInterviewInputs() {
  document.getElementById("resumeFile").value = "";
  document.getElementById("resumeText").value = "";
  document.getElementById("jdText").value = "";
  App.resumeText = "";
  App.jdText = "";
  App.analysis = null;
  App.questions = [];
  App.answers = [];
}

document.getElementById("restartBtn").addEventListener("click", () => {
  resetInterviewInputs();
  goToScreen("upload");
});

document.getElementById("backToProfileBtn").addEventListener("click", () => {
  resetInterviewInputs();
  if (typeof window.refreshProfile === "function") window.refreshProfile();
  goToScreen("profile");
});
