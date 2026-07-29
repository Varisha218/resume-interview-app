// Handles the live interview: webcam, face-api.js emotion detection
// (informational only — never scored, see utils/fairness.py), mic-based
// silence detection, speech-to-text transcript capture, per-question
// timers, and delegates all answer scoring + adaptive difficulty selection
// to the backend (utils/transcript_analyzer.py, utils/adaptive_engine.py).

const SILENCE_SKIP_SECONDS = 8; // if no speech volume for this long, auto-advance
const VOLUME_THRESHOLD = 0.02; // RMS threshold below which we consider "silence"
const FACE_SAMPLE_INTERVAL_MS = 700;

// Base time budgets per difficulty tier (seconds) — harder questions get a
// little more thinking time. Mock mode runs tighter than practice overall.
const TIME_BUDGET = {
  practice: { easy: 90, medium: 110, hard: 140 },
  mock: { easy: 70, medium: 85, hard: 105 },
};

let videoEl, overlayCanvas, overlayCtx;
let mediaStream = null;
let audioContext = null;
let analyserNode = null;
let audioDataArray = null;
let silenceCheckInterval = null;
let silentSeconds = 0;

let faceSampleInterval = null;
let modelsLoaded = false;

let recognition = null;
let recognitionSupported = false;

let questionIndex = 0;
let questionTimerInterval = null;
let questionTimeLeft = 0;

let currentQuestionState = null; // resets each question

async function loadFaceModels() {
  if (modelsLoaded) return;
  const MODEL_URL = "https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@master/weights";
  try {
    await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL);
    await faceapi.nets.faceExpressionNet.loadFromUri(MODEL_URL);
    modelsLoaded = true;
  } catch (e) {
    console.warn("Could not load face-api models (check internet connection for first run):", e);
  }
}

async function setupWebcam() {
  videoEl = document.getElementById("webcam");
  overlayCanvas = document.getElementById("overlay");
  overlayCtx = overlayCanvas.getContext("2d");

  mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  videoEl.srcObject = mediaStream;

  await new Promise((resolve) => {
    videoEl.onloadedmetadata = () => resolve();
  });

  overlayCanvas.width = videoEl.clientWidth;
  overlayCanvas.height = videoEl.clientHeight;
}

function setupAudioSilenceDetection() {
  audioContext = new (window.AudioContext || window.webkitAudioContext)();
  const source = audioContext.createMediaStreamSource(mediaStream);
  analyserNode = audioContext.createAnalyser();
  analyserNode.fftSize = 2048;
  audioDataArray = new Uint8Array(analyserNode.fftSize);
  source.connect(analyserNode);

  silentSeconds = 0;
  silenceCheckInterval = setInterval(() => {
    analyserNode.getByteTimeDomainData(audioDataArray);
    let sumSquares = 0;
    for (let i = 0; i < audioDataArray.length; i++) {
      const normalized = (audioDataArray[i] - 128) / 128;
      sumSquares += normalized * normalized;
    }
    const rms = Math.sqrt(sumSquares / audioDataArray.length);

    const micBadge = document.getElementById("micBadge");
    if (rms < VOLUME_THRESHOLD) {
      silentSeconds += 1;
      micBadge.textContent = `Silence (${silentSeconds}s)`;
      if (silentSeconds >= SILENCE_SKIP_SECONDS) {
        micBadge.textContent = "Silence — moving on";
        advanceQuestion("silence");
      }
    } else {
      silentSeconds = 0;
      micBadge.textContent = "Listening";
    }
  }, 1000);
}

function setupFaceSampling() {
  faceSampleInterval = setInterval(async () => {
    if (!modelsLoaded || !videoEl || videoEl.paused || videoEl.ended) return;

    const detection = await faceapi
      .detectSingleFace(videoEl, new faceapi.TinyFaceDetectorOptions())
      .withFaceExpressions();

    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

    if (detection && currentQuestionState) {
      currentQuestionState.faceDetectedFrames += 1;

      // Face detection is captured for descriptive feedback only — it is
      // never sent into the score. See utils/fairness.py.
      const expressions = detection.expressions;
      const dominant = Object.entries(expressions).sort((a, b) => b[1] - a[1])[0][0];
      currentQuestionState.emotionCounts[dominant] = (currentQuestionState.emotionCounts[dominant] || 0) + 1;
      document.getElementById("emotionBadge").textContent = dominant;
    }
    if (currentQuestionState) currentQuestionState.totalFrames += 1;
  }, FACE_SAMPLE_INTERVAL_MS);
}

function setupSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    recognitionSupported = false;
    document.getElementById("transcriptBox").textContent =
      "Speech-to-text isn't supported in this browser. Try Google Chrome for live transcription.";
    return;
  }
  recognitionSupported = true;
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";

  recognition.onresult = (event) => {
    let finalText = "";
    let interimText = "";
    for (let i = 0; i < event.results.length; i++) {
      const transcriptPiece = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += transcriptPiece + " ";
      else interimText += transcriptPiece;
    }
    if (currentQuestionState) currentQuestionState.transcript = finalText;
    document.getElementById("transcriptBox").textContent = finalText + interimText;
  };

  recognition.onerror = (e) => {
    console.warn("Speech recognition error:", e.error);
  };

  recognition.onend = () => {
    if (document.getElementById("screen-interview").classList.contains("active")) {
      try { recognition.start(); } catch (e) { /* already started */ }
    }
  };
}

function newQuestionState() {
  return {
    transcript: "",
    emotionCounts: {},
    faceDetectedFrames: 0,
    totalFrames: 0,
    startTime: Date.now(),
  };
}

function startQuestionTimer(seconds) {
  clearInterval(questionTimerInterval);
  questionTimeLeft = seconds;
  updateTimerDisplay();
  questionTimerInterval = setInterval(() => {
    questionTimeLeft -= 1;
    updateTimerDisplay();
    if (questionTimeLeft <= 0) {
      advanceQuestion("timeout");
    }
  }, 1000);
}

function updateTimerDisplay() {
  const m = Math.max(0, Math.floor(questionTimeLeft / 60));
  const s = Math.max(0, questionTimeLeft % 60);
  document.getElementById("timer").textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function showQuestion(question, difficulty) {
  questionIndex += 1;
  App.currentQuestion = question;
  App.difficulty = difficulty;

  document.getElementById("questionCounter").textContent = `Question ${questionIndex}/${App.maxQuestions}`;
  const badge = document.getElementById("difficultyBadge");
  if (badge) {
    badge.textContent = difficulty;
    badge.className = `badge difficulty-${difficulty}`;
  }
  document.getElementById("questionText").textContent = question.question;
  document.getElementById("transcriptBox").textContent = "";
  document.getElementById("practiceFeedback").classList.add("hidden");
  currentQuestionState = newQuestionState();
  silentSeconds = 0;

  const seconds = (TIME_BUDGET[App.mode] || TIME_BUDGET.practice)[difficulty] || 100;
  startQuestionTimer(seconds);

  if (recognitionSupported) {
    try { recognition.start(); } catch (e) { /* may already be running */ }
  }
}

async function finalizeCurrentQuestion(skipReason) {
  if (!currentQuestionState || !App.currentQuestion) return null;

  if (recognitionSupported) {
    try { recognition.stop(); } catch (e) { /* ignore */ }
  }

  const durationSeconds = Math.max(1, (Date.now() - currentQuestionState.startTime) / 1000);
  const transcript = currentQuestionState.transcript.trim();
  const faceDetectRatio = currentQuestionState.totalFrames
    ? currentQuestionState.faceDetectedFrames / currentQuestionState.totalFrames
    : 0;

  const resp = await fetch("/api/interview/next", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pool: App.pool,
      mode: App.mode,
      asked_ids: App.askedIds,
      current_difficulty: App.difficulty,
      last_question: App.currentQuestion,
      transcript,
      duration_seconds: durationSeconds,
      max_questions: App.maxQuestions,
    }),
  });
  const data = await resp.json();

  const answer = {
    question: App.currentQuestion.question,
    difficulty: App.difficulty,
    transcript,
    evaluation: data.evaluation,
    emotion_counts: currentQuestionState.emotionCounts,
    face_detect_ratio: faceDetectRatio,
    skip_reason: skipReason || "answered",
  };
  App.answers.push(answer);

  if (App.mode === "practice") {
    showPracticeFeedback(data.evaluation);
  }

  App.askedIds = data.asked_ids;
  return data;
}

function showPracticeFeedback(evaluation) {
  const box = document.getElementById("practiceFeedback");
  box.classList.remove("hidden");
  box.textContent = `${evaluation.tip} (score: ${Math.round(evaluation.overall)}%)`;
}

async function advanceQuestion(reason) {
  clearInterval(questionTimerInterval);
  const btnSkip = document.getElementById("skipBtn");
  if (btnSkip) btnSkip.disabled = true;

  const data = await finalizeCurrentQuestion(reason);
  if (btnSkip) btnSkip.disabled = false;

  if (!data || data.done || !data.next_question) {
    endInterview();
  } else {
    showQuestion(data.next_question, data.difficulty);
  }
}

function cleanupMedia() {
  clearInterval(silenceCheckInterval);
  clearInterval(faceSampleInterval);
  clearInterval(questionTimerInterval);
  if (recognitionSupported && recognition) {
    recognition.onend = null;
    try { recognition.stop(); } catch (e) { /* ignore */ }
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
}

async function endInterview() {
  cleanupMedia();

  const resp = await fetch("/api/interview/finish", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: App.mode,
      answers: App.answers,
    }),
  });

  if (resp.status === 401) {
    alert("Your session expired — please log in again to save this session.");
    goToScreen("auth");
    return;
  }

  const summary = await resp.json();

  renderSummary(summary);
  goToScreen("summary");
}

document.getElementById("skipBtn").addEventListener("click", () => advanceQuestion("manual_skip"));
document.getElementById("endInterviewBtn").addEventListener("click", () => advanceQuestion("ended_early"));

window.startInterview = async function () {
  questionIndex = 0;

  try {
    await setupWebcam();
  } catch (e) {
    alert("Camera/microphone access is required for the interview. Please allow access and try again.");
    goToScreen("mode");
    return;
  }

  await loadFaceModels();
  setupAudioSilenceDetection();
  setupFaceSampling();
  setupSpeechRecognition();

  showQuestion(App.currentQuestion, App.difficulty);
};

// ---------- Summary rendering ----------

function renderSummary(summary) {
  const answers = App.answers;
  const breakdown = summary.score_breakdown || {};

  const streakBanner = document.getElementById("streakBanner");
  if (streakBanner && summary.streak) {
    streakBanner.classList.remove("hidden");
    const s = summary.streak;
    streakBanner.innerHTML = `<span class="streak-flame">🔥</span> <strong>${s.current_streak}-day streak</strong>` +
      (s.current_streak >= s.longest_streak && s.current_streak > 1 ? " — new personal best!" : ` · longest: ${s.longest_streak}`);
  }

  const medalBanner = document.getElementById("medalBanner");
  const newMedals = summary.newly_awarded_medals || [];
  if (medalBanner) {
    if (newMedals.length) {
      medalBanner.classList.remove("hidden");
      medalBanner.innerHTML = `<strong>New medal${newMedals.length > 1 ? "s" : ""} unlocked!</strong> ` +
        newMedals.map((m) => `<span class="medal-pill">${m.icon} ${m.label}</span>`).join(" ");
    } else {
      medalBanner.classList.add("hidden");
    }
  }

  // Keep the profile hub in sync so streak/medals are current next visit.
  App.profile = { ...App.profile, streak: summary.streak, history: summary.history };
  if (typeof setTopbarUser === "function") setTopbarUser(App.user, App.profile);

  document.getElementById("answerScore").textContent = answers.length ? `${Math.round(breakdown.overall)}%` : "N/A";
  document.getElementById("answerScoreLabel").textContent =
    breakdown.overall >= 60 ? "Strong overall answers" : breakdown.overall >= 30 ? "Reasonable, room to improve" : "Needs more depth/specifics";

  // Emotional engagement is shown as descriptive-only context (see fairness
  // report) — it never factors into answerScore above.
  const emotionTotals = {};
  let totalEmotionSamples = 0;
  answers.forEach((a) => {
    Object.entries(a.emotion_counts || {}).forEach(([emotion, count]) => {
      emotionTotals[emotion] = (emotionTotals[emotion] || 0) + count;
      totalEmotionSamples += count;
    });
  });
  const positiveEmotions = ["happy", "neutral", "surprised"];
  const positiveCount = Object.entries(emotionTotals)
    .filter(([e]) => positiveEmotions.includes(e))
    .reduce((sum, [, c]) => sum + c, 0);
  const engagementPct = totalEmotionSamples ? Math.round((positiveCount / totalEmotionSamples) * 100) : 0;
  document.getElementById("emotionScore").textContent = totalEmotionSamples ? `${engagementPct}%` : "N/A";
  const dominantEmotion = Object.entries(emotionTotals).sort((a, b) => b[1] - a[1])[0];
  document.getElementById("emotionScoreLabel").textContent = dominantEmotion
    ? `Most common expression: ${dominantEmotion[0]} (not scored — see fairness note)`
    : "No face data captured";

  const avgFaceRatio = answers.length
    ? Math.round((answers.reduce((sum, a) => sum + a.face_detect_ratio, 0) / answers.length) * 100)
    : 0;
  document.getElementById("eyeContactScore").textContent = `${avgFaceRatio}%`;

  const totalFillers = answers.reduce((sum, a) => sum + (a.evaluation?.filler_count || 0), 0);
  const avgWpm = answers.length
    ? Math.round(answers.reduce((sum, a) => sum + (a.evaluation?.wpm || 0), 0) / answers.length)
    : 0;
  const silenceSkips = answers.filter((a) => a.skip_reason === "silence").length;
  const timeouts = answers.filter((a) => a.skip_reason === "timeout").length;

  document.getElementById("speechStats").innerHTML = `
    <li>Average speaking pace: ~${isFinite(avgWpm) ? avgWpm : 0} words/min</li>
    <li>Total filler words used: ${totalFillers}</li>
    <li>Questions auto-skipped due to silence: ${silenceSkips}</li>
    <li>Questions that ran out of time: ${timeouts}</li>
    <li>Highest difficulty reached: ${summary.highest_difficulty_reached || "-"}</li>
  `;

  const breakdownEl = document.getElementById("questionBreakdown");
  breakdownEl.innerHTML = answers
    .map((a, i) => {
      const score = a.evaluation?.overall ?? 0;
      const tag = score >= 60 ? "good" : score >= 30 ? "partial" : "weak";
      const tagLabel = score >= 60 ? "Good" : score >= 30 ? "Partial" : "Weak";
      return `
        <div class="qb-item">
          <strong>Q${i + 1} (${a.difficulty}): ${a.question}</strong>
          <span class="qb-tag ${tag}">${tagLabel} (${Math.round(score)}%)</span>
          <div style="color:var(--muted); font-size:13px; margin-top:6px;">
            ${a.transcript ? a.transcript.slice(0, 220) + (a.transcript.length > 220 ? "..." : "") : "<em>No speech captured</em>"}
          </div>
          <div style="color:var(--muted); font-size:13px; margin-top:4px;"><em>${a.evaluation?.tip || ""}</em></div>
        </div>`;
    })
    .join("");

  const recEl = document.getElementById("recommendationsList");
  if (recEl) {
    recEl.innerHTML = (summary.recommendations || []).map((r) => `<li>${r}</li>`).join("");
  }

  const fairnessEl = document.getElementById("fairnessNotes");
  if (fairnessEl) {
    const fr = summary.fairness_report || {};
    fairnessEl.innerHTML = (fr.notes || []).map((n) => `<li>${n}</li>`).join("");
  }

  const historyEl = document.getElementById("progressHistory");
  if (historyEl) {
    const history = summary.history || [];
    historyEl.innerHTML = history.length
      ? history
          .map((h) => {
            const date = new Date(h.created_at * 1000).toLocaleDateString();
            return `<li>${date} — ${h.mode}: ${Math.round(h.overall_score)}% (reached ${h.highest_difficulty_reached})</li>`;
          })
          .join("")
      : "<li>This is your first recorded session.</li>";
  }
}
