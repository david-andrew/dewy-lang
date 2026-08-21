(() => {
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

  let stored = localStorage.getItem(siteKey);
  if (stored !== "light" && stored !== "dark" && localStorage.getItem(linkKey) !== "off") {
    const fromBook = bookToSite[localStorage.getItem(bookKey)];
    if (fromBook) {
      stored = fromBook;
      localStorage.setItem(siteKey, stored);
      localStorage.setItem(bookKey, siteToBook[stored]);
    }
  }

  const theme = stored === "light" || stored === "dark"
    ? stored
    : (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) themeColor.setAttribute("content", theme === "dark" ? "#112b20" : "#f3faf6");
})();
