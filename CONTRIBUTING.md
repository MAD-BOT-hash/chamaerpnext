# Contributing to SHG for ERPNext

Thank you for your interest in improving the SHG app. This document provides
guidelines for contributing code, tests, and documentation.

## Getting Started

1. Fork this repository.
2. Clone your fork locally.
3. Install the app on a Frappe/ERPNext bench:

```bash
bench get-app shg /path/to/chamaerpnext
bench --site [site-name] install-app shg
bench --site [site-name] migrate
```

## Development Workflow

- Create a feature branch from `main` or `develop`.
  - Use a descriptive name, e.g. `feature/loan-repayment-idempotency`.
- Make focused, minimal changes.
- Update or add tests for any new behavior.
- Update relevant documentation in `docs/`.

## Code Style

- Python code must be formatted with **Black** (line length 100).
- Imports are sorted with **isort**.
- Linting is checked with **flake8**.
- Configuration is in `pyproject.toml`.

Run these before committing:

```bash
black shg tests
isort shg tests
flake8 shg tests --max-line-length=100 --extend-ignore=E203,W503
```

## Testing

- Use **pytest** for standalone unit tests:

```bash
pytest tests/
```

- Use the Frappe test runner for integration tests against an ERPNext site:

```bash
bench --site [site-name] run-tests --app shg
```

- Mark slow or integration tests with the appropriate pytest marker.

## API Changes

- All new whitelisted API methods should return the standard envelope via
  `shg.shg.utils.api_utils.success_response` and `error_response`.
- Add documentation to `docs/api.md` including request/response examples.
- Add rate limiting or input validation for public endpoints.

## Security

- Never commit secrets, API keys, or credentials.
- Store credentials using Frappe Password fields or site config.
- Encrypt sensitive PII when required by the configured compliance settings.

## Pull Request Process

1. Ensure CI passes.
2. Update `CHANGELOG.md` with a brief description of the change.
3. Link any related issue.
4. Request review from a maintainer.

## Reporting Issues

Open a GitHub issue and include:

- ERPNext and Frappe versions
- Steps to reproduce
- Expected and actual behavior
- Relevant traceback or screenshots
