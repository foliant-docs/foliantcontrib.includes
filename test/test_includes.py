import logging
import re
from inspect import getsource
from pathlib import Path
from unittest import TestCase
from foliant_test.preprocessor import PreprocessorTestFramework
from .utils import data_file_content
import urllib.request


logging.disable(logging.CRITICAL)


class TestIncludesBasic(TestCase):
    def setUp(self):
        self.ptf = PreprocessorTestFramework('includes')
        self.ptf.context['project_path'] = Path('.')

    def test_src(self):
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md"></include>',
            'sub/sub.md': 'Included content'
        }
        expected_map = {
            'index.md': '# My title\n\nIncluded content',
            'sub/sub.md': 'Included content'
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_url(self):
        input_map = {
            'index.md': '# My title\n\n<include url="https://github.com/foliant-docs/foliantcontrib.includes/raw/master/test/data/from_to/from_anchor.md" nohead="true"></include>',
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_anchor.md")}',
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_repo_path(self):
        input_map = {
            'index.md': '# My title\n\n<include repo_url="https://github.com/foliant-docs/foliantcontrib.includes" path="LICENSE"></include>',
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("../LICENSE")}',
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_include_link(self):
        input_map = {
            'index.md': '# My title\n\n<include repo_url="https://github.com/foliant-docs/foliantcontrib.includes" revision="master" path="LICENSE"></include>',
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("../LICENSE")}',
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_include_internal_links(self):
        input_map = {
            'index.md': '# My title\n\n<include repo_url="https://github.com/foliant-docs/foliantcontrib.includes" revision="master" path="test/data/from_to/from_test_links.md"></include>',
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/to_test_links.md")}',
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_nohead(self):
        input_map = {
            'index.md': '# My title\n\n<include nohead="true" src="sub/sub.md"></include>',
            'sub/sub.md': '# Included title\n\nIncluded content'
        }
        expected_map = {
            'index.md': '# My title\n\nIncluded content',
            'sub/sub.md': '# Included title\n\nIncluded content'
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_sethead(self):
        input_map = {
            'index.md': '# Title\n\n## Subtitle\n\n<include src="other.md" sethead="3"></include>',
            'other.md': '# Included title\n\nIncluded content'
        }
        expected_map = {
            'index.md': '# Title\n\n## Subtitle\n\n### Included title\n\nIncluded content',
            'other.md': '# Included title\n\nIncluded content'
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_inline(self):
        input_map = {
            'index.md': '# My title\n\nIncluded inline: <include inline="true" src="sub/sub.md"></include>',
            'sub/sub.md': '# Included title\n\nIncluded content'
        }
        expected_map = {
            'index.md': '# My title\n\nIncluded inline: # Included title Included content',
            'sub/sub.md': '# Included title\n\nIncluded content'
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_wrap_code(self):
        code = getsource(data_file_content)
        index = '# My title\n\n<include src="sub/sub.md" wrap_code="{type}"></include>'
        input_map = {
            'index.md': index.format(type='triple_backticks'),
            'sub/sub.md': code
        }
        expected_map = {
            'index.md': f'# My title\n\n```\n{code}```\n',
            'sub/sub.md': code
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )
        input_map = {
            'index.md': index.format(type='triple_tildas'),
            'sub/sub.md': code
        }
        expected_map = {
            'index.md': f'# My title\n\n~~~\n{code}~~~\n',
            'sub/sub.md': code
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_wrap_code_single_backticks(self):
        code = 'code inline string'
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" wrap_code="single_backticks"></include>',
            'sub/sub.md': code
        }
        expected_map = {
            'index.md': f'# My title\n\n`code inline string`\n',
            'sub/sub.md': code
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_wrap_code_single_backticks_inline(self):
        code = getsource(data_file_content)
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" wrap_code="single_backticks" inline="true"></include>',
            'sub/sub.md': code
        }
        inline_code = re.sub(r'\s+', ' ', code)
        expected_map = {
            'index.md': f"# My title\n\n`{inline_code}`\n",
            'sub/sub.md': code
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_wrap_code_language(self):
        code = getsource(data_file_content)
        index = '# My title\n\n<include src="sub/sub.md" wrap_code="{type}" code_language="python"></include>'
        input_map = {
            'index.md': index.format(type='triple_backticks'),
            'sub/sub.md': code
        }
        expected_map = {
            'index.md': f'# My title\n\n```python\n{code}```\n',
            'sub/sub.md': code
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )
        input_map = {
            'index.md': index.format(type='triple_tildas'),
            'sub/sub.md': code
        }
        expected_map = {
            'index.md': f'# My title\n\n~~~python\n{code}~~~\n',
            'sub/sub.md': code
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_code_language_single_backticks(self):
        code = 'code inline string'
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" wrap_code="single_backticks" code_language="ignored"></include>',
            'sub/sub.md': code
        }
        expected_map = {
            'index.md': f'# My title\n\n`code inline string`\n',
            'sub/sub.md': code
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_extensions(self):
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md"></include>',
            'index.j2': '# My title\n\n<include src="sub/sub.md"></include>',
            'sub/sub.md': 'Included content'
        }
        expected_map = {
            'index.md': '# My title\n\nIncluded content',
            'index.j2': '# My title\n\n<include src="sub/sub.md"></include>',
            'sub/sub.md': 'Included content'
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )
        self.ptf.options = {'extensions': ['md', 'j2']}
        expected_map = {
            'index.md': '# My title\n\nIncluded content',
            'index.j2': '# My title\n\nIncluded content',
            'sub/sub.md': 'Included content'
        }

    def test_includes_map(self):
        self.ptf.options = {'includes_map': True }
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub-1.md"></include>\n\n<include src="sub/sub-2.md"></include>',
            'sub/sub-1.md': 'Included content 1',
            'sub/sub-2.md': 'Included content 2'
        }
        expected_map = {
            'index.md': '# My title\n\nIncluded content 1\n\nIncluded content 2',
            'static/includes_map.json': "[{\"file\": \"__src__/index.md\", \"includes\": [\"__src__/sub/sub-1.md\", \"__src__/sub/sub-2.md\"]}]",
            'sub/sub-1.md': 'Included content 1',
            'sub/sub-2.md': 'Included content 2'
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_adjust_links_with_md(self):
        input_map = {
            'sub/file_a.md': '# Title file_a\n\n<include src="file_b.md"></include>',
            'sub/file_b.md': 'Included [file_c link](./file_c.md#anchor)',
            'sub/file_c.md': '# Included content \n\n## Header with anchor {#anchor}',
            'file_d.md': '# Title file_d\n\n<include src="sub/file_b.md"></include>'
        }
        expected_map = {
            'sub/file_a.md': '# Title file_a\n\nIncluded [file_c link](../sub/file_c.md#anchor)',
            'sub/file_b.md': 'Included [file_c link](./file_c.md#anchor)',
            'sub/file_c.md': '# Included content \n\n## Header with anchor {#anchor}',
            'file_d.md': '# Title file_d\n\nIncluded [file_c link](sub/file_c.md#anchor)'
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_adjust_links_with_md_two(self):
        input_map = {
            'file_a.md': '# Title file_a\n\n<include src="file_b.md"></include>',
            'file_b.md': 'Included [file_c link](./file_c.md#anchor)',
            'file_c.md': '# Included content \n\n## Header with anchor {#anchor}',
            'sub/file_d.md': '# Title file_d\n\n<include src="../file_b.md"></include>'
        }
        expected_map = {
            'file_a.md': '# Title file_a\n\nIncluded [file_c link](file_c.md#anchor)',
            'file_b.md': 'Included [file_c link](./file_c.md#anchor)',
            'file_c.md': '# Included content \n\n## Header with anchor {#anchor}',
            'sub/file_d.md': '# Title file_d\n\nIncluded [file_c link](../file_c.md#anchor)'
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_adjust_links(self):
        input_map = {
            'file_a.md': '# Title file_a\n\n<include src="file_b.md"></include>',
            'file_b.md': 'Included [file_c link](../file_c/)',
            'file_c.md': '# Included content \n\n## Header',
            'sub/file_d.md': '# Title file_d\n\n<include src="../file_b.md"></include>'
        }
        expected_map = {
            'file_a.md': '# Title file_a\n\nIncluded [file_c link](../file_c/)',
            'file_b.md': 'Included [file_c link](../file_c/)',
            'file_c.md': '# Included content \n\n## Header',
            'sub/file_d.md': '# Title file_d\n\nIncluded [file_c link](../../file_c/)'
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )


    def test_adjust_links_two(self):
        input_map = {
            'sub/file_a.md': '# Title file_a\n\n<include src="file_b.md"></include>',
            'sub/file_b.md': 'Included [file_c link](../file_c/)',
            'file_d.md': '# Title file_d\n\n<include src="sub/file_b.md"></include>'
        }
        expected_map = {
            'sub/file_a.md': '# Title file_a\n\nIncluded [file_c link](../file_c/)',
            'sub/file_b.md': 'Included [file_c link](../file_c/)',
            'file_d.md': '# Title file_d\n\nIncluded [file_c link](../sub/file_c.md)'
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_adjust_links_three(self):
        input_map = {
            'sub/file_a.md': '# Title file_a\n\n<include src="file_b.md"></include>',
            'sub/file_b.md': 'Included [file_c link](../file_c)',
            'sub/file_c.md': '# Included content \n\n## Header',
            'file_d.md': '# Title file_d\n\n<include src="sub/file_b.md"></include>'
        }
        expected_map = {
            'sub/file_a.md': '# Title file_a\n\nIncluded [file_c link](../file_c)',
            'sub/file_b.md': 'Included [file_c link](../file_c)',
            'sub/file_c.md': '# Included content \n\n## Header',
            'file_d.md': '# Title file_d\n\nIncluded [file_c link](../sub/file_c.md)'
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )
