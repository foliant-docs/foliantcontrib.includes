import re
from io import StringIO
from pathlib import Path


class ContentProcessor:
    _heading_pattern = re.compile(
        r'^(?P<hashes>\#{1,6})\s+(?P<content>.*\S+)(?P<tail>\s*)$',
        flags=re.MULTILINE
    )
    _image_pattern = re.compile(r'\!\[(?P<caption>.*?)\]\((?P<path>((?!:\/\/).)+?)\)')
    _link_pattern = re.compile(r'\[(?P<text>.*?)\]\((?P<path>((?!:\/\/).)+?)\)')
    _tag_body_pattern = re.compile(
        r'(\$(?P<repo>[^\#^\$]+)(\#(?P<revision>[^\$]+))?\$)?' +
        r'(?P<path>[^\#]+)' +
        r'(\#(?P<from_heading>[^:]*)(:(?P<to_heading>.+))?)?'
    )

    def __init__(self, preprocessor):
        self.preprocessor = preprocessor
        self.logger = preprocessor.logger

    def _shift_headings(self, content: str, shift: int) -> str:
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

            if new_heading_level <= 6 and new_heading_level >= 1:
                return f'{"#" * new_heading_level} {heading.group("content")}{heading.group("tail")}'
            else:
                self.logger.debug('New heading level is out of range, using bold paragraph text instead of heading')
                return f'**{heading.group("content")}**{heading.group("tail")}'

        return self._heading_pattern.sub(_sub, content)

    def _find_top_heading_level(self, content: str) -> int:
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

    def _cut_from_position_to_position(
            self,
            content: str,
            from_heading: str or None = None,
            to_heading: str or None = None,
            from_id: str or None = None,
            to_id: str or None = None,
            to_end: bool = False,
            sethead: int or None = None,
            nohead: bool = False
    ) -> str:
        '''Cut part of Markdown string between two positions,
        set internal heading level, and remove top heading.

        Starting position may be defined by the heading content,
        ID of the heading, ID of the anchor.

        Ending position may be defined like the starting position,
        and also as the end of the included content.

        If only the starting position is defined, cut to the next heading
        of the same level.

        If neither starting nor ending position is defined,
        the whole string is returned.

        Heading shift and top heading elimination are optional.

        :param content: Markdown content
        :param from_heading: Starting heading
        :param to_heading: Ending heading (will not be incuded in the output)
        :param from_id: ID of starting heading or anchor;
            this argument has higher priority than ``from_heading``
        :param to_id: ID of ending heading (the heading itself will not be incuded in the output)
            or anchor; this argument has higher priority than ``to_heading``
        :param to_end: Flag that tells to cut up to the end of the included content;
            this argument has higher priority than ``to_id``
        :param sethead: Level of the topmost heading in the included content
        :param nohead: Flag that tells to strip the starting heading from the included content

        :returns: Part of the Markdown content between defined positions
            with internal headings adjusted
        '''
        self.logger.debug(
            'Cutting from position to position: ' +
            f'from_heading: {from_heading}, to_heading: {to_heading}, ' +
            f'from_id: {from_id}, to_id: {to_id}, ' +
            f'to_end: {to_end}, ' +
            f'sethead: {sethead}, nohead: {nohead}'
        )

        # First, cut the content from the starting position to the end
        from_heading_line = None
        from_heading_level = None

        if from_id:
            self.logger.debug('Starting point is defined by its ID')

            from_identified_heading_pattern = re.compile(
                r'^\#{1,6}\s+.*\S+\s+\{\#' + rf'{re.escape(from_id)}' + r'\}\s*$',
                flags=re.MULTILINE
            )

            from_anchor_pattern = re.compile(
                rf'(?:(?<!\<))\<anchor(?:\s(?:[^\<\>]*))?\>{re.escape(from_id)}<\/anchor\>',
                flags=re.MULTILINE
            )

            if from_identified_heading_pattern.search(content):
                self.logger.debug('Starting heading with defined ID is found')
                parts = from_identified_heading_pattern.split(content, maxsplit=1)
                if len(parts) > 1:
                    result = parts[1]
                    from_heading_line = from_identified_heading_pattern.search(content).group(0)
                    from_heading_level = len(self._heading_pattern.match(from_heading_line).group('hashes'))
                else:
                    result = ''
            elif from_anchor_pattern.search(content):
                self.logger.debug('Starting anchor with defined ID is found')
                parts = from_anchor_pattern.split(content, maxsplit=1)
                if len(parts) > 1:
                    result = parts[1]
                    previous_content = parts[0]

                    # Find the last heading before the anchor
                    last_heading_match = None
                    for heading_match in self._heading_pattern.finditer(previous_content):
                        last_heading_match = heading_match

                    if last_heading_match:
                        from_heading_level = len(last_heading_match.group('hashes'))
                        self.logger.debug(f'Level of previous heading: {from_heading_level}')
                    else:
                        from_heading_level = self._find_top_heading_level(result)
                        self.logger.debug(f'No previous heading found, top level from result: {from_heading_level}')
                else:
                    result = ''
            else:
                self.logger.debug(
                    'Neither starting heading nor starting anchor is found, '
                    'skipping the included content'
                )
                return ''

        elif from_heading:
            self.logger.debug('Starting heading is defined by its content')

            from_heading_pattern = re.compile(
                r'^\#{1,6}\s+' + rf'{re.escape(from_heading)}\s*$',
                flags=re.MULTILINE
            )

            if from_heading_pattern.search(content):
                self.logger.debug('Starting heading with defined content is found')
                parts = from_heading_pattern.split(content, maxsplit=1)
                if len(parts) > 1:
                    result = parts[1]
                    from_heading_line = from_heading_pattern.search(content).group(0)
                    from_heading_level = len(self._heading_pattern.match(from_heading_line).group('hashes'))
                else:
                    result = ''
            else:
                self.logger.debug('Starting heading is not found, skipping the included content')
                return ''

        else:
            self.logger.debug('Starting point is not defined')

            content_buffer = StringIO(content)
            first_line = content_buffer.readline()

            if self._heading_pattern.fullmatch(first_line):
                self.logger.debug('The content starts with heading')
                result = content_buffer.read()
                from_heading_line = first_line
                from_heading_level = len(self._heading_pattern.match(from_heading_line).group('hashes'))
            else:
                self.logger.debug('The content does not start with heading')
                result = content
                from_heading_level = self._find_top_heading_level(content)

            self.logger.debug(f'Topmost heading level: {from_heading_level}')

        # After that, cut the result to the ending position
        if to_end:
            self.logger.debug('Ending point is defined as the end of the document')

        elif to_id:
            self.logger.debug('Ending point is defined by its ID')

            to_identified_heading_pattern = re.compile(
                r'^\#{1,6}\s+.*\S+\s+\{\#' + rf'{re.escape(to_id)}' + r'\}\s*$',
                flags=re.MULTILINE
            )

            to_anchor_pattern = re.compile(
                rf'(?:(?<!\<))\<anchor(?:\s(?:[^\<\>]*))?\>{re.escape(to_id)}<\/anchor\>'
            )

            if to_identified_heading_pattern.findall(result):
                self.logger.debug('Ending heading with defined ID is found')
                result = to_identified_heading_pattern.split(result)[0]
            elif to_anchor_pattern.findall(result):
                self.logger.debug('Ending anchor with defined ID is found')
                result = to_anchor_pattern.split(result)[0]
            else:
                self.logger.debug('Neither ending heading nor ending anchor is found, cutting to the end')

        elif to_heading:
            self.logger.debug('Ending heading is defined by its content')

            to_heading_pattern = re.compile(
                r'^\#{1,6}\s+' + rf'{re.escape(to_heading)}\s*$',
                flags=re.MULTILINE
            )

            if to_heading_pattern.search(result):
                self.logger.debug('Ending heading with defined content is found')
                parts = to_heading_pattern.split(result, maxsplit=1)
                result = parts[0] if parts else ''
            else:
                self.logger.debug('Ending heading is not found, cutting to the end')

        else:
            self.logger.debug('Ending point is not defined')

            if from_id or from_heading:
                self.logger.debug(
                    'Since starting point is defined, cutting to the next heading of the same level'
                )

                if from_heading_level:
                    to_heading_pattern = re.compile(
                        rf'^\#{{1,{from_heading_level}}}\s+\S+.*$',
                        flags=re.MULTILINE
                    )
                    parts = to_heading_pattern.split(result, maxsplit=1)
                    result = parts[0] if parts else ''
            else:
                self.logger.debug(
                    'Since starting point is not defined, using the whole included content'
                )

        # Finally, take into account the options nohead and sethead
        if not nohead and from_heading_line:
            self.logger.debug(
                'Since nohead option is not specified, and the included content starts with heading, ' +
                'including starting heading into the output'
            )
            result = from_heading_line + result

        if sethead and from_heading_level:
            if sethead > 0:
                self.logger.debug(
                    'Since sethead option is specified, shifting headings levels in the included content'
                )
                result = self._shift_headings(result, sethead - from_heading_level)

        return result

    def _adjust_image_paths(self, content: str, markdown_file_path: Path) -> str:
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

    def _adjust_links(self, content: str, markdown_file_path: Path, origin_file_path: Path) -> str:
        '''Locate internal link referenced in a Markdown string and replace their paths
        with the relative ones.

        :param content: Markdown content
        :param markdown_file_path: Path to the Markdown file containing the content
        :param origin_file_path: Path to the original file where the include tag is located

        :returns: Markdown content with relative internal link paths
        '''
        def _resolve_link(link: str, root_path: Path, depth_origin: int) -> str:
            try:
                resolved_link = (markdown_file_path.absolute().parent / Path(link)).resolve()
                resolved_link = resolved_link.relative_to(root_path)
                resolved_link = '../' * depth_origin + resolved_link.as_posix()
                return resolved_link
            except Exception as exception:
                self.logger.debug(f'An error {exception} occurred when resolving the link: {link}')
                return link

        def _sub(m):
            caption = m.group('text')
            link = m.group('path')
            anchor = ''

            # Split link and anchor
            link_array = m.group('path').split('#')
            if len(link_array) > 1:
                link = link_array[0]
                anchor = f'#{link_array[1]}'

            root_path = self.preprocessor.project_path.absolute() / self.preprocessor.tmp_dir

            # Skip absolute paths and external URLs
            if Path(link).is_absolute() or link.startswith(('http://', 'https://', 'ftp://')):
                return f'[{caption}]({link}{anchor})'

            extension = Path(link).suffix

            try:
                origin_rel = origin_file_path.relative_to(root_path)
                depth_origin = len(origin_rel.parts)
                depth_markdown_file = len(markdown_file_path.relative_to(root_path).parts)
                depth_difference = depth_origin - depth_markdown_file

                if extension == ".md":
                    link = _resolve_link(link, root_path, depth_origin - 1)
                elif extension == "":
                    if depth_origin >= depth_markdown_file:
                        link = '../' * depth_difference + link
                    else:
                        link_split = link.split('/')
                        if link_split and link_split[0] == '..':
                            if link_split[-1] == '':
                                link_split = link_split[:-1]
                            link_split = link_split[1:]
                            link = f"{'/'.join(link_split)}.md"
                            link = _resolve_link(link, root_path, depth_origin)

                # Check if link points to the same file (without anchor)
                if (depth_difference == 0 and
                    Path(Path(link).name).with_suffix('').as_posix() ==
                    Path(origin_rel.name).with_suffix('').as_posix()):
                    link = ''

                self.logger.debug(
                    f'Updating link reference; user specified path: {m.group("path")}, ' +
                    f'resolved path: {link}'
                )

            except Exception as exception:
                self.logger.debug(
                    f'An error {exception} occurred when resolving the link: {m.group("path")}'
                )
                link = m.group('path')

            return f'[{caption}]({link}{anchor})'

        return self._link_pattern.sub(_sub, content)

    def _adjust_paths_in_tags_attributes(self, content: str, modifier: str, base_path: Path) -> str:
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
                rf'(?P<modifier>\s*{re.escape(modifier)}\s+)' +
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

    def _read_source_file_content(self, file_path: Path) -> str:
        '''Read content from source file, handling both temporary and source directory paths.

        :param file_path: Path to the file to read

        :returns: File content as string
        '''
        self.logger.debug(f'Reading source file: {file_path}')

        # If the file is located in a temporary directory, let's try to find the corresponding source file
        if self.preprocessor.working_dir.resolve() in file_path.parents:
            # This is a file in a temporary directory
            try:
                # Get the path to the source file
                src_file_path = self.path_resolver._get_src_file_path(file_path)
                self.logger.debug(f'Mapping temporary file to source file: {src_file_path}')

                if src_file_path.exists():
                    with open(src_file_path, encoding='utf8') as src_file:
                        return src_file.read()
                else:
                    # If the source file is not found, we read from the temporary file
                    self.logger.debug('Source file not found, reading from temporary file')
                    if file_path.exists():
                        with open(file_path, encoding='utf8') as temp_file:
                            return temp_file.read()
                    else:
                        self.logger.warning(f'File not found: {file_path}')
                        return ''
            except Exception as e:
                self.logger.debug(f'Error mapping to source file: {e}, reading from temporary file')
                if file_path.exists():
                    with open(file_path, encoding='utf8') as temp_file:
                        return temp_file.read()
                else:
                    self.logger.warning(f'File not found: {file_path}')
                    return ''
        else:
            # The file is not in the temporary directory, we read it directly
            if file_path.exists():
                with open(file_path, encoding='utf8') as src_file:
                    return src_file.read()
            else:
                self.logger.warning(f'File not found: {file_path}')
                return ''

    def _find_anchors(self, content: str) -> list:
        """Search for anchor links in the text

        :param content: Markdown content

        :returns: List of anchor links
        """
        anchors_list = []

        anchors = re.findall(r'\<anchor\>([\-\_A-Za-z0-9]+)\<\/anchor\>', content)
        anchors_list.extend(anchors)

        custom_ids = re.findall(r'\{\#([\-\_A-Za-z0-9]+)\}', content)
        anchors_list.extend(custom_ids)

        elements_with_ids = re.findall(r'id\=[\"\']([\-\_A-Za-z0-9]+)[\"\']', content)
        anchors_list.extend(elements_with_ids)

        return anchors_list

    def _add_anchors(self, anchor_list: list, content: str) -> list:
        """Add an anchor link to the list of anchor links

        :param anchor_list: The original list
        :param content: Markdown content

        :returns: A list with added anchors
        """
        anchors = self._find_anchors(content)
        if anchors:
            anchor_list.extend(anchors)
        return anchor_list
