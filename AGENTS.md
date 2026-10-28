# X-Orbit engineering standards

The active integrated application is in GuardianChat/. Start with GuardianChat/DEVELOPER_GUIDE.md and GuardianChat/READABILITY_REVIEW.md. The original GuardianLab SDK modules remain independent build targets.

## Human-readable changes

- Preserve behavior, public interfaces, persisted identifiers, security boundaries and data handling unless the human explicitly approves a behavior change.
- Before editing, trace callers, dependencies and current behavior; record a prioritized plan for broad work. Prefer one small responsibility per change.
- Use descriptive, consistent names. Keep existing public/API/database names when renaming would create compatibility risk.
- Add brief module/function descriptions where they help navigation. Explain decisions, assumptions, units, side effects, concurrency, privacy constraints and unusual cases. Avoid comments that merely repeat a statement.
- Keep comments and documentation accurate when code changes. Do not add boilerplate or speculative abstractions.
- Remove code only after checking dynamic dispatch, native/WebView bridges, static asset lists, imports and callers, with evidence that it is unused.
- Establish relevant checks before refactoring; run them afterward. Add focused tests for behavior at risk, including authorization and failures. Report failures/skips/physical-device gaps honestly.
- Keep bug fixes, feature changes and readability-only work in separate focused commits. Commit messages should state the concrete change; descriptions should include validation and material limits.
- Update the developer guide when ownership, data flow, run/test commands or feature entry points change.
- Preserve approved visuals, navigation, GuardianLab protection, existing user records and secrets handling. Do not rename internal Gamebox/Market tables or routes to match newer product labels.
- Do not merge main, introduce paid services, enable real money, deploy publicly or perform destructive migrations without explicit authorization.
- Keep credentials, private data, device account preferences, local backups and runtime receipts out of Git.

## Verification baseline

Version 41 ran 388 Python tests: 375 pass and 13 existing test_rating.py errors refer to obsolete ranking contracts. Keep that gap visible; do not skip/delete tests or restore old ranking behavior just to produce a green result.
JavaScript regression scripts run directly with Node; Android uses Gradle/JDK 21. See the guide for commands and optional dependencies.
