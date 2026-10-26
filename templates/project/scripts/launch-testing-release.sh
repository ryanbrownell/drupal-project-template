#!/usr/bin/env bash

set -Eeuo pipefail

readonly MAIN_BRANCH="main"
readonly CODEX_BRANCH="codex"
readonly REMOTE="origin"

info() {
  printf 'ℹ️  %s\n' "$1"
}

success() {
  printf '✅ %s\n' "$1"
}

fail() {
  printf '❌ %s\n' "$1" >&2
  exit 1
}

handle_error() {
  local exit_code=$?
  printf '❌ Launch preparation stopped unexpectedly on line %s.\n' "$1" >&2
  exit "$exit_code"
}

trap 'handle_error "$LINENO"' ERR

require_command() {
  local command_name=$1

  command -v "$command_name" >/dev/null 2>&1 \
    || fail "Required command '$command_name' is not available."
}

find_latest_release_tag() {
  local tag

  while IFS= read -r tag; do
    if [[ $tag =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      printf '%s\n' "$tag"
      return 0
    fi
  done < <(git tag --merged "$MAIN_BRANCH" --sort=-version:refname)

  return 1
}

require_command git

repository_root=$(git rev-parse --show-toplevel 2>/dev/null) \
  || fail "Run this script from inside a Git repository."
cd "$repository_root"

if [[ -n $(git status --porcelain) ]]; then
  fail "The worktree is not clean. Commit or stash local changes before launching a release."
fi

info "Fetching the latest branches and tags from $REMOTE..."
git fetch "$REMOTE" --prune --tags

git show-ref --verify --quiet "refs/remotes/$REMOTE/$MAIN_BRANCH" \
  || fail "Remote branch '$REMOTE/$MAIN_BRANCH' does not exist."
git show-ref --verify --quiet "refs/remotes/$REMOTE/$CODEX_BRANCH" \
  || fail "Remote branch '$REMOTE/$CODEX_BRANCH' does not exist."
git show-ref --verify --quiet "refs/heads/$CODEX_BRANCH" \
  || fail "Local branch '$CODEX_BRANCH' does not exist."

local_codex_commit=$(git rev-parse "$CODEX_BRANCH")
remote_codex_commit=$(git rev-parse "$REMOTE/$CODEX_BRANCH")

if [[ $local_codex_commit != "$remote_codex_commit" ]]; then
  if git merge-base --is-ancestor \
    "$REMOTE/$CODEX_BRANCH" "$CODEX_BRANCH"; then
    fail "The remote codex branch is missing local commits. Push codex to origin, then run this script again."
  fi

  if git merge-base --is-ancestor \
    "$CODEX_BRANCH" "$REMOTE/$CODEX_BRANCH"; then
    fail "The local codex branch is behind origin/codex. Pull the latest codex branch, then run this script again."
  fi

  fail "The local codex and origin/codex branches have diverged. Reconcile them before running this script again."
fi

success "The local and remote codex branches are synchronized."

if ! git merge-base --is-ancestor \
  "$REMOTE/$CODEX_BRANCH" "$REMOTE/$MAIN_BRANCH"; then
  fail "The main branch is not up to date with codex. Create a pull request from codex to main in GitHub and complete the merge, then run this script again."
fi

success "The main branch contains the latest codex changes."
info "Checking out $MAIN_BRANCH and pulling the latest commit from $REMOTE..."
git checkout "$MAIN_BRANCH"
git pull --ff-only "$REMOTE" "$MAIN_BRANCH"
[[ $(git rev-parse "$MAIN_BRANCH") == "$(git rev-parse "$REMOTE/$MAIN_BRANCH")" ]] \
  || fail "Local main contains unpublished commits. Reconcile it with origin/main first."

previous_tag=$(find_latest_release_tag) || previous_tag=""
if [[ -n $previous_tag ]]; then
  success "The most recent released version is $previous_tag."
  release_prompt="Create release notes for all changes since $previous_tag"
else
  info "This is the first stable release."
  release_prompt="Create release notes for the first release using the commit history and code."
fi

if command -v codex >/dev/null 2>&1; then
  require_command awk
  instructions_file="$repository_root/AGENTS.md"
  [[ -f $instructions_file && -r $instructions_file ]] \
    || fail "Cannot generate release notes: instructions file '$instructions_file' is missing or unreadable."

  # Read the current policy after pulling main, preserving its Markdown and shell literals.
  release_notes_instructions=$(awk '
    $0 == "## Release Notes Requests" { in_section = 1; print; next }
    in_section && /^## / { exit }
    in_section {
      print
      if ($0 ~ /[^[:space:]]/) has_instructions = 1
    }
    END { if (!has_instructions) exit 1 }
  ' "$instructions_file") \
    || fail "Cannot generate release notes: '$instructions_file' must contain a non-empty '## Release Notes Requests' section."

  printf -v release_prompt '%s\n\nFollow these instructions from AGENTS.md:\n\n%s' \
    "$release_prompt" "$release_notes_instructions"
  info "Starting Codex with release-note instructions from $instructions_file."
  # Retain existing authentication without inheriting saved model/tier settings.
  codex exec --ephemeral --ignore-user-config -C "$repository_root" "$release_prompt"
else
  info "Codex is optional. Use this history and diff to prepare release notes:"
  if [[ -n $previous_tag ]]; then
    git log --oneline "$previous_tag..HEAD"
    git diff --stat "$previous_tag..HEAD"
  else
    git log --oneline
    git ls-tree -r --name-only HEAD
  fi
fi
[[ -z $(git status --porcelain) ]] || fail "Release-note preparation changed the worktree. Review the changes before continuing."

while true; do
  read -r -p "🚀 Create and publish a stable vX.Y.Z release in GitHub, then type 'done' to continue: " release_confirmation \
    || fail "Release confirmation was not received. Publish the release and rerun this script."
  if [[ $release_confirmation =~ ^[Dd][Oo][Nn][Ee]$ ]]; then
    break
  fi
  info "Waiting for confirmation. Type 'done' after the GitHub release is published."
done

info "Fetching the new release tag and pulling the latest $MAIN_BRANCH..."
git fetch "$REMOTE" --prune --tags
git pull --ff-only "$REMOTE" "$MAIN_BRANCH"

new_tag=$(find_latest_release_tag) \
  || fail "No release tag matching v<integer>.<integer>.<integer> was found after the release."

if [[ $new_tag == "$previous_tag" ]]; then
  fail "No new release tag was detected. GitHub still reports $previous_tag as the latest matching release tag."
fi

new_tag_commit=$(git rev-parse "${new_tag}^{commit}")
main_commit=$(git rev-parse "$MAIN_BRANCH")
origin_main_commit=$(git rev-parse "$REMOTE/$MAIN_BRANCH")

if [[ $new_tag_commit != "$main_commit" || $main_commit != "$origin_main_commit" ]]; then
  fail "The new tag $new_tag, $MAIN_BRANCH, and $REMOTE/$MAIN_BRANCH do not all identify the same commit."
fi

[[ $(git rev-parse "$REMOTE/$CODEX_BRANCH") == "$remote_codex_commit" ]] \
  || fail "origin/codex changed during release preparation. Reconcile the branch before continuing."
[[ -z $(git status --porcelain) ]] || fail "The worktree changed during release preparation."
success "Detected new release $new_tag at the latest $MAIN_BRANCH commit."
info "Checking out $CODEX_BRANCH and fast-forwarding it to $REMOTE/$MAIN_BRANCH..."
git checkout "$CODEX_BRANCH"
git merge --ff-only "$REMOTE/$MAIN_BRANCH"

info "Pushing the synchronized $CODEX_BRANCH branch to $REMOTE..."
git push "$REMOTE" "$CODEX_BRANCH"

current_commit=$(git rev-parse HEAD)
codex_commit=$(git rev-parse "$CODEX_BRANCH")
origin_codex_commit=$(git rev-parse "$REMOTE/$CODEX_BRANCH")
main_commit=$(git rev-parse "$MAIN_BRANCH")
origin_main_commit=$(git rev-parse "$REMOTE/$MAIN_BRANCH")
new_tag_commit=$(git rev-parse "${new_tag}^{commit}")

if [[ $(git branch --show-current) != "$CODEX_BRANCH" ]]; then
  fail "Validation failed because $CODEX_BRANCH is not the current branch."
fi

if [[ $current_commit != "$new_tag_commit" \
  || $current_commit != "$main_commit" \
  || $current_commit != "$origin_main_commit" \
  || $current_commit != "$codex_commit" \
  || $current_commit != "$origin_codex_commit" ]]; then
  fail "Validation failed: $new_tag, $MAIN_BRANCH, $REMOTE/$MAIN_BRANCH, $CODEX_BRANCH, and $REMOTE/$CODEX_BRANCH are not all at the current commit."
fi

success "Launch validation passed for $new_tag at $current_commit."
printf 'Release %s is published. The testing workflow runs when deployment is enabled.\n' "$new_tag"
printf 'Check the testing pipeline and deployed site before launching %s to production.\n' "$new_tag"
