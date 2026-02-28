---
name: git-add-commit-push
description: Stages relevant changes, creates a clear commit message, and pushes the current branch safely. Use when the user asks to commit and push, publish changes, or run git add/commit/push workflow.
---

# Git Add Commit Push

## Purpose

Run a safe, repeatable Git publish workflow for this project:
1. review repo state
2. stage intended files
3. commit with a meaningful message
4. push current branch

## Workflow

1. Check status and diffs first:
   - `git status --short`
   - `git diff --staged`
   - `git diff`
   - `git log --oneline -n 10`

2. Confirm what to include:
   - Stage only files relevant to the requested change.
   - Do not include secrets (`.env`, private keys, credentials).
   - Leave unrelated local files untracked unless user explicitly asks.

3. Create commit:
   - Use a concise subject that reflects intent (feature/fix/docs/chore).
   - Prefer message format:
     - subject line
     - optional short body with why
   - Use HEREDOC for commit message when scripting.

4. Push:
   - Push current branch with `git push origin HEAD` (or configured branch).
   - If remote moved, report the new URL guidance to the user.

## Safety Rules

- Never use destructive commands (`reset --hard`, force push) unless explicitly requested.
- Never commit `.env` or credential files.
- If commit hooks fail, fix and create a new commit (no amend unless user asks).
- Do not change git config.

## Output to User

After running, report:
- commit hash and message
- pushed branch/remote
- any skipped files and why
- next verification command (for example: `git status`)
