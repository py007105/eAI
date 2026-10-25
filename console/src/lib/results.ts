import CURRENT_NUMBERS from "../../../docs/CURRENT_NUMBERS.md?raw";

function sliceBetween(
  source: string,
  startMarker: string,
  endMarker: string,
): string {
  const start = source.indexOf(startMarker);
  if (start < 0) return "";
  const end = source.indexOf(endMarker, start + startMarker.length);
  return source.slice(start, end < 0 ? undefined : end).trim();
}

export function recordedResultsExcerpt(source = CURRENT_NUMBERS): string {
  const sections = [
    sliceBetween(
      source,
      "## 1. Recovery with approval",
      "**Live human approval:",
    ),
    sliceBetween(
      source,
      "## 2. Autopilot alone under the current policy",
      "## 3.",
    ),
    sliceBetween(
      source,
      "## 5. Prediction (forecast), current system",
      "## 6.",
    ),
  ].filter(Boolean);
  const heading = source.indexOf(
    "- **Public-dataset classifier (dataset A, offline, one run):",
  );
  const modelStart = source.indexOf("- **Model:**", heading);
  const modelEnd = source.indexOf(
    "**The demo** uses the live classifier",
    modelStart,
  );
  const dataset =
    modelStart >= 0 && modelEnd > modelStart
      ? `## Dataset A classifier (offline, one run; separate from the live classifier)\n\n${source.slice(modelStart, modelEnd).trim()}`
      : "";
  const sourcePath = source.indexOf(
    "docs/results/dataset_a_classifier.md",
    modelEnd,
  );
  const sourceStart = source.lastIndexOf("\n", sourcePath) + 1;
  const sourceEnd = source.indexOf("\n", sourcePath);
  if (dataset)
    sections.push(
      `${dataset}\n${source.slice(sourceStart, sourceEnd < 0 ? undefined : sourceEnd).trim()}`,
    );
  return sections.filter((section) => !/\bdemo\b/i.test(section)).join("\n\n");
}
