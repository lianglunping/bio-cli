# Changelog

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
