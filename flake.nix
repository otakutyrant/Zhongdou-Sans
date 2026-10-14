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
          python = pkgs.python3.withPackages (pythonPackages: [ pythonPackages.fonttools ]);
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.chromium
              pkgs.fontconfig
              pkgs.nushell
              pkgs.oxipng
              python
            ];

            # Chromium uses this isolated font catalogue instead of whichever
            # fonts happen to be installed on the machine rendering the demo.
            FONTCONFIG_FILE = pkgs.makeFontsConf {
              fontDirectories = [ pkgs.source-han-sans ];
            };
          };
        }
      );
    };
}
