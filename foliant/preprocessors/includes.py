import re
from io import StringIO
from pathlib import Path
from subprocess import run, CalledProcessError, PIPE, STDOUT

from foliant.preprocessors.base import BasePreprocessor
from foliant.preprocessors import escapecode


class Preprocessor(BasePreprocessor):
    defaults = {
        'recursive': True,
        'cache_dir': Path('.includescache'),
        'aliases': {}
    }
    tags = 'include',

    _heading_pattern = re.compile(
        r'^(?P<hashes>\#{1,6})\s+(?P<content>.*\S+)(?P<tail>\s*)$',
        flags=re.MULTILINE
    )
    _image_pattern = re.compile(r'\!\[(?P<caption>.*)\]\((?P<path>((?!:\/\/).)+)\)')
    _tag_body_pattern = re.compile(
        r'(\$(?P<repo>[^\#^\$]+)(\#(?P<revision>[^\$]+))?\$)?' +
        r'(?P<path>[^\#]+)' +
        r'(\#(?P<from_heading>[^:]*)(:(?P<to_heading>.+))?)?'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._cache_path = self.project_path / self.options['cache_dir']

        self.logger = self.logger.getChild('includes')

        self.logger.debug(f'Preprocessor inited: {self.__dict__}')

    def _find_file(
        self,
        file_name: str,
        lookup_dir: Path
    ) -> Path or None:
        '''Find a file in a directory by name. Check subdirectories recursively.

        :param file_name: Name of the file
        :lookup_dir: Starting directory

        :returns: Path to the found file or None if the file was not found
        :raises: FileNotFoundError
        '''

        self.logger.debug(f'Trying to find the file {file_name} inside the directory {lookup_dir}')

        result = None

        for item in lookup_dir.rglob('*'):
            if item.name == file_name:
                result = item
                break
        else:
            raise FileNotFoundError(file_name)

        self.logger.debug(f'File found: {result}')

        return result

    def _sync_repo(
        self,
        repo_url: str,
        revision: str or None = None
    ) -> Path:
        '''Clone a Git repository to the cache dir. If it has been cloned before, update it.

        :param repo_url: Repository URL
        :param revision: Revision: branch, commit hash, or tag

        :returns: Path to the cloned repository
        '''

        repo_name = repo_url.split('/')[-1].rsplit('.', maxsplit=1)[0]
        repo_path = (self._cache_path / repo_name).resolve()

        self.logger.debug(f'Synchronizing with repo; URL: {repo_url}, revision: {revision}')

        try:
            self.logger.debug(f'Cloning repo {repo_url} to {repo_path}')

            run(
                f'git clone {repo_url} {repo_path}',
                shell=True,
                check=True,
                stdout=PIPE,
                stderr=STDOUT
            )

        except CalledProcessError as exception:
            if repo_path.exists():
                self.logger.debug('Repo already cloned; pulling from remote')

                try:
                    run(
                        'git pull',
                        cwd=repo_path,
                        shell=True,
                        check=True,
                        stdout=PIPE,
                        stderr=STDOUT
                    )

                except CalledProcessError as exception:
                    self.logger.warning(str(exception))

            else:
                self.logger.error(str(exception))

        if revision:
            run(
                f'git checkout {revision}',
                cwd=repo_path,
                shell=True,
                check=True,
                stdout=PIPE,
                stderr=STDOUT
            )

        return repo_path

    def _shift_headings(
        self,
        content: str,
        shift: int
    ) -> str:
        '''Shift Markdown headings in a string by a given value. The shift
        can be positive or negative.

        :param content: Markdown content
        :param shift: Heading shift

        :returns: Markdown content with headings shifted by ``shift``
        '''

        def _sub(heading):
            new_heading_level = len(heading.group('hashes')) + shift

            self.logger.debug(
                f'Shift heading level to {new_heading_level}, heading content: {heading.group("content")}'
            )

            if new_heading_level <= 6:
                return f'{"#" * new_heading_level} {heading.group("content")}{heading.group("tail")}'

            else:
                self.logger.debug('New heading level is out of range, using bold paragraph text instead of heading')

                return f'**{heading.group("content")}**{heading.group("tail")}'

        return self._heading_pattern.sub(_sub, content)

    def _find_top_heading_level(
        self,
        content: str
    ) -> int:
        '''Find the highest level heading (i.e. having the least '#'s)
        in a Markdown string.

        :param content: Markdown content

        :returns: Maximum heading level detected; if no heading is found, 0 is returned
        '''

        result = float('inf')

        for heading in self._heading_pattern.finditer(content):
            heading_level = len(heading.group('hashes'))

            if heading_level < result:
                result = heading_level

            self.logger.debug(f'Maximum heading level: {result}')

        return result if result < float('inf') else 0

    def _cut_from_heading_to_heading(
        self,
        content: str,
        from_heading: str or None = None,
        to_heading: str or None = None,
        from_id: str or None = None,
        to_id: str or None = None,
        sethead: int or None = None,
        nohead: bool = False
    ) -> str:
        '''Cut part of Markdown string between two headings
        defined by their content or their IDs,
        set internal heading level, and remove top heading.

        If only the starting heading is defined, cut to the next heading
        of the same level.

        If neither starting nor ending heading is defined,
        the whole string is returned.

        Heading shift and top heading elimination are optional.

        :param content: Markdown content
        :param from_heading: Starting heading
        :param to_heading: Ending heading (will not be incuded in the output)
        :param from_id: ID of starting heading;
            this argument has higher priority than ``from_heading``
        :param to_id: ID of ending heading (the heading itself will not be incuded in the output);
            this argument has higher priority than ``to_heading``
        :param sethead: Level of the topmost heading in the included content
        :param nohead: Flag that tells to strip the starting heading from the included content

        :returns: Part of the Markdown content between headings with internal headings adjusted
        '''

        self.logger.debug(
            'Cutting from heading to heading: ' +
            f'from_heading: {from_heading}, to_heading: {to_heading}, ' +
            f'from_id: {from_id}, to_id: {to_id}, ' +
            f'sethead: {sethead}, nohead: {nohead}'
        )

        from_heading_pattern = None

        if from_id:
            self.logger.debug('Starting heading is defined by its ID')

            from_heading_pattern = re.compile(
                r'^\#{1,6}\s+.+\S+\s+\{\#' + rf'{from_id}' + r'\}\s*$',
                flags=re.MULTILINE
            )

        elif from_heading:
            self.logger.debug('Starting heading is defined by its content')

            from_heading_pattern = re.compile(
                r'^\#{1,6}\s+' + rf'{from_heading}\s*$',
                flags=re.MULTILINE
            )

        else:
            self.logger.debug('Starting heading is not defined')

        if from_heading_pattern:
            if not from_heading_pattern.findall(content):
                self.logger.debug(
                    'Defined starting heading is not found in the included content, ' +
                    'so the included content must be skipped'
                )

                return ''

            from_heading_line = from_heading_pattern.findall(content)[0]
            from_heading_level = len(self._heading_pattern.match(from_heading_line).group('hashes'))

            result = from_heading_pattern.split(content)[1]

        else:
            content_buffer = StringIO(content)

            first_line = content_buffer.readline()

            if self._heading_pattern.fullmatch(first_line):
                from_heading_line = first_line
                from_heading_level = len(self._heading_pattern.match(from_heading_line).group('hashes'))
                result = content_buffer.read()

            else:
                from_heading_line = ''
                from_heading_level = self._find_top_heading_level(content)
                result = content

        self.logger.debug(f'Level of starting heading of the included content: {from_heading_level}')

        to_heading_pattern = None

        if to_id:
            self.logger.debug('Ending heading is defined by its ID')

            to_heading_pattern = re.compile(
                r'^\#{1,6}\s+.+\S+\s+\{\#' + rf'{to_id}' + r'\}\s*$',
                flags=re.MULTILINE
            )

        elif to_heading:
            self.logger.debug('Ending heading is defined by its content')

            to_heading_pattern = re.compile(
                r'^\#{1,6}\s+' + rf'{to_heading}\s*$',
                flags=re.MULTILINE
            )

        else:
            self.logger.debug('Ending heading is not defined')

            if from_heading_pattern:
                self.logger.debug(
                    'Since starting heading is defined, cutting to the next heading of the same level'
                )

                to_heading_pattern = re.compile(
                    rf'^\#{{1,{from_heading_level}}}\s+\S+.+$',
                    flags=re.MULTILINE
                )

            else:
                self.logger.debug(
                    'Since starting heading is not defined, using the whole included content'
                )

        if to_heading_pattern:
            result = to_heading_pattern.split(result)[0]

        if nohead:
            self.logger.debug(
                'Since nohead option is specified, do not use starting heading in the output'
            )
        else:
            self.logger.debug(
                'Since nohead option is not specified, including starting heading into the output'
            )

            result = from_heading_line + result

        if sethead:
            if sethead > 0:
                self.logger.debug(
                    'Since sethead option is specified, shifting headings levels in the included content'
                )

                result = self._shift_headings(
                    result,
                    sethead - from_heading_level
                )

        return result

    def _adjust_image_paths(
        self,
        content: str,
        markdown_file_path: Path
    ) -> str:
        '''Locate images referenced in a Markdown string and replace their paths
        with the absolute ones.

        :param content: Markdown content
        :param markdown_file_path: Path to the Markdown file containing the content

        :returns: Markdown content with absolute image paths
        '''

        def _sub(image):
            image_caption = image.group('caption')
            image_path = (markdown_file_path.parent / Path(image.group('path'))).resolve()

            self.logger.debug(
                f'Updating image reference; user specified path: {image.group("path")}, ' +
                f'absolute path: {image_path}, caption: {image_caption}'
            )

            return f'![{image_caption}]({image_path})'

        return self._image_pattern.sub(_sub, content)

    def _adjust_paths_in_tags_attributes(
        self,
        content: str,
        modifier: str,
        base_path: Path
    ) -> str:
        '''Locate pseudo-XML tags in Markdown string. Replace the paths
        that are specified as values of pseudo-XML tags attributes
        preceded by modifiers (i.e. YAML tags such as ``!path``)
        with absolute ones based on ``base_path``.

        :param content: Markdown content
        :param modifier: Modifier (i.e. YAML tag) that precedes an attribute value
        :param base_path: Base path that the replaced paths must be relative to

        :returns: Markdown content with absolute paths in attributes
            of pseudo-XML tags
        '''

        def sub_tag(match):
            def sub_path_attribute(match):
                quote = match.group('quote')
                modifier = match.group('modifier')
                resolved_path = (base_path / match.group('path')).resolve()
                adjusted_quoted_attribute_value = f'{quote}{modifier}{resolved_path}{quote}'

                self.logger.debug(
                    'Updating path in tag attribute value; ' +
                    f'user specified value: {quote}{modifier}{match.group("path")}{quote}, ' +
                    f'adjusted value: {adjusted_quoted_attribute_value}'
                )

                return adjusted_quoted_attribute_value

            path_attribute_pattern = re.compile(
                r'''(?P<quote>'|")''' +
                rf'(?P<modifier>\s*{modifier}\s+)' +
                r'(?P<path>.+?)' +
                r'(?P=quote)',
                re.DOTALL
            )

            open_tag = path_attribute_pattern.sub(sub_path_attribute, match.group('open_tag'))
            body = match.group('body')
            closing_tag = match.group('closing_tag')

            return f'{open_tag}{body}{closing_tag}'

        tag_pattern = re.compile(
            r'(?<!\<)(?P<open_tag><(?P<tag>\S+)(?:\s[^\<\>]*)?\>)'
            r'(?P<body>.*?)'
            r'(?P<closing_tag>\<\/(?P=tag)\>)',
            re.DOTALL
        )

        return tag_pattern.sub(sub_tag, content)

    def _get_src_file_path(
        self,
        markdown_file_path: Path
    ) -> Path:
        '''Translate the path of Markdown file that is located inside the temporary working directory
        into the path of the corresponding Markdown file that is located inside the source directory
        of Foliant project.

        :param markdown_file_path: Path to Markdown file that is located inside the temporary working directory

        :returns: Mapping of Markdown file path to the source directory
        '''

        path_relative_to_working_dir = markdown_file_path.relative_to(self.working_dir.resolve())

        self.logger.debug(
            'Currently processed Markdown file path relative to working dir: ' +
            f'{path_relative_to_working_dir}'
        )

        path_mapped_to_src_dir = (
            self.project_path.resolve() /
            self.config['src_dir'] /
            path_relative_to_working_dir
        )

        self.logger.debug(
            'Currently processed Markdown file path mapped to source dir: ' +
            f'{path_mapped_to_src_dir}'
        )

        return path_mapped_to_src_dir

    def _get_included_file_path(
        self,
        user_specified_path: str or Path,
        current_processed_file_path: Path
    ) -> Path:
        '''Resolve user specified path to the local included file.

        :param user_specified_path: User specified string that represents
            the path to a local file

        :param current_processed_file_path: Path to the currently processed Markdown file
            that contains include statements

        :returns: Local path of the included file relative to the currently processed Markdown file
        '''

        self.logger.debug(f'Currently processed Markdown file: {current_processed_file_path}')

        included_file_path = (current_processed_file_path.parent / user_specified_path).resolve()

        self.logger.debug(f'User-specified included file path: {included_file_path}')

        if (
            self.working_dir.resolve() in current_processed_file_path.parents
            and
            self.working_dir.resolve() not in included_file_path.parents
        ):
            self.logger.debug(
                'Currently processed file is located inside the working dir, ' +
                'but included file is located outside the working dir. ' +
                'So currently processed file path should be rewritten with the path of corresponding file ' +
                'that is located inside the source dir'
            )

            included_file_path = (
                self._get_src_file_path(current_processed_file_path).parent / user_specified_path
            ).resolve()

        else:
            self.logger.debug(
                'Using these paths without changes'
            )

        self.logger.debug(f'Finally, included file path: {included_file_path}')

        return included_file_path

    def _process_include(
        self,
        included_file_path: Path,
        project_root_path: Path or None = None,
        from_heading: str or None = None,
        to_heading: str or None = None,
        from_id: str or None = None,
        to_id: str or None = None,
        sethead: int or None = None,
        nohead: bool = False
    ) -> str:
        '''Replace a local include statement with the file content. Necessary
        adjustments are applied to the content: cut between certain headings,
        strip the top heading, set heading level.

        :param included_file_path: Path to the included file
        :param project_root_path: Path to the “root” directory of Foliant project
            that the currently processed Markdown file belongs to
        :param from_heading: Include starting from this heading
        :param to_heading: Include up to this heading (not including the heading itself)
        :param from_heading: Include starting from the heading that has this ID
        :param to_heading: Include up to the heading that has this ID
            (not including the heading itself)
        :param sethead: Level of the topmost heading in the included content
        :param nohead: Flag that tells to strip the starting heading from the included content

        :returns: Included file content
        '''

        self.logger.debug(
            f'Included file path: {included_file_path}, from heading: {from_heading}, ' +
            f'to heading: {to_heading}, sethead: {sethead}, nohead: {nohead}'
        )

        with open(included_file_path, encoding='utf8') as included_file:
            included_content = included_file.read()

            if self.config.get('escape_code', False):
                self.logger.debug(
                    'Since escape_code mode is on, applying the escapecode preprocessor ' +
                    'to the included file content'
                )

                included_content = escapecode.Preprocessor(
                    self.context,
                    self.logger,
                    self.quiet,
                    self.debug,
                    {}
                ).escape(included_content)

            included_content = self._cut_from_heading_to_heading(
                included_content,
                from_heading,
                to_heading,
                from_id,
                to_id,
                sethead,
                nohead
            )

            included_content = self._adjust_image_paths(included_content, included_file_path)

            if project_root_path:
                included_content = self._adjust_paths_in_tags_attributes(
                    included_content,
                    '!path',
                    project_root_path
                )

                included_content = self._adjust_paths_in_tags_attributes(
                    included_content,
                    '!project_path',
                    project_root_path
                )

            included_content = self._adjust_paths_in_tags_attributes(
                included_content,
                '!rel_path',
                included_file_path.parent
            )

        return included_content

    def process_includes(
        self,
        markdown_file_path: Path,
        content: str,
        project_root_path: Path or None = None,
        sethead: int or None = None
    ) -> str:
        '''Replace all include statements with the respective file contents.

        :param markdown_file_path: Path to currently processed Markdown file
        :param content: Markdown content
        :param project_root_path: Path to the “root” directory of Foliant project
            that the currently processed Markdown file belongs to
        :param sethead: Level of the topmost heading in the content,
            it may be set when the method is called recursively

        :returns: Markdown content with resolved includes
        '''

        markdown_file_path = markdown_file_path.resolve()

        self.logger.debug(f'Processing Markdown file: {markdown_file_path}')

        processed_content = ''

        include_statement_pattern = re.compile(
            rf'((?<!\<)\<(?:{"|".join(self.tags)})(?:\s[^\<\>]*)?\>.*?\<\/(?:{"|".join(self.tags)})\>)',
            flags=re.DOTALL
        )

        content_parts = include_statement_pattern.split(content)

        for content_part in content_parts:
            include_statement = self.pattern.fullmatch(content_part)

            if include_statement:
                current_project_root_path = project_root_path

                body = self._tag_body_pattern.match(include_statement.group('body').strip())
                options = self.get_options(include_statement.group('options'))

                self.logger.debug(
                    f'Processing include statement; body: {body}, options: {options}, ' +
                    f'current project root path: {current_project_root_path}'
                )

                current_sethead = sethead

                self.logger.debug(
                    f'Current sethead: {current_sethead}, ' +
                    f'user-specified sethead: {options.get("sethead")}'
                )

                if options.get('sethead'):
                    if current_sethead:
                        current_sethead += options['sethead'] - 1

                    else:
                        current_sethead = options['sethead']

                    self.logger.debug(f'Set new current sethead: {current_sethead}')

                # If the tag body is not empty, the legacy syntax is expected:
                #
                # <include project_root="..." sethead="..." nohead="..." inline="...">
                # ($repo_url#revision$path|src)#from_heading:to_heading
                # </include>
                #
                # If the tag body is empty, the new syntax is expected:
                #
                # <include
                #     repo_url="..." revision="..." path="..." | src="..."
                #     project_root="..."
                #     from_heading="..." to_heading="..."
                #     from_id="..." to_id="..."
                #     sethead="..." nohead="..." inline="..."
                # ></include>

                if body:
                    self.logger.debug('Using the legacy syntax rules')

                    if body.group('repo'):
                        self.logger.debug('File in Git repository referenced')

                        repo_from_alias = self.options['aliases'].get(body.group('repo'))

                        revision = None

                        if repo_from_alias:
                            self.logger.debug(f'Alias found: {body.group("repo")}, resolved as: {repo_from_alias}')

                            if '#' in repo_from_alias:
                                repo_url, revision = repo_from_alias.split('#', maxsplit=1)

                            else:
                                repo_url = repo_from_alias

                        else:
                            repo_url = body.group('repo')

                        if body.group('revision'):
                            revision = body.group('revision')

                            self.logger.debug(
                                f'Highest priority revision specified in the include statement: {revision}'
                            )

                        self.logger.debug(f'Repo URL: {repo_url}, revision: {revision}')

                        repo_path = self._sync_repo(repo_url, revision)

                        self.logger.debug(f'Local path of the repo: {repo_path}')

                        included_file_path = repo_path / body.group('path')

                        if included_file_path.name.startswith('^'):
                            included_file_path = self._find_file(
                                included_file_path.name[1:], included_file_path.parent
                            )

                        self.logger.debug(f'Resolved path to the included file: {included_file_path}')

                        current_project_root_path = (
                            repo_path / options.get('project_root', '')
                        ).resolve()

                        self.logger.debug(f'Set new current project root path: {current_project_root_path}')

                        processed_content_part = self._process_include(
                            included_file_path=included_file_path,
                            project_root_path=current_project_root_path,
                            from_heading=body.group('from_heading'),
                            to_heading=body.group('to_heading'),
                            sethead=current_sethead,
                            nohead=options.get('nohead')
                        )

                    else:
                        self.logger.debug('Local file referenced')

                        included_file_path = self._get_included_file_path(body.group('path'), markdown_file_path)

                        if included_file_path.name.startswith('^'):
                            included_file_path = self._find_file(
                                included_file_path.name[1:], included_file_path.parent
                            )

                        self.logger.debug(f'Resolved path to the included file: {included_file_path}')

                        if options.get('project_root'):
                            current_project_root_path = (
                                markdown_file_path.parent / options.get('project_root')
                            ).resolve()

                            self.logger.debug(f'Set new current project root path: {current_project_root_path}')

                        processed_content_part = self._process_include(
                            included_file_path=included_file_path,
                            project_root_path=current_project_root_path,
                            from_heading=body.group('from_heading'),
                            to_heading=body.group('to_heading'),
                            sethead=current_sethead,
                            nohead=options.get('nohead')
                        )

                else:
                    self.logger.debug('Using the new syntax rules')

                    if options.get('repo_url') and options.get('path'):
                        self.logger.debug('File in Git repository referenced')

                        repo_path = self._sync_repo(options.get('repo_url'), options.get('revision'))

                        self.logger.debug(f'Local path of the repo: {repo_path}')

                        included_file_path = repo_path / options['path']

                        self.logger.debug(f'Resolved path to the included file: {included_file_path}')

                        current_project_root_path = (
                            repo_path / options.get('project_root', '')
                        ).resolve()

                        self.logger.debug(f'Set new current project root path: {current_project_root_path}')

                        processed_content_part = self._process_include(
                            included_file_path=included_file_path,
                            project_root_path=current_project_root_path,
                            from_heading=options.get('from_heading'),
                            to_heading=options.get('to_heading'),
                            from_id=options.get('from_id'),
                            to_id=options.get('to_id'),
                            sethead=current_sethead,
                            nohead=options.get('nohead')
                        )

                    elif options.get('src'):
                        self.logger.debug('Local file referenced')

                        included_file_path = self._get_included_file_path(options.get('src'), markdown_file_path)

                        self.logger.debug(f'Resolved path to the included file: {included_file_path}')

                        if options.get('project_root'):
                            current_project_root_path = (
                                markdown_file_path.parent / options.get('project_root')
                            ).resolve()

                            self.logger.debug(f'Set new current project root path: {current_project_root_path}')

                        processed_content_part = self._process_include(
                            included_file_path=included_file_path,
                            project_root_path=current_project_root_path,
                            from_heading=options.get('from_heading'),
                            to_heading=options.get('to_heading'),
                            from_id=options.get('from_id'),
                            to_id=options.get('to_id'),
                            sethead=current_sethead,
                            nohead=options.get('nohead')
                        )

                    else:
                        self.logger.warning(
                            'Neither repo_url+path nor src specified, ignoring the include statement'
                        )

                        processed_content_part = ''

                if self.options['recursive'] and self.pattern.search(processed_content_part):
                    self.logger.debug('Recursive call of include statements processing')

                    processed_content_part = self.process_includes(
                        included_file_path,
                        processed_content_part,
                        current_project_root_path,
                        current_sethead
                    )

                if options.get('inline'):
                    self.logger.debug('Processing included content part as inline')

                    processed_content_part = re.sub(r'\s+', ' ', processed_content_part).strip()

            else:
                processed_content_part = content_part

            processed_content += processed_content_part

        return processed_content

    def apply(self):
        self.logger.info('Applying preprocessor')

        for markdown_file_path in self.working_dir.rglob('*.md'):
            with open(markdown_file_path, encoding='utf8') as markdown_file:
                content = markdown_file.read()

            processed_content = self.process_includes(
                markdown_file_path,
                content,
                self.project_path.resolve()
            )

            if processed_content:
                with open(markdown_file_path, 'w', encoding='utf8') as markdown_file:
                    markdown_file.write(processed_content)

        self.logger.info('Preprocessor applied')
