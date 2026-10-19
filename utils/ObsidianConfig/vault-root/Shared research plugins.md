# Shared research plugins

`ocreate` copies `/Users/gradyclopton/utils/ObsidianConfig` and checks that the maintained plugin set is present and enabled before creating a vault.

The shared builds were refreshed from `research_2025` on 2026-10-17: Study Studio (including annotations and citation/evidence navigation), Slide Studio, Image Gallery, Ink Studio, Math Studio, Code Links, Research Outline, and Pandoc Reference List. Their command shortcuts are carried into new vaults. Existing Research Colors remains included.

Plugin code is copied separately from research data. New vaults start with empty practice state and image favorites. No research annotations, citation records, bibliography, or paper notes are copied. Pandoc's automatic Zotero pull is off in the clean defaults; configure a bibliography when needed.

When refreshing shared builds, update the plugin files in the template and validate their hashes against the accepted deployed builds. Do not copy vault-specific plugin data or credentials from a research vault. The Chemistry setup receipt records the source paths and installed hashes.

On first open, register the created folder through Obsidian's Open folder as vault dialog if it is not already known to Obsidian. The shell vault registry and Obsidian's own registry are separate.
