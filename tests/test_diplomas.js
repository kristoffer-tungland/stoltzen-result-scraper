const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { finishedParticipants, filterAndSort, nameSize } = require("../diplomas.js");

test("diplomas are created only for runners with a valid finish time", () => {
  const csv = fs.readFileSync(path.join(__dirname, "fixtures", "diplomas.csv"), "utf8");
  const people = finishedParticipants(csv);
  assert.deepEqual(people.map(person => [person.name, person.time]), [
    ["Kari Eksempel", "11:58"],
    ["Kristoffer Langt Etternavn Med Mange Deler", "12:34"],
  ]);
  assert.equal(nameSize(people[1].name), "21pt");
});

test("print layout fixes every certificate to one A4 page", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "diplomer.html"), "utf8");
  const viewer = fs.readFileSync(path.join(__dirname, "..", "results_viewer.html"), "utf8");
  assert.match(html, /@page\{size:A4 portrait;margin:0\}/);
  assert.match(html, /\.certificate,\.certificate\.active\{display:block!important;width:210mm!important;height:297mm!important/);
  assert.match(html, /break-after:page;page-break-after:always/);
  assert.match(html, /class="recipient"/);
  assert.match(html, /class="finish-time"/);
  assert.match(html, /id="heroUpload"[^>]*type="file"/);
  assert.match(html, /assets\/diplom-sti\.jpg/);
  assert.match(html, /assets\/fonts\/UnifrakturCook-Bold\.ttf/);
  assert.match(html, /assets\/fonts\/GreatVibes-Regular\.ttf/);
  assert.match(viewer, /href="diplomer\.html"/);
});

test("diplomas filter by gender and order by numeric finish time", () => {
  const csv = "Navn,Gruppe,Klasse,Tid\n" +
    "Kari,Dame,Kvinner,10:00\n" +
    "Anne,Dame,Kvinner,9:59\n" +
    "Berit,Dame,Kvinner,12:00\n" +
    "Ola,Mann,Menn,8:00\n" +
    "Per,Pluss,Pluss 90kg,11:00\n" +
    "Uten tid,Dame,Kvinner,\n";
  const people = finishedParticipants(csv);
  assert.deepEqual(filterAndSort(people, { gender: "Dame", sort: "time-asc" }).map(person => person.name),
    ["Anne", "Kari", "Berit"]);
  assert.deepEqual(filterAndSort(people, { gender: "Dame", sort: "time-desc" }).map(person => person.name),
    ["Berit", "Kari", "Anne"]);
  assert.deepEqual(filterAndSort(people, { gender: "Mann", sort: "time-asc" }).map(person => person.name),
    ["Ola", "Per"]);
  assert.deepEqual(filterAndSort(people, { query: "kari" }).map(person => person.name), ["Kari"]);
  assert.equal(people.length, 5);
});

test("diploma page exposes gender and time order controls", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "diplomer.html"), "utf8");
  assert.match(html, /id="filterGender"/);
  assert.match(html, /id="sortTime"/);
  assert.match(html, /value="time-asc"/);
  assert.match(html, /value="time-desc"/);
});
