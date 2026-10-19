# Research Colors

Private fork of Colored Text 1.0.0, upstream commit 60d98f033e8dcf144d60d585bf8d489683d67e49. Preserve the original MIT license and attribution. No publishing remote is configured.

The only functional customization recovered from the docs and shared installed bundles adds font-weight:bold when coloring selected text, in both the context menu and command path. This source fork preserves those two edits exactly. It deliberately retains the existing span syntax and existing notes.

Separate ID research-colors prevents community Colored Text updates from replacing our build. During migration copy original data.json once and remap colored-text: hotkeys to research-colors: (suffix unchanged). Keep the original installed but disabled for rollback. Never enable both at once. Do not commit personal settings. Build with npm ci --ignore-scripts and npm run build; test first in code_links_lab.
