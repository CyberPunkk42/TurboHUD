# TurboHUD — notes for AI agents

TurboHUD is a new tool for Turbo Sliders Unlimited (TSU): a HUD overlay on top of the
running game (fuel estimate, minimap, lap times). Stack: Python with Qt (PySide6),
shipped as a bundled app for Windows, macOS and Linux (`docs/STACK.md`). The app is in
`turbohud/` (start: `launch_turbohud.py`, or `run_turbohud.sh` / `run_turbohud.cmd`);
builds come from `tools/build_app.py` (`.github/workflows/build.yml` runs only for a
release tag, a pull request or by hand, none of which is used). Findings and
suggested features are in `docs/SUGGESTIONS.md` (local only).
Sister project: LiveryStudio (`../LiveryStudio`), an offline livery editor (Python 3.12+
with Tk, standard library only). Reuse its findings about TSU's files where they apply,
but never import from or write into that folder.

## Start here
1. Read `RESUME.md` (once it exists): current state, next steps and recent changes.
2. Read `docs/SUGGESTIONS.md` if it is there: what the game exposes, suggested features,
   open decisions. It is private and gitignored: never commit it, quote it in commits or
   PRs, or move its contents into tracked files. The repository will be made public
   later for the TSU community.
3. Read `docs/IMPROVEMENT_BACKLOG.md` (once it exists): open items ordered by value.

## Where things are
- This folder is a Git repository (branch `main`) next to `../LiveryStudio`. Since
  2026-11-11 it is kept in step with a **private** GitHub repository
  (`https://github.com/CyberPunkk42/TurboHUD.git`), so the Mac and the Windows PC can both
  pull and push. The remote's name differs by clone: on the Mac it is `github` and
  `origin` is an old local bundle (`../TurboHUD.bundle`); the Windows PC's clone came
  from GitHub, so there it is `origin`. Check with `git remote -v` and push only to the
  remote whose URL is that GitHub address, never to the bundle; only `main` after the
  user merged into it and branches the user asks for; never force-push, never make the
  repository public (the user decides that), never use `gh`.
- Every commit's author and committer is `CyberPunkk42`
  `<203462244+CyberPunkk42@users.noreply.github.com>` (set in this clone's `user.name` and
  `user.email`; set them the same in every clone). Never the user's real name or a personal
  email: before the first push the whole history was rewritten for that (a backup of the
  old history is in `../TurboHUD-backup-2026-11-11-before-author-rewrite.git`, local only).
- The user plays on Linux (Omarchy, Hyprland on Wayland) with TSU's native Linux build.
  Its data is in `~/.config/unity3d/Turbo Sliders/Unlimited/<SteamID>/` (logs in `Logs/`,
  stats in `Scripts/`, recordings in `Recordings/`).
- Never change the system or Omarchy/Hyprland configuration (no edits to
  `~/.config/hypr/`, no system settings, no `ptrace_scope` change). Anything Linux-
  specific must affect only TurboHUD itself, e.g. settings inside its own process or
  runtime requests aimed at TurboHUD's own window.
- The user's TSU data (`player.json`, liveries in `SavedPaintJobs`) lives in
  `%USERPROFILE%\AppData\LocalLow\Turbo Sliders\Unlimited\<Steam ID>`. On the user's Mac,
  TSU runs in a CrossOver bottle, so the same folder is inside the bottle. Read from it
  only; never write to the game's folders. Test on copies.

## Personal data: never in commits
The user's Steam ID, Windows username, computer names, real name and personal email must
not appear in any commit (files, messages, author or committer), even for people the user
trusts: the repository is on GitHub, and will be public later.
- TSU writes the player's Steam ID into every exported paint job as `exportId`, so
  never commit real liveries or other game data. `samples/` stays local (gitignored).
- In fixtures, use the placeholder ID `76561197960265728`. In docs and logs, write
  `<SteamID>` and `<user>`, also in file paths. Code reads the real ID at runtime.
- Other players' names (drivers seen in races, logs and recordings, the testers' in-game
  names) never go into tracked files or commit messages either: in notes write "a car" or
  "a driver", in tests made-up names. The pre-push hook does not know them, so check by hand.
- A Git pre-push hook blocks any push containing the Steam ID, the user name or the
  computer name, including inside `.zip` and `.z` files, in commit messages and in the
  author and committer. It must be installed before any push. Its
  terms are worked out on the machine, never stored in the repository. Install it in
  every clone with `py -3 -B tools/privacy_check.py --install` (macOS/Linux:
  `python3`), and never bypass it (`--no-verify`). On a PC without TSU, the user lists
  the Steam ID and Windows user name in the clone's untracked `.git/privacy_terms.txt`;
  never ask for them or write them anywhere else. That file on the Mac also lists the real
  name, the personal email and the Mac's computer names, with `allow: CyberPunkk42` (the
  public account name, which contains the Mac's user name); give a new clone the same.
  Paths in docs use `%USERPROFILE%`.

## Branches and approval
The user approves every change by merging it locally. There are no pull requests.
- Never commit to `main`. Never merge into `main` yourself unless the user says so for
  that branch.
- Start each task from `main`: `git switch main`, then
  `git switch -c <type>/<short-name>`. Types: `feature/`, `fix/`, `docs/`, `chore/`.
  Keep one task (usually one backlog item) per branch.
- On the branch: make the change, run the checks below, commit. Then stop and tell the
  user the branch name and:
  - what changed and why, naming the backlog item
  - how it was verified
  - anything not verified, or that the user should try by hand
- Fixes requested in review go on the same branch as further commits.
- After the user approves: `git switch main`, `git merge --no-ff <branch>`,
  `git branch -d <branch>`.
- Builds and releases are made locally from `main` with `tools/build_app.py`. Ask
  before tagging a release.

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
