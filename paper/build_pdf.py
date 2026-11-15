"""Build paper/report.pdf from paper/report.md with the Apart-layout LaTeX template (pandoc + xelatex).

Usage: uv run python paper/build_pdf.py
Splits the title, author lines and abstract out of report.md, passes them to paper/template/apart.latex,
and bolds the "Figure N." labels in captions. Needs pandoc and xelatex (TeX Live).
"""

import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def md_inline(text: str) -> str:
    out = subprocess.run(["pandoc", "-f", "markdown", "-t", "latex"], input=text, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def main() -> None:
    src = (HERE / "report.md").read_text()
    lines = src.splitlines()
    title = lines[0].lstrip("# ").strip()
    authors, affil = lines[2].strip(), lines[3].strip()
    abstract = src.split("## Abstract", 1)[1].split("\n## ", 1)[0].strip()
    body = "## 1. Introduction" + src.split("\n## 1. Introduction", 1)[1]
    body = re.sub(r"!\[(Figure \d+\.)", r"![**\1**", body)
    with tempfile.TemporaryDirectory() as tmp:
        md = Path(tmp) / "body.md"
        md.write_text(body)
        tex = HERE / "report.tex"
        subprocess.run(["pandoc", str(md), "-f", "markdown+autolink_bare_uris", "-t", "latex", "-s", "--shift-heading-level-by=-1",
                        "--template", str(HERE / "template" / "apart.latex"), "--resource-path", f"{HERE}:{HERE.parent}",
                        "-V", f"title={title}", "-V", f"authors={md_inline(authors)}", "-V", f"affil={md_inline(affil)}",
                        "-V", f"abstract={md_inline(abstract)}", "-M", f"title={title}", "-o", str(tex)], check=True)
    for _ in range(2):
        r = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "report.tex"], cwd=HERE,
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-3000:])
            raise SystemExit("xelatex failed")
    log = (HERE / "report.log").read_text(errors="ignore")
    missing = sorted(set(re.findall(r"Missing character: There is no (.) ", log)))
    print("built", HERE / "report.pdf", "| missing glyphs:", missing or "none")
    for ext in ("aux", "log", "out", "tex"):
        (HERE / f"report.{ext}").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
