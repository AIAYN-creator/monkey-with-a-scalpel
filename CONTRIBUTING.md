# Contributing

Thanks for your interest. This project builds a laboratory robotic assistant in the open, step by step, with a human approving every step. Please read this page and [PUBLIC_POLICY.md](PUBLIC_POLICY.md) before contributing.

## Scope

This repository covers **Phases 0-2 only**: simulation, hardware and inert phantoms. Contributions involving animals, biological tissue or anything from Phase 3 are out of scope and will not be accepted here.

## How to contribute

1. **Open an issue first** for anything bigger than a typo. Describe what you want to change and why.
2. **Fork or branch**, make your change, and keep it focused: one topic per pull request.
3. **Open a pull request** against `main`. Describe what changed, how you tested it, and anything a reviewer should check.
4. **Wait for review.** `main` is protected: changes land through reviewed pull requests, and the required checks must pass.

## What must never be committed

- Credentials, tokens, API keys, `.env` files, private keys.
- Personal data of collaborators, unless they agreed to be named.
- Anything related to Phase 3: protocols, drafts, correspondence with institutions.
- Receipts, addresses and account details.

The `.gitignore` ignores everything by default and whitelists files one by one. If you add a new file, add it to the whitelist in the same pull request. A CI check fails if a forbidden file is tracked.

## Safety-critical changes

Changes that touch the emergency stop, limit switches, watchdog, motion limits or anything that can move hardware need:

- a description of the failure modes you considered,
- tests or a documented manual test,
- review from the project owner before merging.

Nothing that moves hardware is run by an agent on its own. A human runs it.

## Code style

- Python 3.12. Lint with `ruff check .`; the CI runs it.
- Keep dependencies pinned in `requirements.txt`.
- Comments explain why, not what.
- Code, comments, commit messages and documentation in this repository are in English.

## Commits

- Short imperative subject line, for example `Add gantry model to the simulation`.
- Explain the reason in the body when it is not obvious.
- If an AI assistant helped, say so in a `Supervised-by:` trailer naming the assistant. The human who reviewed and approved the change remains the author and is responsible for it.

## Reporting a safety concern

If you spot something that could make the hardware unsafe, or content that should not be public, open an issue marked `safety` or contact the project owner directly. Do not wait for the next release.

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
