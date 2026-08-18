# Changelog

All notable changes to the SHG app for ERPNext are documented in this file.

## [Unreleased]

### Added
- `pyproject.toml` with Black, isort, flake8, mypy, and pytest configuration.
- `shg.shg.utils.api_utils` for standardized API response envelopes and validation helpers.
- `shg.shg.api.health` health-check endpoint for monitoring app, DB, scheduler, and payment config status.
- GitHub Actions CI workflow for JSON fixture validation, linting, and test collection.
- `.gitignore` and `MANIFEST.in` updated to exclude `__pycache__` and `.pyc` files.
- `CONTRIBUTING.md` and `CHANGELOG.md`.

### Changed
- Removed duplicate `SHG Contribution` entry in `hooks.py` `doctype_js` mapping.
- Removed tracked `__pycache__` artifacts from the repository.

### Fixed
- Repository hygiene: Python cache files and local environment files are now ignored.
