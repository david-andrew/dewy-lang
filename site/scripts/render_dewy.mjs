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

const tokenColors = (palette) => [
  { settings: { foreground: palette.foreground } },
  {
    scope: ["comment", "punctuation.definition.comment"],
    settings: { foreground: palette.comment, fontStyle: "italic" },
  },
  {
    scope: ["string", "punctuation.definition.string"],
    settings: { foreground: palette.string },
  },
  {
    scope: ["constant.character.escape", "constant.character.escape.unicode"],
    settings: { foreground: palette.escape },
  },
  {
    scope: ["constant.numeric", "storage.type.numeric.prefix"],
    settings: { foreground: palette.number },
  },
  {
    scope: ["constant.language", "variable.language"],
    settings: { foreground: palette.constant },
  },
  {
    scope: ["keyword.control", "keyword.declaration", "storage.modifier"],
    settings: { foreground: palette.keyword, fontStyle: "bold" },
  },
  {
    scope: ["keyword.operator", "keyword.other.word-operator"],
    settings: { foreground: palette.operator },
  },
  {
    scope: ["entity.name.function", "support.function"],
    settings: { foreground: palette.function },
  },
  {
    scope: ["entity.name.type", "support.type", "storage.type"],
    settings: { foreground: palette.type },
  },
  {
    scope: ["variable.parameter", "entity.name.tag.heredoc-delimiter"],
    settings: { foreground: palette.parameter },
  },
  {
    scope: ["entity.name.tag.metatag", "keyword.other.metatag"],
    settings: { foreground: palette.metatag },
  },
  {
    scope: ["invalid", "invalid.illegal"],
    settings: { foreground: palette.invalid, fontStyle: "underline" },
  },
];

const makeTheme = (name, background, palette) => ({
  name,
  type: "dark",
  colors: {
    "editor.background": background,
    "editor.foreground": palette.foreground,
  },
  settings: tokenColors(palette),
});

const lightTheme = makeTheme("dewy-code-light", "#1c2822", {
  foreground: "#d8e4dd",
  comment: "#82988c",
  string: "#acd18f",
  escape: "#f0c978",
  number: "#c7b5ee",
  constant: "#ef9b83",
  keyword: "#7eddb9",
  operator: "#a8daca",
  function: "#82caee",
  type: "#f0c978",
  parameter: "#e9bf8a",
  metatag: "#ef9b83",
  invalid: "#ff8178",
});
const darkTheme = makeTheme("dewy-code-dark", "#07140f", {
  foreground: "#d5e8dd",
  comment: "#789184",
  string: "#a9d695",
  escape: "#f4d27f",
  number: "#cfbaf7",
  constant: "#f2a188",
  keyword: "#7ee8c0",
  operator: "#a9e2cf",
  function: "#85d4f5",
  type: "#f4d27f",
  parameter: "#edc58f",
  metatag: "#f2a188",
  invalid: "#ff8a82",
});

const highlighter = await createHighlighter({
  langs: [language],
  themes: [lightTheme, darkTheme],
});

const results = sources.map((source) => {
  const rendered = highlighter.codeToHtml(source, {
    lang: "dewy",
    themes: {
      light: lightTheme.name,
      dark: darkTheme.name,
    },
    defaultColor: false,
  });
  const style = rendered.match(/^<pre\b[^>]*\bstyle="([^"]*)"/)?.[1] ?? "";
  const inner = rendered.match(/<code>([\s\S]*)<\/code>/)?.[1];
  if (inner === undefined) {
    throw new Error("Shiki returned an unexpected HTML shape");
  }
  return { inner, style };
});

highlighter.dispose();
process.stdout.write(JSON.stringify(results));
