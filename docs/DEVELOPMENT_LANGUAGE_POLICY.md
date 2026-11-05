# Development Communication and Localization Policy

This repository's canonical guidance is [AGENTS.md](../AGENTS.md), committed on `main` and shared with the private planning repository.

## English for GitHub collaboration, not for every file

Use **English by default** for GitHub issues, pull requests, commit messages, reviews, design discussions, developer notes, and other engineering communication. ChatGPT conversations with the project owner may remain in **Turkish**.

**This is a flexible convention, not an English-only repository policy.** Turkish, German, English, and additional languages are welcome for:

- Application UI translations, locale resources, strings, sample content, and localized interface prototypes.
- Language-specific documentation and help pages (for example, `docs/tr/`, `docs/de/`, and `docs/en/`).
- Translation-oriented comments, screenshots, test fixtures, accessibility materials, and examples.
- Existing documentation, including Turkish guides already present on `main`.

Technical documentation and code comments normally use English when they address collaborators across languages, but **they do not need to be translated or renamed when the purpose is explicitly localized**. No English-only CI check, forced file renaming, or deletion of historical Turkish/German material.

## Future multilingual README

The planned README structure may use:

- `README.md` — English default
- `README.tr.md` — Turkish
- `README.de.md` — German

These are future documentation targets, not a claim that all three are already available. Preserve accurate implementation and hardware-test status in every language.

The same language preference applies to the private `Tihulu/tihulu-survival-kit-plan` repository.
