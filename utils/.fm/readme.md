README — Bridges ➜ Mac transfer (your working setup)

Purpose
  Copy a file or directory FROM Bridges TO your Mac using your existing helpers.
  Workflow: open a reverse SSH tunnel on the Mac, then run `transfer` on Bridges.

What you already have
  • Mac alias  : transfer -> ~/utils/.fm/transfer.sh
  • Bridges alias: transfer -> ~/utils/.fm/transfer.sh
  • Reverse-tunnel port: 8023 (must match on both sides)
  • Mac landing folder (set in Bridges helper): /Users/gradyclopton/Documents/Transfer
  • Optional tools on Bridges: fm -> ~/utils/.fm/file_manager.sh  (NOT used for copying)

Quick recipe (every time)
  1) On your Mac (new Terminal tab/window; keep it running):
       transfer start bridges
     This opens the reverse tunnel to Bridges and waits in the foreground.

  2) On Bridges (your login shell), push the data back to your Mac:
       transfer [-d] [-n NAME] <source_path>

     Options:
       -d, --date      Prepend a time-stamped mm-dd-yy-HHMM directory on the Mac.
       -n, --name      Wrap the payload in a subfolder named NAME.

  3) When the copy finishes, stop the Mac tunnel with Ctrl-C.

Examples (Bridges commands you can paste)
  # Plain copy of a directory
  transfer /ocean/projects/mat220011p/clopton/AIMD/CeO2/VASP6_AUTO/02-mp-2629-Ce7O12/17_ARCH

  # Add timestamp folder under the destination
  transfer -d /ocean/projects/mat220011p/clopton/AIMD/CeO2/VASP6_AUTO/02-mp-2629-Ce7O12/17_ARCH

  # Timestamp + wrapper folder
  transfer -d -n Ce7O12_ARCH /ocean/projects/mat220011p/clopton/AIMD/CeO2/VASP6_AUTO/02-mp-2629-Ce7O12/17_ARCH

Where the files land on the Mac
  Base folder:
    /Users/gradyclopton/Documents/Transfer
  With -d:
    /Users/gradyclopton/Documents/Transfer/mm-dd-yy-HHMM/
  With -d -n NAME:
    /Users/gradyclopton/Documents/Transfer/mm-dd-yy-HHMM/NAME/

What success looks like on Bridges
  You’ll see a line like:
    ✅  <SRC> → /Users/gradyclopton/Documents/Transfer/...

Mental model (so you remember which transfer is which)
  • Mac side `transfer start bridges` opens the reverse tunnel:
      Bridges:8023 → Mac:ssh
  • Bridges side `transfer ...` verifies the tunnel, creates the dest path on your Mac,
    then scp’s the payload to DEST_USER@localhost:-P 8023.

Common pitfalls
  • Don’t run: fm transfer ...   (that calls file_manager.sh; it is not the copy tool)
  • If you see “Tunnel … not up”, re-run `transfer start bridges` on the Mac and keep it open.
  • If SSH to the Mac is refused, enable macOS Remote Login:
      System Settings → General → Sharing → Remote Login (on)
      or: sudo systemsetup -setremotelogin on
  • Port must match: 8023 on both scripts. Change both sides if you ever pick a different port.

Sanity checks
  • On Mac:   type transfer   → should point to ~/utils/.fm/transfer.sh
  • On Bridges: type transfer → should point to ~/utils/.fm/transfer.sh
  • After a run, verify files under:
      /Users/gradyclopton/Documents/Transfer[/mm-dd-yy-HHMM][/NAME]/


README — Bridges scratch ➜ local SSD archive

Purpose
  Mirror Bridges calculation data to a local SSD so local `vo` analysis,
  Obsidian notebooks, figures, and slide workflows can operate on the same
  directory layout used on Bridges.

Default destination
  /Volumes/Extreme SSD/bridges2_archive

Default source
  clopton@bridges2.psc.edu:/jet/home/clopton/scratch

Resulting local layout
  /Volumes/Extreme SSD/bridges2_archive/scratch/...

Quick commands
  Preview the whole transfer:
    fm archive --local --status

  Mirror the whole scratch tree:
    fm archive --local --all

  Mirror only convergence tests:
    fm archive --local convergence_tests

  Mirror convergence tests without the scrolling per-file progress output:
    fm archive --local convergence_tests --quiet

  Mirror one calculation directory:
    fm archive --local /jet/home/clopton/scratch/convergence_tests/CeO2_mp-1018664

Important behavior
  The command uses rsync and preserves the scratch-relative folder structure.
  It does not delete local files by default, because the SSD copy is meant to
  be a backup. If you intentionally want a strict mirror, add `--delete`.

  The system rsync on this Mac is Apple's older rsync. It supports per-file
  progress only, not modern whole-transfer progress. Use `--quiet` if the
  scrolling file list is too noisy.

  The default rsync mode is friendly to the current ExFAT SSD format: it copies
  contents, directories, symlinks, and timestamps, but does not try to preserve
  Unix owners, groups, or permission bits.

  Mac metadata sidecar files are suppressed during transfer where possible:
  `._*` and `.DS_Store` are excluded, `COPYFILE_DISABLE=1` is set for rsync,
  and any sidecars created by the ExFAT write path are deleted after a
  successful non-dry-run archive.

  The command preserves symlinks by default. That keeps old broken active-file
  symlinks from making the archive fail. If you are archiving a tree whose
  active-file symlinks still resolve on Bridges and you want those targets as
  real local files, add `--copy-unsafe-links`.

Configuration
  Override the default SSD archive root for one command:
    fm archive --local convergence_tests --dest "/Volumes/Extreme SSD/bridges2_archive"

  Or set it in the shell:
    export FM_LOCAL_ARCHIVE="/Volumes/Extreme SSD/bridges2_archive"

  Other environment overrides:
    FM_REMOTE_USER
    FM_REMOTE_HOST
    FM_REMOTE_SCRATCH
