import re
from pathlib import Path
from json import dump


class IncludesMapProcessor:
    def __init__(self, preprocessor):
        self.preprocessor = preprocessor
        self.logger = preprocessor.logger

    def _has_not_build_meta(self, content: str) -> bool:
        '''Check if content has not_build: true in front matter.

        :param content: File content

        :returns: True if file has not_build: true in metadata
        '''
        # Simple check for front matter with not_build: true
        front_matter_pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL | re.MULTILINE)
        match = front_matter_pattern.match(content)

        if match:
            front_matter = match.group(1)
            # Check for not_build: true
            not_build_pattern = re.compile(r'not_build\s*:\s*true', re.IGNORECASE)
            return bool(not_build_pattern.search(front_matter))

        return False

    def process_includes_for_map(
            self,
            markdown_file_path: Path,
            content: str,
            recipient_md_path: str
    ) -> None:
        '''Process includes specifically for includes_map generation.
        This method only collects includes information without modifying content.

        :param markdown_file_path: Path to currently processed Markdown file
        :param content: Markdown content
        :param recipient_md_path: Path to the file in source directory
        '''
        self.logger.debug(f'Processing includes for map: {markdown_file_path}')

        if self._has_not_build_meta(content):
            self.logger.debug(f'File {markdown_file_path} has not_build: true, but still processing for includes_map')

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

                body = self.content_processor._tag_body_pattern.match(include_statement.group('body').strip())
                options = self.preprocessor.get_options(include_statement.group('options'))

                if body and body.group('path'):
                    if body.group('repo'):
                        # File in Git repository
                        repo_from_alias = self.preprocessor.options['aliases'].get(body.group('repo'))

                        revision = None

                        if repo_from_alias:
                            if '#' in repo_from_alias:
                                repo_url, revision = repo_from_alias.split('#', maxsplit=1)
                            else:
                                repo_url = repo_from_alias
                        else:
                            repo_url = body.group('repo')

                        if body.group('revision'):
                            revision = body.group('revision')

                        # Create link to repository file
                        include_link = self.content_processor.create_full_link(repo_url, revision, body.group('path'))
                        donor_md_path = include_link + body.group('path')
                        donor_md_path = self.content_processor.clean_tokens(donor_md_path)

                        # Process include for anchors
                        _, anchors = self.content_processor._process_include_for_includes_map(
                            included_file_path=Path('/dummy/path'),  # dummy path for repo files
                            from_heading=body.group('from_heading'),
                            to_heading=body.group('to_heading')
                        )

                        if self.preprocessor.includes_map_anchors:
                            donor_anchors = donor_anchors + anchors

                    else:
                        # Local file
                        included_file_path = self.path_resolver._get_included_file_path(body.group('path'), markdown_file_path)
                        donor_md_path = self.path_resolver._prepare_path_for_includes_map(included_file_path)
                        donor_md_path = self.content_processor.clean_tokens(donor_md_path)

                        # Process include for anchors (reading from source file)
                        _, anchors = self.content_processor._process_include_for_includes_map(
                            included_file_path=included_file_path,
                            from_heading=body.group('from_heading'),
                            to_heading=body.group('to_heading')
                        )

                        if self.preprocessor.includes_map_anchors:
                            donor_anchors = donor_anchors + anchors

                else:  # if body is missing or empty
                    if options.get('repo_url') and options.get('path'):
                        # File in Git repository
                        include_link = self.content_processor.create_full_link(
                            options.get('repo_url'),
                            options.get('revision'),
                            options.get('path')
                        )
                        donor_md_path = include_link + options.get('path')
                        donor_md_path = self.content_processor.clean_tokens(donor_md_path)

                        # Process include for anchors
                        _, anchors = self.content_processor._process_include_for_includes_map(
                            included_file_path=Path('/dummy/path'),  # dummy path for repo files
                            from_heading=options.get('from_heading'),
                            to_heading=options.get('to_heading'),
                            from_id=options.get('from_id'),
                            to_id=options.get('to_id'),
                            to_end=options.get('to_end')
                        )

                        if self.preprocessor.includes_map_anchors:
                            donor_anchors = donor_anchors + anchors

                    elif options.get('url'):
                        # File from URL
                        donor_md_path = options['url']
                        donor_md_path = self.content_processor.clean_tokens(donor_md_path)

                    elif options.get('src'):
                        # Local file
                        included_file_path = self.path_resolver._get_included_file_path(options.get('src'), markdown_file_path)
                        donor_md_path = self.path_resolver._prepare_path_for_includes_map(included_file_path)
                        donor_md_path = self.content_processor.clean_tokens(donor_md_path)

                        # Process include for anchors (reading from source file)
                        _, anchors = self.content_processor._process_include_for_includes_map(
                            included_file_path=included_file_path,
                            from_heading=options.get('from_heading'),
                            to_heading=options.get('to_heading'),
                            from_id=options.get('from_id'),
                            to_id=options.get('to_id'),
                            to_end=options.get('to_end')
                        )

                        if self.preprocessor.includes_map_anchors:
                            donor_anchors = donor_anchors + anchors

                # Add to includes_map
                if donor_md_path and (recipient_md_path in self.preprocessor.chapters or "index.md" in recipient_md_path):
                    if not self.content_processor._exist_in_includes_map(self.preprocessor.includes_map, recipient_md_path):
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

    def collect_includes_map(self, source_files_extensions):
        '''Collect includes map from all source files.'''
        # Process source directory files for includes_map
        src_dir_path = self.preprocessor.project_path / self.preprocessor.src_dir
        for source_files_extension in source_files_extensions:
            for source_file_path in src_dir_path.rglob(source_files_extension):
                # Get relative path from src_dir
                rel_path = source_file_path.relative_to(src_dir_path)

                # Read content from source file
                with open(source_file_path, encoding='utf8') as source_file:
                    source_content = source_file.read()

                # Determine recipient path for includes_map
                recipient_md_path = f'{self.preprocessor.src_dir}/{rel_path.as_posix()}'

                # Process includes for map collection
                self.process_includes_for_map(
                    source_file_path,
                    source_content,
                    recipient_md_path
                )

    def write_includes_map(self):
        '''Write includes map to file.'''
        output = f'{self.preprocessor.working_dir}/static/includes_map.json'
        Path(f'{self.preprocessor.working_dir}/static/').mkdir(parents=True, exist_ok=True)

        # Sort includes_map for consistent output
        def sort_includes_map(data):
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        if 'includes' in item and isinstance(item['includes'], list):
                            item['includes'].sort()
                        if 'anchors' in item and isinstance(item['anchors'], list):
                            item['anchors'].sort()
                data.sort(key=lambda x: x.get('file', ''))
            return data

        sorted_includes_map = sort_includes_map(self.preprocessor.includes_map)
        with open(output, 'w', encoding='utf8') as f:
            dump(sorted_includes_map, f)
        self.logger.debug(f'includes_map written to {output}')
