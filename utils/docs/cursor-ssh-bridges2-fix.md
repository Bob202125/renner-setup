# Cursor SSH to PSC Bridges2 – Fixes for Lock Loops, Install Failures, and Broken `.cursor-server`

## What went wrong

This turned out to be a stack of separate problems rather than one single Cursor bug.

First, Cursor sometimes tried to connect using the wrong saved target, `ssh gclopton@bridges.psc.edu`, which is wrong for both the hostname and the username. The correct Bridges login is `clopton@bridges2.psc.edu`, or the SSH alias `bridges` if `~/.ssh/config` is set correctly.

Second, Cursor repeatedly got stuck in the remote install loop:

```text
Lock heartbeat is stale but owner PID ... is still running; keeping lock.
Install in progress, sleeping for a bit...
```

That happened because stuck remote installer `bash` processes on Bridges were still holding Cursor lock files under `/run/user/86471/`.

Third, even when the remote install succeeded, the local forwarding layer on the Mac still failed. The symptoms were `mux_client_request_session`, `Address already in use`, `Socket closed`, and failed SOCKS forwarding. The main culprit was OpenSSH multiplexing and the Bridges control socket being reused by Cursor.

Finally, the install failure that actually blocked the last working reconnect was:

```text
Error creating server install directory /jet/home/clopton/.cursor-server/bin/linux-x64/...
```

This was partly due to space pressure in `/jet/home/clopton`, but the direct cause was worse: `~/.cursor-server` was a broken symlink:

```text
/jet/home/clopton/.cursor-server -> /scratch/clopton/cursor-server
```

The target `/scratch/clopton/cursor-server` did not exist, so Cursor could not create `~/.cursor-server/bin/...`.

## What fixed it

The successful fix had four parts.

On the Mac, SSH multiplexing was disabled for Bridges in `~/.ssh/config`. The working Bridges block is:

```sshconfig
Host bridges bridges2.psc.edu
    HostName bridges2.psc.edu
    User clopton
    ControlMaster no
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

This prevented Cursor from reusing a stale or conflicting control socket for Bridges.

On Bridges, stale Cursor runtime files and stuck installer processes were cleared:

```bash
pkill -u "$USER" -f "cursor-server|server-main|multiplex-server|cursor-remote|bash --login -c bash|bash -c bash --login -c bash" 2>/dev/null || true
rm -f /run/user/$(id -u)/cursor-remote-* /run/user/$(id -u)/cursor-remote-lock*
```

Then large `WAVECAR` files were deleted from the live scratch convergence tests tree, excluding anything with `archive` in the path:

```bash
find /jet/home/clopton/scratch/convergence_tests -type f \( -name WAVECAR -o -name 'WAVECAR*' \) ! -ipath '*archive*' ! -ipath '*Archive*' -print -delete
```

That removed `106` files totaling about `10.94 GiB`.

Then the broken `~/.cursor-server` symlink was replaced with a real directory:

```bash
rm -f /jet/home/clopton/.cursor-server
mkdir -p /jet/home/clopton/.cursor-server/bin/linux-x64/224838f96445be37e3db643a163a817c15b36060
```

After that, Cursor was able to install again.

## Quick recovery procedure

If Cursor starts looping on Bridges again, use this order.

First, make sure Cursor is connecting to the right host. The target should be `bridges`, `bridges2.psc.edu`, or `clopton@bridges2.psc.edu`. It should not be `bridges.psc.edu`, and it should not use the Campus Cluster username `gclopton`.

Second, make sure Bridges SSH multiplexing is still disabled locally:

```bash
ssh -G bridges 2>/dev/null | egrep '^(hostname|user|controlmaster|controlpath|controlpersist) '
```

`controlmaster false` is the desired result.

Third, if Cursor is in the lock loop, log into Bridges in a normal terminal and run:

```bash
pkill -u "$USER" -f "cursor-server|server-main|multiplex-server|cursor-remote|bash --login -c bash|bash -c bash --login -c bash" 2>/dev/null || true
rm -f /run/user/$(id -u)/cursor-remote-* /run/user/$(id -u)/cursor-remote-lock*
```

Fourth, if Cursor reports an install directory error, check whether `~/.cursor-server` is a broken link:

```bash
ls -ld ~/.cursor-server
file ~/.cursor-server
```

If it is a broken symlink, replace it:

```bash
rm -f ~/.cursor-server
mkdir -p ~/.cursor-server
```

Fifth, if `/jet/home/clopton` is tight on space, delete unneeded `WAVECAR` files in the live scratch convergence tests tree:

```bash
find /jet/home/clopton/scratch/convergence_tests -type f \( -name WAVECAR -o -name 'WAVECAR*' \) ! -ipath '*archive*' ! -ipath '*Archive*' -print -delete
```

Then verify space:

```bash
df -h /jet
du -sh /jet/home/clopton 2>/dev/null
```

## Notes

The issue does not appear to be only a Cursor-side bug. The actual failure was the combination of local SSH multiplexing, stale remote lock owners, disk pressure, and a broken `~/.cursor-server` symlink on Bridges.

If this happens again, start by checking `~/.cursor-server` and `/run/user/$(id -u)/cursor-remote-*` before reinstalling Cursor on the Mac. Those were the highest-signal checks.

Because the Bridges password was shared during debugging, it should be changed after the session.
