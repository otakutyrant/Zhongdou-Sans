#!/usr/bin/env nu

# Render the built site in Chromium and require its in-page geometry audit.
def main [] {
  let project_root = (^git rev-parse --show-toplevel | str trim)
  let site_page = ($project_root | path join "build" "site" "index.html")

  if (which chromium | is-empty) {
    error make {
      msg: "Chromium is required. Run this check with `nix develop -c nur site check-layout`."
    }
  }

  let chromium_profile = (^mktemp -d --tmpdir "zhongdou-site-layout.XXXXXX" | str trim)
  let site_url = $"file://($site_page)?layout-test=1"
  let chromium_arguments = [
    "--headless=new"
    "--allow-file-access-from-files"
    "--disable-background-networking"
    "--disable-component-update"
    "--disable-default-apps"
    "--disable-gpu"
    "--disable-sync"
    "--force-device-scale-factor=1"
    "--no-sandbox"
    "--no-first-run"
    "--no-pings"
    "--run-all-compositor-stages-before-draw"
    $"--user-data-dir=($chromium_profile)"
    "--virtual-time-budget=1000"
    "--window-size=1280,960"
    "--dump-dom"
  ]

  let result = try {
    ^chromium ...$chromium_arguments $site_url | complete
  } catch {|render_error|
    rm -r $chromium_profile
    error make { msg: $"Chromium could not check the site layout: ($render_error.msg)" }
  }

  if $result.exit_code != 0 {
    rm -r $chromium_profile
    error make { msg: $"Chromium exited with status ($result.exit_code): ($result.stderr)" }
  }
  if not ($result.stdout | str contains 'data-layout-check="passed"') {
    let detail = ($result.stdout | parse --regex 'data-layout-error="(?<message>[^"]+)"' | get -o 0.message)
    rm -r $chromium_profile
    error make {
      msg: $"Punctuation-grid layout check failed: ($detail | default 'the page did not report a passing result')"
    }
  }

  let screenshot_dir = ($project_root | path join "build" "assessment" "site")
  mkdir $screenshot_dir
  let screenshot_targets = [
    { name: "games-desktop.png", viewport: "1400,1000" }
    { name: "games-narrow.png", viewport: "760,1800" }
  ]
  let visual_url = $"file://($site_page)?visual-test=games"

  for target in $screenshot_targets {
    let screenshot_path = ($screenshot_dir | path join $target.name)
    let screenshot_arguments = [
      "--headless=new"
      "--allow-file-access-from-files"
      "--disable-background-networking"
      "--disable-component-update"
      "--disable-default-apps"
      "--disable-gpu"
      "--disable-sync"
      "--force-device-scale-factor=1"
      "--hide-scrollbars"
      "--no-sandbox"
      "--no-first-run"
      "--no-pings"
      "--run-all-compositor-stages-before-draw"
      $"--user-data-dir=($chromium_profile)"
      "--virtual-time-budget=3000"
      $"--window-size=($target.viewport)"
      $"--screenshot=($screenshot_path)"
    ]
    let screenshot_result = (^chromium ...$screenshot_arguments $visual_url | complete)
    if $screenshot_result.exit_code != 0 {
      rm -r $chromium_profile
      error make {
        msg: $"Chromium could not render ($target.name): ($screenshot_result.stderr)"
      }
    }
    let screenshot_size = (ls $screenshot_path | get size | first)
    if $screenshot_size < 50kb {
      rm -r $chromium_profile
      error make {
        msg: $"Chromium rendered an empty or incomplete QA image: ($target.name) is only ($screenshot_size)"
      }
    }
  }

  rm -r $chromium_profile
  print "Validated all punctuation-grid items against their rendered cell centers."
  print $"Rendered visual QA screenshots in ($screenshot_dir)."
}
