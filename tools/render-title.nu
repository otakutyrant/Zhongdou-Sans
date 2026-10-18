#!/usr/bin/env nu

# Embed the built variable font in the two README title specimens. Keeping the
# font inside each SVG makes the punctuation reproducible on GitHub and on
# systems that do not have Zhongdou Sans installed.
def main [--output-dir: path] {
  let project_root = (^git rev-parse --show-toplevel | str trim)
  let destination = if ($output_dir | is-empty) {
    $project_root | path join "images"
  } else {
    $output_dir | path expand
  }
  let template_path = ($project_root | path join "demo" "title.svg")
  let font_path = ($project_root | path join "build" "ZhongdouSansVF.ttf")

  if not ($font_path | path exists) {
    error make { msg: "The built font is missing. Run `nur demo build` first." }
  }

  mkdir $destination
  let font_data = (open --raw $font_path | encode base64)
  let template = (open --raw $template_path | str replace "@@FONT_DATA@@" $font_data)
  let themes = [
    {
      name: "light"
      paper: "#fbfdff"
      ink: "#496270"
      soft: "#b8dcfa"
      faint: "#eaf5ff"
      red: "#a93a43"
      line: "#cbdce8"
      wash_start: "#ffffff"
      wash_end: "#f5faff"
    }
    {
      name: "dark"
      paper: "#0d141b"
      ink: "#9cb5c0"
      soft: "#456879"
      faint: "#182731"
      red: "#f16062"
      line: "#263b47"
      wash_start: "#111c24"
      wash_end: "#0b1117"
    }
  ]

  for theme in $themes {
    let rendered = ($template
      | str replace "@@PAPER@@" $theme.paper
      | str replace "@@INK@@" $theme.ink
      | str replace "@@SOFT@@" $theme.soft
      | str replace "@@FAINT@@" $theme.faint
      | str replace "@@RED@@" $theme.red
      | str replace "@@LINE@@" $theme.line
      | str replace "@@WASH_START@@" $theme.wash_start
      | str replace "@@WASH_END@@" $theme.wash_end)
    let output_path = ($destination | path join $"Title.($theme.name).svg")
    $rendered | save --force $output_path
    print $"Rendered ($output_path)"
  }
}
