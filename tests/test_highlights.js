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
  assert.equal(result.firstFinisher.navn, "Først");
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
  assert.equal(result.fastestStairs.navn, "I trappene");
  assert.equal(result.biggestByTime.runner.navn, "Tidspers");
  assert.equal(result.biggestByTime.improvementSeconds, 120);
  assert.equal(result.biggestByPercent.runner.navn, "Prosentpers");
  assert.equal(result.biggestByPercent.improvementPercent, 20);
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
