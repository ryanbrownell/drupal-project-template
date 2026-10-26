#!/usr/bin/env bash

# Exercise the release workflow with isolated Git/Codex stubs and no remote writes.
set -Eeuo pipefail
trap 'printf "FAIL: release launch regression on line %s.\n" "$LINENO" >&2' ERR

script_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
release_script="$script_directory/launch-testing-release.sh"
test_directory=$(mktemp -d)
trap 'rm -rf -- "$test_directory"' EXIT
test_repository="$test_directory/repository with spaces"

mkdir -p "$test_directory/bin" "$test_directory/saved-config" "$test_repository"
cat > "$test_directory/saved-config/config.toml" <<'CONFIG'
model = "account-incompatible-model"
service_tier = "priority"
CONFIG

# Include nested headings, Markdown, indentation, and shell literals to detect rewriting.
cat > "$test_directory/release-note-instructions" <<'INSTRUCTIONS'
## Release Notes Requests

When asked for release notes "since <tag>":

- Analyze commit history and code diffs for `<tag>..HEAD`.
  - Run `git log --oneline <tag>..HEAD`.

### Required output

- Use a clever H1 title with matching emojis after the headline.
  - Example: `# Text Me Maybe: SMS TFA Debut 📲🔐`
- Preserve literal $HOME, ${HOME}, $(printf expanded), and backslashes \.
- State whether tests were run.
INSTRUCTIONS

{
  printf '# Project guidance\n\nDo not include this unrelated instruction.\n\n'
  cat "$test_directory/release-note-instructions"
  printf '\n## Other instructions\n\nDo not include this later instruction.\n'
} > "$test_repository/AGENTS.md"

cat > "$test_directory/bin/git" <<'GIT'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "$TEST_RUN_DIRECTORY/git.log"
case "$1" in
  rev-parse)
    if [[ $2 == "--show-toplevel" ]]; then
      printf '%s\n' "$TEST_REPOSITORY_ROOT"
    else
      printf 'release-commit\n'
    fi
    ;;
  status)
    if [[ $TEST_DIRTY_WORKTREE == "true" ]]; then
      printf ' M modified-file\n'
    fi
    ;;
  fetch)
    fetch_count=0
    if [[ -f "$TEST_RUN_DIRECTORY/fetch-count" ]]; then
      read -r fetch_count < "$TEST_RUN_DIRECTORY/fetch-count"
    fi
    printf '%s\n' "$((fetch_count + 1))" > "$TEST_RUN_DIRECTORY/fetch-count"
    ;;
  tag)
    read -r fetch_count < "$TEST_RUN_DIRECTORY/fetch-count"
    # Ignore prerelease tags even when they sort ahead of the latest stable tag.
    printf 'v99.0.0-rc1\n'
    if (( fetch_count > 1 )); then
      printf 'v1.30.4\n'
    fi
    if [[ ${TEST_FIRST_RELEASE:-false} != true ]]; then
      printf 'v1.30.3\n'
    fi
    ;;
  branch) printf 'codex\n' ;;
  show-ref|merge-base|checkout|pull|merge|push) ;;
  *) printf 'Unexpected Git command: %s\n' "$*" >&2; exit 1 ;;
esac
GIT

cat > "$test_directory/bin/codex" <<'CODEX'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$@" > "$TEST_RUN_DIRECTORY/codex-args"
printf '%s\n' "${CODEX_HOME:-}" > "$TEST_RUN_DIRECTORY/codex-home"
[[ -f "$TEST_CODEX_CONFIG_ROOT/config.toml" ]]
# Model access fails if the script inherits the incompatible user configuration.
if [[ " $* " != *" --ignore-user-config "* ]]; then
  printf 'The configured model is not supported for this account.\n' >&2
  exit 1
fi
exit "$TEST_CODEX_EXIT_CODE"
CODEX
chmod +x "$test_directory/bin/git" "$test_directory/bin/codex"

# Capture each scenario without letting an expected failure terminate the tests.
run_launch() {
  local scenario=$1
  local codex_exit_code=$2
  local dirty_worktree=${3:-false}
  run_directory="$test_directory/$scenario"
  mkdir -p "$run_directory"
  launch_exit_code=0
  PATH="$test_directory/bin:$PATH" \
    TEST_CODEX_CONFIG_ROOT="$test_directory/saved-config" \
    TEST_RUN_DIRECTORY="$run_directory" \
    TEST_REPOSITORY_ROOT="$test_repository" \
    TEST_CODEX_EXIT_CODE="$codex_exit_code" \
    TEST_DIRTY_WORKTREE="$dirty_worktree" \
    bash "$release_script" <<< 'done' > "$run_directory/stdout" 2> "$run_directory/stderr" \
    || launch_exit_code=$?
}

# Compare the complete prompt so extra sections or rewritten instructions fail the test.
assert_codex_prompt() {
  local release_request=${1:-"Create release notes for all changes since v1.30.3"}
  printf 'exec\n--ephemeral\n--ignore-user-config\n-C\n%s\n%s\n\nFollow these instructions from AGENTS.md:\n\n%s\n' \
    "$test_repository" "$release_request" "$(< "$test_directory/release-note-instructions")" > "$test_directory/expected-args"
  diff -u "$test_directory/expected-args" "$run_directory/codex-args"
}

# Invalid policies must stop generation before publication or branch synchronization.
assert_instruction_failure() {
  local expected_message=$1
  [[ $launch_exit_code == 1 ]]
  [[ $(< "$run_directory/stderr") == *"$expected_message"* ]]
  [[ $(< "$run_directory/stderr") == *"$test_repository/AGENTS.md"* ]]
  [[ ! -f "$run_directory/codex-args" ]]
  [[ $(< "$run_directory/fetch-count") == 1 ]]
  [[ $(< "$run_directory/git.log") != *"reset --hard"* ]]
  [[ $(< "$run_directory/git.log") != *"push "* ]]
}

run_launch configured-model 0
[[ $launch_exit_code == 0 ]]
assert_codex_prompt
[[ $(< "$run_directory/codex-home") == "${CODEX_HOME:-}" ]]
[[ $(< "$run_directory/stdout") == *"Launch validation passed for v1.30.4"* ]]
[[ $(< "$run_directory/git.log") == *"push origin codex"* ]]

# Policy edits apply on the next run, including a final line without a newline.
printf '## Release Notes Requests\n\n- Use the updated policy with literal ${HOME}.' \
  > "$test_directory/release-note-instructions"
cp "$test_directory/release-note-instructions" "$test_repository/AGENTS.md"
run_launch updated-instructions 0
[[ $launch_exit_code == 0 ]]
assert_codex_prompt

run_launch generation-failure 42
[[ $launch_exit_code == 42 ]]
[[ $(< "$run_directory/stderr") == *"Launch preparation stopped unexpectedly on line"* ]]
[[ $(< "$run_directory/fetch-count") == 1 ]]
[[ $(< "$run_directory/git.log") != *"reset --hard"* ]]
[[ $(< "$run_directory/git.log") != *"push "* ]]

run_launch dirty-worktree 0 true
[[ $launch_exit_code == 1 ]]
[[ $(< "$run_directory/stderr") == *"The worktree is not clean."* ]]
[[ ! -f "$run_directory/codex-args" ]]
[[ ! -f "$run_directory/fetch-count" ]]

TEST_FIRST_RELEASE=true run_launch first-release 0
[[ $launch_exit_code == 0 ]]
assert_codex_prompt "Create release notes for the first release using the commit history and code."
[[ $(< "$run_directory/git.log") == *'merge --ff-only origin/main'* ]]
[[ $(< "$run_directory/git.log") != *'reset --hard'* ]]

mv "$test_repository/AGENTS.md" "$test_directory/saved-AGENTS.md"
run_launch missing-instructions-file 0
assert_instruction_failure "is missing or unreadable"

cat > "$test_repository/AGENTS.md" <<'AGENTS'
# Other guidance

The text "## Release Notes Requests" is not a section heading here.

## Release Notes Requests Extra

- This similarly named section must not be used.
AGENTS
run_launch missing-instructions-section 0
assert_instruction_failure "must contain a non-empty '## Release Notes Requests' section"

printf '## Release Notes Requests\n \t\n## Other instructions\n\n- This is outside the empty section.\n' \
  > "$test_repository/AGENTS.md"
run_launch empty-instructions-section 0
assert_instruction_failure "must contain a non-empty '## Release Notes Requests' section"

printf 'PASS: first and subsequent release launches pass project instructions verbatim, reject missing or empty policies, preserve authentication, ignore incompatible user settings, and stop on generation failure or a dirty worktree.\n'
