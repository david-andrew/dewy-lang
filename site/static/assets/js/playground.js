(() => {
  // Every run gets a fresh sandboxed iframe (opaque origin, no network). One game
  // runs at a time; each run stops after its card's lifetime in seconds.
  const stoppers = [];
  document.querySelectorAll('[data-program]').forEach(button => {
    const card = button.closest('article');
    const host = card.querySelector('[data-run-host]');
    const status = card.querySelector('[data-run-status]');
    const isGame = card.classList.contains('game-card');
    const idle = Array.from(host.childNodes);
    const lifetime = Number(button.dataset.lifetime || 15);
    let timer, generation = 0, running = false;
    const stop = (message = 'Stopped. Run again for a fresh instance.') => {
      generation++;
      clearTimeout(timer);
      if (!running) return;
      running = false;
      host.replaceChildren(...idle);
      card.classList.remove('is-running');
      status.textContent = message;
    };
    stoppers.push({isGame, stop});
    card.querySelector('[data-stop]').addEventListener('click', () => stop());
    const full = card.querySelector('[data-fullscreen]');
    if (full) full.addEventListener('click', () => {
      const frame = host.querySelector('iframe');
      if (!frame) { status.textContent = 'Start the game first.'; return; }
      (frame.requestFullscreen || frame.webkitRequestFullscreen || (() => {})).call(frame);
    });
    button.addEventListener('click', async () => {
      if (isGame) stoppers.forEach(s => { if (s.isGame) s.stop('Stopped: another game started.'); });
      stop();
      const current = generation;
      status.textContent = 'Loading…';
      try {
        const response = await fetch(button.dataset.program, {cache: 'no-cache'});
        if (!response.ok) throw new Error('Example could not be loaded.');
        const source = await response.text();
        if (current !== generation) return;
        const frame = document.createElement('iframe');
        frame.title = card.querySelector('h3').textContent + (isGame ? ' game' : ' output');
        frame.setAttribute('sandbox', 'allow-scripts');
        frame.setAttribute('allow', 'fullscreen; gamepad');
        frame.srcdoc = source;
        running = true;
        host.replaceChildren(frame);
        card.classList.add('is-running');
        if (isGame) frame.addEventListener('load', () => frame.focus(), {once: true});
        const minutes = lifetime >= 60 ? `${Math.round(lifetime / 60)} minutes` : `${lifetime} seconds`;
        status.textContent = `Running in a sandbox. Stops after ${minutes}.`;
        timer = setTimeout(() => stop('Stopped after its time limit. Run again for a fresh instance.'), lifetime * 1000);
      } catch (error) {
        if (current === generation) status.textContent = error.message;
      }
    });
  });
})();
