# Changelog

## Unreleased

- Reorganize the README around installation and everyday commands; preserve detailed usage, companion-tool, recovery and development guides under `docs/`.
- Read CLI and installed release versions from the same `VERSION` file.
- Include the changelog and split guides in installed releases and their source checksums.
- Describe preview, compression and restore commands in root help.
- Run synthetic regressions on Linux (Python 3.8 / 3.12) and macOS (Python 3.12) through GitHub Actions.
- Extend isolated upgrade acceptance to check command versions and installed documentation.

## 0.1.7

- Share owned subprocess-group cleanup and bounded diagnostics across previews, compression, installation and version probes; handle the macOS zombie-group signal race.
- Add optional preview backend deadlines and restore member/output-byte limits, with explicit limitations and examples.
- Avoid retaining all tar member objects; apply directory metadata from deepest paths first.
- Publish downloaded archives and executables without clobbering existing files; reject symlink targets and retain failed partials.
- Verify managed wrapper content and execute permission before reusing an installed release.
- Extend synthetic regression coverage for failures, concurrency, resource limits and installation integrity.

## 0.1.6

- Use an atomic directory lock for installation on shared filesystems without flock/lockf support.
- Reject concurrent installation with an owner record; never automatically steal a stale lock.
- Preserve v0.1.5 failure evidence and add lock ownership/release regression coverage.

## 0.1.5

- Preflight directory members against the safe restore policy before publishing archives.
- Keep a sibling incomplete status until all restore metadata succeeds, including read-only archive roots.
- Let mutually exclusive `-C` / `-o` choose restore mode independently of filename suffix.
- Stage and serialize installations, preserve complete release entries, and compensate activation failures with retained failure records.
- Add `bio-cli tools` with examples and read-only `bio-cli doctor` path/version diagnostics.
- Add synthetic roundtrip, metadata failure, staged retry and activation rollback regressions.


## 0.1.4

- Show command-specific usage instead of internal Python invocation details.
- Add Chinese option descriptions, bioinformatics examples, format boundaries and pager instructions to peek help.
- Add concise compression/recovery examples and clarify root/subcommand help routing.
- Replace per-character Python escaping with a compiled control-character scan, preserving Unicode and whitespace behavior.

## 0.1.3

- Resolve managed dependency aliases during upgrades and reuse their real executables.
- Reject conflicting same-release dependency overrides; record effective runtime paths.
- Stop tar previews at the requested entry count before reading the last entry's payload.
- Escape terminal controls in binary metadata names and reported errors.
- Add regression tests for alternate wrapper paths, immutable configuration and bounded tar reads.

## 0.1.2

- Exclude the active managed wrapper directory when resolving dependencies during upgrades.
- Add isolated regression coverage for upgrade cycles and non-interactive version probes.

## 0.1.1

- Close standard input during dependency version probes. Older bzip2 versions otherwise wait for input in interactive terminals.

## 0.1.0

- Add bounded bioinformatics previews, non-overwriting compression and archive recovery.
- Add versioned personal installation and pinned upstream CLI downloads.
- Add synthetic acceptance tests covering text, BAM/BCF/CRAM and archive safety.
