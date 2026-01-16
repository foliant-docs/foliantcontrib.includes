import re
import urllib.request
import urllib.error
import urllib.parse
import socket
from pathlib import Path
from hashlib import md5


class URLHandler:
    def __init__(self, preprocessor):
        self.preprocessor = preprocessor
        self.logger = preprocessor.logger

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
            self.preprocessor._downloaded_dir_path /
            f'{md5(url.encode()).hexdigest()[:8]}_{url_path.stem}{extra_stem}{url_path.suffix}{extra_suffix}'
        )

        self.logger.debug(f'Downloaded file path: {downloaded_file_path}')

        if not downloaded_file_path.exists():
            self.logger.debug('Performing URL request')
            try:
                response = urllib.request.urlopen(url, timeout=2)
            except (urllib.error.HTTPError, urllib.error.URLError) as error:
                self.logger.error(f'Data is not retrieved with {error}\nURL: {url}')
                raise
            except socket.timeout:
                self.logger.error(f'socket timed out - URL {url}')
                raise
            else:
                charset = 'utf-8'

                if response.headers.get('Content-Type'):
                    charset_match = re.search(
                        r'(^|[\s;])charset=(?P<charset>[^\s;]+)',
                        response.headers['Content-Type']
                    )

                    if charset_match:
                        charset = charset_match.group('charset')

                self.logger.debug(f'Detected source charset: {charset}')

                downloaded_content = response.read().decode(charset)

                self.preprocessor._downloaded_dir_path.mkdir(parents=True, exist_ok=True)

                # Convert relative paths to absolute links in downloaded content
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
                        if relative_path and sub_relative_path:
                            dict_new_link[line] = (
                                sub_relative_path[0] + '(' +
                                url.rpartition('/')[0].replace('raw', 'blob') + '/' +
                                relative_path[0].partition('(')[2]
                            )

                for line in dict_new_link:
                    downloaded_content = downloaded_content.replace(line, dict_new_link[line])

                with open(downloaded_file_path, 'w', encoding='utf8') as downloaded_file:
                    downloaded_file.write(downloaded_content)
        else:
            self.logger.debug('File found in cache, it was already downloaded at this run')

        return downloaded_file_path
