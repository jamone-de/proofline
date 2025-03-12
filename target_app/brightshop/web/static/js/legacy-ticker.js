// Old dashboard widgets from the jQuery days. Not referenced by any template.
function renderLegacyTicker(items) {
  return items.map(function (i) { return "<li>" + i + "</li>"; }).join("");
}
