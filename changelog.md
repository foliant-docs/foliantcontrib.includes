# 1.0.12

-   In included files convert paths in tag parameters, which are specified with modifiers !rel_path, !project_path and !path into correct absolute paths. By default the project root for !project_path and !path modifiers is either the current project root, or repository root if it is import from remote repo.
-   Add optional project_root parameter for imports from remote repos. If it is specified — the project root is considered repo_root/project_root_param_value. For local imports this parameter is ignored
-   Add src parameter for specifying the path to included file. This parameter has priority over specifying path in the body. This parameter supports Foliant 1.0.9 modifiers !project_path and !rel_path

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
