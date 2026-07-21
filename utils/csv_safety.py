"""CSV formula-injection defense.

Excel/Sheets treat a cell as a formula if it *starts with* `=`, `+`, `-`,
or `@` (Excel also treats a leading tab the same way) -- so a malicious
issue title like `=cmd|'/c calc'!A1` would execute if written to a CSV
verbatim and later opened in a spreadsheet program. Neutralized here by
prefixing a leading apostrophe, the standard fix: spreadsheet software
displays the value as plain text (the apostrophe becomes invisible) rather
than evaluating it. Applied to every field of every exported row, not just
ones a form technically allows a user to type into (title, description,
category, names, etc. all pass through this).
"""

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t")


def neutralize(value) -> str:
    """Return `value` as a CSV-safe string.

    `None` becomes an empty string. Anything else is stringified first (so
    ints/dates from a DB row can be passed straight through) and then
    prefixed with a leading apostrophe if it starts with a character a
    spreadsheet would interpret as the start of a formula.
    """
    if value is None:
        return ""
    text = str(value)
    if text.startswith(_DANGEROUS_PREFIXES):
        return "'" + text
    return text
