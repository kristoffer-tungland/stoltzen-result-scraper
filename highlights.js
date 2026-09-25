(function (root) {
  "use strict";

  function parseCsv(input) {
    const text = String(input || "").replace(/^\uFEFF/, "");
    const records = [];
    let record = [], cell = "", quoted = false;
    for (let index = 0; index < text.length; index += 1) {
      const char = text[index];
      if (char === '"') {
        if (quoted && text[index + 1] === '"') { cell += '"'; index += 1; }
        else quoted = !quoted;
      } else if (char === "," && !quoted) {
        record.push(cell); cell = "";
      } else if ((char === "\n" || char === "\r") && !quoted) {
        if (char === "\r" && text[index + 1] === "\n") index += 1;
        record.push(cell); cell = "";
        if (record.some(value => value.trim())) records.push(record);
        record = [];
      } else {
        cell += char;
      }
    }
    record.push(cell);
    if (record.some(value => value.trim())) records.push(record);
    if (!records.length) return [];
    const headers = records.shift().map(header => header.toLowerCase().replaceAll("å", "aa"));
    return records.map(values => Object.fromEntries(headers.map((header, index) => [header, values[index] || ""])));
  }

  function seconds(value) {
    if (!/^\d{1,3}:\d{2}(?::\d{2})?$/.test(String(value || ""))) return null;
    const parts = value.split(":").map(Number);
    if (parts.some((part, index) => index > 0 && part >= 60)) return null;
    const total = parts.length === 2 ? parts[0] * 60 + parts[1] : parts[0] * 3600 + parts[1] * 60 + parts[2];
    return total > 0 ? total : null;
  }

  function median(values) {
    const ordered = [...values].sort((a, b) => a - b);
    if (!ordered.length) return null;
    const middle = Math.floor(ordered.length / 2);
    return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
  }

  function calculate(rows) {
    const finished = rows.filter(row => seconds(row.tid) !== null);
    const fastest = (items, field) => [...items].sort((a, b) => seconds(a[field]) - seconds(b[field]) || a.navn.localeCompare(b.navn, "nb"));
    const firstFinisher = finished.filter(row => Number.isFinite(Date.parse(row.maalpassering)))
      .sort((a, b) => Date.parse(a.maalpassering) - Date.parse(b.maalpassering))[0] || null;
    const stairRunners = rows.filter(row => seconds(row.trappetid) !== null);
    const fastestStairs = fastest(stairRunners, "trappetid")[0] || null;
    const improvements = finished.map(row => {
      const previous = seconds(row.bestetidligere || row.bestetid);
      const current = seconds(row.tid);
      if (previous === null || current >= previous) return null;
      return { runner: row, improvementSeconds: previous - current,
        improvementPercent: (previous - current) / previous * 100 };
    }).filter(Boolean);
    const biggestByTime = [...improvements].sort((a, b) => b.improvementSeconds - a.improvementSeconds)[0] || null;
    const biggestByPercent = [...improvements].sort((a, b) => b.improvementPercent - a.improvementPercent)[0] || null;

    const pacingGroups = new Map();
    for (const row of finished) {
      const first = seconds(row.startentid), total = seconds(row.tid);
      if (first === null || first >= total) continue;
      if (!pacingGroups.has(row.gruppe)) pacingGroups.set(row.gruppe, []);
      pacingGroups.get(row.gruppe).push({ runner: row, first, rest: total - first });
    }
    const hardStarters = [];
    let eligibleHardCount = 0;
    for (const group of pacingGroups.values()) {
      if (group.length < 5) continue;
      eligibleHardCount += group.length;
      const firstMedian = median(group.map(item => item.first));
      const restMedian = median(group.map(item => item.rest));
      for (const item of group) {
        const score = (item.rest / restMedian) / (item.first / firstMedian) - 1;
        if (score >= 0.10) hardStarters.push({ runner: item.runner, score });
      }
    }
    hardStarters.sort((a, b) => b.score - a.score);

    return {
      participantCount: rows.length,
      finishedCount: finished.length,
      firstFinisher, fastestStairs, biggestByTime, biggestByPercent,
      topMen: fastest(finished.filter(row => row.gruppe === "Mann"), "tid").slice(0, 5),
      topWomen: fastest(finished.filter(row => row.gruppe === "Dame"), "tid").slice(0, 5),
      hardStarters: hardStarters.slice(0, 5), eligibleHardCount,
    };
  }

  const api = { parseCsv, seconds, median, calculate };
  root.StoltzenHighlights = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
