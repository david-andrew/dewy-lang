(() => {
  const offset = location.pathname.indexOf("/udewy/reference/");
  const root = offset >= 0 ? `${location.pathname.slice(0, offset)}/udewy/` : "/udewy/";
  const leftButtons = document.querySelector("#menu-bar .left-buttons");
  const rightButtons = document.querySelector("#menu-bar .right-buttons");

  if (leftButtons && rightButtons) {
    const home = document.createElement("a");
    home.className = "udewy-toolbar-link udewy-home-link";
    home.href = root;
    home.textContent = "µDewy";
    home.setAttribute("aria-label", "µDewy website home");
    leftButtons.append(home);

    const peer = document.createElement("a");
    peer.className = "udewy-toolbar-link udewy-peer-link";
    peer.href = `${root}showcase/`;
    peer.textContent = "Showcase";
    peer.setAttribute("aria-label", "µDewy showcase");
    rightButtons.prepend(peer);
  }

  const themeMap = {
    light: "udewy-light",
    navy: "udewy-dark",
    coal: "udewy-dark",
    "dewy-light": "udewy-light",
    "dewy-dark": "udewy-dark",
  };
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
      if (button.id === "udewy-light" || button.id === "udewy-dark") {
        localStorage.setItem("udewy-theme-link", "on");
        localStorage.setItem("dewy-theme", button.id === "udewy-dark" ? "dark" : "light");
      } else {
        localStorage.setItem("udewy-theme-link", "off");
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
    const html = document.documentElement;
    const udewy = html.classList.contains("udewy-light") || html.classList.contains("udewy-dark");
    if (!udewy) return;
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
