(() => {
  // Theme mode: "auto" (follow the system), "light" or "dark".
  // dewy-theme holds the site's mode; the docs books mirror it in mdbook-theme
  // (auto removes the key, so mdBook follows the system too) unless the reader
  // picked a non-Dewy book theme (dewy-theme-link = "off").
  const siteKey = "dewy-theme";
  const bookKey = "mdbook-theme";
  const linkKey = "dewy-theme-link";
  const bookToSite = {
    light: "light",
    "dewy-light": "light",
    navy: "dark",
    coal: "dark",
    "dewy-dark": "dark",
  };
  const siteToBook = { light: "dewy-light", dark: "dewy-dark" };

  let mode = "auto";
  try {
    mode = localStorage.getItem(siteKey);
    if (mode !== "light" && mode !== "dark" && mode !== "auto") {
      // No site choice yet: adopt an explicit Dewy book choice, else follow the system.
      const fromBook = localStorage.getItem(linkKey) !== "off"
        ? bookToSite[localStorage.getItem(bookKey)]
        : undefined;
      mode = fromBook || "auto";
      if (fromBook) {
        localStorage.setItem(siteKey, mode);
        localStorage.setItem(bookKey, siteToBook[mode]);
      }
    }
  } catch {
    mode = "auto";
  }

  const theme = mode === "auto"
    ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : mode;
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.dataset.themeMode = mode;
  root.style.colorScheme = theme;
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) {
    const udewy = root.dataset.site === "udewy";
    const colors = udewy
      ? { light: "#eef7fa", dark: "#0c1c22" }
      : { light: "#f3faf6", dark: "#0e241b" };
    themeColor.setAttribute("content", colors[theme]);
  }
})();
