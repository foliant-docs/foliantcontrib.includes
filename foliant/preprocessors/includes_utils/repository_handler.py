from pathlib import Path
from subprocess import run, CalledProcessError, PIPE, STDOUT


class RepositoryHandler:
    def __init__(self, preprocessor):
        self.preprocessor = preprocessor
        self.logger = preprocessor.logger

    def _sync_repo(self, repo_url: str, revision: str or None = None) -> Path:
        '''Clone a Git repository to the cache dir. If it has been cloned before, update it.

        :param repo_url: Repository URL
        :param revision: Revision: branch, commit hash, or tag

        :returns: Path to the cloned repository
        '''
        repo_name = repo_url.split('/')[-1].rsplit('.', maxsplit=1)[0]
        repo_path = (self.preprocessor._cache_dir_path / repo_name).resolve()

        self.logger.debug(f'Synchronizing with repo; URL: {repo_url}, revision: {revision}')

        try:
            if not repo_path.exists():
                self.logger.debug(f'Cloning repo {repo_url} to {repo_path}')

                run(
                    f'git clone {repo_url} {repo_path}',
                    shell=True,
                    check=True,
                    stdout=PIPE,
                    stderr=STDOUT
                )
            else:
                self.logger.debug('Repo already exists; pulling from remote')
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
                    self.logger.warning(f"Git pull failed: {exception}")

        except CalledProcessError as exception:
            self.logger.error(f"Git operation failed: {exception}")
            raise

        if revision:
            try:
                run(
                    f'git checkout {revision}',
                    cwd=repo_path,
                    shell=True,
                    check=True,
                    stdout=PIPE,
                    stderr=STDOUT
                )
            except CalledProcessError as exception:
                self.logger.warning(f"Failed to checkout revision {revision}: {exception}")

        return repo_path
