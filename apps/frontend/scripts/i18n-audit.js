const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

const localeRoot = path.resolve("messages");
const locales = ["en", "tr"];

function filesFor(locale) {
  const directory = path.join(localeRoot, locale);
  return fs.readdirSync(directory)
    .filter((name) => name.endsWith(".ts") && name !== "index.ts")
    .sort()
    .map((name) => path.join(directory, name));
}

function keysFrom(file) {
  const sourceText = fs.readFileSync(file, "utf8");
  const source = ts.createSourceFile(file, sourceText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const keys = new Set();
  function visit(node) {
    if (ts.isPropertyAssignment(node) && (ts.isStringLiteral(node.name) || ts.isNoSubstitutionTemplateLiteral(node.name))) {
      keys.add(node.name.text);
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  return keys;
}

function catalog(locale) {
  const keys = new Set();
  for (const file of filesFor(locale)) {
    for (const key of keysFrom(file)) {
      if (keys.has(key)) throw new Error(`Duplicate ${locale} translation key: ${key}`);
      keys.add(key);
    }
  }
  return keys;
}

const catalogs = Object.fromEntries(locales.map((locale) => [locale, catalog(locale)]));
const missingInTr = [...catalogs.en].filter((key) => !catalogs.tr.has(key)).sort();
const missingInEn = [...catalogs.tr].filter((key) => !catalogs.en.has(key)).sort();
const result = {
  locales,
  keyCounts: Object.fromEntries(locales.map((locale) => [locale, catalogs[locale].size])),
  missingInTr,
  missingInEn,
  complete: missingInTr.length === 0 && missingInEn.length === 0,
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
process.exitCode = result.complete ? 0 : 1;
