(function (root) {
  "use strict";

  const highlights = typeof module !== "undefined" && module.exports
    ? require("./highlights.js") : root.StoltzenHighlights;

  function finishedParticipants(csv) {
    return highlights.parseCsv(csv).map((row, index) => ({
      id: index,
      name: String(row.navn || "").trim(),
      time: String(row.tid || "").trim(),
      gender: row.gruppe || "",
    })).filter(row => row.name && highlights.seconds(row.time) !== null)
      .sort((a, b) => a.name.localeCompare(b.name, "nb"));
  }

  function filterAndSort(entries, { gender = "", sort = "name", query = "" } = {}) {
    const search = query.trim().toLocaleLowerCase("nb");
    const visible = entries.filter(entry => (!gender || entry.gender === gender)
      && (!search || entry.name.toLocaleLowerCase("nb").includes(search)));
    const byName = (a, b) => a.name.localeCompare(b.name, "nb") || a.id - b.id;
    if (sort === "time-asc" || sort === "time-desc") {
      const direction = sort === "time-asc" ? 1 : -1;
      visible.sort((a, b) => direction * (highlights.seconds(a.time) - highlights.seconds(b.time)) || byName(a, b));
    } else visible.sort(byName);
    return visible;
  }

  function nameSize(name) {
    if (name.length > 36) return "21pt";
    if (name.length > 27) return "25pt";
    return "32pt";
  }

  const api = { finishedParticipants, filterAndSort, nameSize };
  root.StoltzenDiplomas = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
