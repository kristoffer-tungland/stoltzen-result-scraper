const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

test("scene and overview switch without navigating away from fullscreen document", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "results_viewer.html"), "utf8");
  const source = html.match(/function setViewMode\(mode\)\{[\s\S]*?\n\}\nasync function toggleFullscreen/)?.[0];
  assert.ok(source, "view mode handler is present");
  assert.match(html, /id="overviewMode"[^>]*type="button"/);
  assert.match(html, /id="overviewFrame"/);

  const active = new Set();
  const buttons = Object.fromEntries(["lookup", "scene", "overview"].map(mode => [mode + "Mode", {
    classList: { toggle(name, enabled) { if (enabled) active.add(mode); else active.delete(mode); } },
    setAttribute() {},
  }]));
  let frameSource = "";
  const frame = {
    getAttribute(name) { return name === "src" ? frameSource || null : null; },
    removeAttribute(name) { if (name === "src") frameSource = ""; },
    set src(value) { frameSource = value; },
  };
  const fullscreenElement = {};
  let navigations = 0;
  const context = {
    URL, viewMode: "scene", location: {
      href: "http://localhost/results_viewer.html#scene",
      replace() { navigations += 1; },
    },
    history: { replaceState() {} },
    localStorage: { setItem() {} },
    document: {
      fullscreenElement,
      body: { classList: { toggle() {} } },
      getElementById(id) { return id === "overviewFrame" ? frame : buttons[id]; },
    },
    updateDisplay() {}, restartSceneRotation() {},
  };
  const setViewMode = vm.runInNewContext(source.replace(/\nasync function toggleFullscreen$/, "") + "; setViewMode", context);

  setViewMode("overview");
  assert.equal(frameSource, "oversikter.html?embedded=1&v=3");
  assert.deepEqual([...active], ["overview"]);
  setViewMode("scene");
  assert.equal(frameSource, "");
  assert.deepEqual([...active], ["scene"]);
  assert.equal(context.document.fullscreenElement, fullscreenElement);
  assert.equal(navigations, 0);

  context.location.href = "http://localhost/results_viewer.html?year=2025&event=78991#scene";
  setViewMode("overview");
  assert.equal(frameSource, "oversikter.html?embedded=1&v=3&year=2025&event=78991");
});

test("direct overview URL enters the shared viewer", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "oversikter.html"), "utf8");
  assert.match(html, /target\.search=location\.search;target\.hash="overview"/);
  assert.match(html, /html\.embedded \.header\{display:none\}/);
});
