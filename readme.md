Here's a consolidated version with all agreed improvements incorporated.

# Note
Note the transcript folder is not consecutive, i.e. missing folders
13. Radical Grace Series
14. 1st John Teaching Series
These are by Gary Carpenter, there is no plan to include them now. May or may not fill it in later. 

# Dave Roberson Transcript Archive

Build a static GitHub Pages website for a Dave Roberson sermon transcript archive.

The user is not a web developer. Do not assume knowledge of HTML, CSS, JavaScript, JSON, routing, build systems, or website architecture.

Before implementation, propose the design first. If a better design exists, suggest it.

---

# Main Goals

The website should be:

* Simple
* Fast
* Mobile-friendly
* Easy to maintain
* Easy to expand later

The landing page should immediately show the teaching index.

Users should be able to:

* Browse series
* Browse teachings
* Search/filter by title or series
* Read transcripts online
* Open/download PDFs
* Download the complete archive ZIP

Do not host MP3 files.

Do not link to individual MP3 files.

---

# Source Folder Structure

Organize source files by language first.

Current implementation only requires English, but the structure should support future languages without redesign.

```text
project/
├── source/
│   └── en/
│       ├── md/
│       ├── pdf/
│       ├── md-section/
│       ├── pdf-section/
│       └── series.json
│
├── scripts/
└── website/
```

Future languages should follow the same structure:

```text
project/
├── source/
│   ├── en/
│   │   ├── md/
│   │   ├── pdf/
│   │   ├── md-section/
│   │   ├── pdf-section/
│   │   └── series.json
│   │
│   └── zh/
│       ├── md/
│       ├── pdf/
│       ├── md-section/
│       ├── pdf-section/
│       └── series.json
│
├── scripts/
└── website/
```

Folder meanings:

```text
md/            = transcripts without section headers
pdf/           = PDFs without section headers
md-section/    = transcripts with section headers
pdf-section/   = PDFs with section headers
```

Example:

```text
source/en/md/
    1091-01-The New Nature - The Light of Men.md

source/en/pdf/
    1091-01-The New Nature - The Light of Men.pdf

source/en/md-section/
    1091-01-The New Nature - The Light of Men.md

source/en/pdf-section/
    1091-01-The New Nature - The Light of Men.pdf
```

Use identical base filenames across all four folders whenever possible.

---

# Series Metadata

Each language may have its own series titles.

Store series metadata in:

```text
source/en/series.json
source/zh/series.json
```

Example:

```json
{
  "1091": "The New Nature",
  "1094": "A Type of Atoning Blood of Christ"
}
```

---

# Transcript Versions

Each teaching already exists in four versions:

1. Markdown without section headers
2. Markdown with section headers
3. PDF without section headers
4. PDF with section headers

Use these existing files.

Do not generate alternate transcript views dynamically.

---

# Recommended Website Output Structure

Generate the website into:

```text
website/
├── index.html
├── about.html
├── assets/
│   ├── css/
│   └── js/
│
└── en/
    ├── index.html
    ├── about.html
    │
    ├── data/
    │   └── teachings.json
    │
    ├── teachings/
    │   ├── html/
    │   ├── html-section/
    │   ├── pdf/
    │   └── pdf-section/
    │
    └── files/
        └── complete-archive.zip
```

The root:

```text
/
```

should automatically redirect to:

```text
/en/
```

Only English needs to be implemented now.

---

# Build Script

Create:

```text
scripts/build_site.py
```

The user should only need to run:

```bash
python scripts/build_site.py
```

The build script should:

* Read all source folders
* Read series metadata
* Convert Markdown files into HTML pages
* Copy PDFs into the correct output folders
* Generate clean HTML filenames
* Generate metadata
* Generate ZIP archives
* Create required folders automatically
* Validate source files
* Warn if matching files are missing
* Rebuild the entire website folder from scratch

The website folder should be considered disposable.

The build script should be able to delete and regenerate it completely.

Future support should allow:

```bash
python scripts/build_site.py --lang en
python scripts/build_site.py --lang zh
```

without changing folder structure.

---

# File Mapping

Map source folders to website output folders:

```text
source/en/md/
    → website/en/teachings/html/

source/en/pdf/
    → website/en/teachings/pdf/

source/en/md-section/
    → website/en/teachings/html-section/

source/en/pdf-section/
    → website/en/teachings/pdf-section/
```

---

# Filename Rules

Use the same base filename across all four source folders.

Example:

```text
1091-01-The New Nature - The Light of Men.md
1091-01-The New Nature - The Light of Men.pdf
```

Generate clean HTML filenames automatically.

Example:

```text
1091-01-the-new-nature-the-light-of-men.html
```

---

# Metadata

Generate:

```text
website/en/data/teachings.json
```

automatically.

Each teaching entry should include:

* Series ID
* Series title
* Teaching ID
* Teaching title
* HTML path without section headers
* HTML path with section headers
* PDF path without section headers
* PDF path with section headers

Do not manually maintain this file.

---

# Transcript Style Toggle

Provide a site-wide transcript style toggle.

Default:

```text
No Section Headers
```

Alternative:

```text
With Section Headers
```

The selected style should be remembered using localStorage.

When "No Section Headers" is selected:

* Read → HTML without section headers
* PDF → PDF without section headers

When "With Section Headers" is selected:

* Read → HTML with section headers
* PDF → PDF with section headers

Do not show four links per teaching.

Only show:

* Read
* PDF

The destination changes based on the selected transcript style.

---

# Search / Filter

Implement a simple client-side search/filter.

Search only:

* Teaching title
* Series title
* Teaching ID
* Series ID

Do not implement full-text transcript search.

Do not index transcript contents.

No backend search.

No database.

---

# Landing Page

The landing page should be the main teaching index.

Include:

* Site title
* Short description
* Transcript style toggle
* Search/filter box
* Series list
* Complete teaching index
* Link to download the complete archive ZIP

Each teaching should display:

* Read
* PDF

The link destination depends on the selected transcript style.

---

# About Page

Include:

* Purpose of the archive
* Link to Dave Roberson's original website
* Link to original sermon series pages when available
* Link to the complete archive ZIP

Do not host MP3 files.

Do not link to individual MP3 files.

---

# Complete ZIP Archive

Generate:

```text
website/en/files/complete-archive.zip
```

The ZIP archive should contain all versions:

```text
md/
pdf/
md-section/
pdf-section/
```

This allows users to download the complete archive in one file.

---

# Language Support

Design for future multilingual support.

Example:

```text
/en/
/zh/
```

The future language switch should change:

* Navigation
* Labels
* Metadata
* Transcript links

Only English should be implemented now.

---

# JavaScript Requirements

Keep JavaScript minimal.

Use it only for:

* Teaching index rendering
* Search/filter
* Transcript style toggle
* Remembering toggle preference with localStorage

---

# Design Requirements

Use:

* Static HTML
* CSS
* Vanilla JavaScript

Do not use:

* Backend services
* Databases
* User accounts
* Comments
* Ads
* Heavy frameworks

Keep dependencies minimal.

---

# README

Create a simple README.md explaining the workflow:

```text
1. Add new files into the source folders.
2. Run python scripts/build_site.py.
3. Review the generated website.
4. Deploy website/ to GitHub Pages.
```

---

# Before Coding

Before implementation, first propose:

1. Site architecture
2. Folder structure
3. Metadata format
4. Build workflow
5. Search/filter implementation
6. Transcript toggle implementation
7. Language support strategy
8. Long-term maintenance workflow

Then implement the approved design.
