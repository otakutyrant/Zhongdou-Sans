#!/usr/bin/env nu

# Build the derivative font and render its committed README specimen.
def main [] {
  let project_root = (^git rev-parse --show-toplevel | str trim)
  let build_dir = ($project_root | path join "build")
  let output_path = ($project_root | path join "images" "demo.png")
  let input_font = ($project_root | path join "fonts" "variable" "ZhudouSansVF.ttf")
  let output_font = ($build_dir | path join "ZhongdouSansVF.ttf")
  let demo_page = ($project_root | path join "demo" "index.html")

  if (which chromium | is-empty) or (which oxipng | is-empty) {
    error make {
      msg: "Missing demo tools. Run this script with `nix develop -c nu tools/render-demo.nu`."
    }
  }

  mkdir $build_dir
  ^python ($project_root | path join "tools" "build_font.py") $input_font $output_font
  ^nu ($project_root | path join "tools" "render-title.nu")

  # A fresh profile prevents extensions and user preferences from affecting pixels.
  let chromium_profile = (^mktemp -d --tmpdir "zhongdou-demo.XXXXXX" | str trim)
  let demo_url = $"file://($demo_page)"
  let chromium_arguments = [
    "--headless=new"
    "--disable-background-networking"
    "--disable-component-update"
    "--disable-default-apps"
    "--disable-gpu"
    "--disable-sync"
    "--force-device-scale-factor=1"
    "--hide-scrollbars"
    # GitHub-hosted runners cannot configure Nix's setuid Chromium sandbox.
    "--no-sandbox"
    "--no-first-run"
    "--no-pings"
    $"--user-data-dir=($chromium_profile)"
    "--virtual-time-budget=1500"
    "--window-size=2560,1440"
    $"--screenshot=($output_path)"
  ]

  try {
    ^chromium ...$chromium_arguments $demo_url
  } catch {|render_error|
    rm -r $chromium_profile
    error make { msg: $"Chromium could not render the demo: ($render_error.msg)" }
  }

  rm -r $chromium_profile
  ^oxipng --opt max --strip safe --quiet $output_path

  print $"Rendered ($output_path)"
}
