// Cover screen: fade in the CTA, then hand off into the main app.
// Entry is gated behind login/signup (see auth.js) — the cover button
// routes to the auth screen, or straight to the profile hub if a
// session cookie is already present.

document.addEventListener("DOMContentLoaded", () => {
  const cta = document.getElementById("coverCta");
  if (cta) setTimeout(() => cta.classList.add("reveal"), 450);
});

document.getElementById("enterAppBtn")?.addEventListener("click", () => {
  document.getElementById("screen-cover").classList.remove("active");
  document.getElementById("topbar")?.classList.remove("hidden");

  if (typeof window.routeAfterCover === "function") {
    window.routeAfterCover();
  } else if (typeof goToScreen === "function") {
    goToScreen("auth");
  }
  document.querySelector("main.container")?.scrollIntoView({ behavior: "smooth", block: "start" });
});
