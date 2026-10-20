(() => {
  document.querySelectorAll('[data-program]').forEach(button => {
    const card = button.closest('article');
    const host = card.querySelector('[data-run-host]');
    const status = card.querySelector('[data-run-status]');
    let timer, generation = 0;
    const stop = () => {
      generation++;
      clearTimeout(timer);
      host.replaceChildren();
      status.textContent = 'Stopped. Run again for a fresh instance.';
    };
    card.querySelector('[data-stop]').addEventListener('click', stop);
    button.addEventListener('click', async () => {
      stop();
      const current = generation;
      status.textContent = 'Loading…';
      try {
        const response = await fetch(button.dataset.program, {cache: 'no-cache'});
        if (!response.ok) throw new Error('Example could not be loaded.');
        const source = await response.text();
        if (current !== generation) return;
        const frame = document.createElement('iframe');
        frame.title = card.querySelector('h3').textContent + ' output';
        frame.setAttribute('sandbox', 'allow-scripts');
        frame.srcdoc = source;
        host.replaceChildren(frame);
        status.textContent = 'Running in a sandbox. Stops after 15 seconds.';
        timer = setTimeout(stop, 15000);
      } catch (error) {
        if (current === generation) status.textContent = error.message;
      }
    });
  });
})();
