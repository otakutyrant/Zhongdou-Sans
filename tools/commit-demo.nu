#!/usr/bin/env nu

# Commit and publish the generated demo only when rendering changed its pixels.
def main [] {
  let image_path = "images/demo.png"
  let unchanged = (^git diff --quiet -- $image_path | complete).exit_code == 0

  if $unchanged {
    print "The committed demo image is already current."
    return
  }

  ^git config user.name "github-actions[bot]"
  ^git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  ^git add $image_path
  ^git commit --message "docs: update generated demo"
  ^git push origin HEAD:main
}
