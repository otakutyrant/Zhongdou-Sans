# Zhongdou Sans project instructions

## Development environment

- Use the repository's Nix flake for project tools. Use Nushell for shell scripts and pipelines.
- Use `nurfile` as the command catalogue. The main verification commands are
  `nur demo build`, `nur demo render`, `nur title render`, and `nur site build`.
- Do not repeatedly invoke a project dependency with `nix run nixpkgs#…`. If a
  diagnostic or build tool becomes part of the normal workflow, add it to
  `flake.nix` with a comment explaining why the project needs it.
- Check `git status --short` before editing. Preserve unrelated user changes.

## Font-editing invariants

- Trace the complete shaping path before changing a glyph: Unicode `cmap`, the
  default glyph, language-specific `locl`, vertical `vert`, and relevant GSUB
  lookup order can all select different outlines. A code point alone does not
  identify what the renderer displays.
- Keep glyph geometry in the font. CSS may select language, writing mode, and
  line-breaking behavior, but must not use transforms, offsets, or spacing to
  hide faulty outlines or metrics.
- Treat ink bounds, advance width, side bearings, vertical origin, and vertical
  advance as separate quantities. Centering an outline does not imply changing
  its full-width advance.
- When moving a base glyph, inspect every composite that references it. A
  horizontal translation is rotated into another axis by rotated vertical
  composites. Update dependent glyph geometry and horizontal/vertical metrics
  deliberately; do not assume recomputing bearings repairs the outline.
- Apply changes to every variable-font master and inspect variation deltas.
  Make transformations idempotent and reject unexpected upstream bounds rather
  than silently stacking another translation.
- Check paired punctuation together: opening and closing forms, horizontal and
  vertical forms, every supported weight, and the relevant language systems.
- Keep the project's deliberately small OpenType surface. Do not restore
  unrelated inherited features or removed characters while repairing `locl` or
  `vert` behavior.
- Do not alter license declarations unless the user explicitly requests it.

## Verification

- Verify the built font, not only `source/Zhongdou Sans.glyphs` or build-script
  intent. Rebuild before drawing conclusions about a renderer.
- Use FontTools to inspect glyph bounds, `hmtx`/`vmtx`, components, and GSUB.
  Use `hb-shape` to confirm selected glyphs and advances, and `hb-view` to make
  focused horizontal and vertical specimens.
- Render the real Chromium demo/site after metric or substitution changes and
  inspect the output image. A single cropped screenshot is evidence of a bug,
  not sufficient verification of the fix.
- Test the default and extreme weights. For vertical punctuation, test in a
  phrase with adjacent Han characters so displacement within the em is visible.
- Do not infer one renderer from another. Chromium, GTK Text Editor, and Kitty
  have different fallback and shaping behavior. CSS's computed `font-family`
  also does not prove which physical face rendered a character; inspect the
  rendered font or platform match.
- Remember that emoji fonts may contain ordinary digits for keycap sequences.
  Fontconfig fallback order can therefore affect plain digits even when the
  requested family appears unrelated to emoji.

## Web artifacts

- Keep `demo/index.html` as the compact README specimen and `site/` as the
  separate public homepage.
- Custom line-breaking rules are valid when they express the intended rigid
  inscription layout. They must not compensate for glyph geometry.
- Regenerate tracked screenshots only through the repository tasks, and review
  the resulting diff before committing generated assets.
