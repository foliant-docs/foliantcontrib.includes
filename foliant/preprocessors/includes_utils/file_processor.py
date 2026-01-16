import re
from pathlib import Path


class FileProcessor:
    def __init__(self, preprocessor):
        self.preprocessor = preprocessor
        self.logger = preprocessor.logger
        self.content_processor = preprocessor.content_processor
        self.path_resolver = preprocessor.path_resolver
        self.repository_handler = preprocessor.repository_handler
        self.url_handler = preprocessor.url_handler

    def create_full_link(self, repo_url: str, revision: str, path: str) -> str:
        """Create full link to file in repository."""
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]

        if revision:
            full_repo_url = repo_url + '/tree/' + revision + '/' + path.rpartition('/')[0]
        else:
            full_repo_url = repo_url + '/-/blob/master/' + path.rpartition('/')[0]

        return full_repo_url

    def clean_tokens(self, url: str) -> str:
        """Remove authentication tokens from URLs."""
        token_pattern = r"(https*://)(.*)@(.*)"
        s = url
        if hasattr(self.preprocessor, 'enable_clean_tokens') and self.preprocessor.enable_clean_tokens:
            if re.search(token_pattern, str(url)):
                s = re.sub(token_pattern, r"\1\3", str(url))
        return s

    def _exist_in_includes_map(self, includes_map: list, path: str) -> bool:
        """Check if path exists in includes map."""
        for obj in includes_map:
            if obj["file"] == path:
                return True
        return False

    def _has_not_build_meta(self, content: str) -> bool:
        '''Check if content has not_build: true in front matter.'''
        front_matter_pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL | re.MULTILINE)
        match = front_matter_pattern.match(content)

        if match:
            front_matter = match.group(1)
            not_build_pattern = re.compile(r'not_build\s*:\s*true', re.IGNORECASE)
            return bool(not_build_pattern.search(front_matter))

        return False

    def _process_include_for_includes_map(
            self,
            included_file_path: Path,
            from_heading: str or None = None,
            to_heading: str or None = None,
            from_id: str or None = None,
            to_id: str or None = None,
            to_end: bool = False
    ) -> (str, list):
        '''Process include statement specifically for includes_map generation.
        Reads content from source files directly, not from temporary directory.

        :param included_file_path: Path to the included file
        :param from_heading: Include starting from this heading
        :param to_heading: Include up to this heading
        :param from_id: Include starting from the heading or the anchor that has this ID
        :param to_id: Include up to the heading or the anchor that has this ID
        :param to_end: Flag that tells to cut to the end of document

        :returns: Tuple of (included file content, list of anchors)
        '''
        self.logger.debug(f'Processing include for includes_map: {included_file_path}')
        anchors = []

        # Reading the contents of the file from the source directory
        content = self.content_processor._read_source_file_content(included_file_path)

        if not content:
            return '', anchors

        # Check if the file has not_build: true
        if self._has_not_build_meta(content):
            self.logger.debug(f'File {included_file_path} has not_build: true, but still processing for includes_map')

        # Removing metadata from content
        from foliant.meta.tools import remove_meta
        content = remove_meta(content)

        # Cut content based on parameters
        content = self.content_processor._cut_from_position_to_position(
            content,
            from_heading,
            to_heading,
            from_id,
            to_id,
            to_end
        )

        # Find anchors
        if self.preprocessor.includes_map_anchors:
            anchors = self.content_processor._add_anchors(anchors, content)

        return content, anchors

    def _process_include(
            self,
            included_file_path: Path,
            project_root_path: Path or None = None,
            from_heading: str or None = None,
            to_heading: str or None = None,
            from_id: str or None = None,
            to_id: str or None = None,
            to_end: bool = False,
            sethead: int or None = None,
            nohead: bool = False,
            include_link: str or None = None,
            origin_file_path: Path = None
    ) -> (str, list):
        '''Replace a local include statement with the file content. Necessary
        adjustments are applied to the content: cut between certain headings,
        strip the top heading, set heading level.

        :param included_file_path: Path to the included file
        :param project_root_path: Path to the "root" directory of Foliant project
            that the currently processed Markdown file belongs to
        :param from_heading: Include starting from this heading
        :param to_heading: Include up to this heading (not including the heading itself)
        :param from_id: Include starting from the heading or the anchor that has this ID
        :param to_id: Include up to the heading or the anchor that has this ID
            (not including the heading itself)
        :param to_end: Flag that tells to cut to the end of document
        :param sethead: Level of the topmost heading in the included content
        :param nohead: Flag that tells to strip the starting heading from the included content
        :param include_link: Link to the included file for URL includes
        :param origin_file_path: Path to the original file where include tag is located

        :returns: Tuple of (included file content, list of anchors)
        '''
        self.logger.debug(
            f'Included file path: {included_file_path}, from heading: {from_heading}, ' +
            f'to heading: {to_heading}, sethead: {sethead}, nohead: {nohead}'
        )

        anchors = []

        if not included_file_path.exists():
            if self.preprocessor.options['allow_failure']:
                self.logger.error(f'The url or repo_url link is not correct, file not found: {included_file_path}')

                path_error_link = Path(self.preprocessor.project_path / '.error_link').resolve()

                if not path_error_link.exists():
                    path_error_link.mkdir(parents=True)

                path_error_file = path_error_link / included_file_path.name
                with open(path_error_file, 'w+', encoding='utf8') as f:
                    if self.preprocessor.options['stub_text']:
                        f.write(f'The url or repo_url link is not correct, file not found: {included_file_path}')

                included_file_path = path_error_file
            else:
                self.logger.error(f'The url or repo_url link is not correct, file not found: {included_file_path}')
                return '', anchors

        with open(included_file_path, encoding='utf8') as included_file:
            included_content = included_file.read()

            # Convert relative paths to absolute links for URL includes
            if include_link:
                dict_new_link = {}
                regexp_find_link = re.compile(r'\[.+?\]\(.+?\)')
                regexp_find_path = re.compile(r'\(.+?\)')

                old_found_link = regexp_find_link.findall(included_content)

                for line in old_found_link:
                    relative_path = regexp_find_path.findall(line)

                    for ex_line in relative_path:
                        exceptions_characters = re.findall(r'https?://[^\s]+|@|:|\.png|\.jpeg|\.svg', ex_line)
                        if exceptions_characters:
                            continue
                        else:
                            sub_relative_path = re.findall(r'\[.+?\]', line)
                            if sub_relative_path and relative_path:
                                dict_new_link[line] = (
                                    sub_relative_path[0] + '(' +
                                    include_link.rpartition('/')[0].replace('raw', 'blob') + '/' +
                                    relative_path[0].partition('(')[2]
                                )

                for line in dict_new_link:
                    included_content = included_content.replace(line, dict_new_link[line])

            # Removing metadata from content before including
            from foliant.meta.tools import remove_meta
            included_content = remove_meta(included_content)
            included_content = self.content_processor._cut_from_position_to_position(
                included_content,
                from_heading,
                to_heading,
                from_id,
                to_id,
                to_end,
                sethead,
                nohead
            )

            # Find anchors
            if self.preprocessor.includes_map_anchors:
                anchors = self.content_processor._add_anchors(anchors, included_content)

            if self.preprocessor.config.get('escape_code', False):
                if isinstance(self.preprocessor.config['escape_code'], dict):
                    escapecode_options = self.preprocessor.config['escape_code'].get('options', {})
                else:
                    escapecode_options = {}

                self.logger.debug(
                    'Since escape_code mode is on, applying the escapecode preprocessor ' +
                    'to the included file content'
                )

                from foliant.preprocessors import escapecode
                included_content = escapecode.Preprocessor(
                    self.preprocessor.context,
                    self.preprocessor.logger,
                    self.preprocessor.quiet,
                    self.preprocessor.debug,
                    escapecode_options
                ).escape(included_content)

            included_content = self.content_processor._adjust_image_paths(included_content, included_file_path)
            if origin_file_path:
                included_content = self.content_processor._adjust_links(included_content, included_file_path, origin_file_path)

            if project_root_path:
                included_content = self.content_processor._adjust_paths_in_tags_attributes(
                    included_content,
                    '!path',
                    project_root_path
                )

                included_content = self.content_processor._adjust_paths_in_tags_attributes(
                    included_content,
                    '!project_path',
                    project_root_path
                )

            included_content = self.content_processor._adjust_paths_in_tags_attributes(
                included_content,
                '!rel_path',
                included_file_path.parent
            )

        return included_content, anchors

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
        :param project_root_path: Path to the "root" directory of Foliant project
            that the currently processed Markdown file belongs to
        :param sethead: Level of the topmost heading in the content,
            it may be set when the method is called recursively

        :returns: Markdown content with resolved includes
        '''
        if self.preprocessor.includes_map_enable:
            if markdown_file_path.as_posix().startswith(self.preprocessor.working_dir.as_posix()):
                recipient_md_path = f'{self.preprocessor.src_dir}/{markdown_file_path.relative_to(self.preprocessor.working_dir).as_posix()}'
            else:
                recipient_md_path = f'{self.preprocessor.src_dir}/{markdown_file_path.as_posix()}'

        markdown_file_path = markdown_file_path.resolve()

        self.logger.debug(f'Processing Markdown file: {markdown_file_path}')

        processed_content = ''

        include_statement_pattern = re.compile(
            rf'((?<!\<)\<(?:{"|".join(self.preprocessor.tags)})(?:\s[^\<\>]*)?\>.*?\<\/(?:{"|".join(self.preprocessor.tags)})\>)',
            flags=re.DOTALL
        )

        content_parts = include_statement_pattern.split(content)

        for content_part in content_parts:
            include_statement = self.preprocessor.pattern.fullmatch(content_part)

            if include_statement:
                donor_md_path = None
                donor_anchors = []

                current_project_root_path = project_root_path

                body = self.content_processor._tag_body_pattern.match(include_statement.group('body').strip())
                options = self.preprocessor.get_options(include_statement.group('options'))

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

                """
                If the tag body is not empty, the legacy syntax is expected:

                <include project_root="..." sethead="..." nohead="..." inline="...">
                ($repo_url#revision$path|src)#from_heading:to_heading
                </include>

                If the tag body is empty, the new syntax is expected:

                <include
                    repo_url="..." revision="..." path="..." | url="..." | src="..."
                    project_root="..."
                    from_heading="..." to_heading="..."
                    from_id="..." to_id="..."
                    to_end="..."
                    sethead="..." nohead="..."
                    inline="..."
                    wrap_code="..."
                    code_language="..."
                ></include>
                """

                if body and body.group('path'):
                    self.logger.debug('Using the legacy syntax rules')

                    if body.group('repo'):
                        self.logger.debug('File in Git repository referenced')

                        repo_from_alias = self.preprocessor.options['aliases'].get(body.group('repo'))

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

                        repo_path = self.repository_handler._sync_repo(repo_url, revision)
                        self.logger.debug(f'Local path of the repo: {repo_path}')

                        included_file_path = repo_path / body.group('path')

                        if self.preprocessor.includes_map_enable:
                            include_link = self.create_full_link(repo_url, revision, body.group('path'))
                            donor_md_path = include_link + body.group('path')
                            donor_md_path = self.clean_tokens(donor_md_path)
                            self.logger.debug(f'Set the repo URL of the included file to {recipient_md_path}: {donor_md_path} (1)')

                        if included_file_path.name.startswith('^'):
                            included_file_path = self.path_resolver._find_file(
                                included_file_path.name[1:], included_file_path.parent
                            )

                        self.logger.debug(f'Resolved path to the included file: {included_file_path}')

                        current_project_root_path = (
                            repo_path / options.get('project_root', '')
                        ).resolve()

                        self.logger.debug(f'Set new current project root path: {current_project_root_path}')

                        processed_content_part, anchors = self._process_include(
                            included_file_path=included_file_path,
                            project_root_path=current_project_root_path,
                            from_heading=body.group('from_heading'),
                            to_heading=body.group('to_heading'),
                            sethead=current_sethead,
                            nohead=options.get('nohead'),
                            origin_file_path=markdown_file_path
                        )

                        if self.preprocessor.includes_map_enable and self.preprocessor.includes_map_anchors:
                            donor_anchors = donor_anchors + anchors

                    else:
                        self.logger.debug('Local file referenced')

                        included_file_path = self.path_resolver._get_included_file_path(body.group('path'), markdown_file_path)

                        if included_file_path.name.startswith('^'):
                            included_file_path = self.path_resolver._find_file(
                                included_file_path.name[1:], included_file_path.parent
                            )

                        self.logger.debug(f'Resolved path to the included file: {included_file_path}')

                        if options.get('project_root'):
                            current_project_root_path = (
                                markdown_file_path.parent / options.get('project_root')
                            ).resolve()

                            self.logger.debug(f'Set new current project root path: {current_project_root_path}')

                        processed_content_part, anchors = self._process_include(
                            included_file_path=included_file_path,
                            project_root_path=current_project_root_path,
                            from_heading=body.group('from_heading'),
                            to_heading=body.group('to_heading'),
                            sethead=current_sethead,
                            nohead=options.get('nohead'),
                            origin_file_path=markdown_file_path
                        )

                        if self.preprocessor.includes_map_enable:
                            donor_md_path = self.path_resolver._prepare_path_for_includes_map(included_file_path)
                            donor_md_path = self.clean_tokens(donor_md_path)
                            self.logger.debug(f'Set the path of the included file to {recipient_md_path}: {donor_md_path} (2)')

                            if self.preprocessor.includes_map_enable and self.preprocessor.includes_map_anchors:
                                donor_anchors = donor_anchors + anchors

                else:  # if body is missing or empty
                    self.logger.debug('Using the new syntax rules')

                    if options.get('repo_url') and options.get('path'):
                        self.logger.debug('File in Git repository referenced')

                        repo_path = self.repository_handler._sync_repo(options.get('repo_url'), options.get('revision'))
                        self.logger.debug(f'Local path of the repo: {repo_path}')

                        included_file_path = repo_path / options['path']
                        self.logger.debug(f'Resolved path to the included file: {included_file_path}')

                        current_project_root_path = (
                            repo_path / options.get('project_root', '')
                        ).resolve()

                        include_link = self.create_full_link(
                            options.get('repo_url'),
                            options.get('revision'),
                            options.get('path')
                        )

                        self.logger.debug(f'Set new current project root path: {current_project_root_path}')

                        processed_content_part, anchors = self._process_include(
                            included_file_path=included_file_path,
                            project_root_path=current_project_root_path,
                            from_heading=options.get('from_heading'),
                            to_heading=options.get('to_heading'),
                            from_id=options.get('from_id'),
                            to_id=options.get('to_id'),
                            to_end=options.get('to_end'),
                            sethead=current_sethead,
                            nohead=options.get('nohead'),
                            include_link=include_link,
                            origin_file_path=markdown_file_path
                        )

                        if self.preprocessor.includes_map_enable:
                            donor_md_path = include_link + options.get('path')
                            donor_md_path = self.clean_tokens(donor_md_path)
                            self.logger.debug(f'Set the link of the included file to {recipient_md_path}: {donor_md_path} (3)')

                            if self.preprocessor.includes_map_enable and self.preprocessor.includes_map_anchors:
                                donor_anchors = donor_anchors + anchors

                    elif options.get('url'):
                        self.logger.debug('File to get by URL referenced')

                        included_file_path = self.url_handler._download_file_from_url(options['url'])
                        self.logger.debug(f'Resolved path to the included file: {included_file_path}')

                        if options.get('project_root'):
                            current_project_root_path = (
                                markdown_file_path.parent / options.get('project_root')
                            ).resolve()

                            self.logger.debug(f'Set new current project root path: {current_project_root_path}')

                        processed_content_part, anchors = self._process_include(
                            included_file_path=included_file_path,
                            project_root_path=current_project_root_path,
                            from_heading=options.get('from_heading'),
                            to_heading=options.get('to_heading'),
                            from_id=options.get('from_id'),
                            to_id=options.get('to_id'),
                            to_end=options.get('to_end'),
                            sethead=current_sethead,
                            nohead=options.get('nohead'),
                            origin_file_path=markdown_file_path
                        )

                        if self.preprocessor.includes_map_enable:
                            donor_md_path = options['url']
                            donor_md_path = self.clean_tokens(donor_md_path)
                            self.logger.debug(f'Set the URL of the included file to {recipient_md_path}: {donor_md_path} (4)')

                            if self.preprocessor.includes_map_enable and self.preprocessor.includes_map_anchors:
                                donor_anchors = donor_anchors + anchors

                    elif options.get('src'):
                        self.logger.debug('Local file referenced')

                        included_file_path = self.path_resolver._get_included_file_path(options.get('src'), markdown_file_path)
                        self.logger.debug(f'Resolved path to the included file: {included_file_path}')

                        if self.preprocessor.includes_map_enable:
                            donor_md_path = self.path_resolver._prepare_path_for_includes_map(included_file_path)
                            self.logger.debug(f'Set the path of the included file to {recipient_md_path}: {donor_md_path} (5)')

                        if options.get('project_root'):
                            current_project_root_path = (
                                markdown_file_path.parent / options.get('project_root')
                            ).resolve()

                            self.logger.debug(f'Set new current project root path: {current_project_root_path}')

                        processed_content_part, anchors = self._process_include(
                            included_file_path=included_file_path,
                            project_root_path=current_project_root_path,
                            from_heading=options.get('from_heading'),
                            to_heading=options.get('to_heading'),
                            from_id=options.get('from_id'),
                            to_id=options.get('to_id'),
                            to_end=options.get('to_end'),
                            sethead=current_sethead,
                            nohead=options.get('nohead'),
                            origin_file_path=markdown_file_path
                        )

                        if self.preprocessor.includes_map_enable:
                            donor_md_path = self.path_resolver._prepare_path_for_includes_map(included_file_path)
                            donor_md_path = self.clean_tokens(donor_md_path)
                            self.logger.debug(f'Set the path of the included file to {recipient_md_path}: {donor_md_path} (5)')

                            if self.preprocessor.includes_map_enable and self.preprocessor.includes_map_anchors:
                                donor_anchors = donor_anchors + anchors
                    else:
                        self.logger.warning(
                            'Neither repo_url+path nor src specified, ignoring the include statement'
                        )
                        processed_content_part = ''

                if self.preprocessor.options['recursive'] and self.preprocessor.pattern.search(processed_content_part):
                    self.logger.debug('Recursive call of include statements processing')

                    processed_content_part = self.process_includes(
                        included_file_path,
                        processed_content_part,
                        current_project_root_path,
                        current_sethead
                    )

                wrap_code = options.get('wrap_code', '')

                if wrap_code == 'triple_backticks' or wrap_code == 'triple_tildas':
                    wrapper = ''
                    if wrap_code == 'triple_backticks':
                        self.logger.debug('Wrapping included content as fence code block with triple backticks')
                        wrapper = '```'
                    elif wrap_code == 'triple_tildas':
                        self.logger.debug('Wrapping included content as fence code block with triple tildas')
                        wrapper = '~~~'

                    code_language = options.get('code_language', '')

                    if code_language:
                        self.logger.debug(f'Specifying code language: {code_language}')
                    else:
                        self.logger.debug('Do not specify code language')

                    if not processed_content_part.endswith('\n'):
                        processed_content_part += '\n'

                    processed_content_part = (
                        f'{wrapper}{code_language}\n{processed_content_part}{wrapper}\n'
                    )

                elif wrap_code == 'single_backticks':
                    self.logger.debug('Wrapping included content as inline code with single backticks')
                    processed_content_part = '`' + processed_content_part + '`'

                if options.get('inline'):
                    self.logger.debug(
                        'Processing included content part as inline, multiple lines will be stretched into one'
                    )
                    processed_content_part = re.sub(r'\s+', ' ', processed_content_part).strip()

                if self.preprocessor.includes_map_enable:
                    if donor_md_path:
                        # Only add to includes_map if the recipient file is in chapters list
                        if recipient_md_path in self.preprocessor.chapters or "index.md" in recipient_md_path:
                            if not self._exist_in_includes_map(self.preprocessor.includes_map, recipient_md_path):
                                if not self.preprocessor.includes_map_anchors or len(donor_anchors) == 0:
                                    self.preprocessor.includes_map.append({'file': recipient_md_path, "includes": []})
                                else:
                                    self.preprocessor.includes_map.append({'file': recipient_md_path, "includes": [], 'anchors': []})

                            for i, f in enumerate(self.preprocessor.includes_map):
                                if f['file'] == recipient_md_path:
                                    if donor_md_path not in self.preprocessor.includes_map[i]['includes']:
                                        self.preprocessor.includes_map[i]['includes'].append(donor_md_path)

                                    if self.preprocessor.includes_map_anchors:
                                        if 'anchors' not in self.preprocessor.includes_map[i]:
                                            self.preprocessor.includes_map[i]['anchors'] = []
                                        for anchor in donor_anchors:
                                            if anchor not in self.preprocessor.includes_map[i]['anchors']:
                                                self.preprocessor.includes_map[i]['anchors'].append(anchor)
                        else:
                            self.logger.debug(f'File {recipient_md_path} is not in chapters, skipping includes_map')

            else:
                processed_content_part = content_part

            processed_content += processed_content_part

        return processed_content
