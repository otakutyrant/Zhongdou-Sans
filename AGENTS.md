# Zhongdou Sans project instructions

## Project foundation

Zhongdou Sans is a CJK punctuation fallback variable font, its build and QA
tooling, generated specimens, Nix package, and framework-free static website. It
is intentionally not based on an application framework. Maintained code uses
Python 3.14, Nushell, Nix, JavaScript, CSS, and HTML.

Work from the repository root. Allow the tracked `.envrc` once by running
`direnv allow`; nix-direnv then loads the pinned `nix develop` environment. Run
non-interactive commands through `direnv exec` when the shell hook has not
already loaded it. Use Nushell for scripts and pipelines, and preserve
unrelated worktree changes. Use `nur --help` and focused `nur <task> --help`
output to discover the current validation, formatting, build, server, release,
and Panoptor interfaces. Use the Nur-owned workflow when one exists instead of
duplicating its commands.

## Source and generated artifacts

- `fonts/variable/ZhudouSansVF.ttf` is the upstream input to the automated
  build. Treat files under `source/` as font-editor and historical reference
  artifacts, not as automated build inputs unless the task catalog says
  otherwise.
- Derived fonts, website output, QA images, and temporary specimens belong
  under ignored `build/`.
- `images/demo.png`, `images/Title.light.svg`, and `images/Title.dark.svg` are
  tracked generated outputs. Regenerate them only through their owning Nur
  task, review the diff, and never hide stale output by editing them directly.
- `demo/` owns the compact README specimen; `site/` owns the separate public
  homepage. Keep those responsibilities distinct.
- Biome owns JavaScript and CSS formatting; authored HTML remains
  hand-formatted. Ruff owns Python formatting, and `nixfmt-tree` owns Nix
  formatting. The project intentionally does not use a Nushell formatter.
- Pyright is strict by default. File-local basic-mode suppressions are reserved
  for FontTools' runtime-generated OpenType table interfaces; do not broaden
  them to ordinary project code.
- Do not alter license declarations or reserved-font-name behavior unless the
  user explicitly requests it. Check `LICENSE` before changing distribution,
  naming, embedding, or derivative-font behavior.

## Font-editing invariants

- Trace the complete shaping path before changing a glyph: Unicode `cmap`,
  default glyphs, language-specific `locl`, vertical `vert`, variation
  selectors, and GSUB lookup order may select different outlines. A code point
  alone does not identify what renders.
- Keep glyph geometry in the font. CSS may select language, writing mode, and
  line breaking, but must not use transforms, offsets, or spacing to disguise
  faulty outlines or metrics.
- Treat ink bounds, advance width, side bearings, vertical origin, and vertical
  advance as separate quantities. Centering an outline does not imply changing
  its full-width advance.
- When moving a base glyph, inspect every referencing composite. Rotated
  vertical composites may turn horizontal movement into movement on another
  axis; update dependent geometry and both metric directions deliberately.
- Apply edits to every variable-font master and inspect variation deltas.
  Transformations must be idempotent and reject unexpected upstream bounds
  rather than stacking silently.
- Check paired punctuation together in horizontal and vertical shaping, at
  default and extreme weights, and for every relevant language system.
- Preserve the deliberately small OpenType surface. Do not restore unrelated
  inherited features or removed characters while repairing `locl` or `vert`.

## Verification and rendering

Use Nur's focused tasks during development and its complete deterministic gate
before handoff when practical. Verify the built font, not just source data or
script intent, and rebuild before diagnosing renderer behavior.

- Use FontTools for bounds, metrics, components, and GSUB; HarfBuzz shaping for
  selected glyphs and advances; and focused renders for visual assessment.
- Exercise the real Chromium demo or site after substitution, metric, or
  layout changes. A cropped screenshot may demonstrate a defect but cannot by
  itself verify the fix.
- Put vertical punctuation beside Han characters so displacement within the em
  is visible, and test default and extreme weights.
- Do not infer one renderer from another. Chromium, GTK/Pango, and Kitty have
  different shaping and fallback behavior, and a computed CSS family does not
  prove which physical face rendered a character.
- Emoji fonts may include ordinary digits for keycap sequences, so fallback
  order can affect plain digits.
- Custom line breaking is valid for the intended inscription layout, but must
  not compensate for faulty glyph geometry.

## Panoptor and collaboration

The project supports one isolated Panoptor per active worktree. Each human or
agent may use the Nur-discovered Panoptor interface in its own worktree to
supervise automatic validations and the long-running site server. Before
launching a covered validation or service, check for that worktree's session.
When it is running, use the Nur controls to inspect role state, readiness, and
bounded output and to freshly rerun or restart affected roles; do not launch
duplicate watchers or services. A running role or previously successful result
is not evidence for later edits. Use standalone one-shot tasks when Panoptor is
absent, lacks a suitable role, or the complete deterministic workflow requires
them. Panoptor is persistent and headless: attaching or detaching its TUI does
not start or stop its roles. Never control another worktree's session or claim
its live state as validation of this checkout, and do not call Process Compose
directly.

Use Git with strict Conventional Commits: `type(scope): imperative summary`.
Keep each commit independently reviewable and revertible; split a large change
into small, coherent, decoupled commits when useful. Do not commit unless the
user requests it.
