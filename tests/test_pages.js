const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { parseCsv } = require("../highlights.js");

const root = path.join(__dirname, "..");
const docs = path.join(root, "docs");
const read = name => fs.readFileSync(path.join(docs, name));

test("Pages entry point opens only the archived 2026 view", () => {
  const index = read("index.html").toString("utf8");
  assert.match(index, /results_viewer\.html\?static=1&amp;year=2026&amp;event=78640/);
  assert.doesNotMatch(index, /2025|78991/);
});

test("published CSV is an unchanged 2026 snapshot with real finish times", () => {
  const published = read("results.csv");
  assert.deepEqual(published, fs.readFileSync(path.join(root, "results.csv")));
  const rows = parseCsv(published.toString("utf8"));
  assert.equal(rows.length, 109);
  assert.equal(rows.filter(row => row.tid).length, 90);
  assert.equal(rows.find(row => row.navn === "Kristoffer Tungland")?.tid, "");
});

test("all pages and their local dependencies are published", () => {
  for (const name of [
    "results_viewer.html", "oversikter.html", "diplomer.html",
    "highlights.js", "diplomas.js", "assets/diplom-lopere.jpg",
    "assets/diplom-sti.jpg", "assets/fonts/GreatVibes-Regular.ttf",
    "assets/fonts/UnifrakturCook-Bold.ttf",
  ]) {
    assert.ok(fs.statSync(path.join(docs, name)).size > 0, name);
  }
  assert.deepEqual(fs.readdirSync(docs).filter(name => name.endsWith(".csv")), ["results.csv"]);
});

test("archived pages do not poll for fresh result files", () => {
  const viewer = read("results_viewer.html").toString("utf8");
  const overview = read("oversikter.html").toString("utf8");
  const diplomas = read("diplomer.html").toString("utf8");
  assert.match(viewer, /if\(!STATIC_MODE\)window\.setInterval\(refreshLiveData,AUTO_REFRESH_MS\)/);
  assert.match(overview, /if\(!STATIC_MODE\)window\.setInterval\(\(\)=>refresh\(\),intervalMs\)/);
  assert.match(diplomas, /STATIC_MODE\?"results\.csv":"results\.csv\?t="/);
  for (const html of [viewer, overview, diplomas]) {
    assert.match(html, /get\("static"\)==="1"/);
  }
});

test("published inline scripts are valid JavaScript", () => {
  for (const name of ["results_viewer.html", "oversikter.html", "diplomer.html"]) {
    const html = read(name).toString("utf8");
    for (const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) {
      new vm.Script(match[1], { filename: name });
    }
  }
});
