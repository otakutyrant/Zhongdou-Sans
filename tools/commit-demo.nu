#!/usr/bin/env nu

# Commit and publish generated specimens only when rendering changed them.
def main [] {
  let image_paths = ["images/demo.png" "images/Title.light.svg" "images/Title.dark.svg"]
  let unchanged = (^git diff --quiet -- ...$image_paths | complete).exit_code == 0

  if $unchanged {
    print "The committed specimen images are already current."
    return
  }

  ^git config user.name "github-actions[bot]"
  ^git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  ^git add ...$image_paths
  ^git commit --message "docs: update generated specimens"
  ^git push origin HEAD:main
}
