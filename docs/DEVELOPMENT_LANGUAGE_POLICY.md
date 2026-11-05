# Repository Language Policy

**Effective:** November 5, 2026.

## Engineering and GitHub communication

**English is the default language for all development communication in this repository.** This applies to:

- Commit messages, branches and PR titles/descriptions, PR reviews and comments, issues, milestones, and GitHub Actions workflow names/log messages authored by the project.
- Code comments, docstrings, test names and assertions, new architecture documents, hardware integration notes, checklists, and technical guides.
- Example configuration labels and the developer-facing UI prototype, unless an example is explicitly demonstrating localization.

The project owner and assistant may continue discussing work in **Turkish in ChatGPT**. GitHub-facing summaries of those discussions should be written in clear English, without changing technical meaning.

## User-facing product languages

The Tihulu application is intended to support **English, Turkish, and German** (and potentially more) through a proper localization system. User-visible application strings are different from developer communication. Do not hard-code translated UI copy into service logic; use language keys and locale files when the production UI is implemented.

## Future README structure

The current public README and existing Turkish guides are **legacy documentation** and are not being removed merely to change the development language. A separate, reviewed documentation milestone will create and maintain:

- `README.md` — English canonical landing page
- `README.tr.md` — Turkish
- `README.de.md` — German

Each README should link to the others with a visible language switcher and accurately describe the **actual** release/deployment status. Do not assert that a feature is implemented merely because an English technical plan exists.

## Existing material and translations

When editing new Stage 4 implementation docs, prefer English filenames without a language suffix. Existing Turkish documentation in `main` remains available until the multilingual-documentation milestone; no silent translation of all legacy documents and no accidental feature-scope changes.
