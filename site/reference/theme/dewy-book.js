(() => {
  const marker = location.pathname.includes("/learn/") ? "/learn/" : "/reference/";
  const offset = location.pathname.indexOf(marker);
  const root = offset >= 0 ? location.pathname.slice(0, offset + 1) : "/";
  const leftButtons = document.querySelector("#menu-bar .left-buttons");
  const rightButtons = document.querySelector("#menu-bar .right-buttons");

  if (leftButtons && rightButtons) {
    const home = document.createElement("a");
    home.className = "dewy-toolbar-link dewy-home-link";
    home.href = root;
    home.textContent = "Dewy";
    home.setAttribute("aria-label", "Dewy website home");
    leftButtons.append(home);

    const peer = document.createElement("a");
    peer.className = "dewy-toolbar-link dewy-peer-link";
    peer.href = marker === "/learn/" ? `${root}reference/` : `${root}learn/`;
    peer.textContent = marker === "/learn/" ? "Reference" : "Learn";
    peer.setAttribute(
      "aria-label",
      marker === "/learn/" ? "Dewy language reference" : "Learning Dewy",
    );
    rightButtons.prepend(peer);
  }

  const themeMap = { light: "dewy-light", navy: "dewy-dark", coal: "dewy-dark" };
  try {
    const stored = localStorage.getItem("mdbook-theme");
    if (stored && themeMap[stored]) {
      const next = themeMap[stored];
      localStorage.setItem("mdbook-theme", next);
      document.documentElement.classList.remove(stored);
      document.documentElement.classList.add(next);
    }
  } catch {
    // ignore
  }

  document.getElementById("theme-list")?.addEventListener("click", (event) => {
    const button = event.target.closest("button.theme");
    if (!button) return;
    try {
      if (button.id === "dewy-light" || button.id === "dewy-dark") {
        localStorage.setItem("dewy-theme-link", "on");
        localStorage.setItem("dewy-theme", button.id === "dewy-dark" ? "dark" : "light");
      } else {
        localStorage.setItem("dewy-theme-link", "off");
      }
    } catch {
      // ignore
    }
  });

  const sheets = {
    ayu: document.querySelector("#ayu-highlight-css"),
    night: document.querySelector("#tomorrow-night-css"),
    light: document.querySelector("#highlight-css"),
  };

  const syncHighlight = () => {
    if (!sheets.night || !sheets.light || !sheets.ayu) return;
    const dark = document.documentElement.classList.contains("dewy-dark");
    if (!dark) return;
    sheets.ayu.disabled = true;
    sheets.night.disabled = false;
    sheets.light.disabled = true;
  };

  syncHighlight();
  new MutationObserver(syncHighlight).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
})();
