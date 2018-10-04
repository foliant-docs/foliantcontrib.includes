# 1.0.9 (under development)

-   Don't crash on failed repo sync (i.e. when you're offline).

# 1.0.8

-   Require at least one space after hashes in the beginning of each heading.
-   Add `inline` option to the `<include>` tag.
-   Fix the bug: do not ignore empty lines after headings when using `sethead`.
-   Fix the bug: allow to use less than 3 characters in the heading content.
-   Do not mark as headings the strings that contain more than 6 leading hashes. If shifted heading level is more than 6, mark the heading content as bold paragraph text, not as heading.

# 1.0.7

-   Fix paths resolving in case of recursive processing of include statements.
-   Allow revision markers in repo aliases.

# 1.0.6

-   Fix logging in file search method.
-   Fix top heading level calculation.

# 1.0.5

-   Use paths that are relative to the current processed Markdown file.
-   Fix `sethead` behavior for headings that contains hashes (`#`).

# 1.0.4

-   Fix the pattern for headings detection.

# 1.0.3

-   Allow hashes (`#` characters) in the content of headings.

# 1.0.2

-   Fix inappropriate translation of image URLs into local paths.

# 1.0.1

-   Fix git repo name detection when the repo part contains full stops.
