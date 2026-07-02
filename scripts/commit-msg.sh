#!/bin/bash
#
# commit-msg hook — validate conventional commit format
#
# Regex: type(scope): subject (max 72 chars)
# Types: feat, fix, docs, style, refactor, test, chore, ci, perf, build, revert
#
# Install:
#   cp scripts/commit-msg.sh .git/hooks/commit-msg
#   chmod +x .git/hooks/commit-msg
# Or via pre-commit:
#   pre-commit install --hook-type commit-msg

commit_msg_file="$1"
commit_msg=$(head -1 "$commit_msg_file")

# Allow merge commits
if echo "$commit_msg" | grep -qE "^Merge "; then
  exit 0
fi

# Allow fixup! / squash! autosquash commits
if echo "$commit_msg" | grep -qE "^(fixup|squash)!"; then
  exit 0
fi

pattern="^(feat|fix|docs|style|refactor|test|chore|ci|perf|build|revert)(\(.+\))?: .{1,72}$"

if ! echo "$commit_msg" | grep -qE "$pattern"; then
  echo "ERROR: Commit message does not follow Conventional Commits format."
  echo ""
  echo "  Expected: type(scope): description (max 72 chars)"
  echo "  Example:  feat(compute): implement archetype classifier"
  echo ""
  echo "  Types: feat, fix, docs, style, refactor, test, chore, ci, perf, build, revert"
  exit 1
fi
