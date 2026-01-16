from pathlib import Path

from foliant.preprocessors.base import BasePreprocessor

from .includes_utils.content_processor import ContentProcessor
from .includes_utils.file_processor import FileProcessor
from .includes_utils.path_resolver import PathResolver
from .includes_utils.repository_handler import RepositoryHandler
from .includes_utils.url_handler import URLHandler
from .includes_utils.includes_map_processor import IncludesMapProcessor


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._cache_dir_path = self.project_path / self.options['cache_dir']
        self._downloaded_dir_path = self._cache_dir_path / '_downloaded_content'
        self.src_dir = self.config.get('src_dir')
        self.tmp_dir = self.config.get('tmp_dir', '__folianttmp__')

        # Setup includes map
        self.includes_map_enable = False
        self.includes_map_anchors = False
        if 'includes_map' in self.options:
            self.includes_map_enable = True
            if isinstance(self.options['includes_map'], dict) and 'anchors' in self.options['includes_map']:
                self.includes_map_anchors = True

        if self.includes_map_enable:
            self.includes_map = []
            self.enable_clean_tokens = True

        self.content_processor = ContentProcessor(self)
        self.path_resolver = PathResolver(self)
        self.repository_handler = RepositoryHandler(self)
        self.url_handler = URLHandler(self)
        self.file_processor = FileProcessor(self)

        if self.includes_map_enable:
            self.includes_map_processor = IncludesMapProcessor(self)

        self.chapters = []
        self._chapters_list(self.config["chapters"], self.chapters) # converting chapters to a list

        self.logger = self.logger.getChild('includes')
        self.logger.debug(f'Preprocessor inited: {self.__dict__}')

    def _chapters_list(self, obj, chapters: list) -> None:
        '''Converting chapters to a list
        :param obj: Chapters from config
        :param chapters: List of chapters
        '''
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, str):
                    chapters.append(f"{self.src_dir}/{item}")
                else:
                    self._chapters_list(item, chapters)
        elif isinstance(obj, Path):
            chapters.append(f"{self.src_dir}/{obj.as_posix()}")
        elif isinstance(obj, dict):
            for _, v in obj.items():
                if isinstance(v, str):
                    chapters.append(f"{self.src_dir}/{v}")
                else:
                    self._chapters_list(v, chapters)

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
                "Didn't you forget to put it there?"
            )

        return source_files_extensions

    def apply(self):
        """Apply the preprocessor to all source files."""
        self.logger.info('Applying preprocessor')

        # Cleaning up downloads because the content of remote source may have modified
        if self._downloaded_dir_path.exists():
            from shutil import rmtree
            rmtree(self._downloaded_dir_path, ignore_errors=True)

        source_files_extensions = self._get_source_files_extensions()

        # First pass: collect includes_map for all files from source directory
        if self.includes_map_enable:
            self.logger.debug('First pass: collecting includes_map from source files')
            self.includes_map_processor.collect_includes_map(source_files_extensions)

        # Second pass: process files in working directory
        self.logger.debug('Second pass: processing includes in working directory')
        for source_files_extension in source_files_extensions:
            for source_file_path in self.working_dir.rglob(source_files_extension):
                with open(source_file_path, encoding='utf8') as source_file:
                    source_content = source_file.read()

                processed_content = self.file_processor.process_includes(
                    source_file_path,
                    source_content,
                    self.project_path.resolve()
                )

                if processed_content:
                    with open(source_file_path, 'w', encoding='utf8') as processed_file:
                        processed_file.write(processed_content)

        # Write includes map (sort data for consistent output)
        if self.includes_map_enable:
            self.includes_map_processor.write_includes_map()

        self.logger.info('Preprocessor applied')
