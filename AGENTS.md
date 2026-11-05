# Development Communication and Localization Guidelines

These guidelines apply to the Tihulu Survival Kit project, including the public application repository and the private planning repository.

## Preferred language for GitHub collaboration

Use **English by default** for GitHub-facing development communication: commit messages, pull request titles and descriptions, issue discussions, review comments, technical summaries, plans, checkpoints, changelogs, and engineering notes.

The project owner may communicate with the assistant in **Turkish**; respond in Turkish in the chat, while writing GitHub-facing collaboration and development messages in English.

## Multilingual content is welcome — not an English-only rule

**English is a preference for collaboration, not a strict restriction on repository files.**

- User-facing UI strings, localization files, help text, screenshots, sample content, and language-specific documentation may be in **Turkish, German, English, or another supported language**.
- Appropriate structures include `locales/tr/`, `locales/de/`, `locales/en/`, `docs/tr/`, `docs/de/`, and localized filenames such as `README.tr.md` / `README.de.md`. These paths are examples, not required structure.
- Keep translation content in its own language rather than translating it into English merely to satisfy a repository convention.
- Code comments and technical documentation should usually be English, but localized explanations or examples are fine when relevant.
- Existing Turkish or German documents can remain. Do not mass-rename, rewrite, or delete them just to enforce a language convention.
- Do **not** add an automated English-only lint or CI gate.
- The public README may later have coordinated English/Turkish/German versions; do not treat that future work as already completed.

Always preserve technical meaning, confidentiality, and the actual implementation status when transferring information between the project chat and GitHub.
