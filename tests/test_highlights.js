const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { parseCsv, calculate } = require("../highlights.js");

test("viewer treats legacy +90 kg rows as a class, not a gender", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "results_viewer.html"), "utf8");
  const source = html.match(/^function parseCSV\(csv\)\{.*$/m)?.[0];
  assert.ok(source);
  const parseViewerCsv = vm.runInNewContext(`${source}; parseCSV`);
  const [row] = parseViewerCsv("Gruppe,Klasse,Navn\nPluss,Pluss 90kg,Ola\n");
  assert.equal(row.gruppe, "Mann");
  assert.equal(row.klasse, "Pluss 90kg");
  assert.doesNotMatch(html, /id="filterGroup"[^<]*<option value="Pluss"/);
});

test("CSV parser keeps quoted names and Norwegian headers", () => {
  const rows = parseCsv('Navn,Gruppe,BesteÅr\r\n"Nordmann, Kari",Dame,2024\r\n');
  assert.deepEqual(rows, [{ navn: "Nordmann, Kari", gruppe: "Dame", besteaar: "2024" }]);
});

test("legacy +90 kg CSV rows join men's leaderboard while retaining class", () => {
  const rows = parseCsv("Navn,Gruppe,Klasse,Tid\nOla,Pluss,Pluss 90kg,9:00\n");
  assert.equal(rows[0].gruppe, "Mann");
  assert.equal(rows[0].klasse, "Pluss 90kg");
  assert.equal(calculate(rows).topMen[0].navn, "Ola");
});

test("first arrival uses finish clock, while leaderboards use elapsed time", () => {
  const rows = [
    { navn: "Raskest", gruppe: "Mann", tid: "9:00", maalpassering: "2026-09-25T11:00:00" },
    { navn: "Først", gruppe: "Mann", tid: "12:00", maalpassering: "2026-09-25T10:30:00" },
    { navn: "Uten klokke", gruppe: "Mann", tid: "8:00", maalpassering: "" },
  ];
  const result = calculate(rows);
  assert.equal(result.firstFinishers[0].navn, "Først");
  assert.deepEqual(result.topMen.map(row => row.navn), ["Uten klokke", "Raskest", "Først"]);
});

test("stairs include a runner before finishing, and personal records require history", () => {
  const rows = [
    { navn: "I trappene", gruppe: "Dame", tid: "", trappetid: "3:10" },
    { navn: "Tidspers", gruppe: "Dame", tid: "10:00", bestetidligere: "12:00", trappetid: "3:40" },
    { navn: "Prosentpers", gruppe: "Dame", tid: "4:00", bestetidligere: "5:00" },
    { navn: "Nykommer", gruppe: "Dame", tid: "3:00", bestetidligere: "" },
  ];
  const result = calculate(rows);
  assert.equal(result.fastestStairsRunners[0].navn, "I trappene");
  assert.equal(result.biggestByTime[0].runner.navn, "Tidspers");
  assert.equal(result.biggestByTime[0].differenceSeconds, -120);
  assert.equal(result.biggestByPercent[0].runner.navn, "Prosentpers");
  assert.equal(result.biggestByPercent[0].differencePercent, -20);
});

test("top five are separated by gender and sorted by finish time", () => {
  const rows = Array.from({ length: 6 }, (_, index) => ({
    navn: `M${index}`, gruppe: "Mann", tid: `${15 - index}:00`,
  })).concat(Array.from({ length: 6 }, (_, index) => ({
    navn: `K${index}`, gruppe: "Dame", tid: `${16 - index}:00`,
  })));
  const result = calculate(rows);
  assert.deepEqual(result.topMen.map(row => row.navn), ["M5", "M4", "M3", "M2", "M1"]);
  assert.deepEqual(result.topWomen.map(row => row.navn), ["K5", "K4", "K3", "K2", "K1"]);
});

test("hard start compares early and remaining sections with group medians", () => {
  const rows = Array.from({ length: 5 }, (_, index) => ({
    navn: `Jevn ${index}`, gruppe: "Dame", startentid: "2:00", tid: "10:00",
  }));
  rows.push({ navn: "Hard start", gruppe: "Dame", startentid: "1:30", tid: "11:20" });
  let result = calculate(rows);
  assert.equal(result.eligibleHardCount, 6);
  assert.equal(result.hardStarters[0].runner.navn, "Hard start");
  assert.ok(result.hardStarters[0].score > 0.1);

  result = calculate(rows.slice(0, 4));
  assert.equal(result.eligibleHardCount, 0);
  assert.deepEqual(result.hardStarters, []);
});

test("every highlight ranking contains at most five verified runners", () => {
  const rows = Array.from({ length: 7 }, (_, index) => ({
    navn: `Runner ${index}`,
    gruppe: "Mann",
    tid: `${10 + index}:00`,
    maalpassering: `2026-09-25T12:0${index}:00`,
    trappetid: `3:0${index}`,
    bestetidligere: `${12 + index}:00`,
  }));
  const result = calculate(rows);
  assert.equal(result.firstFinishers.length, 5);
  assert.equal(result.fastestStairsRunners.length, 5);
  assert.equal(result.biggestByTime.length, 5);
  assert.equal(result.biggestByPercent.length, 5);
  assert.deepEqual(result.firstFinishers.map(row => row.navn), rows.slice(0, 5).map(row => row.navn));
});

test("largest slowdown ranks only finishers slower than a previous best", () => {
  const rows = [
    { navn: "Slower 3", tid: "13:00", bestetidligere: "10:00" },
    { navn: "Slower 1", tid: "11:00", bestetidligere: "10:00" },
    { navn: "Newcomer", tid: "20:00", bestetidligere: "" },
    { navn: "Improved", tid: "9:00", bestetidligere: "10:00" },
    { navn: "Unfinished", tid: "", bestetidligere: "10:00" },
    { navn: "Slower 2", tid: "12:00", bestetidligere: "10:00" },
  ];
  const result = calculate(rows);
  assert.deepEqual(result.worstByTime.map(item => item.runner.navn), ["Slower 3", "Slower 2", "Slower 1"]);
  assert.deepEqual(result.worstByTime.map(item => item.differenceSeconds), [180, 120, 60]);
});

test("overview renders five-place lists and shows the times behind each best-time difference", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "oversikter.html"), "utf8");
  const script = html.match(/<script>\s*const H = window\.StoltzenHighlights;([\s\S]*?)<\/script>/)?.[0]
    .replace(/^<script>/, "").replace(/<\/script>$/, "");
  assert.ok(script);
  const elements = new Map();
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, {
        textContent: "", innerHTML: "", addEventListener() {},
        classList: { add() {}, toggle() {} },
      });
      return elements.get(id);
    },
    addEventListener() {},
  };
  const render = vm.runInNewContext(`${script}\nrender`, {
    window: { StoltzenHighlights: { parseCsv, calculate }, setInterval() {} },
    document, fetch: () => new Promise(() => {}), parent: {},
  });
  const rows = Array.from({ length: 6 }, (_, index) => ({
    navn: `Runner ${index}`, gruppe: "Mann", tid: `${11 + index}:00`,
    maalpassering: `2026-09-25T12:0${index}:00`, trappetid: `3:0${index}`,
    bestetidligere: "10:00", startentid: "2:00",
  }));
  render(calculate(rows));
  for (const id of ["firstFinish", "fastestStairs", "worstByTime", "topMen"]) {
    assert.equal((elements.get(id).innerHTML.match(/<li>/g) || []).length, 5, id);
  }
  assert.match(elements.get("worstByTime").innerHTML, /10:00 → 16:00/);
  assert.equal(elements.get("participantCount").textContent, 6);
  assert.equal(elements.get("finishedCount").textContent, 6);
});

test("overview warns when the CSV itself is stale despite a fresh browser fetch", async () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "oversikter.html"), "utf8");
  const script = html.match(/<script>\s*const H = window\.StoltzenHighlights;([\s\S]*?)<\/script>/)?.[0]
    .replace(/^<script>/, "").replace(/<\/script>$/, "");
  const elements = new Map();
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, {
        textContent: "", innerHTML: "", addEventListener() {},
        classList: { add() {}, toggle() {} },
      });
      return elements.get(id);
    },
    addEventListener() {},
  };
  vm.runInNewContext(script, {
    window: { StoltzenHighlights: { parseCsv, calculate }, setInterval() {} },
    document, parent: {},
    fetch: async () => ({
      ok: true,
      headers: { get: () => new Date(Date.now() - 10 * 60 * 1000).toUTCString() },
      text: async () => "Navn,Tid,Maalpassering,Trappetid,StartenTid\nKari,11:00,2026-09-25T12:00:00,3:00,2:00\n",
    }),
  });
  await new Promise(resolve => setImmediate(resolve));
  assert.match(elements.get("status").textContent, /ikke oppdatert siden/);
});
