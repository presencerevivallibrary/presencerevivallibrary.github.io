# Presence Revival Library

Presence Revival Library is a static website for browsing, reading, and downloading Pastor Dave Roberson sermon transcripts.

The generated site lives in `website/`. The source content lives in `source/`.

## Source Layout

Each language follows the same structure:

```text
source/
  en/
    md/
    pdf/
    md-section/
    pdf-section/
    series.json
```

Folder meanings:

- `md/`: transcripts without section headers
- `pdf/`: PDFs without section headers
- `md-section/`: transcripts with section headers
- `pdf-section/`: PDFs with section headers

## Workflow

1. Add or update files in the `source/` folders.
2. Run `python scripts/build_site.py`.
3. Review the generated `website/` output.
4. Commit and push the updated files to `master`.

## GitHub Pages

This repository includes a GitHub Actions workflow that deploys the contents of `website/` to GitHub Pages whenever you push to `master`.

After the initial one-time setup in GitHub, future updates are:

1. Update files in `source/`.
2. Run `python scripts/build_site.py`.
3. Check the generated `website/`.
4. Commit and push to `master`.

GitHub will then publish the site automatically.

## Local Python

If `python` is not available on your PATH, try one of these:

- `py scripts/build_site.py`
- `where.exe python`
- `where.exe conda`

If you find a Conda installation, you can run the build with:

```powershell
<PATH-TO-CONDA-EXE> run -p <PATH-TO-CONDA-ENV> python scripts/build_site.py
```

For example, if `where.exe conda` shows your Conda executable location, use that path in place of `<PATH-TO-CONDA-EXE>`, and use the environment or install root in place of `<PATH-TO-CONDA-ENV>`.

To verify that interpreter:

```powershell
<PATH-TO-CONDA-EXE> run -p <PATH-TO-CONDA-ENV> python --version
```

## Build Notes

- The build script is intended to rebuild `website/` from source content.
- `website/` is disposable output and should not be edited by hand.
- English is implemented now, and the build script is already structured for future `--lang` support.
- The public site title is `Presence Revival Library`.

## Current Content Notes

- Transcript folders are intentionally not consecutive.
- Series `13. Radical Grace Series` and `14. 1st John Teaching Series` are not currently included in this archive.
