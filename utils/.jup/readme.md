# Jupyter + Molten in an Obsidian Vault (quick README)

This is a tiny playbook for spinning up a per-vault Conda environment, registering it as a Jupyter kernel with our `jup` helper, and running code from Neovim/Molten in three formats: `.py`, `.md`, and paired `.ipynb`.

## Prereqs

* Conda (miniforge/mambaforge/etc.).
* Neovim with LazyVim.
* Molten installed and registered, **host Python** set at the very top of your `init.lua`, e.g.
  `vim.g.python3_host_prog = "/opt/homebrew/Caskroom/miniforge/base/envs/nvim/bin/python"`.
* The `jup` helper on your `PATH` (we placed it in `~/utils/.jup/bin/jup`).
* For inline figures: either run Neovim **in Kitty** with `image.nvim` or **in WezTerm** with the wezterm provider.

## Create a per-vault environment

From the **root of the vault**:

```bash
# minimal form: uses the folder name for the kernel’s display text
jup init

# or be explicit and pick a Python version
jup init electronic_structure python=3.11

# optional: a lean kernel with just ipykernel
jup init electronic_structure --lite
```

This creates a Conda env (named like `obs-electronic-structure`), installs your science stack, and registers a Jupyter kernel called `Python (electronic_structure)`. It also writes an `environment.yml` you can commit.

To see what exists later:

```bash
jup list           # shows conda envs and kernelspecs
```

If you ever rename/remove an env, clean the stale kernel:

```bash
jupyter kernelspec remove <kernel-name> -y
```

## Launch Neovim and attach the kernel

Open Neovim **in the terminal you want for images**:

* Kitty + `image.nvim`
* or WezTerm + `wezterm` provider

Then:

```
:MoltenInit
```

Pick your vault’s kernel (e.g., `obs-electronic-structure` / “Python (electronic\_structure)”). From here, anything you evaluate goes to that env.

## Run code from a Python file

Create `test_molten.py` in the vault and open it in Neovim:

```python
import sys, numpy as np
print("kernel python:", sys.executable)
np.arange(6).reshape(2, 3)

import matplotlib.pyplot as plt
plt.plot([0,1,2,3],[0,1,4,9])
plt.title("Molten smoke test")
plt.show()
```

Evaluate a line with `:MoltenEvaluateLine`, or visually select the block and run your mapping (e.g., `<leader>mv`). Output appears below the code; plots appear inline when your terminal/provider supports it.

## Run code from Markdown

Make `MoltenTest.md`:

````markdown
# Molten in Markdown

```python
import sys, numpy as np
print("kernel python:", sys.executable)
np.arange(5)**2
````

```python
import matplotlib.pyplot as plt
plt.plot([0,1,2,3],[0,1,4,9]); plt.show()
```

````

Attach with `:MoltenInit`, place the cursor inside a fence, visually select the lines of code (not the closing backticks), and evaluate. For nicer layout in Markdown, set:

```lua
vim.g.molten_virt_lines_off_by_1 = true
````

## Work with real `.ipynb` notebooks (via Jupytext pairing)

Molten doesn’t edit `.ipynb` directly. The simplest flow is to keep a text source of truth and pair it to an `.ipynb`:

```bash
# in the vault
cat > test_notebook.py <<'PY'
# %% [markdown]
# A tiny paired notebook

# %%
import sys, numpy as np
print("hello from:", sys.executable)
np.arange(9).reshape(3,3)
PY

# pair the .py to an .ipynb alongside it
conda activate obs-electronic-structure
jupytext --set-formats ipynb,py:percent test_notebook.py
```

Open `test_notebook.py` in Neovim, `:MoltenInit`, evaluate cells. The paired `test_notebook.ipynb` can be opened in JupyterLab later with the same content. (If you need full `.ipynb` editing in Vim, use Jupytext; if you need browser-side notebooks driven from Vim, look at jupynium—but Molten + Jupytext is the cleanest for this setup.)

## Inline images: terminals and backends

* **Terminals:** `image.nvim` requires Kitty; the WezTerm provider requires WezTerm. In iTerm you won’t see inline images by design—save figures to files (`plt.savefig(...)`) or open them externally (`os.system("open path.png")`).
* **Matplotlib backend:** if plots don’t show even in Kitty/WezTerm, ensure the inline backend is present:

  ```bash
  conda activate obs-electronic-structure
  conda install -c conda-forge matplotlib-inline -y
  ```

  Or force it at the top of your cell:

  ```python
  import matplotlib; matplotlib.use('module://matplotlib_inline.backend_inline')
  ```

## Tiny quality-of-life tips

* A quick Kitty launcher so you can stay in iTerm day-to-day:

  ```zsh
  alias kvim='kitty --single-instance -d "$PWD" nvim'
  ```
* Auto-choose the provider based on terminal:

  ```lua
  local term = vim.env.TERM_PROGRAM
  if term == "kitty" then
    vim.g.molten_image_provider = "image.nvim"
  elseif term == "WezTerm" then
    vim.g.molten_image_provider = "wezterm"
  end
  ```

## Troubleshooting in one breath

If `:MoltenInit` isn’t a command, run `:UpdateRemotePlugins`, restart, and confirm `vim.g.python3_host_prog` points at your tiny `nvim` env with `pynvim` + `jupyter_client`. If a kernel won’t launch, re-register it from that env:

```bash
conda activate <env>
python -m ipykernel install --user --name <env> --display-name "Python (<name>)"
```

If images fail, verify you’re in Kitty/WezTerm and that ImageMagick is installed (`brew install imagemagick`) for `image.nvim`.

That’s the whole loop: `jup init` in the vault, `:MoltenInit` in Neovim, then run code from `.py`, `.md`, or a Jupytext-paired notebook.

