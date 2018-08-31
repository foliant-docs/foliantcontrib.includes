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
      aliases:
        ...
```

`cache_dir`
:   Path to the directory for cloned repositories. It can be a path relative to the project path or a global one; you can use `~/` shortcut.

    >   **Note**
    >
    >    To include files from remote repositories, the preprocessor clones them. To save time during build, cloned repositories are stored and reused in future builds.

`recursive`
:   Flag that defines whether includes in included documents should be processed.

`aliases`
:   Mapping from aliases to Git repository URLs. Once defined here, an alias can be used to refer to the repository instead of its full URL.

    For example, if you set this alias in the config:

        - includes:
          aliases:
            foo: https://github.com/boo/bar.git
            baz: https://github.com/foo/far.git#develop

    you can include README.md file content from this repository using this syntax:

        <<include>$foo$path/to/doc.md</include>

        <<include>$baz#master$path/to/doc.md</include> 

    Note that in the second example we override the default revision.

## Usage

To include a document from your machine, put the path to it between `<<include>...</include>` tags:

```markdown
Text below is taken from another document.

<<include>/path/to/another/document.md</include>
```

To include a document from a remote Git repository, put its URL between `$`s in front of the document path:

```markdown
Text below is taken from a remote repository.

<<include>
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
<<include>$foo$path/to/doc.md</include>
```

You can also specify a particular branch or revision:

```markdown
Text below is taken from a remote repository on branch develop.

<<include>$foo#develop$path/to/doc.md</include>
```

To include a part of a document between two headings, use the `#Start:Finish` syntax after the file path:

```markdown
Include content from "Intro" up to "Credits":

<<include>sample.md#Intro:Credits</include>

Include content from start up to "Credits":

<<include>sample.md#:Credits</include>

Include content from "Intro" up to the next heading of the same level:

<<include>sample.md#Intro</include>
```


### Options

`sethead`
:   The level of the topmost heading in the included content. Use it to guarantee that the included text doesn't break the parent document's heading order:

        # Title

        ## Subtitle

        <<include sethead="3">
            other.md
        </include>

`nohead`
:   Flag that tells the preprocessor to strip the starting heading from the included content:

        # My Custom Heading

        <<include nohead="true">
            other.md#Original Heading
        </include>

    Default is `false`.

`inline`
:   Flag that tells the preprocessor to replace sequences of whitespace characters of many kinds (including `\r`, `\n`, and `\t`) with single spaces (` `) in the included content, and then to strip leading and trailing spaces. It may be useful in single-line table cells. Default value is `false`.

Options can be combined. For example, use both `sethead` and `nohead` if you want to include a section with a custom heading:

```markdown
# My Custom Heading

<<include sethead="1" nohead="true">
  other.md#Original Heading
</include>
```
