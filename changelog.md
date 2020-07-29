# 1.1.12

-   Add the `wrap_code` and `code_language` attributes to mark up the included content as fence code block or inline code.
-   Prevent to create cache directory when it’s not needed. Improve code style. Refactor a little.

# 1.1.11

-   Add the `extensions` config parameter to process file types different from `.md`.
-   Add the `url` attribute to include content that is available by HTTP(S) URL.

# 1.1.9

-   Support meta 1.3.

# 1.1.8

-   Support meta 1.2.

# 1.1.7

-   Allow to specify custom options for EscapeCode preprocessor as the `escape_code.options` config parameter value.

# 1.1.6

-   Escape regular expression metacharacters in starting and ending headings, IDs, modifiers.

# 1.1.5

-   Remove meta blocks from the included content.

# 1.1.4

-   Allow for the starting and ending headings to be 1-character long.

# 1.1.3

-   Allow to specify IDs of anchors in the `from_id` and `to_id` attributes. Support the `to_end` attribute.

# 1.1.2

-   Fix include statement regex pattern. Tags joined with `|` must be in non-capturing parentheses.

# 1.1.1

-   Support `escape_code` config option. Require Foliant 1.0.10 and escapecode preprocessor 1.0.0.
-   Process `sethead` recursively.

# 1.1.0

-   Support Foliant 1.0.9. Add processing of `!path`, `!project_path`, and `!rel_path` modifiers (i.e. YAML tags) in attribute values of pseudo-XML tags inside the included content. Replace the values that preceded by these modifiers with absolute paths resolved depending on current context.
-   Allow to specify the top-level (“root”) directory of Foliant project that the included file belongs to, with optional `project_root` attribute of the `<include>` tag. This can be necessary to resolve the `!path` and the `!project_path` modifiers in the included content correctly.
-   Allow to specify all necessary parameters of each include statement as attribute values of pseudo-XML tags. Keep legacy syntax for backward compatibility.
-   Update README.

# 1.0.11

-   Take into account the results of work of preprocessors that may be applied before includes within a single Foliant project. Rewrite the currently processed Markdown file path with the path of corresponding file that is located inside the project source directory *only* if the currently processed Markdown file is located inside the temporary working directory *and* the included file is located outside the temporary working directory. Keep all paths unchanged in all other cases.

# 1.0.10

-   Do not rewrite source Markdown file if an error occurs.

# 1.0.9

-   Don’t crash on failed repo sync (i.e. when you’re offline).

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
