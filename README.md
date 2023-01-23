[![](https://img.shields.io/pypi/v/foliantcontrib.includes.svg)](https://pypi.org/project/foliantcontrib.includes/) [![](https://img.shields.io/github/v/tag/foliant-docs/foliantcontrib.includes.svg?label=GitHub)](https://github.com/foliant-docs/foliantcontrib.includes)

# Includes for Foliant

Includes preprocessor lets you reuse parts of other documents in your Foliant project sources. It can include from files on your local machine and remote Git repositories. You can include entire documents as well as parts between particular headings, removing or normalizing included headings on the way.

## Installation

```shell
$ pip install foliantcontrib.includes
```

## Config

To enable the preprocessor with default options, add `includes` to `preprocessors` section in the project config:

```yaml
preprocessors:
    - includes
```

The preprocessor has a number of options:

```yaml
preprocessors:
    - includes:
        cache_dir: !path .includescache
        recursive: true
        extensions:
            - md
            - j2
        aliases:
            ...
```

`cache_dir`
:   Path to the directory for cloned Git repositories. It can be a path relative to the project path or a global one; you can use `~/` shortcut.

    >    **Note**
    >
    >    To include files from remote repositories, the preprocessor clones them. To save time during build, cloned repositories are stored and reused in future builds.

`recursive`
:   Flag that defines whether includes in included documents should be processed.

`extensions`
:   List of file extensions that defines the types of files which should be processed looking for include statements. Might be useful if you need to include some content from third-party sources into non-Markdown files like configs, templates, reports, etc. Defaults to `[md]`.

`aliases`
:   Mapping from aliases to Git repository URLs. Once defined here, an alias can be used to refer to the repository instead of its full URL.

    >    **Note**
    >
    >    Aliases are available only within the legacy syntax of include statements (see below).

    For example, if you set this alias in the config:

        - includes:
            aliases:
                foo: https://github.com/boo/bar.git
                baz: https://github.com/foo/far.git#develop

    you can include the content of `doc.md` files from these repositories using the following syntax:

        <include>$foo$path/to/doc.md</include>

        <include>$baz#master$path/to/doc.md</include>

    Note that in the second example the default revision (`develop`) will be overridden with the custom one (`master`).

## Usage

The preprocessor allows two syntax variants for include statements.

The **legacy** syntax is simpler and shorter but less flexible. There are no plans to extend it.

The **new** syntax introduced in version 1.1.0 is stricter and more flexible. It is more suitable for complex cases, and it can be easily extended in the future. This is the preferred syntax.

Both variants of syntax use the `<include>...</include>` tags.

If the included file is specified between the tags, it’s the legacy syntax. If the file is referenced in the tag attributes (`src`, `repo_url`, `path`), it’s the new one.

### The New Syntax

To enforce using the new syntax rules, put no content between `<include>...</include>` tags, and specify a local file or a file in a remote Git repository in tag attributes.

To include a local file, use the `src` attribute:

```markdown
Text below is taken from another document.

<include src="path/to/another/document.md"></include>
```

To include a file from a remote Git repository, use the `repo_url` and `path` attributes:

```markdown
Text below is taken from a remote repository.

<include repo_url="https://github.com/foo/bar.git" path="path/to/doc.md"></include>
```

You have to specify the full remote repository URL in the `repo_url` attribute, aliases are not supported here.

Optional branch or revision can be specified in the `revision` attribute:

```markdown
Text below is taken from a remote repository on branch develop.

<include repo_url="https://github.com/foo/bar.git" revision="develop" path="path/to/doc.md"></include>
```

To include a text from HTTP(S) URL use the `url` attributes:

```markdown
Text below is taken from a remote repository on the default branch.

<include url="https://github.com/foo/bar/path/to/doc.md"></include>
```

> **Note**
>
> For projects in GitHub, you must specify the full path to the raw file, while not specifying the file extension `.md`.
    
``` markdown
<include url="https://github.com/path/to/doc/raw/master/doc" nohead="true"></include>
```

> For projects in GitLab, you must specify the full path to the raw file, and you must specify the file extension `.md`.

```markdown
<include url="https://gitlub.com/path/to/doc/raw/master/doc.md" nohead="true"></include>
```

To include a code snippet, use `wrap_code` and `code_language` attributes:

```markdown
<include src="path/to/some/config.yaml"
wrap_code="triple_backticks" code_language="yaml">
</include>
```

#### Attributes

`src`
:   Path to the local file to include.

`url`
:   HTTP(S) URL of the content that should be included.

`repo_url`
:   Full remote Git repository URL without a revision.

`path`
:   Path to the file inside the remote Git repository.

>    **Note**
>    
>    Path parameter is required!
        Its absence will lead to incorrect operation Foliant.

>    **Note**
>
>    If you are using the new syntax, the `src` attribute is required to include a local file, `url` is required to include a remote file, and the `repo_url` and `path` attributes are required to include a file from a remote Git repository. All other attributes are optional.

>    **Note**
>
>    Foliant 1.0.9 supports the processing of attribute values as YAML. You can precede the values of attributes by the `!path`, `!project_path`, and `!rel_path` modifiers (i.e. YAML tags). These modifiers can be useful in the `src`, `path`, and `project_root` attributes.

`revision`
:   Revision of the Git repository.

`from_heading`
:   Full content of the starting heading when it’s necessary to include some part of the referenced file content. If the `to_heading`, `to_id`, or `to_end` attribute is not specified, the preprocessor cuts the included content to the next heading of the same level. *The referenced heading is included.*

`to_heading`
:   Full content of the ending heading when it’s necessary to include some part of the referenced file content. *The referenced heading will not be included.*

`from_id`
:   ID of the starting heading or starting anchor when it’s necessary to include some part of the referenced file content. The `from_id` attribute has higher priority than `from_heading`. If the `to_heading`, `to_id`, or `to_end` attribute is not specified, the preprocessor cuts the included content to the next heading of the same level. *The referenced id is included.*

> **NOTE:** If you want `from_id` and `to_id` features to work with [anchors](https://foliant-docs.github.io/docs/preprocessors/anchors/), make sure that anchors preprocessor is listed *after* includes in foliant.yml.

`to_id`
:   ID of the ending heading or ending anchor when it’s necessary to include some part of the referenced file content. The `to_id` attribute has higher priority than `to_heading`. *The referenced id will not be included.*

`to_end`
:   Flag that tells the preprocessor to cut to the end of the included content. Otherwise, if `from_heading` or `from_id` is specified, the preprocessor cuts the included content to the next heading of the same level as the starting heading, or the heading that precedes the starting anchor.

    Example:

        ## Some Heading {#custom_id}

        <anchor>one_more_custom_id</anchor>

    Here `Some Heading {#custom_id}` is the full content of the heading, `custom_id` is its ID, and `one_more_custom_id` is the ID of the anchor.

`wrap_code`
:   Attribute that allows to mark up the included content as fence code block or inline code by wrapping the content with additional Markdown syntax constructions. Available values are: `triple_backticks`—to add triple backticks separated with newlines before and after the included content; `triple_tildas`—to do the same but using triple tildas; `single_backticks`—to add single backticks before and after the included content without adding extra newlines. Note that this attribute doesn’t affect the included content. So if the content consists of multiple lines, and the `wrap_code` attribute with the value `single_backticks` is set, all newlines within the content will be kept. To perform forced conversion of multiple lines into one, use the `inline` attribute.

`code_language`
:   Language of the included code snippet that should be additionally marked up as fence code block by using the `wrap_code` attribute with the value `triple_backticks` or `triple_tildas`. Note that the `code_language` attribute doesn’t take effect to inline code that is obtained when the `single_backticks` value is used. The value of this attribute should be a string without whitespace characters, usually in lowercase; examples: `python`, `bash`, `json`.

### Optional Attributes Supported in Both Syntax Variants

`sethead`
:   The level of the topmost heading in the included content. Use it to guarantee that the included text does not break the parent document’s heading order:

        # Title

        ## Subtitle

        <include src="other.md" sethead="3"></include>

`nohead`
:   Flag that tells the preprocessor to strip the starting heading from the included content:

        # My Custom Heading

        <include src="other.md" from_heading="Original Heading" nohead="true"></include>

    Default is `false`.

    By default, the starting heading is included to the output, and the ending heading is not. Starting and ending anchors are never included into the output.

`inline`
:   Flag that tells the preprocessor to replace sequences of whitespace characters of many kinds (including `\r`, `\n`, and `\t`) with single spaces (` `) in the included content, and then to strip leading and trailing spaces. It may be useful in single-line table cells. Default value is `false`.

`project_root`
:   Path to the top-level (“root”) directory of Foliant project that the included file belongs to. This option may be needed to resolve the `!path` and `!project_path` modifiers in the included content properly.

    >    **Note**
    >
    >    By default, if a local file is included, `project_root` points to the top-level directory of the current Foliant project, and if a file in a remote Git repository is referenced, `project_root` points to the top-level directory of this repository. In most cases you don’t need to override the default behavior.

Different options can be combined. For example, use both `sethead` and `nohead` if you need to include a section with a custom heading:

```markdown
# My Custom Heading

<include src="other.md" from_heading="Original Heading" sethead="1" nohead="true"></include>
```

### The Legacy Syntax

This syntax was the only supported in the preprocessor up to version 1.0.11. It’s weird and cryptic, you had to memorize strange rules about `$`, `#` and stuff. The new syntax described above is much cleaner.

The legacy syntax is kept for backward compatibility. To use it, put the reference to the included file between `<include>...</include>` tags.

Local path example:

```markdown
Text below is taken from another document.

<include>path/to/another/document.md</include>
```

The path may be either relative to currently processed Markdown file or absolute.

To include a document from a remote Git repository, put its URL between `$`s before the document path:

```markdown
Text below is taken from a remote repository.

<include>
    $https://github.com/foo/bar.git$path/to/doc.md
</include>
```

If the repository alias is defined in the project config, you can use it instead of the URL:

```yaml
- includes:
    aliases:
        foo: https://github.com/foo/bar.git
```

And then in the source:

```markdown
<include>$foo$path/to/doc.md</include>
```

You can also specify a particular branch or revision:

```markdown
Text below is taken from a remote repository on branch develop.

<include>$foo#develop$path/to/doc.md</include>
```

To include a part of a document between two headings, use the `#Start:Finish` syntax after the file path:

```markdown
Include content from “Intro” up to “Credits”:

<include>sample.md#Intro:Credits</include>

Include content from start up to “Credits”:

<include>sample.md#:Credits</include>

Include content from “Intro” up to the next heading of the same level:

<include>sample.md#Intro</include>
```

In the legacy syntax, problems may occur with the use of `$`, `#`, and `:` characters in filenames and headings, since these characters may be interpreted as delimiters.
