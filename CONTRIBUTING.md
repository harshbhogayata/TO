# Contributing to TalentOrbit

Thank you for contributing! This document explains how to contribute code, documentation, and fixes in a way that keeps the project healthy and reviewable.

- Fork the repo and create a feature branch from `main` named `feature/<short-description>` or `fix/<short-description>`.
- Keep PRs small and focused. Large features should be split into smaller PRs when possible.
- Write tests for new behavior and make sure existing tests pass.
- Run linters and formatters before opening a PR:

```bash
# frontend
npm run lint
npm run format

# backend (example using pre-commit hooks or flake8/isort)
# run tests
pytest
```

- Commit message style: Use present-tense, imperative messages and include a short description and the motivation. Example:

```
feat(auth): add two-factor authentication via SMS

Adds optional TFA for all accounts with phone numbers. Includes tests and docs.
```

- Pull Request checklist:
  - [ ] Clear title and description
  - [ ] Linked issue (if applicable)
  - [ ] Tests added/updated
  - [ ] Lint/format passed
  - [ ] Updated documentation (README, inline docs)

- Review process:
  - At least one approving review required before merge
  - Keep an eye on CI status; fix failing checks

- Branch protection:
  - `main` is protected; use PRs for all merges

Thanks — your contributions help keep TalentOrbit secure and reliable.
