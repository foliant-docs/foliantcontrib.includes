from pathlib import Path
from os import getcwd


class PathResolver:
    def __init__(self, preprocessor):
        self.preprocessor = preprocessor
        self.logger = preprocessor.logger

    def _find_file(self, file_name: str, lookup_dir: Path) -> Path or None:
        '''Find a file in a directory by name. Check subdirectories recursively.

        :param file_name: Name of the file
        :param lookup_dir: Starting directory

        :returns: Path to the found file or None if the file was not found
        :raises: FileNotFoundError
        '''
        self.logger.debug(f'Trying to find the file {file_name} inside the directory {lookup_dir}')
        result = None

        for item in lookup_dir.rglob('*'):
            if item.name == file_name:
                result = item
                break

        if result is None:
            raise FileNotFoundError(f"File not found: {file_name}")

        self.logger.debug(f'File found: {result}')
        return result

    def _get_src_file_path(self, markdown_file_path: Path) -> Path:
        '''Translate the path of Markdown file that is located inside the temporary working directory
        into the path of the corresponding Markdown file that is located inside the source directory
        of Foliant project.

        :param markdown_file_path: Path to Markdown file that is located inside the temporary working directory

        :returns: Mapping of Markdown file path to the source directory
        '''
        path_relative_to_working_dir = markdown_file_path.relative_to(self.preprocessor.working_dir.resolve())

        self.logger.debug(
            'Currently processed Markdown file path relative to working dir: ' +
            f'{path_relative_to_working_dir}'
        )

        path_mapped_to_src_dir = (
            self.preprocessor.project_path.resolve() /
            self.preprocessor.config['src_dir'] /
            path_relative_to_working_dir
        )

        self.logger.debug(
            'Currently processed Markdown file path mapped to source dir: ' +
            f'{path_mapped_to_src_dir}'
        )

        return path_mapped_to_src_dir

    def _get_included_file_path(self, user_specified_path: str or Path, current_processed_file_path: Path) -> Path:
        '''Resolve user specified path to the local included file.

        :param user_specified_path: User specified string that represents
            the path to a local file

        :param current_processed_file_path: Path to the currently processed Markdown file
            that contains include statements

        :returns: Local path of the included file relative to the currently processed Markdown file
        '''
        self.logger.debug(f'Currently processed Markdown file: {current_processed_file_path}')
        included_file_path = (current_processed_file_path.parent / Path(user_specified_path)).resolve()

        self.logger.debug(f'User-specified included file path: {included_file_path}')

        if (
            self.preprocessor.working_dir.resolve() in current_processed_file_path.parents
            and
            self.preprocessor.working_dir.resolve() not in included_file_path.parents
        ):
            self.logger.debug(
                'Currently processed file is located inside the working dir, ' +
                'but included file is located outside the working dir. ' +
                'So currently processed file path should be rewritten with the path of corresponding file ' +
                'that is located inside the source dir'
            )

            included_file_path = (
                self._get_src_file_path(current_processed_file_path).parent / Path(user_specified_path)
            ).resolve()
        else:
            self.logger.debug('Using these paths without changes')

        self.logger.debug(f'Finally, included file path: {included_file_path}')
        return included_file_path

    def _prepare_path_for_includes_map(self, path: Path) -> str:
        """Prepare path for includes map."""
        donor_path = None
        if path.as_posix().startswith(self.preprocessor.working_dir.as_posix()):
            _path = path.relative_to(self.preprocessor.working_dir)
            donor_path = f"{self.preprocessor.src_dir}/{_path.as_posix()}"
        elif path.as_posix().startswith(getcwd()):
            _path = path.relative_to(getcwd())
            if _path.as_posix().startswith(self.preprocessor.working_dir.as_posix()):
                _path = _path.relative_to(self.preprocessor.working_dir)
                donor_path = f"{self.preprocessor.src_dir}/{_path.as_posix()}"
            else:
                donor_path = _path.as_posix()
        return donor_path
