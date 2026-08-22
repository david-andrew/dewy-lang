(() => {
  const demos = [
    {
      slug: "plasma",
      title: "Plasma",
      blurb: "A fullscreen WebGL fragment shader driven from µDewy.",
      source: "https://github.com/david-andrew/dewy-lang/blob/master/udewy/tests/test_webgl_plasma.udewy",
    },
    {
      slug: "water",
      title: "Water",
      blurb: "Pointer motion and clicks spawn overlapping ripple rings.",
      source: "https://github.com/david-andrew/dewy-lang/blob/master/udewy/tests/test_webgl_water.udewy",
    },
    {
      slug: "slime-volleyball",
      title: "Slime Volleyball",
      blurb: "A two-slime match with CPU, stages, and short sound effects.",
      source: "https://github.com/david-andrew/dewy-lang/blob/master/udewy/tests/test_slime_volleyball.udewy",
    },
    {
      slug: "crypt",
      title: "μCrypt",
      blurb: "A Wolfenstein-style raycast dungeon with combat and procedural audio.",
      source: "https://github.com/david-andrew/dewy-lang/tree/master/udewy/tests/crypt",
    },
    {
      slug: "uzero2",
      title: "μZero2",
      blurb: "A hover racer with tracks, AI, an editor, and an engine note.",
      source: "https://github.com/david-andrew/dewy-lang/tree/master/udewy/tests/uzero2",
    },
  ];

  const tabs = document.querySelector("[data-demo-tabs]");
  const frame = document.querySelector("[data-demo-frame]");
  const blurb = document.querySelector("[data-demo-blurb]");
  const source = document.querySelector("[data-demo-source]");
  if (!tabs || !frame || !blurb || !source) return;

  let selected = demos[0];
  let iframe = null;

  const demoUrl = (demo) => `demos/${demo.slug}/`;
  const bySlug = (slug) => demos.find((demo) => demo.slug === slug) || demos[0];

  const focusDemo = () => {
    if (!iframe) return;
    iframe.focus({ preventScroll: true });
    try {
      const inner = iframe.contentDocument;
      const canvas = inner?.querySelector("canvas");
      if (canvas && canvas.tabIndex < 0) canvas.tabIndex = 0;
      iframe.contentWindow?.focus();
      (canvas || inner?.body || inner?.documentElement)?.focus?.({ preventScroll: true });
    } catch {
      // same-origin only; ignore if the frame is mid-navigation
    }
  };

  const tearDown = () => {
    if (!iframe) return;
    iframe.src = "about:blank";
    iframe.remove();
    iframe = null;
  };

  const mount = (demo) => {
    tearDown();
    iframe = document.createElement("iframe");
    iframe.className = "demo-iframe";
    iframe.title = demo.title;
    iframe.tabIndex = 0;
    iframe.setAttribute("allow", "autoplay");
    iframe.addEventListener("load", focusDemo);
    iframe.src = demoUrl(demo);
    frame.replaceChildren(iframe);
    requestAnimationFrame(focusDemo);
  };

  const syncChrome = (demo) => {
    selected = demo;
    blurb.textContent = demo.blurb;
    source.href = demo.source;
    source.textContent = "Source";
    tabs.querySelectorAll("[data-demo]").forEach((tab) => {
      const active = tab.getAttribute("data-demo") === demo.slug;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    const hash = `#${demo.slug}`;
    if (location.hash !== hash) {
      history.replaceState(null, "", hash);
    }
  };

  const select = (demo) => {
    syncChrome(demo);
    mount(demo);
  };

  demos.forEach((demo, index) => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "demo-tab";
    tab.setAttribute("role", "tab");
    tab.setAttribute("data-demo", demo.slug);
    tab.id = `demo-tab-${demo.slug}`;
    tab.setAttribute("aria-controls", "demo-stage");
    tab.textContent = demo.title;
    tab.addEventListener("mousedown", (event) => event.preventDefault());
    tab.addEventListener("click", () => select(demo));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      const step = event.key === "ArrowRight" ? 1 : -1;
      const next = demos[(index + step + demos.length) % demos.length];
      select(next);
    });
    tabs.append(tab);
  });
  frame.id = "demo-stage";

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      tearDown();
      return;
    }
    mount(selected);
  });
  window.addEventListener("pagehide", () => tearDown());

  select(bySlug(location.hash.replace(/^#/, "")));
})();
