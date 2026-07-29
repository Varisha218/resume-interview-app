// Auth + profile: login/signup, session check, and rendering the
// streaks/medals/history hub. Talks to /api/auth/* and /api/profile.

function setTopbarUser(user, profile) {
  const wrap = document.getElementById("topbarUser");
  if (!user) {
    wrap?.classList.add("hidden");
    return;
  }
  wrap?.classList.remove("hidden");
  document.getElementById("topbarUsername").textContent = user.username;
  const streak = profile?.streak?.current_streak ?? 0;
  document.getElementById("topbarStreak").textContent = `🔥 ${streak}`;
}

function renderProfile(user, profile) {
  document.getElementById("profileUsername").textContent = user.username;

  const streak = profile.streak || { current_streak: 0, longest_streak: 0 };
  document.getElementById("currentStreakNum").textContent = streak.current_streak;
  document.getElementById("longestStreakNum").textContent = streak.longest_streak;
  const flame = document.getElementById("streakFlame");
  flame.style.opacity = streak.current_streak > 0 ? "1" : "0.35";

  const medalGrid = document.getElementById("medalGrid");
  const earned = profile.medals?.earned || [];
  const locked = profile.medals?.locked || [];
  medalGrid.innerHTML =
    earned.map((m) => `
      <div class="medal earned" title="${m.label}">
        <div class="medal-icon">${m.icon}</div>
        <div class="medal-label">${m.label}</div>
      </div>`).join("") +
    locked.map((m) => `
      <div class="medal locked" title="${m.desc}">
        <div class="medal-icon">${m.icon}</div>
        <div class="medal-label">${m.label}</div>
      </div>`).join("");

  const historyEl = document.getElementById("profileHistory");
  const history = profile.history || [];
  historyEl.innerHTML = history.length
    ? history.map((h) => {
        const date = new Date(h.created_at * 1000).toLocaleDateString();
        return `<li>${date} — ${h.mode}: ${Math.round(h.overall_score)}% (reached ${h.highest_difficulty_reached})</li>`;
      }).join("")
    : `<li class="detail-text">No sessions yet — start your first interview below.</li>`;
}

window.refreshProfile = async function () {
  try {
    const resp = await fetch("/api/profile");
    if (!resp.ok) return;
    const profile = await resp.json();
    App.profile = profile;
    if (App.user) renderProfile(App.user, profile);
    setTopbarUser(App.user, profile);
  } catch (e) {
    // non-fatal — profile screen just won't refresh
  }
};

window.routeAfterCover = function () {
  if (App.user) {
    goToScreen("upload");
    window.refreshProfile();
  } else {
    goToScreen("auth");
  }
};

// ---------- Session check on page load ----------

(async function checkSession() {
  try {
    const resp = await fetch("/api/auth/me");
    const data = await resp.json();
    if (data.user) {
      App.user = data.user;
      App.profile = data.profile;
      setTopbarUser(data.user, data.profile);
    }
  } catch (e) {
    // treat as logged out
  }
})();

// ---------- Auth tabs ----------

document.querySelectorAll(".auth-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".auth-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const target = tab.dataset.tab;
    document.getElementById("loginForm").classList.toggle("hidden", target !== "login");
    document.getElementById("signupForm").classList.toggle("hidden", target !== "signup");
  });
});

// ---------- Login ----------

document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("loginError");
  errorEl.textContent = "";
  const identifier = document.getElementById("loginIdentifier").value.trim();
  const password = document.getElementById("loginPassword").value;

  const btn = e.target.querySelector(".auth-submit");
  btn.disabled = true;
  btn.textContent = "Logging in...";
  try {
    const resp = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: identifier, password }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "Login failed.");

    App.user = data.user;
    App.profile = data.profile;
    setTopbarUser(data.user, data.profile);
    renderProfile(data.user, data.profile);
    goToScreen("upload");
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Log In";
  }
});

// ---------- Sign up ----------

document.getElementById("signupForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("signupError");
  errorEl.textContent = "";
  const username = document.getElementById("signupUsername").value.trim();
  const email = document.getElementById("signupEmail").value.trim();
  const password = document.getElementById("signupPassword").value;

  const btn = e.target.querySelector(".auth-submit");
  btn.disabled = true;
  btn.textContent = "Creating account...";
  try {
    const resp = await fetch("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "Could not create account.");

    App.user = data.user;
    App.profile = data.profile;
    setTopbarUser(data.user, data.profile);
    renderProfile(data.user, data.profile);
    goToScreen("upload");
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Create Account";
  }
});

// ---------- Logout ----------

async function doLogout() {
  await fetch("/api/auth/logout", { method: "POST" });
  App.user = null;
  App.profile = null;
  setTopbarUser(null, null);
  goToScreen("auth");
}

document.getElementById("topbarLogoutBtn").addEventListener("click", doLogout);

document.getElementById("topbarProfileBtn").addEventListener("click", () => {
  if (!App.user) return;
  App.pendingInterviewStart = false;
  document.getElementById("startNewInterviewBtn").textContent = "Start New Interview →";
  window.refreshProfile();
  goToScreen("profile");
});

// ---------- Profile hub actions ----------

document.getElementById("startNewInterviewBtn").addEventListener("click", () => {
  if (window.App && window.App.pendingInterviewStart) {
    window.App.pendingInterviewStart = false;
    document.getElementById("startNewInterviewBtn").textContent = "Start New Interview →";
    if (window.startInterviewFromMode) window.startInterviewFromMode();
  } else {
    goToScreen("upload");
  }
});
