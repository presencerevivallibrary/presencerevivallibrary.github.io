
const STYLE_STORAGE_KEY = "presence-revival-library-style";

function getSavedStyle() {
  const saved = window.localStorage.getItem(STYLE_STORAGE_KEY);
  return saved === "section" ? "section" : "plain";
}

function setSavedStyle(style) {
  window.localStorage.setItem(STYLE_STORAGE_KEY, style);
}

function bindStyleToggle(onChange) {
  const buttons = [...document.querySelectorAll("[data-style-option]")];
  if (!buttons.length) {
    return;
  }

  const apply = (style) => {
    buttons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.styleOption === style);
    });
    if (typeof onChange === "function") {
      onChange(style);
    }
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const style = button.dataset.styleOption === "section" ? "section" : "plain";
      setSavedStyle(style);
      apply(style);
    });
  });

  apply(getSavedStyle());
}

function resolveLinks(teaching, style) {
  const isSection = style === "section";
  const readPath = isSection && teaching.available.htmlSection ? teaching.paths.htmlSection : teaching.paths.html;
  const pdfPath = isSection && teaching.available.pdfSection ? teaching.paths.pdfSection : teaching.paths.pdf;
  return { readPath, pdfPath };
}

function displayTeachingLabel(teachingId, title) {
  const trimmedId = teachingId.trim();
  const trimmedTitle = title.trim();
  if (trimmedId.endsWith(trimmedTitle)) {
    const prefix = trimmedId.slice(0, trimmedId.length - trimmedTitle.length).replace(/[\s\-_]+$/, "");
    if (prefix) {
      return `${prefix} ${trimmedTitle}`.trim();
    }
  }
  const match = trimmedId.match(/^([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)(?:\s*[-_]\s*|\s+)(.+)$/);
  if (match && match[2].trim().toLowerCase() === trimmedTitle.toLowerCase()) {
    return `${match[1]} ${trimmedTitle}`.trim();
  }
  return trimmedId === trimmedTitle ? trimmedTitle : `${trimmedId} ${trimmedTitle}`.trim();
}

function renderTeachingIndex(seriesList, style) {
  const container = document.getElementById("teaching-index");
  if (!container) {
    return;
  }

  container.innerHTML = seriesList.map((series) => `
    <details class="teaching-series" id="series-${series.seriesId}">
      <summary class="teaching-series-summary">
        <span class="teaching-series-title">${escapeHtml(series.seriesTitle)}</span>
        <span class="teaching-series-count">${series.teachings.length} teaching${series.teachings.length === 1 ? "" : "s"}</span>
      </summary>
      <div class="teaching-list">
        ${series.teachings.map((teaching) => renderTeachingItem(teaching, style)).join("")}
      </div>
    </details>
  `).join("");
}

function renderTeachingItem(teaching, style) {
  const { readPath, pdfPath } = resolveLinks(teaching, style);
  const combinedTitle = displayTeachingLabel(teaching.teachingId, teaching.title);
  return `
    <article class="teaching-item">
      <div class="teaching-title">${escapeHtml(combinedTitle)}</div>
      <div class="teaching-links">
        <a class="text-link" href="./${encodePath(readPath)}">Read</a>
        <a class="text-link" href="./${encodePath(pdfPath)}">PDF</a>
      </div>
    </article>
  `;
}

function encodePath(path) {
  return path.split("/").map(encodeURIComponent).join("/").replace(/%2F/g, "/");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function filterSeries(payload, query) {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return payload.series;
  }

  return payload.series
    .map((series) => {
      const seriesMatches = [series.seriesId, series.seriesTitle].some((value) => value.toLowerCase().includes(needle));
      const teachings = series.teachings.filter((teaching) =>
        [teaching.title, teaching.teachingId, teaching.seriesTitle, teaching.seriesId]
          .some((value) => value.toLowerCase().includes(needle))
      );

      if (seriesMatches && teachings.length === 0) {
        return series;
      }

      return { ...series, teachings };
    })
    .filter((series) => series.teachings.length > 0);
}

async function initLibraryPage() {
  const container = document.getElementById("teaching-index");
  if (!container) {
    return;
  }

  const inlineData = document.getElementById("library-data");
  let payload = null;
  if (inlineData && inlineData.textContent) {
    payload = JSON.parse(inlineData.textContent);
  } else {
    const response = await fetch("./data/teachings.json");
    payload = await response.json();
  }
  const render = () => {
    const style = getSavedStyle();
    renderTeachingIndex(payload.series, style);
  };

  bindStyleToggle(render);
  render();
}

function initTranscriptPage() {
  const transcriptShell = document.querySelector(".transcript-shell");
  const pdfLink = document.querySelector(".transcript-pdf-link");
  if (!transcriptShell || !pdfLink) {
    return;
  }

  bindStyleToggle((style) => {
    pdfLink.setAttribute("href", style === "section" ? pdfLink.dataset.sectionPdf : pdfLink.dataset.plainPdf);
    const currentStyle = transcriptShell.dataset.pageStyle === "section" ? "section" : "plain";
    if (style !== currentStyle) {
      window.location.href = style === "section" ? transcriptShell.dataset.sectionRead : transcriptShell.dataset.plainRead;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  void initLibraryPage();
  initTranscriptPage();
});
