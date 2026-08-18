window.addEventListener(
  "message",
  function (event) {
    // Check event.origin here to ensure the message is from a trusted source
    if (
      event.data.width === undefined ||
      event.data.height === undefined ||
      event.data.id === undefined
    ) {
      return;
    }
    const { width, height, id } = event.data;
    const iframe = document.getElementById(id);
    if (iframe) {
      iframe.style.height = height + "px";
    }
  },
  false
);
