(() => {
  const marker = location.pathname.includes("/learn/") ? "/learn/" : "/reference/";
  const offset = location.pathname.indexOf(marker);
  const root = offset >= 0 ? location.pathname.slice(0, offset + 1) : "/";
  const leftButtons = document.querySelector("#menu-bar .left-buttons");
  const rightButtons = document.querySelector("#menu-bar .right-buttons");

  if (!leftButtons || !rightButtons) return;

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
  peer.setAttribute("aria-label", marker === "/learn/" ? "Dewy language reference" : "Learning Dewy");
  rightButtons.prepend(peer);
})();
