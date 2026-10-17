{
  lib,
  stdenvNoCC,
  fetchFromGitHub,
  python3Packages,
  source ? null,
}:

stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "zhongdou-sans";
  version = "3.001";

  # Nixpkgs fetches the formal release, while the development flake overrides
  # this argument with its own source tree so local edits can be built directly.
  src =
    if source != null then
      source
    else
      fetchFromGitHub {
        owner = "otakutyrant";
        repo = "Zhongdou-Sans";
        rev = "v${finalAttrs.version}";
        hash = "sha256-0wk9OLPhlQbtFKPIWU3Pp/ursAyxvI7r5AzABG57LQs=";
      };

  strictDeps = true;
  nativeBuildInputs = [ python3Packages.fonttools ];

  buildPhase = ''
    runHook preBuild
    python tools/build_font.py fonts/variable/ZhudouSansVF.ttf ZhongdouSansVF.ttf
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    install -Dm444 ZhongdouSansVF.ttf "$out/share/fonts/truetype/ZhongdouSansVF.ttf"
    runHook postInstall
  '';

  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    python tools/check_release.py "v${finalAttrs.version}" \
      "$out/share/fonts/truetype/ZhongdouSansVF.ttf"
    runHook postInstallCheck
  '';

  meta = {
    description = "CJK punctuation font with centered Simplified Chinese punctuation";
    homepage = "https://github.com/otakutyrant/Zhongdou-Sans";
    license = lib.licenses.ofl;
    maintainers = [
      {
        name = "otakutyrant";
        email = "otakutyrant@gmail.com";
        github = "otakutyrant";
        githubId = 64188229;
      }
    ];
    platforms = lib.platforms.all;
  };
})
