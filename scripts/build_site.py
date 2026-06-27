from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from urllib.parse import urlparse

SITE_TITLE = "Presence Revival Library"
SITE_SUBTITLE = "A transcript library of teaching series from Dave Roberson Ministries."
SITE_ORIGIN = "https://presencerevivallibrary.github.io"
GOOGLE_SITE_VERIFICATION = "FDOeGfz85FjGx8LN5331PPQDQ7skHXJPFLHPnRgZWDQ"
DEFAULT_INDEXNOW_KEY = "50283fcd-8c76-4cfd-9bd7-9a8b4002f647"
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", DEFAULT_INDEXNOW_KEY).strip()
DEFAULT_LANG = "en"
STYLE_PLAIN = "plain"
STYLE_SECTION = "section"
SOURCE_VARIANTS = {
    "md": ("md", ".md"),
    "pdf": ("pdf", ".pdf"),
    "md_section": ("md-section", ".md"),
    "pdf_section": ("pdf-section", ".pdf"),
}


@dataclass
class Teaching:
    series_id: str
    series_title: str
    teaching_id: str
    source_stem: str
    title: str
    sort_key: str
    paths: dict[str, Path | None]
    urls: dict[str, str]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Presence Revival Library static site.")
    parser.add_argument("--lang", default=DEFAULT_LANG, help="Language code to build, default: en")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    source_root = root / "source" / args.lang
    output_root = root / "website"
    lang_root = output_root / args.lang

    if not source_root.exists():
        print(f"Error: source language folder not found: {source_root}", file=sys.stderr)
        return 1

    series_map = load_series_map(source_root)
    teachings, warnings = collect_teachings(source_root, series_map)

    rebuild_output(output_root)
    write_root_redirects(output_root, args.lang)
    write_assets(output_root / "assets")
    write_language_site(source_root, lang_root, args.lang, series_map, teachings)
    write_sitemap(output_root, args.lang, teachings)
    write_robots(output_root)
    write_indexnow_files(output_root, args.lang, teachings)

    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    print(f"Built {SITE_TITLE} for '{args.lang}' with {len(teachings)} teachings.")
    return 0


def load_series_map(source_root: Path) -> dict[str, str]:
    series_file = source_root / "series.json"
    if series_file.exists():
        raw = json.loads(series_file.read_text(encoding="utf-8"))
        return {str(key): str(value) for key, value in raw.items()}

    derived: dict[str, str] = {}
    for folder in sorted((source_root / "md").iterdir()):
        if not folder.is_dir():
            continue
        match = re.match(r"^(\d{2})\s+(.+)$", folder.name)
        if match:
            derived[match.group(1)] = match.group(2)
    return derived


def collect_teachings(source_root: Path, series_map: dict[str, str]) -> tuple[list[Teaching], list[str]]:
    collected: dict[tuple[str, str], dict[str, Path | None]] = {}
    warnings: list[str] = []

    for key, (folder_name, suffix) in SOURCE_VARIANTS.items():
        variant_root = source_root / folder_name
        if not variant_root.exists():
            warnings.append(f"Missing source folder: {variant_root}")
            continue

        for path in variant_root.rglob(f"*{suffix}"):
            if not path.is_file():
                continue
            series_id, series_title = extract_series_from_path(path)
            collected.setdefault(
                (series_id, path.stem),
                {
                    "series_title": series_title,
                    "md": None,
                    "pdf": None,
                    "md_section": None,
                    "pdf_section": None,
                },
            )[key] = path

    teachings: list[Teaching] = []
    for (series_id, stem), item in sorted(collected.items(), key=lambda value: build_sort_key(value[0][0], value[0][1])):
        series_title = series_map.get(series_id) or item["series_title"]
        title = extract_title(item["md"]) or extract_title(item["md_section"]) or prettify_title_from_stem(stem)
        teaching = Teaching(
            series_id=series_id,
            series_title=series_title,
            teaching_id=stem,
            source_stem=stem,
            title=title,
            sort_key=build_sort_key(series_id, stem),
            paths={key: item.get(key) for key in ("md", "pdf", "md_section", "pdf_section")},
            urls=build_urls(stem),
        )
        for variant_key, variant_path in teaching.paths.items():
            if variant_path is None:
                warnings.append(f"Missing {variant_key} for series {series_id}: {stem}")
        teachings.append(teaching)

    return teachings, warnings


def extract_series_from_path(path: Path) -> tuple[str, str]:
    folder = path.parent.name
    match = re.match(r"^(\d{2})\s+(.+)$", folder)
    if match:
        return match.group(1), match.group(2)
    return "00", folder


def extract_title(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped.startswith("# "):
                    return stripped[2:].strip()
    except UnicodeDecodeError:
        return None
    return None


def prettify_title_from_stem(stem: str) -> str:
    title = stem
    title = re.sub(r"^[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*[-_\s]+", "", title)
    title = title.replace("_", " ").replace("-", " ").strip()
    return title or stem


def build_sort_key(series_id: str, stem: str) -> str:
    parts = re.split(r"(\d+)", stem)
    normalized = "".join(part.zfill(8) if part.isdigit() else part.lower() for part in parts)
    return f"{series_id.zfill(4)}::{normalized}"


def build_urls(stem: str) -> dict[str, str]:
    slug = slugify(stem)
    return {
        "html": f"teachings/html/{slug}.html",
        "html_section": f"teachings/html-section/{slug}.html",
        "pdf": f"teachings/pdf/{stem}.pdf",
        "pdf_section": f"teachings/pdf-section/{stem}.pdf",
    }


def slugify(value: str) -> str:
    value = value.lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[â€™']", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "teaching"


def rebuild_output(output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)


def write_root_redirects(output_root: Path, lang: str) -> None:
    (output_root / "index.html").write_text(
        redirect_document(f"./{lang}/index.html"),
        encoding="utf-8",
    )
    (output_root / "about.html").write_text(
        redirect_document(f"./{lang}/about.html"),
        encoding="utf-8",
    )


def redirect_document(destination: str) -> str:
    safe_destination = html.escape(destination, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url={safe_destination}">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="google-site-verification" content="{GOOGLE_SITE_VERIFICATION}">
  <title>{SITE_TITLE}</title>
  <link rel="canonical" href="{safe_destination}">
</head>
<body>
  <p>Redirecting to <a href="{safe_destination}">{safe_destination}</a>...</p>
</body>
</html>
"""


def write_assets(assets_root: Path) -> None:
    css_root = assets_root / "css"
    js_root = assets_root / "js"
    css_root.mkdir(parents=True, exist_ok=True)
    js_root.mkdir(parents=True, exist_ok=True)
    (css_root / "site.css").write_text(SITE_CSS, encoding="utf-8")
    (js_root / "site.js").write_text(SITE_JS, encoding="utf-8")


def write_language_site(
    source_root: Path,
    lang_root: Path,
    lang: str,
    series_map: dict[str, str],
    teachings: list[Teaching],
) -> None:
    (lang_root / "data").mkdir(parents=True, exist_ok=True)
    (lang_root / "files").mkdir(parents=True, exist_ok=True)
    (lang_root / "teachings" / "html").mkdir(parents=True, exist_ok=True)
    (lang_root / "teachings" / "html-section").mkdir(parents=True, exist_ok=True)
    (lang_root / "teachings" / "pdf").mkdir(parents=True, exist_ok=True)
    (lang_root / "teachings" / "pdf-section").mkdir(parents=True, exist_ok=True)

    copy_variant_files(lang_root, teachings)
    write_teaching_pages(lang_root, lang, teachings)
    write_data_file(lang_root, lang, teachings)
    write_index_page(lang_root, lang, teachings)
    write_about_page(source_root, lang_root, lang)
    write_complete_archive(source_root, lang_root)


def copy_variant_files(lang_root: Path, teachings: list[Teaching]) -> None:
    for teaching in teachings:
        for key, source_path in teaching.paths.items():
            if source_path is None or not key.startswith("pdf"):
                continue
            target = lang_root / teaching.urls["pdf" if key == "pdf" else "pdf_section"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target)


def write_teaching_pages(lang_root: Path, lang: str, teachings: list[Teaching]) -> None:
    global_navigation = build_global_navigation(teachings)
    for teaching in teachings:
        for key, target_name in (("md", "html"), ("md_section", "html_section")):
            source_path = teaching.paths[key]
            if source_path is None:
                continue
            html_body = strip_leading_title(
                render_markdown(source_path.read_text(encoding="utf-8")),
                teaching.title,
            )
            other_target = teaching.urls["html_section" if target_name == "html" else "html"]
            file_path = lang_root / teaching.urls[target_name]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            asset_prefix = "../../../assets"
            nav_prefix = "../../"
            file_path.write_text(
                page_shell(
                    lang=lang,
                    title=f"{teaching.title} | {SITE_TITLE}",
                    description=f"{teaching.title} from {teaching.series_title}.",
                    asset_prefix=asset_prefix,
                    nav_prefix=nav_prefix,
                    page_content=teaching_article(
                        teaching=teaching,
                        article_html=html_body,
                        current_style=STYLE_SECTION if target_name == "html_section" else STYLE_PLAIN,
                        navigation=global_navigation.get((teaching.series_id, teaching.teaching_id), {}),
                    ),
                    body_class="transcript-page",
                    extra_markup="",
                    header_links=transcript_header_links(nav_prefix=nav_prefix),
                    header_controls=transcript_header_controls(),
                ),
                encoding="utf-8",
            )


def write_data_file(lang_root: Path, lang: str, teachings: list[Teaching]) -> None:
    payload = build_library_payload(lang, teachings)
    (lang_root / "data" / "teachings.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_library_payload(lang: str, teachings: list[Teaching]) -> dict[str, object]:
    series_entries: list[dict[str, object]] = []
    grouped: dict[str, list[Teaching]] = {}
    titles: dict[str, str] = {}
    for teaching in teachings:
        grouped.setdefault(teaching.series_id, []).append(teaching)
        titles[teaching.series_id] = teaching.series_title

    for series_id in sorted(grouped.keys(), key=lambda item: (int(item) if item.isdigit() else item)):
        ordered_teachings = sorted(grouped[series_id], key=lambda item: item.sort_key)
        series_entries.append(
            {
                "seriesId": series_id,
                "seriesTitle": titles[series_id],
                "count": len(ordered_teachings),
                "teachings": [serialize_teaching(teaching) for teaching in ordered_teachings],
            }
        )

    payload = {
        "siteTitle": SITE_TITLE,
        "language": lang,
        "defaultStyle": STYLE_PLAIN,
        "series": series_entries,
        "teachings": [serialize_teaching(teaching) for teaching in sorted(teachings, key=lambda item: item.sort_key)],
    }
    return payload


def display_teaching_label(teaching_id: str, title: str) -> str:
    trimmed_id = teaching_id.strip()
    trimmed_title = title.strip()
    if trimmed_id.endswith(trimmed_title):
        prefix = trimmed_id[: -len(trimmed_title)].rstrip(" -_")
        if prefix:
            return f"{prefix} {trimmed_title}".strip()
    match = re.match(r"^([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)(?:\s*[-_]\s*|\s+)(.+)$", trimmed_id)
    if match and match.group(2).strip().lower() == trimmed_title.lower():
        return f"{match.group(1)} {trimmed_title}".strip()
    return f"{trimmed_id} {trimmed_title}".strip() if trimmed_id != trimmed_title else trimmed_title


def build_global_navigation(teachings: list[Teaching]) -> dict[tuple[str, str], dict[str, Teaching | None]]:
    ordered = sorted(teachings, key=lambda item: item.sort_key)
    navigation: dict[tuple[str, str], dict[str, Teaching | None]] = {}
    for index, teaching in enumerate(ordered):
        navigation[(teaching.series_id, teaching.teaching_id)] = {
            "previous": ordered[index - 1] if index > 0 else None,
            "next": ordered[index + 1] if index < len(ordered) - 1 else None,
        }
    return navigation


def serialize_teaching(teaching: Teaching) -> dict[str, object]:
    return {
        "seriesId": teaching.series_id,
        "seriesTitle": teaching.series_title,
        "teachingId": teaching.teaching_id,
        "title": teaching.title,
        "paths": {
            "html": teaching.urls["html"],
            "htmlSection": teaching.urls["html_section"],
            "pdf": teaching.urls["pdf"],
            "pdfSection": teaching.urls["pdf_section"],
        },
        "available": {
            "html": teaching.paths["md"] is not None,
            "htmlSection": teaching.paths["md_section"] is not None,
            "pdf": teaching.paths["pdf"] is not None,
            "pdfSection": teaching.paths["pdf_section"] is not None,
        },
    }


def write_index_page(lang_root: Path, lang: str, teachings: list[Teaching]) -> None:
    payload = build_library_payload(lang, teachings)
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    inline_data = (
        '<script id="library-data" type="application/json">'
        + payload_json
        + "</script>"
    )
    page = page_shell(
        lang=lang,
        title=SITE_TITLE,
        description="Browse and read the Presence Revival Library transcript archive.",
        asset_prefix="../assets",
        nav_prefix="./",
        page_content=index_content(),
        body_class="index-page",
        extra_markup=inline_data,
        header_links=index_header_links(),
        header_controls=index_header_controls(),
    )
    (lang_root / "index.html").write_text(page, encoding="utf-8")


def write_about_page(source_root: Path, lang_root: Path, lang: str) -> None:
    about_html = render_markdown((source_root / "about.md").read_text(encoding="utf-8"))
    transcript_html = render_markdown((source_root / "about-transcript.md").read_text(encoding="utf-8"))
    page = page_shell(
        lang=lang,
        title=f"About | {SITE_TITLE}",
        description="About the Presence Revival Library.",
        asset_prefix="../assets",
        nav_prefix="./",
        page_content=f"""
<section class="page-section prose about-panel">
  {about_html}
</section>

<section class="page-section prose about-panel">
  {transcript_html}
</section>
""",
        body_class="about-page",
        extra_markup="",
        header_links=about_header_links(),
        header_controls="",
        show_footer=True,
    )
    (lang_root / "about.html").write_text(page, encoding="utf-8")


def write_complete_archive(source_root: Path, lang_root: Path) -> None:
    archive_path = lang_root / "files" / "complete-archive.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for folder_name, _suffix in (value for value in SOURCE_VARIANTS.values()):
            folder = source_root / folder_name
            if not folder.exists():
                continue
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=str(path.relative_to(source_root)).replace("\\", "/"))


def write_sitemap(output_root: Path, lang: str, teachings: list[Teaching]) -> None:
    urls = build_public_urls(lang, teachings)

    url_nodes = "\n".join(
        f"  <url><loc>{html.escape(url, quote=False)}</loc></url>"
        for url in urls
    )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{url_nodes}\n"
        "</urlset>\n"
    )
    (output_root / "sitemap.xml").write_text(sitemap, encoding="utf-8")


def write_robots(output_root: Path) -> None:
    robots = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {SITE_ORIGIN}/sitemap.xml\n"
    )
    (output_root / "robots.txt").write_text(robots, encoding="utf-8")


def write_indexnow_files(output_root: Path, lang: str, teachings: list[Teaching]) -> None:
    if not INDEXNOW_KEY:
        manifest_path = output_root / "indexnow.json"
        if manifest_path.exists():
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            key = str(payload.get("key", "")).strip()
            if key:
                key_file_path = output_root / f"{key}.txt"
                if key_file_path.exists():
                    key_file_path.unlink()
            manifest_path.unlink()
        return

    key_file_name = f"{INDEXNOW_KEY}.txt"
    key_file_path = output_root / key_file_name
    key_file_path.write_text(INDEXNOW_KEY, encoding="utf-8")

    payload = {
        "host": indexnow_host(),
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_ORIGIN}/{key_file_name}",
        "urlList": build_public_urls(lang, teachings),
    }
    (output_root / "indexnow.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def indexnow_host() -> str:
    parsed = urlparse(SITE_ORIGIN)
    return parsed.netloc


def build_public_urls(lang: str, teachings: list[Teaching]) -> list[str]:
    urls = [
        f"{SITE_ORIGIN}/{lang}/index.html",
        f"{SITE_ORIGIN}/{lang}/about.html",
    ]
    urls.extend(
        f"{SITE_ORIGIN}/{lang}/{teaching.urls['html']}"
        for teaching in sorted(teachings, key=lambda item: item.sort_key)
        if teaching.paths["md"] is not None
    )
    return urls


def page_shell(
    *,
    lang: str,
    title: str,
    description: str,
    asset_prefix: str,
    nav_prefix: str,
    page_content: str,
    body_class: str,
    extra_markup: str = "",
    header_links: str = "",
    header_controls: str = "",
    show_footer: bool = True,
) -> str:
    title_html = html.escape(title)
    description_html = html.escape(description, quote=True)
    footer_html = f"""
    <footer class="site-footer">
      <p>{SITE_TITLE} is a static reading library built for simple long-term maintenance.</p>
    </footer>""" if show_footer else ""
    return f"""<!doctype html>
<html lang="{html.escape(lang)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{description_html}">
  <meta name="google-site-verification" content="{GOOGLE_SITE_VERIFICATION}">
  <title>{title_html}</title>
  <link rel="stylesheet" href="{asset_prefix}/css/site.css">
</head>
<body class="{body_class}">
  <div class="page-shell">
    <header class="site-header">
      <div class="site-branding">
        <a class="site-brand" href="{nav_prefix}index.html">{SITE_TITLE}</a>
        <p class="site-subtitle">{SITE_SUBTITLE}</p>
        <nav class="site-nav" aria-label="Primary">{header_links}</nav>
      </div>
      <div class="site-controls">{header_controls}</div>
    </header>
    <main>
      {page_content}
    </main>
    {footer_html}
  </div>
  {extra_markup}
  <script src="{asset_prefix}/js/site.js" defer></script>
</body>
</html>
"""


def index_content() -> str:
    return f"""
<section class="page-section">
  <div class="section-heading section-heading-tools">
    <h2>Teaching Series</h2>
    <div class="section-tools">
      {style_toggle_markup(compact=True, label="View:", plain_label="Original", section_label="AI Headings")}
      <a class="section-tool-link section-tool-link-right" href="./files/complete-archive.zip">Download Full Archive</a>
    </div>
  </div>
  <div id="teaching-index" class="teaching-index"></div>
</section>

<noscript>
  <section class="page-section card-stack">
    <article class="card">
      <h2>JavaScript is required for the teaching index</h2>
      <p>This site uses a small script to render the teaching index and remember your preferred view.</p>
    </article>
  </section>
</noscript>
"""


def style_toggle_markup(
    *,
    compact: bool = False,
    label: str = "Transcript style",
    plain_label: str = "No Section Headers",
    section_label: str = "With Section Headers",
) -> str:
    if compact:
        return f"""
<section class="style-panel style-panel-compact" aria-labelledby="style-toggle-heading">
  <p id="style-toggle-heading" class="style-panel-label">{html.escape(label)}</p>
  <div class="style-toggle style-toggle-inline" role="group" aria-label="{html.escape(label)}">
    <button type="button" class="style-option" data-style-option="plain">{html.escape(plain_label)}</button>
    <button type="button" class="style-option" data-style-option="section">{html.escape(section_label)}</button>
  </div>
</section>
"""
    return f"""
<section class="style-panel" aria-labelledby="style-toggle-heading">
  <p id="style-toggle-heading" class="style-panel-label">{html.escape(label)}</p>
  <div class="style-toggle" role="group" aria-label="{html.escape(label)}">
    <button type="button" class="style-option" data-style-option="plain">{html.escape(plain_label)}</button>
    <button type="button" class="style-option" data-style-option="section">{html.escape(section_label)}</button>
  </div>
  <p class="style-help">Your preference is remembered on this device and controls the Read and PDF links site-wide.</p>
</section>
"""


def teaching_article(
    *,
    teaching: Teaching,
    article_html: str,
    current_style: str,
    navigation: dict[str, Teaching | None],
) -> str:
    style_value = "section" if current_style == STYLE_SECTION else "plain"
    plain_html_name = quote(Path(teaching.urls["html"]).name)
    section_html_name = quote(Path(teaching.urls["html_section"]).name)
    combined_title = display_teaching_label(teaching.teaching_id, teaching.title)
    previous_teaching = navigation.get("previous")
    next_teaching = navigation.get("next")
    previous_link = build_transcript_nav_link(previous_teaching, "Previous")
    next_link = build_transcript_nav_link(next_teaching, "Next")
    return f"""
<article class="transcript-shell" data-page-style="{style_value}" data-plain-read="../html/{plain_html_name}" data-section-read="../html-section/{section_html_name}">
  <section class="transcript-intro">
    <h1>{html.escape(teaching.series_title)}</h1>
    <div class="section-tools transcript-tools">
      {style_toggle_markup(compact=True, label="View:", plain_label="Original", section_label="AI Headings")}
      <a class="section-tool-link section-tool-link-right transcript-pdf-link" href="../pdf/{quote(Path(teaching.urls['pdf']).name)}" data-plain-pdf="../pdf/{quote(Path(teaching.urls['pdf']).name)}" data-section-pdf="../pdf-section/{quote(Path(teaching.urls['pdf_section']).name)}">Download PDF</a>
    </div>
    <nav class="transcript-pagination" aria-label="Teaching navigation">
      {previous_link}
      {next_link}
    </nav>
  </section>
  <section class="page-section prose transcript-content">
    <h2 class="transcript-title">{html.escape(combined_title)}</h2>
    {article_html}
  </section>
  <section class="transcript-footer-nav">
    <nav class="transcript-pagination" aria-label="Teaching navigation bottom">
      {previous_link}
      {next_link}
    </nav>
  </section>
</article>
"""


def build_transcript_nav_link(teaching: Teaching | None, label: str) -> str:
    if teaching is None:
        return f'<span class="transcript-nav-link is-disabled">{html.escape(label)}</span>'
    target = f'../html/{quote(Path(teaching.urls["html"]).name)}'
    title = display_teaching_label(teaching.teaching_id, teaching.title)
    return (
        f'<a class="transcript-nav-link" href="{html.escape(target, quote=True)}">'
        f'{html.escape(label)}: {html.escape(title)}</a>'
    )


def index_header_links() -> str:
    return """
<a class="site-nav-link" href="./index.html">Library</a>
<a class="site-nav-link" href="./about.html">About</a>
"""


def index_header_controls() -> str:
    return ""


def about_header_links() -> str:
    return """
<a class="site-nav-link" href="./index.html">Library</a>
<a class="site-nav-link" href="./about.html">About</a>
"""


def transcript_header_links(*, nav_prefix: str) -> str:
    return f"""
<a class="site-nav-link" href="{nav_prefix}index.html">Library</a>
<a class="site-nav-link" href="{nav_prefix}about.html">About</a>
"""


def transcript_header_controls() -> str:
    return ""


def strip_leading_title(rendered_html: str, title: str) -> str:
    del title
    return re.sub(r"^\s*<h1>.*?</h1>\s*", "", rendered_html, count=1, flags=re.DOTALL)


def render_markdown(markdown_text: str) -> str:
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            blocks.append(f"<h{level}>{render_inline(heading_match.group(2).strip())}</h{level}>")
            index += 1
            continue

        if stripped.startswith(">"):
            quote_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(re.sub(r"^\s*>\s?", "", lines[index]))
                index += 1
            quote_content = render_markdown("\n".join(quote_lines))
            blocks.append(f"<blockquote>{quote_content}</blockquote>")
            continue

        if re.match(r"^\d+\.\s+", stripped):
            list_items: list[str] = []
            while index < len(lines) and re.match(r"^\d+\.\s+", lines[index].strip()):
                item_text = re.sub(r"^\d+\.\s+", "", lines[index].strip())
                list_items.append(f"<li>{render_inline(item_text)}</li>")
                index += 1
            blocks.append(f"<ol>{''.join(list_items)}</ol>")
            continue

        if re.match(r"^[-*]\s+", stripped):
            list_items = []
            while index < len(lines) and re.match(r"^[-*]\s+", lines[index].strip()):
                item_text = re.sub(r"^[-*]\s+", "", lines[index].strip())
                list_items.append(f"<li>{render_inline(item_text)}</li>")
                index += 1
            blocks.append(f"<ul>{''.join(list_items)}</ul>")
            continue

        paragraph_lines: list[str] = []
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate:
                break
            if re.match(r"^(#{1,6})\s+", candidate):
                break
            if candidate.startswith(">") or re.match(r"^\d+\.\s+", candidate) or re.match(r"^[-*]\s+", candidate):
                break
            paragraph_lines.append(candidate)
            index += 1
        blocks.append(f"<p>{render_inline(' '.join(paragraph_lines))}</p>")

    return "\n".join(blocks)


def render_inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: f'<a href="{html.escape(match.group(2), quote=True)}">{match.group(1)}</a>',
        escaped,
    )
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    return escaped


SITE_CSS = """
:root {
  --bg: #f5efe3;
  --bg-accent: #efe3c9;
  --surface: rgba(255, 252, 245, 0.92);
  --surface-strong: #fffaf0;
  --line: rgba(96, 68, 31, 0.18);
  --text: #2e241a;
  --muted: #6e5c4a;
  --accent: #8a4b20;
  --accent-deep: #5e2c11;
  --accent-soft: #d7b88a;
  --shadow: 0 18px 50px rgba(82, 50, 20, 0.12);
  --radius: 22px;
  --radius-sm: 14px;
}

* {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  color: var(--text);
  background:
    radial-gradient(circle at top left, rgba(215, 184, 138, 0.35), transparent 28rem),
    linear-gradient(180deg, #f9f4ea 0%, var(--bg) 58%, #efe7d6 100%);
  font-family: "Aptos", "Segoe UI", system-ui, sans-serif;
  line-height: 1.65;
}

a {
  color: inherit;
}

.page-shell {
  width: min(1180px, calc(100% - 2rem));
  margin: 0 auto;
  padding: 0.6rem 0 2rem;
}

.site-header,
.site-footer {
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  align-items: flex-start;
  padding: 0.85rem 0;
}

.site-header {
  border-bottom: 1px solid var(--line);
  margin-bottom: 1.5rem;
}

.site-footer {
  border-top: 1px solid var(--line);
  margin-top: 2.5rem;
  color: var(--muted);
  font-size: 0.95rem;
}

.site-brand {
  font-family: "Palatino Linotype", "Book Antiqua", Georgia, serif;
  font-size: clamp(1.2rem, 2vw, 1.55rem);
  font-weight: 700;
  text-decoration: none;
  letter-spacing: 0.02em;
}

.site-branding {
  display: grid;
  gap: 0.45rem;
  max-width: 52rem;
}

.site-subtitle {
  margin: 0;
  color: var(--muted);
  font-size: 0.95rem;
}

.site-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  align-items: center;
  justify-content: flex-start;
}

.site-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: flex-start;
  justify-content: flex-end;
}

.site-nav a,
.site-nav-link {
  text-decoration: none;
  color: var(--accent-deep);
  font-size: 0.95rem;
  padding: 0;
}

.site-nav a:hover,
.site-nav a:focus-visible,
.text-link:hover,
.text-link:focus-visible {
  color: var(--accent-deep);
}

.search-panel,
.page-section,
.transcript-intro {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}

.page-section h1,
.transcript-intro h1 {
  font-family: "Palatino Linotype", "Book Antiqua", Georgia, serif;
  font-size: clamp(1.5rem, 3vw, 2.25rem);
  line-height: 1.05;
  margin: 0 0 0.6rem;
}

.transcript-meta,
.results-summary,
.section-heading p {
  color: var(--muted);
}

.button,
.style-option {
  appearance: none;
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 0.8rem 1.2rem;
  font: inherit;
  text-decoration: none;
  cursor: pointer;
  transition: transform 160ms ease, background-color 160ms ease, border-color 160ms ease;
}

.button {
  background: var(--accent-deep);
  color: #fff9f1;
}

.button.secondary {
  background: transparent;
  color: var(--accent-deep);
  border-color: var(--accent-soft);
}

.button:hover,
.button:focus-visible,
.style-option:hover,
.style-option:focus-visible {
  transform: translateY(-1px);
}

.style-panel {
  background: transparent;
  border: 0;
  border-radius: 0;
  padding: 0;
}

.style-panel-label {
  margin: 0;
  font-weight: 600;
  font-size: 0.92rem;
}

.style-panel-compact {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.style-toggle {
  display: grid;
  gap: 0.75rem;
}

.style-toggle-inline {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.2rem;
}

.style-toggle-inline .style-option + .style-option::before {
  content: "|";
  color: var(--muted);
  margin-right: 0.45rem;
}

.style-option {
  border-color: transparent;
  background: transparent;
  color: var(--muted);
  text-align: left;
  padding: 0;
  font-size: 0.92rem;
}

.style-option.is-active {
  background: transparent;
  color: var(--accent-deep);
}

.search-panel,
.page-section,
.transcript-intro {
  margin-top: 1rem;
  padding: 1rem 1.1rem;
}

.search-input {
  width: 100%;
  margin-top: 0.65rem;
  padding: 0.95rem 1rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--line);
  font: inherit;
  background: var(--surface-strong);
}

.section-heading {
  margin-bottom: 0.85rem;
}

.section-heading-tools,
.section-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 0.9rem 1.25rem;
  align-items: center;
}

.section-heading-tools {
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: 0.9rem;
}

.section-tools {
  flex: 1 1 100%;
  width: 100%;
  margin-left: 0;
  justify-content: space-between;
}

.section-tool-link {
  color: var(--accent-deep);
  text-decoration: none;
  white-space: nowrap;
  font-size: 0.92rem;
}

.section-tool-link-right {
  margin-left: auto;
  text-align: right;
}

.transcript-tools {
  margin-top: 0.4rem;
}

.section-heading h2,
.prose h1,
.prose h2,
.prose h3,
.prose h4 {
  font-family: "Palatino Linotype", "Book Antiqua", Georgia, serif;
}

.section-heading h2 {
  margin: 0;
  font-size: clamp(1.5rem, 3vw, 2rem);
}

.card,
.teaching-series {
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: rgba(255, 250, 240, 0.72);
}

.teaching-index {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
}

.teaching-series {
  padding: 0.9rem 1rem;
}

.teaching-series-summary {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: baseline;
  cursor: pointer;
  list-style: none;
  font-weight: 700;
}

.teaching-series-summary::-webkit-details-marker {
  display: none;
}

.teaching-series-title {
  font-size: 1rem;
}

.teaching-series-count {
  color: var(--muted);
  font-size: 0.92rem;
  font-weight: 600;
  white-space: nowrap;
}

.teaching-list {
  display: grid;
  gap: 0.8rem;
  margin-top: 0.8rem;
}

.teaching-item {
  display: grid;
  gap: 0.75rem;
  align-items: start;
  grid-template-columns: minmax(0, 1fr) auto;
  padding: 0.65rem 0;
  border-top: 1px solid rgba(96, 68, 31, 0.12);
}

.teaching-item:first-child {
  border-top: 0;
  padding-top: 0.2rem;
}

.teaching-title {
  font-weight: 400;
}

.teaching-links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.text-link {
  text-decoration: underline;
  text-underline-offset: 0.15em;
}

.transcript-pagination {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem 1rem;
  margin-top: 0.9rem;
}

.transcript-pagination > :last-child {
  margin-left: auto;
  text-align: right;
}

.transcript-nav-link {
  color: var(--accent-deep);
  text-decoration: none;
  background: rgba(255, 250, 240, 0.8);
  border: 1px solid rgba(96, 68, 31, 0.16);
  border-radius: 999px;
  padding: 0.45rem 0.8rem;
  font-size: 0.92rem;
}

.transcript-nav-link.is-disabled {
  color: #8f8677;
  background: rgba(214, 208, 198, 0.6);
  border-color: rgba(143, 134, 119, 0.35);
}

.prose {
  font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
  font-size: 1.06rem;
}

.transcript-title {
  margin-bottom: 1.1rem;
}

.transcript-content h2:not(.transcript-title) {
  font-size: 1.2rem;
  margin-top: 1.5rem;
  margin-bottom: 0.6rem;
}

.transcript-content h3 {
  font-size: 1.05rem;
  margin-top: 1.3rem;
  margin-bottom: 0.5rem;
}

.transcript-content h4 {
  font-size: 0.98rem;
  margin-top: 1.1rem;
  margin-bottom: 0.45rem;
}

.about-page main {
  display: grid;
  gap: 1rem;
}

.about-panel {
  max-width: 76rem;
  width: 100%;
  margin: 0 auto;
}

.prose > :first-child {
  margin-top: 0;
}

.prose p,
.prose ul,
.prose ol,
.prose blockquote {
  margin: 1rem 0;
}

.prose blockquote {
  margin-left: 0;
  padding-left: 1rem;
  border-left: 3px solid var(--accent-soft);
  color: var(--muted);
}

.prose code {
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 0.95em;
}

.is-hidden {
  display: none !important;
}

@media (max-width: 860px) {
  .site-header,
  .site-footer,
  .teaching-item {
    grid-template-columns: 1fr;
    display: grid;
  }

  .teaching-index {
    grid-template-columns: 1fr;
  }

  .site-nav {
    gap: 0.85rem 1rem;
    justify-content: flex-start;
  }

  .site-controls {
    justify-content: flex-start;
  }

  .section-heading-tools,
  .section-tools,
  .transcript-pagination {
    justify-content: flex-start;
  }

  .section-tools {
    width: 100%;
    margin-left: 0;
  }

  .section-tool-link-right,
  .transcript-pagination > :last-child {
    margin-left: auto;
    text-align: right;
  }
}

@media (prefers-reduced-motion: reduce) {
  html {
    scroll-behavior: auto;
  }

  .button,
  .style-option {
    transition: none;
  }
}
"""


SITE_JS = """
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
    const prefix = trimmedId.slice(0, trimmedId.length - trimmedTitle.length).replace(/[\\s\\-_]+$/, "");
    if (prefix) {
      return `${prefix} ${trimmedTitle}`.trim();
    }
  }
  const match = trimmedId.match(/^([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)(?:\\s*[-_]\\s*|\\s+)(.+)$/);
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
"""


if __name__ == "__main__":
    raise SystemExit(main())
