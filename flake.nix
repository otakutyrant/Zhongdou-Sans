{
  description = "Reproducible development tools for Zhongdou Sans";

  inputs = {
    # Pin nixpkgs so Chromium, fontTools, fonts, and the PNG encoder stay stable.
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { nixpkgs, ... }:
    let
      # Chromium supplies this headless rendering workflow on NixOS/Linux.
      forAllSystems = nixpkgs.lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
      ];
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python3.withPackages (pythonPackages: [
            # fontTools uses Brotli when it writes the site's compact WOFF2 subsets.
            pythonPackages.brotli
            pythonPackages.fonttools
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
              pkgs.chromium
              pkgs.fontconfig
              pkgs.git
              # The standard output supplies hb-shape. The Cairo-enabled
              # development output additionally supplies hb-view.
              pkgs.harfbuzz
              harfbuzzView
              pkgs.nushell
              pkgs.oxipng
              # The public site embeds only the glyphs used by its inscription
              # and prose, but the build starts from the official SC face.
              pkgs.sarasa-gothic
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
              echo "Zhongdou Sans dev shell ready: use 'nur --help' to list project tasks."
            '';
          };
        }
      );
    };
}
