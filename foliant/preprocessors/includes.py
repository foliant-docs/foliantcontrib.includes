import re
import urllib.request
import urllib.error
from shutil import rmtree
from io import StringIO
from hashlib import md5
from pathlib import Path
import socket
from subprocess import run, CalledProcessError, PIPE, STDOUT
from json import dump
from os import getcwd


from foliant.preprocessors.base import BasePreprocessor
from foliant.preprocessors import escapecode
from foliant.meta.tools import remove_meta


class Preprocessor(BasePreprocessor):
    defaults = {
        'recursive': True,
        'stub_text': True,
        'allow_failure': True,
        'cache_dir': Path('.includescache'),
        'aliases': {},
        'extensions': ['md']
    }

    tags = 'include',

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._cache_dir_path = self.project_path / self.options['cache_dir']
        self._downloaded_dir_path = self._cache_dir_path / '_downloaded_content'
        self.src_dir = self.config.get('src_dir')
        self.tmp_dir = self.config.get('tmp_dir', '__folianttmp__')

        self.includes_map_enable = False
        self.includes_map_anchors = False
        if 'includes_map' in self.options:
            self.includes_map_enable = True
            if type(self.options['includes_map']) != bool and 'anchors' in self.options['includes_map']:
                self.includes_map_anchors = True

        if self.includes_map_enable:
            self.includes_map = []
            self.enable_clean_tokens = True

        self.chapters = []
        self.chapters_list(self.config["chapters"], self.chapters) # converting chapters to a list

        self.logger = self.logger.getChild('includes')

        self.logger.debug(f'Preprocessor inited: {self.__dict__}')

    def chapters_list(self, obj, chapters: list) -> list:
        '''Converting chapters to a list
        :param config_chapters: Chapters from config
        :param chapters: List of chapters
        '''
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, str):
                    chapters.append(f"{self.src_dir}/{item}")
                else:
                    self.chapters_list(item, chapters)
        elif isinstance(obj, Path):
            chapters.append(f"{self.src_dir}/{obj.as_posix()}")
        elif isinstance(obj, object):
            for _, v in obj.items():
                if isinstance(v, str):
                    chapters.append(f"{self.src_dir}/{v}")
                else:
                    self.chapters_list(v, chapters)

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

    def create_full_link(self, repo_url: str, revision: str, path: str):

        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]

        if revision:
            full_repo_url = repo_url + '/tree/' + revision + '/' + path.rpartition('/')[0]

        else:
            full_repo_url = repo_url + '/-/blob/master/' + path.rpartition('/')[0]

        return full_repo_url

    def _download_file_from_url(self, url: str) -> Path:
        '''Download file as the content of resource located at specified URL.
        Place downloaded file into the cache directory with a unique name.

        :param url: URL to get the included file content

        :returns: Path to the downloaded file
        '''

        self.logger.debug(f'The included file content should be requested at the URL: {url}')

        url_path = Path(urllib.parse.urlparse(url).path)
        extra_stem = ''
        extra_suffix = ''

        if not url_path.stem:
            extra_stem = 'content'

        if not url_path.suffix:
            extra_suffix = '.inc'

        downloaded_file_path = (
                self._downloaded_dir_path /
                f'{md5(url.encode()).hexdigest()[:8]}_{url_path.stem}{extra_stem}{url_path.suffix}{extra_suffix}'
        )

        self.logger.debug(f'Downloaded file path: {downloaded_file_path}')

        if not downloaded_file_path.exists():
            self.logger.debug('Performing URL request')
            try:
                response = urllib.request.urlopen(url, timeout=2)
            except (urllib.error.HTTPError, urllib.error.URLError) as error:
                self.logger.error(f'Data is not retrieved with {error}\nURL: {url}')
            except socket.timeout:
                self.logger.error(f'socket timed out - URL {url}')
            else:
                charset = 'utf-8'

                if response.headers['Content-Type']:
                    charset_match = re.search(r'(^|[\s;])charset=(?P<charset>[^\s;]+)', response.headers['Content-Type'])

                    if charset_match:
                        charset = charset_match.group('charset')

                self.logger.debug(f'Detected source charset: {charset}')

                downloaded_content = response.read().decode(charset)

                self._downloaded_dir_path.mkdir(parents=True, exist_ok=True)

                # The beginning of the block codes for converting relative paths to links
                dict_new_link = {}
                regexp_find_link = re.compile(r'\[.+?\]\(.+?\)')
                regexp_find_path = re.compile(r'\(.+?\)')

                old_found_link = regexp_find_link.findall(downloaded_content)

                for line in old_found_link:
                    exceptions_characters = re.findall(r'http|@|:', line)
                    if exceptions_characters:
                        continue
                    else:
                        relative_path = regexp_find_path.findall(line)
                        sub_relative_path = re.findall(r'\[.+?\]', line)
                        dict_new_link[line] = sub_relative_path[0] + '(' + url.rpartition('/')[0].replace('raw',
                                                                                                        'blob') + '/' + \
                                            relative_path[0].partition('(')[2]

                for line in dict_new_link:
                    downloaded_content = downloaded_content.replace(line, dict_new_link[line])
                # End of the conversion code block

                with open(downloaded_file_path, 'w', encoding='utf8') as downloaded_file:
                    downloaded_file.write(downloaded_content)
        else:
            self.logger.debug('File found in cache, it was already downloaded at this run')

        return downloaded_file_path

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
        repo_path = (self._cache_dir_path / repo_name).resolve()

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
                except Exception as exception:
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

        if from_id:
            self.logger.debug('Starting point is defined by its ID')

            from_identified_heading_pattern = re.compile(
                r'^\#{1,6}\s+.*\S+\s+\{\#' + rf'{re.escape(from_id)}' + r'\}\s*$',
                flags=re.MULTILINE
            )

            from_anchor_pattern = re.compile(
                rf'(?:(?<!\<))\<anchor(?:\s(?:[^\<\>]*))?\>{re.escape(from_id)}<\/anchor\>'
            )

            if from_identified_heading_pattern.findall(content):
                self.logger.debug('Starting heading with defined ID is found')

                result = from_identified_heading_pattern.split(content)[1]

                from_heading_line = from_identified_heading_pattern.findall(content)[0]
                from_heading_level = len(self._heading_pattern.match(from_heading_line).group('hashes'))

                self.logger.debug(f'Level of starting heading: {from_heading_level}')

            elif from_anchor_pattern.findall(content):
                self.logger.debug('Starting anchor with defined ID is found')

                result = from_anchor_pattern.split(content)[1]

                previous_content = from_anchor_pattern.split(content)[0]

                from_heading_line = None
                from_heading_level = None

                for previous_heading_match in self._heading_pattern.finditer(previous_content):
                    from_heading_level = len(previous_heading_match.group('hashes'))

                self.logger.debug(f'Level of starting heading: {from_heading_level}')

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

            if from_heading_pattern.findall(content):
                self.logger.debug('Starting heading with defined content is found')

                result = from_heading_pattern.split(content)[1]

                from_heading_line = from_heading_pattern.findall(content)[0]
                from_heading_level = len(self._heading_pattern.match(from_heading_line).group('hashes'))

                self.logger.debug(f'Level of starting heading: {from_heading_level}')

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
                from_heading_line = None
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

            if to_heading_pattern.findall(result):
                self.logger.debug('Ending heading with defined content is found')

                result = to_heading_pattern.split(result)[0]

            else:
                self.logger.debug('Ending heading is not found, cutting to the end')

        else:
            self.logger.debug('Ending point is not defined')

            if from_id or from_heading:
                self.logger.debug(
                    'Since starting point is defined, cutting to the next heading of the same level'
                )

                to_heading_pattern = re.compile(
                    rf'^\#{{1,{from_heading_level}}}\s+\S+.*$',
                    flags=re.MULTILINE
                )

                result = to_heading_pattern.split(result)[0]

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

    def _adjust_links(
            self,
            content: str,
            markdown_file_path: Path,
            origin_file_path: Path
    ) -> str:
        '''Locate internal link referenced in a Markdown string and replace their paths
        with the relative ones.

        :param content: Markdown content
        :param markdown_file_path: Path to the Markdown file containing the content

        :returns: Markdown content with relative internal link paths
        '''
        def _resolve_link(link, root_path, depth_origin):
            try:
                resolved_link = (markdown_file_path.absolute().parent / Path(link)).resolve()
                resolved_link = resolved_link.relative_to(root_path)
                resolved_link = '../' * depth_origin + resolved_link.as_posix()
                return resolved_link
            except Exception as exception:
                self.logger.debug(
                    f'An error {exception} occurred when resolving the link: {link}'
                )

        def _sub(m):
            caption = m.group('text')
            link = m.group('path')
            anchor = ''
            link_array = m.group('path').split('#')
            if len(link_array) > 1:
                link = link_array[0]
                anchor = f'#{link_array[1]}'
            root_path = self.project_path.absolute() / self.tmp_dir
            if not Path(link).is_absolute():
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
                            if link_split[0] == '..':
                                if link_split[-1] == '':
                                    link_split = link_split[:-1]
                                link_split = link_split[1:]
                                link = f"{'/'.join(link_split)}.md"
                                link = _resolve_link(link, root_path, depth_origin)
                    if (
                        depth_difference == 0
                        ) and (
                            Path(Path(link).name).with_suffix('').as_posix() == Path(origin_rel.name).with_suffix('').as_posix()
                        ):
                        link = ''
                    self.logger.debug(
                        f'Updating link reference; user specified path: {m.group("path")}, ' +
                        f'absolute path: {link}'
                    )
                except Exception as exception:
                    self.logger.debug(
                        f'An error {exception} occurred when resolving the link: {m.group("path")}'
                    )

            return f'[{caption}]({link}{anchor})'

        return self._link_pattern.sub(_sub, content)

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
        :param project_root_path: Path to the “root” directory of Foliant project
            that the currently processed Markdown file belongs to
        :param from_heading: Include starting from this heading
        :param to_heading: Include up to this heading (not including the heading itself)
        :param from_id: Include starting from the heading or the anchor that has this ID
        :param to_id: Include up to the heading or the anchor that has this ID
            (not including the heading itself)
        :param to_end: Flag that tells to cut to the end of document
        :param sethead: Level of the topmost heading in the included content
        :param nohead: Flag that tells to strip the starting heading from the included content

        :returns: Included file content
        '''

        self.logger.debug(
            f'Included file path: {included_file_path}, from heading: {from_heading}, ' +
            f'to heading: {to_heading}, sethead: {sethead}, nohead: {nohead}'
        )

        anchors = []

        if not included_file_path.exists():
            if self.options['allow_failure']:
                self.logger.error(f'The url or repo_url link is not correct, file not found: {included_file_path}')

                path_error_link = Path(self.project_path/'.error_link').resolve()

                if not Path(path_error_link).exists():
                    Path(path_error_link).mkdir()

                path_error_file = open(path_error_link/included_file_path.name, 'w+', encoding='utf8')

                if self.options['stub_text']:
                    path_error_file.write(f'The url or repo_url link is not correct, file not found: {included_file_path}')
                path_error_file.close()

                included_file_path = path_error_link/included_file_path.name
            else:
                self.logger.error(f'The url or repo_url link is not correct, file not found: {included_file_path}')
                return '', anchors

        with open(included_file_path, encoding='utf8') as included_file:
            included_content = included_file.read()

            # The beginning of the block codes for converting relative paths to links
            if include_link:
                dict_new_link = {}
                regexp_find_link = re.compile(r'\[.+?\]\(.+?\)')
                regexp_find_path = re.compile(r'\(.+?\)')

                old_found_link = regexp_find_link.findall(included_content)

                for line in old_found_link:
                    relative_path = regexp_find_path.findall(line)

                    for ex_line in relative_path:
                        exceptions_characters = re.findall(r'https?://[^\s]+|@|:|\.png|\.jpeg|.svg', ex_line)
                        if exceptions_characters:
                            continue
                        else:
                            sub_relative_path = re.findall(r'\[.+?\]', line)
                            dict_new_link[line] = sub_relative_path[0] + '(' + include_link.rpartition('/')[0].replace(
                                'raw', 'blob') + '/' + relative_path[0].partition('(')[2]

                for line in dict_new_link:
                    included_content = included_content.replace(line, dict_new_link[line])
            # End of the conversion code block

            # Removing metadata from content before including
            included_content = remove_meta(included_content)
            included_content = self._cut_from_position_to_position(
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
            if self.includes_map_anchors:
                anchors = self._add_anchors(anchors, included_content)

            if self.config.get('escape_code', False):
                if isinstance(self.config['escape_code'], dict):
                    escapecode_options = self.config['escape_code'].get('options', {})
                else:
                    escapecode_options = {}

                self.logger.debug(
                    'Since escape_code mode is on, applying the escapecode preprocessor ' +
                    'to the included file content'
                )

                included_content = escapecode.Preprocessor(
                    self.context,
                    self.logger,
                    self.quiet,
                    self.debug,
                    escapecode_options
                ).escape(included_content)

            included_content = self._adjust_image_paths(included_content, included_file_path)
            included_content = self._adjust_links(included_content, included_file_path, origin_file_path)

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

        return included_content, anchors

    def _find_anchors(self, content: str) -> list:
        """Search for anchor links in the text

        :param content: Markdown content

        :returns: List of anchor links
        """
        anchors_list = []

        anchors = re.findall(r'\<anchor\>([\-\_A-Za-z0-9]+)\<\/anchor\>', content)
        for anchor in anchors:
            anchors_list.append(anchor)
        custom_ids = re.findall(r'\{\#([\-\_A-Za-z0-9]+)\}', content)
        for anchor in custom_ids:
            anchors_list.append(anchor)
        elements_with_ids = re.findall(r'id\=[\"\']([\-\_A-Za-z0-9]+)[\"\']', content)
        for anchor in elements_with_ids:
            anchors_list.append(anchor)
        return anchors_list

    def _add_anchors(self, l: list, content: str) -> list:
        """Add an anchor link to the list of anchor links

        :param l: The original list
        :param content: Markdown content

        :returns: A list with added anchors
        """
        anchors = self._find_anchors(content)
        if anchors:
            l.extend(anchors)
        return l

    def clean_tokens(self, url: str) -> str:
        token_pattern = r"(https*://)(.*)@(.*)"
        s = url
        if self.enable_clean_tokens:
            if re.search(token_pattern, str(url)):
                s = re.sub(token_pattern, r"\1\3", str(url))
        return s

    def _prepare_path_for_includes_map(self, path: Path) -> str:
        donor_path = None
        if path.as_posix().startswith(self.working_dir.as_posix()):
            _path = path.relative_to(self.working_dir)
            donor_path = f"{self.src_dir}/{_path.as_posix()}"
        elif path.as_posix().startswith(getcwd()):
            _path = path.relative_to(getcwd())
            if _path.as_posix().startswith(self.working_dir.as_posix()):
                _path = _path.relative_to(self.working_dir)
                if _path.as_posix().startswith(self.working_dir.as_posix()):
                    donor_path = f"{self.src_dir}/{_path.relative_to(self.working_dir).as_posix()}"
                else:
                    donor_path = f"{self.src_dir}/{_path.as_posix()}"
            else:
                donor_path = _path.as_posix()
        return donor_path

    def _exist_in_includes_map(self, includes_map: list, path: str) -> bool:
        for obj in includes_map:
            if obj["file"] == path:
                return True
        return False

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

        if self.includes_map_enable:
            if markdown_file_path.as_posix().startswith(self.working_dir.as_posix()):
                recipient_md_path = f'{self.src_dir}/{markdown_file_path.relative_to(self.working_dir).as_posix()}'
            else:
                recipient_md_path = f'{self.src_dir}/{markdown_file_path.as_posix()}'

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
                if self.includes_map_enable:
                    donor_md_path = None
                    donor_anchors = []

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

                        if self.includes_map_enable:
                            donor_md_path = included_file_path.as_posix()
                            donor_md_path = self.clean_tokens(donor_md_path)
                            self.logger.debug(f'Set the repo URL of the included file to {recipient_md_path}: {donor_md_path} (1)')
                        if included_file_path.name.startswith('^'):
                            included_file_path = self._find_file(
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

                        if self.includes_map_enable and self.includes_map_anchors:
                            donor_anchors = donor_anchors + anchors

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

                        processed_content_part, anchors = self._process_include(
                            included_file_path=included_file_path,
                            project_root_path=current_project_root_path,
                            from_heading=body.group('from_heading'),
                            to_heading=body.group('to_heading'),
                            sethead=current_sethead,
                            nohead=options.get('nohead'),
                            origin_file_path=markdown_file_path
                        )

                        if self.includes_map_enable:
                            donor_md_path = self._prepare_path_for_includes_map(included_file_path)
                            donor_md_path = self.clean_tokens(donor_md_path)
                            self.logger.debug(f'Set the path of the included file to {recipient_md_path}: {donor_md_path} (2)')

                            if self.includes_map_enable and self.includes_map_anchors:
                                donor_anchors = donor_anchors + anchors

                else:  # if body is missing
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

                        include_link = self.create_full_link(options.get('repo_url'), options.get('revision'),
                                                             options.get('path'))

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

                        if self.includes_map_enable:
                            donor_md_path = include_link + options.get('path')
                            donor_md_path = self.clean_tokens(donor_md_path)
                            self.logger.debug(f'Set the link of the included file to {recipient_md_path}: {donor_md_path} (3)')

                            if self.includes_map_enable and self.includes_map_anchors:
                                donor_anchors = donor_anchors + anchors

                    elif options.get('url'):
                        self.logger.debug('File to get by URL referenced')

                        included_file_path = self._download_file_from_url(options['url'])

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

                        if self.includes_map_enable:
                            donor_md_path = options['url']
                            donor_md_path = self.clean_tokens(donor_md_path)
                            self.logger.debug(f'Set the URL of the included file to {recipient_md_path}: {donor_md_path} (4)')

                            if self.includes_map_enable and self.includes_map_anchors:
                                donor_anchors = donor_anchors + anchors

                    elif options.get('src'):
                        self.logger.debug('Local file referenced')

                        included_file_path = self._get_included_file_path(options.get('src'), markdown_file_path)
                        self.logger.debug(f'Resolved path to the included file: {included_file_path}')

                        if self.includes_map_enable:
                            donor_md_path = self._prepare_path_for_includes_map(included_file_path)
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

                        if self.includes_map_enable:
                            donor_md_path = self._prepare_path_for_includes_map(included_file_path)
                            donor_md_path = self.clean_tokens(donor_md_path)
                            self.logger.debug(f'Set the path of the included file to {recipient_md_path}: {donor_md_path} (5)')

                            if self.includes_map_enable and self.includes_map_anchors:
                                donor_anchors = donor_anchors + anchors
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
                            f'{wrapper}{code_language}' + '\n' + processed_content_part + wrapper + '\n'
                    )

                elif wrap_code == 'single_backticks':
                    self.logger.debug('Wrapping included content as inline code with single backticks')

                    processed_content_part = '`' + processed_content_part + '`'

                if options.get('inline'):
                    self.logger.debug(
                        'Processing included content part as inline, multiple lines will be stretched into one'
                    )

                    processed_content_part = re.sub(r'\s+', ' ', processed_content_part).strip()

                if self.includes_map_enable:
                    if donor_md_path:
                        if recipient_md_path in self.chapters or "index.md" in recipient_md_path:
                            if not self._exist_in_includes_map(self.includes_map, recipient_md_path):
                                if not self.includes_map_anchors or len(donor_anchors) == 0:
                                    self.includes_map.append({'file': recipient_md_path, "includes": []})
                                else:
                                    self.includes_map.append({'file': recipient_md_path, "includes": [], 'anchors': []})

                            for i, f in enumerate(self.includes_map):
                                if f['file'] == recipient_md_path:
                                    self.includes_map[i]['includes'].append(donor_md_path)

                                    if self.includes_map_anchors:
                                        if 'anchors' not in self.includes_map[i]:
                                            self.includes_map[i]['anchors'] = []
                                        for anchor in donor_anchors:
                                            if anchor not in self.includes_map[i]['anchors']:
                                                self.includes_map[i]['anchors'].append(anchor)

            else:
                processed_content_part = content_part

            processed_content += processed_content_part

        return processed_content

    def _get_source_files_extensions(self) -> list:
        '''Get list of specified extensions from the ``extensions`` config param,
        and convert it into list of glob patterns for each file type.

        :returns: List of glob patters for each file type specified in config
        '''

        extensions_from_config = list(set(self.options['extensions']))
        source_files_extensions = []
        md_involved = False

        for extension in extensions_from_config:
            extension = extension.lstrip('.')

            source_files_extensions.append(f'*.{extension}')

            if extension == 'md':
                md_involved = True

        if not md_involved:
            self.logger.warning(
                "Markdown file extension 'md' is not mentioned in the extensions list! " +
                "Didn’t you forget to put it there?"
            )

        return source_files_extensions

    def apply(self):

        self.logger.info('Applying preprocessor')

        # Cleaning up downloads because the content of remote source may have modified
        if self._downloaded_dir_path.exists():
            rmtree(self._downloaded_dir_path, ignore_errors=True)

        source_files_extensions = self._get_source_files_extensions()

        for source_files_extension in source_files_extensions:
            for source_file_path in self.working_dir.rglob(source_files_extension):
                with open(source_file_path, encoding='utf8') as source_file:
                    source_content = source_file.read()

                processed_content = self.process_includes(
                    source_file_path,
                    source_content,
                    self.project_path.resolve()
                )

                if processed_content:
                    with open(source_file_path, 'w', encoding='utf8') as processed_file:
                        processed_file.write(processed_content)

        # Write includes map
        if self.includes_map_enable:
            output = f'{self.working_dir}/static/includes_map.json'
            Path(f'{self.working_dir}/static/').mkdir(parents=True, exist_ok=True)
            with open(f'{self.working_dir}/static/includes_map.json', 'w', encoding='utf8') as f:
                dump(self.includes_map, f)
            self.logger.debug(f'includes_map write to {output}')

        self.logger.info('Preprocessor applied')
