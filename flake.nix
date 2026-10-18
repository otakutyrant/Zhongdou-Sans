{
  description = "Reproducible development tools for Zhongdou Sans";

  inputs = {
    # Pin nixpkgs so Chromium, fontTools, fonts, and the PNG encoder stay stable.
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    # nu-lint is not packaged in nixpkgs yet, so pin its own flake alongside
    # the rest of the development environment.
    nu-lint.url = "git+https://codeberg.org/wvhulle/nu-lint";
  };

  outputs =
    {
      self,
      nixpkgs,
      nu-lint,
      ...
    }:
    let
      # Chromium supplies this headless rendering workflow on NixOS/Linux.
      forAllSystems = nixpkgs.lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
      ];
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          # Reuse the nixpkgs-ready expression while building the current
          # working tree instead of downloading the latest formal release.
          default = pkgs.callPackage ./package.nix { source = self; };
        }
      );

      # nixfmt-tree applies the official Nix style to every Nix file and also
      # provides a non-mutating CI mode used by the Nur command catalog.
      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixfmt-tree);

      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python3.withPackages (pythonPackages: [
            # fontTools uses Brotli when it writes the site's compact WOFF2 subsets.
            pythonPackages.brotli
            pythonPackages.fonttools
            # Keep Python checks in the same interpreter environment as the
            # font scripts so Pylint and pytest can resolve FontTools imports.
            pythonPackages.pylint
            pythonPackages.pytest
          ]);

          # Cairo support makes hb-view available alongside hb-shape, allowing
          # focused PNG specimens of the exact glyph sequence HarfBuzz shapes.
          harfbuzzView = (pkgs.harfbuzz.override { withCairo = true; }).dev;

          # Nur bundles a matching Nushell runtime. Pin its official binary so
          # contributors do not need the task runner in their global profile.
          nurVersion = "0.30.2+0.115.1";
          nurRelease =
            {
              x86_64-linux = {
                target = "x86_64-unknown-linux-gnu";
                hash = "sha256-z3tGydpAvg5uinfmZYH/fr6uB+nok2ajVK77C/tgDV4=";
              };
              aarch64-linux = {
                target = "aarch64-unknown-linux-gnu";
                hash = "sha256-hFOd+XN5/gPvZ0F7CPnAQlyBK1f3rB+Gge2ePjgTPk4=";
              };
            }
            .${system};
          nur = pkgs.stdenvNoCC.mkDerivation {
            pname = "nur";
            version = nurVersion;
            src = pkgs.fetchurl {
              url = "https://github.com/nur-taskrunner/nur/releases/download/v${nurVersion}/nur-${nurVersion}-${nurRelease.target}.tar.gz";
              inherit (nurRelease) hash;
            };
            sourceRoot = "nur-${nurVersion}-${nurRelease.target}";
            nativeBuildInputs = [ pkgs.autoPatchelfHook ];
            buildInputs = [ pkgs.stdenv.cc.cc.lib ];
            installPhase = ''
              runHook preInstall
              install -Dm755 nur $out/bin/nur
              runHook postInstall
            '';
          };
        in
        {
          default = pkgs.mkShell {
            packages = [
              # Biome checks the framework-free JavaScript and CSS without
              # introducing a separate Node package graph.
              pkgs.biome
              pkgs.basedpyright
              pkgs.chromium
              pkgs.fontconfig
              pkgs.git
              # GitHub CLI publishes release artifacts from the validated tag.
              pkgs.gh
              # The standard output supplies hb-shape. The Cairo-enabled
              # development output additionally supplies hb-view.
              pkgs.harfbuzz
              harfbuzzView
              # Kitty hosts the optional Panoptor workspace; all pane commands
              # still enter through Nur tasks.
              pkgs.kitty
              pkgs.nixfmt-tree
              pkgs.nushell
              pkgs.oxipng
              pkgs.ruff
              # The public site embeds only the glyphs used by its inscription
              # and prose, but the build starts from the official SC face.
              pkgs.sarasa-gothic
              pkgs.watchexec
              nu-lint.packages.${system}.default
              nur
              python
            ];

            # Chromium uses this isolated font catalogue instead of whichever
            # fonts happen to be installed on the machine rendering the demo.
            FONTCONFIG_FILE = pkgs.makeFontsConf {
              fontDirectories = [ pkgs.source-han-sans ];
            };

            # Sarasa packages its regional faces in a TrueType Collection.
            # tools/build_site.py selects the SC face at collection index 1.
            SARASA_REGULAR_TTC = "${pkgs.sarasa-gothic}/share/fonts/truetype/Sarasa-Regular.ttc";

            shellHook = ''
              # Keep stdout available for machine-readable task output such as
              # `nur --quiet panoptor status --json`.
              echo "Zhongdou Sans dev shell ready: use 'nur --help' to list project tasks." >&2
            '';
          };
        }
      );
    };
}
