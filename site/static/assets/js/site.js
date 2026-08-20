(() => {
  const THEME_KEY = "dewy-theme";
  const themeColors = { light: "#f3faf6", dark: "#112b20" };
  const themeColor = document.querySelector('meta[name="theme-color"]');

  const currentTheme = () => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");

  const applyTheme = (theme) => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    if (themeColor) themeColor.setAttribute("content", themeColors[theme]);
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const next = theme === "dark" ? "light" : "dark";
      const label = `Switch to ${next} theme`;
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
    });
  };

  applyTheme(currentTheme());

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const theme = currentTheme() === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, theme);
      applyTheme(theme);
    });
  });

  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (event) => {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") return;
    applyTheme(event.matches ? "dark" : "light");
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
