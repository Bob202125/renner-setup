# Cursor SSH to UIUC Campus Cluster – Fix for "Failed to connect"

## What’s going wrong

- SSH **does** reach the cluster; the failure happens during Cursor’s **remote install** step.
- The cluster’s **login scripts** run `lfs quota` with `/taiga/illinois/eng/shared`, which errors with **"lfs quota: invalid id '/taiga/illinois/eng/shared'"** and prints to **stderr**.
- That stderr output is mixed with Cursor’s install handshake, so Cursor times out or misinterprets the stream and reports **"Failed to connect"**.

So the underlying issue is **cluster login/profile scripts**, not your SSH keys or Cursor’s SSH client.

---

## What was changed on your Mac (Cursor)

- **Longer SSH connect timeout** (90 seconds) for Remote-SSH, so Cursor waits longer before giving up.  
  Set in Cursor user settings: `"remote.SSH.connectTimeout": 90`.

This might be enough if the install was only slow; if not, use the cluster-side fix below.

---

## Fix on the cluster (recommended)

You need to **reduce or silence the broken quota output** when the shell is **non-interactive** (e.g. when Cursor connects). Do this from a **normal terminal** SSH session (e.g. `ssh cc` or `ssh gclopton@cc-login.campuscluster.illinois.edu`).

### 1. See where the quota is run

On the cluster, run:

```bash
grep -r "lfs quota\|quota" /etc/profile.d/ 2>/dev/null
grep -n -E "lfs|quota" ~/.bash_profile ~/.bashrc ~/.profile 2>/dev/null
```

- If it’s in **your** `~/.bashrc` or `~/.bash_profile`: wrap that part so it only runs for **interactive** shells (see below).
- If it’s only in **/etc/profile.d/** (system): you can’t edit that; use the “early return” in step 2 to skip your own profile for non-interactive, and **report the error to Campus Cluster / NCSA** so they can fix the system script.

### 2. Skip your profile for non-interactive (Cursor) sessions

Add this **at the very top** of your **`~/.bash_profile`** on the cluster (create the file if it doesn’t exist):

```bash
# Let Cursor/VS Code Remote-SSH connect without running full login profile (avoids lfs quota stderr)
case $- in *i*) ;; *) return;; esac
```

That makes **non-interactive** login shells (like Cursor’s) skip the rest of `~/.bash_profile`. It does **not** stop `/etc/profile` or `/etc/profile.d/*` from running, so if the broken `lfs quota` is in a system file, you still need to report it (see above). If the quota is in your own rc/profile, wrap it in an interactive check instead:

```bash
# Only run quota in interactive shells
if [[ $- == *i* ]]; then
  # your existing quota / lfs command here
fi
```

### 3. Report the system error (if it’s in /etc)

If the `lfs quota` call is in a system file, send Campus Cluster / NCSA support something like:

- **Error:** `lfs quota: invalid id '/taiga/illinois/eng/shared'`
- **When:** On SSH login (and when using Cursor Remote-SSH).
- **Ask:** Fix or make the quota check conditional so it doesn’t break non-interactive SSH (e.g. Cursor, VS Code Remote-SSH).

---

## After changing the cluster

1. Save `~/.bash_profile` (and any `~/.bashrc` you edited) on the cluster.
2. In Cursor, try connecting again to `gclopton@cc-login.campuscluster.illinois.edu` (or your `cc` host).

If it still fails, check the Cursor Remote-SSH log (e.g. **Output** → **Remote - SSH**) and look for the same `lfs quota` stderr; that usually means the quota is coming from system profile and support needs to fix it.
