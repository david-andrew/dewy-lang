window.addEventListener(
  "message",
  function (event) {
    // Check event.origin here to ensure the message is from a trusted source
    const { width, height } = event.data;
    const iframe = document.getElementById("DemoIframe");
    if (iframe) {
      // console.log(
      //   `received width/height ${width}/${height}`,
      //   "setting height",
      //   height
      // );
      iframe.style.height = height + "px";
    }
  },
  false
);
// console.log("dewy_online_interpreter_handler.js loaded successfully!");
