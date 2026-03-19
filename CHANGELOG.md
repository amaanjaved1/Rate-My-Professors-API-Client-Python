# Changelog

## 2.1.0

- **Helpers** (formerly dedupe): `normalize_comment` strips HTML by default and supports `strip_punctuation`; `is_valid_comment` returns a `ValidationResult` with `valid` and `issues` instead of a boolean, checking for empty, too short, all caps, excessive repeats, and no alphabetic characters.
- **Ingest example**: Updated to use `is_valid_comment(...).valid` for the new return type.
