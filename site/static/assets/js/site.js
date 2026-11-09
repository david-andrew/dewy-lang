(() => {
  const THEME_KEY = "dewy-theme";
  const BOOK_KEY = "mdbook-theme";
  const LINK_KEY = "dewy-theme-link";
  const root = document.documentElement;
  const themeColors = root.dataset.site === "udewy"
    ? { light: "#eef7fa", dark: "#0c1c22" }
    : { light: "#f3faf6", dark: "#0e241b" };
  const themeColor = document.querySelector('meta[name="theme-color"]');
  const systemDark = matchMedia("(prefers-color-scheme: dark)");

  const systemTheme = () => (systemDark.matches ? "dark" : "light");
  const opposite = (theme) => (theme === "dark" ? "light" : "dark");
  const storedMode = () => {
    try {
      const mode = localStorage.getItem(THEME_KEY);
      return mode === "light" || mode === "dark" ? mode : "auto";
    } catch {
      return "auto";
    }
  };
  let mode = root.dataset.themeMode || storedMode();

  // From auto, the first click always changes the look (to the opposite of the
  // system); the second pins the system look; the third returns to auto.
  const nextMode = (current) => {
    const system = systemTheme();
    if (current === "auto") return opposite(system);
    if (current === system) return "auto";
    return system;
  };
  const describe = (value) => (value === "auto"
    ? `automatic (${systemTheme()}, following the system)`
    : value);

  const applyMode = (value) => {
    mode = value;
    const theme = value === "auto" ? systemTheme() : value;
    root.dataset.theme = theme;
    root.dataset.themeMode = value;
    root.style.colorScheme = theme;
    if (themeColor) themeColor.setAttribute("content", themeColors[theme]);
    const next = nextMode(value);
    const label = `Theme: ${describe(value)}. Switch to ${next === "auto" ? "automatic (follow the system)" : `${next} theme`}`;
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
    });
  };

  const saveMode = (value) => {
    try {
      localStorage.setItem(THEME_KEY, value);
      if (localStorage.getItem(LINK_KEY) !== "off") {
        if (value === "auto") localStorage.removeItem(BOOK_KEY);
        else localStorage.setItem(BOOK_KEY, value === "dark" ? "dewy-dark" : "dewy-light");
      }
    } catch {
      // Storage unavailable: the choice lasts for this page only.
    }
  };

  applyMode(mode);

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const value = nextMode(mode);
      saveMode(value);
      applyMode(value);
    });
  });

  systemDark.addEventListener("change", () => applyMode(mode));
  window.addEventListener("storage", (event) => {
    if (event.key === THEME_KEY || event.key === null) applyMode(storedMode());
  });

  const navToggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-nav]");
  if (navToggle && nav) {
    navToggle.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", String(open));
    });
  }

  const copyText = async (value) => {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      const fallback = document.createElement("textarea");
      fallback.value = value;
      fallback.setAttribute("readonly", "");
      fallback.style.position = "fixed";
      fallback.style.opacity = "0";
      document.body.append(fallback);
      fallback.select();
      const copied = document.execCommand("copy");
      fallback.remove();
      return copied;
    }
  };

  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const value = button.getAttribute("data-copy") || "";
      const original = button.dataset.copyLabel || button.textContent;
      button.dataset.copyLabel = original;
      const repeated = button.classList.contains("copied");
      const copied = await copyText(value);

      window.clearTimeout(button.copyResetTimer);
      button.classList.toggle("copied", copied);
      button.classList.toggle("copy-failed", !copied);
      button.textContent = copied ? (repeated ? "Copied again ✓" : "Copied ✓") : "Copy failed";
      button.setAttribute("aria-label", copied ? "Install command copied" : "Install command could not be copied");

      button.copyResetTimer = window.setTimeout(() => {
        button.textContent = original;
        button.classList.remove("copied", "copy-failed");
        button.removeAttribute("aria-label");
      }, 1800);
    });
  });

  const header = document.querySelector("[data-header]");
  const heroBrand = document.querySelector("[data-hero-brand]");
  const narrowDisplay = window.matchMedia("(max-width: 720px)");
  if (header && heroBrand && !narrowDisplay.matches && "IntersectionObserver" in window) {
    header.classList.add("brand-watch");
    requestAnimationFrame(() => requestAnimationFrame(() => header.classList.add("brand-ready")));
    new IntersectionObserver(([entry]) => {
      header.classList.toggle("show-brand", !entry.isIntersecting);
    }, { rootMargin: "-56px 0px 0px 0px" }).observe(heroBrand);
  }

  const install = document.querySelector("[data-install]");
  if (install) {
    const unix = "curl -fsSL https://dewy-lang.org/install.sh | bash";
    const commands = {
      linux: { prompt: "$", command: unix, hint: "Linux x86-64 and ARM64" },
      macos: { prompt: "$", command: unix, hint: "macOS on Apple silicon" },
      windows: { prompt: "PS>", command: "irm https://dewy-lang.org/install.ps1 | iex", hint: "Windows x64, in PowerShell" },
    };
    const osTabs = [...install.querySelectorAll('[role="tab"][data-os]')];
    const panel = install.querySelector('[role="tabpanel"]');
    const code = panel.querySelector("code");
    const copy = panel.querySelector("[data-copy]");
    const prompt = panel.querySelector("[data-install-prompt]");
    const hint = install.querySelector("[data-install-hint]");

    const selectOs = (os, focus = false) => {
      const entry = commands[os];
      osTabs.forEach((tab) => {
        const selected = tab.dataset.os === os;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        if (selected) {
          panel.setAttribute("aria-labelledby", tab.id);
          if (focus) tab.focus();
        }
      });
      // One span per word, so narrow screens wrap between words, never inside a URL.
      code.replaceChildren(...entry.command.split(" ").flatMap((word, i) => {
        const span = document.createElement("span");
        span.textContent = word;
        return i ? [" ", span] : [span];
      }));
      copy.setAttribute("data-copy", entry.command);
      prompt.textContent = entry.prompt;
      hint.textContent = entry.hint;
    };

    const detectOs = () => {
      const platform = (navigator.userAgentData?.platform || navigator.platform || "").toLowerCase();
      const agent = navigator.userAgent.toLowerCase();
      if (platform.startsWith("win") || agent.includes("windows")) return "windows";
      if (platform.startsWith("mac") || /macintosh|mac os x/.test(agent)) return "macos";
      return "linux";
    };

    osTabs.forEach((tab, index) => {
      tab.addEventListener("click", () => selectOs(tab.dataset.os));
      tab.addEventListener("keydown", (event) => {
        const moves = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: osTabs.length - 1 };
        if (!(event.key in moves)) return;
        event.preventDefault();
        const target = osTabs[(moves[event.key] + osTabs.length) % osTabs.length];
        selectOs(target.dataset.os, true);
      });
    });
    selectOs(detectOs());
  }

  const tabs = [...document.querySelectorAll("[data-tour-tab]")];
  const panels = [...document.querySelectorAll("[data-tour-panel]")];
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("aria-controls");
      tabs.forEach((item) => item.setAttribute("aria-selected", String(item === tab)));
      panels.forEach((panel) => {
        panel.hidden = panel.id !== target;
      });
    });
  });
})();
