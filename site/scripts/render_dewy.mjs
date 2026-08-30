/** Render Dewy source with the VS Code extension's TextMate grammar. */

import { readFile } from "node:fs/promises";
import process from "node:process";

import { createHighlighter } from "shiki";

const grammarPath = process.argv[2];
if (!grammarPath) {
  throw new Error("usage: node render_dewy.mjs GRAMMAR_PATH");
}

const input = await new Promise((resolve, reject) => {
  const chunks = [];
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => chunks.push(chunk));
  process.stdin.on("end", () => resolve(chunks.join("")));
  process.stdin.on("error", reject);
});
const sources = JSON.parse(input);
if (!Array.isArray(sources) || sources.some((source) => typeof source !== "string")) {
  throw new TypeError("renderer input must be a JSON array of source strings");
}

const grammar = JSON.parse(await readFile(grammarPath, "utf8"));
const language = {
  ...grammar,
  name: "dewy",
};
const theme = "dark-plus";

const highlighter = await createHighlighter({
  langs: [language],
  themes: [theme],
});

const results = sources.map((source) => {
  const rendered = highlighter.codeToHtml(source, {
    lang: "dewy",
    theme,
  });
  const preStyle = rendered.match(/^<pre\b[^>]*\bstyle="([^"]*)"/)?.[1] ?? "";
  const style = preStyle
    .split(";")
    .filter((declaration) => !declaration.trim().startsWith("background-color:"))
    .join(";");
  const inner = rendered.match(/<code>([\s\S]*)<\/code>/)?.[1];
  if (inner === undefined) {
    throw new Error("Shiki returned an unexpected HTML shape");
  }
  return { inner, style };
});

highlighter.dispose();
process.stdout.write(JSON.stringify(results));
