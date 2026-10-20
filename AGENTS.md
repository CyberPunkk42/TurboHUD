# TurboKit — notes for AI agents

TurboKit is a new tool for Turbo Sliders Unlimited (TSU). Its purpose, stack and entry
point are still to be decided; update this section once they are.
Sister project: LiveryStudio (`../LiveryStudio`), an offline livery editor (Python 3.12+
with Tk, standard library only). Reuse its findings about TSU's files where they apply,
but never import from or write into that folder.

## Start here
1. Read `RESUME.md` (once it exists): current state, next steps and recent changes.
2. Read `docs/IMPROVEMENT_BACKLOG.md` (once it exists): open items ordered by value.

## Where things are
- This folder is the working copy and a private GitHub repository
  (https://github.com/CyberPunkk42/TurboKit, branch `main`). It sits next to
  `../LiveryStudio`. Commits use the GitHub noreply address: set
  `git config user.email 203462244+CyberPunkk42@users.noreply.github.com` in every clone.
- The user's TSU data (`player.json`, liveries in `SavedPaintJobs`) lives in
  `%USERPROFILE%\AppData\LocalLow\Turbo Sliders\Unlimited\<Steam ID>`. On the user's Mac,
  TSU runs in a CrossOver bottle, so the same folder is inside the bottle. Read from it
  only; never write to the game's folders. Test on copies.

## Personal data: never on GitHub
The user's Steam ID and Windows username must not appear in any commit, even for
people the user trusts.
- TSU writes the player's Steam ID into every exported paint job as `exportId`, so
  never commit real liveries or other game data. `samples/` stays local (gitignored).
- In fixtures, use the placeholder ID `76561197960265728`. In docs and logs, write
  `<SteamID>` and `<user>`, also in file paths. Code reads the real ID at runtime.
- A Git pre-push hook blocks any push containing the Steam ID, the user name or the
  computer name, including inside `.zip` and `.z` files and in commit messages. Its
  terms are worked out on the machine, never stored in the repository. Install it in
  every clone with `py -3 -B tools/privacy_check.py --install` (macOS/Linux:
  `python3`), and never bypass it (`--no-verify`). On a PC without TSU, the user lists
  the Steam ID and Windows user name in the clone's untracked `.git/privacy_terms.txt`;
  never ask for them or write them anywhere else. Paths in docs use `%USERPROFILE%`.
- Never use `git push --all` or `git push --mirror`.

## Branches and pull requests
The user approves every change by merging its pull request on GitHub. GitHub Free
cannot enforce this for a private repository, so it is up to you to follow it.
- Never commit to `main` or push to it. Never merge a pull request yourself
  (`gh pr merge`, or a local merge into `main`), unless the user says so for that PR.
- Start each task from an up-to-date `main`: `git switch main`, `git pull`, then
  `git switch -c <type>/<short-name>`. Types: `feature/`, `fix/`, `docs/`, `chore/`.
  Keep one task (usually one backlog item) per branch.
- On the branch: make the change, run the checks below, commit, then push with
  `git push -u origin <branch>`.
- Open the PR against `main` (`gh pr create --base main` where `gh` exists; on the
  user's Mac there is no `gh`, so give the pushed-branch URL). In the description, say:
  - what changed and why, naming the backlog item
  - how it was verified
  - anything not verified, or that the user should try by hand
- Then stop and give the user the PR link. Fixes requested in review go on the same
  branch as further commits.
- After the user merges: `git switch main`, `git pull`, `git branch -d <branch>`.
  GitHub deletes the remote branch.
- Pull requests are opened under the user's own GitHub account, so GitHub shows no
  "Approve" button. The user approves by clicking **Merge**.
- Releases are built only from `main` after the merge. Ask before pushing a release
  tag (`vYYYY.MM.DD`).

## Working rules
- When something is finished, in the same branch and pull request as the work:
  - update the backlog
  - keep `RESUME.md`'s "Current state" and "Next steps" true
  - add a dated entry at the top of its "Recent changes", and append the same entry
    to `docs/PROGRESS.md`
- New or changed behavior gets tests in the same pull request. Tests use temporary
  folders and never real liveries. All tests must pass before committing.
- Python: on Windows use `py -3`; on the user's Mac use `/opt/homebrew/bin/python3.13`
  (Apple's `python3` is too old).
- Line endings: `.gitattributes` stores files byte for byte. Keep each file's endings
  when editing; a script that reads and writes text can silently convert a whole file
  (`git diff --stat` shows it).
- Formatting: Ruff, with settings in `pyproject.toml` (quotes are kept as written).
  Ruff lives only in a `.buildtools/` tools environment, never in the app.
- Project skill: `senior-engineer` (in `.claude/skills` and `.agents/skills`).
