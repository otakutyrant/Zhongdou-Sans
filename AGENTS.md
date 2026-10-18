# Zhongdou Sans project instructions

## Working environment

- Enter the pinned toolchain with `nix develop`; run repository tasks through
  the root `nurfile`. Use Nushell for scripts and pipelines.
- Check `git status --short` before editing and preserve unrelated user work.
- Do not repeatedly use `nix run nixpkgs#…`. Add recurring tools to `flake.nix`
  with a comment explaining why the project needs them, then update the lock.
- Keep the root task catalog self-contained while the project remains small.
- Use strict Conventional Commits: `type(scope): imperative summary`. Prefer
  `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, and `chore`; mark
  breaking changes with `!` and a `BREAKING CHANGE:` footer.

## Task catalog

Run commands below from the repository root inside `nix develop`.

- `nur check fast`: Nushell, Python, web, flake-evaluation, and formatting
  checks. Use this during normal editing.
- `nur check`: the complete gate, including punctuation shaping, real Chromium
  interaction/layout checks, the Nix package build, and specimen freshness.
- `nur check watch`: rerun the fast gate when maintained files change.
- `nur python check`, `nur web check`, `nur nu check`, and `nur nix check`:
  focused diagnostic groups. Their sibling `format` tasks apply formatting.
- `nur font build`: produce `build/ZhongdouSansVF.ttf` from the upstream font.
- `nur punctuation check`: inspect all encoded punctuation at weights 250, 400,
  and 900 in horizontal and vertical shaping.
- `nur site build`, `nur site check`, and `nur site preview`: build, exercise in
  Chromium, or serve the public homepage.
- `nur specimens check`: render into `build/` and compare against tracked
  specimens without modifying them. `nur specimens render` updates them.
- `nur package build`: build the distributable Nix package without a `result`
  symlink. `nur release build <tag>` runs the full gate before metadata checks.

Pull requests run `nur check`. Before handing off a change, run the narrowest
relevant task during development and the complete gate when practical.

## Panoptor workspace

- `nur panoptor start` opens a two-pane Kitty workspace: the site watcher and
  the fast-check watcher. It uses a project-specific Unix socket with
  socket-only remote control.
- `nur panoptor status` reports whether it is available.
- `nur panoptor inspect site` and `nur panoptor inspect checks` read recent pane
  output; use `--lines` to change the amount.
- `nur panoptor stop` closes only this project's Kitty workspace.

## Source and generated artifacts

- `fonts/variable/ZhudouSansVF.ttf` is upstream input. The derivative font,
  website, QA images, and temporary specimens belong under ignored `build/`.
- `images/demo.png`, `images/Title.light.svg`, and `images/Title.dark.svg` are
  tracked outputs. Regenerate them only with `nur specimens render`, review the
  diff, and never hide stale output by editing generated files directly.
- Keep `demo/index.html` as the compact README specimen and `site/` as the
  separate public homepage.
- Biome owns JavaScript and CSS formatting; authored HTML remains hand-formatted.
  Ruff owns Python formatting. `nixfmt-tree` owns Nix formatting. The project
  intentionally does not use a Nushell formatter.
- Pyright is strict by default. File-local basic-mode suppressions are reserved
  for FontTools' runtime-generated OpenType table interfaces; do not broaden
  them to ordinary project code.

## Font-editing invariants

- Trace the complete shaping path before changing a glyph: Unicode `cmap`, the
  default glyph, language-specific `locl`, vertical `vert`, and GSUB lookup
  order can all select different outlines. A code point alone does not identify
  what a renderer displays.
- Keep glyph geometry in the font. CSS may select language, writing mode, and
  line-breaking behavior, but must not use transforms, offsets, or spacing to
  hide faulty outlines or metrics.
- Treat ink bounds, advance width, side bearings, vertical origin, and vertical
  advance as separate quantities. Centering an outline does not imply changing
  its full-width advance.
- When moving a base glyph, inspect every composite that references it. A
  horizontal translation is rotated into another axis by rotated vertical
  composites. Update dependent geometry and both metric directions deliberately.
- Apply changes to every variable-font master and inspect variation deltas.
  Transformations must be idempotent and reject unexpected upstream bounds
  instead of silently stacking another translation.
- Check paired punctuation together: opening and closing, horizontal and
  vertical, every supported weight, and relevant language systems.
- Keep the deliberately small OpenType surface. Do not restore unrelated
  inherited features or removed characters while repairing `locl` or `vert`.
- Do not alter license declarations unless the user explicitly requests it.

## Font and renderer verification

- Verify the built font, not only source data or build-script intent. Rebuild
  before drawing conclusions about a renderer.
- Use FontTools for bounds, `hmtx`/`vmtx`, components, and GSUB; use `hb-shape`
  for selected glyphs and advances; use `hb-view` for focused specimens.
- Render the real Chromium demo/site after metric or substitution changes and
  inspect the output. A single cropped screenshot demonstrates a bug but is not
  sufficient verification of a fix.
- Test the default and extreme weights. Put vertical punctuation in a phrase
  with adjacent Han characters so displacement inside the em is visible.
- Do not infer one renderer from another. Chromium, GTK Text Editor, and Kitty
  have different fallback and shaping behavior. A computed CSS family does not
  prove which physical face rendered a character.
- Emoji fonts may contain ordinary digits for keycap sequences, so Fontconfig
  fallback order can affect plain digits even when the requested family seems
  unrelated to emoji.
- Custom line breaking is valid for the intended rigid inscription layout, but
  it must not compensate for faulty glyph geometry.
