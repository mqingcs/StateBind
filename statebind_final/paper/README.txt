StateBind MMM 2027 camera-ready LaTeX source

Corresponding author: Qing Mu. Equal contribution,
author order, affiliations and existing email addresses are preserved.

Main file: main.tex
Engine: XeLaTeX + BibTeX (not pdfLaTeX for the validated build).
The supplied main.bbl is the final bibliography; all five included figures are vector PDF masters with embedded fonts.

Build with a complete current TeX Live installation including newtx, kastrup/binhex,
babel-english, microtype, booktabs, multirow, graphicx, xcolor, url and hyperref:
  xelatex -no-pdf -interaction=nonstopmode -halt-on-error main.tex
  bibtex main
  xelatex -no-pdf -interaction=nonstopmode -halt-on-error main.tex
  xelatex -no-pdf -interaction=nonstopmode -halt-on-error main.tex

For the validated metadata timestamp, set SOURCE_DATE_EPOCH=1793473200 and
FORCE_SOURCE_DATE=1 before compiling. After the last XeLaTeX pass, run:
  xdvipdfmx -V 5 -o main.pdf main.xdv

Validated runtime: XeTeX 0.999996 / xdvipdfmx 20240305, LaTeX 2024-11-01 patch 2,
newtxtext 1.744, newtxmath 1.754. The font setup is exactly the current Springer
sample: newtxtext and newtxmath[varvw], with no font scaling or margin/spacing
reductions. Different TeX distributions can produce different PDF metadata or
line breaking; inspect a new build before uploading it.

Template: official Springer LNCS 2.25, dated 2026-09-03. Class and bibliography
style are supplied unmodified. Source:
https://link.springer.com/series/558/information-for-authors-and-editors
Event requirements checked 2026-10-31; corrective source review 2026-11-01:
https://mmm2027.net/author_camera_ready.html
Conference-specific empty page style overrides the sample's running headers.

The current publisher class and amsmath (loaded by newtxmath) produce one known
compatibility warning: 'Unable to redefine math accent \vec'. The manuscript
uses \vect/\boldsymbol, not \vec. Final output has no undefined references,
missing glyphs, font substitutions or overfull boxes. This harmless class-package
warning has not been hidden or patched by changing the publisher class.

DescriptionTexts.txt contains the five figure alternative descriptions emitted
by the official class from the inline \Description commands.

Source provenance: mqingcs/StateBind, main commit
9f16b4036d0abfb0d0c052fba8f7ad4cf41c1cf7, statebind_final/paper.
Every original source file was matched to the current GitHub blob hash before
editing. No experiments, results, claims or reviewer-driven content were changed.
Editable SVG artwork and the main-figure generator are delivered separately;
they are not needed to compile this submission source package.

Visual-harmony revision, 2026-11-01:
- Tables 1--3 all use unscaled \small (9 TeX pt; measured 8.9664 PDF pt).
- Table 2 no longer uses whole-table resizebox enlargement.
- Table 3 uses the same 9 pt cells rather than scriptsize.
- Tables 2 and 3 use 4 pt column padding; no cell words, numbers, captions,
  table structure or scientific prose were changed. Table 1 was already 9 pt.
- The new Fig. 4 uses the same serif font family as Figs. 1, 2, 3 and 5;
  its scientific content, evidence, diagram geometry and canvas are unchanged.
The paragraph, heading, author, caption and reference font setup is unchanged
from the corrected LNCS/newtx edition; Qing Mu remains corresponding author.

Final source sign-off, 2026-11-01: added the missing Table 1 cross-reference
(Table~\ref{tab:dataset}) to the existing development/held-out split sentence.
No scientific claim, value or other manuscript wording changed in this step.
