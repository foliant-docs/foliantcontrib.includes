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

    def test_includes_map_with_not_build_file(self):
        '''Test includes_map generation for files with not_build: true parameter.'''
        self.ptf.options = {'includes_map': True }
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub-1.md"></include>',
            'not_build.md': """---
not_build: true
---

# Not built file

<include src="sub/sub-2.md"></include>""",
            'sub/sub-1.md': 'Included content 1',
            'sub/sub-2.md': 'Included content 2'
        }
        expected_map = {
            'index.md': '# My title\n\nIncluded content 1',
            'static/includes_map.json': "[{\"file\": \"__src__/index.md\", \"includes\": [\"__src__/sub/sub-1.md\"]}, {\"file\": \"__src__/not_build.md\", \"includes\": [\"__src__/sub/sub-2.md\"]}]",
            'not_build.md': """---
not_build: true
---

# Not built file

Included content 2""",
            'sub/sub-1.md': 'Included content 1',
            'sub/sub-2.md': 'Included content 2'
        }

        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_includes_map_with_anchors_and_not_build(self):
        '''Test includes_map generation with anchors for files with not_build: true.'''
        self.ptf.options = {'includes_map': {'anchors': True} }
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub-1.md"></include>',
            'not_build.md': """---
not_build: true
---

# Not built file

<include src="sub/sub-2.md"></include>""",
            'sub/sub-1.md': '# Included 1 {#anchor1}\n\nContent 1\n\n<anchor>anchor2</anchor>',
            'sub/sub-2.md': '# Included 2 {#anchor3}\n\nContent 2\n\n<anchor>anchor4</anchor>'
        }
        expected_map = {
            'index.md': '# My title\n\n# Included 1 {#anchor1}\n\nContent 1\n\n<anchor>anchor2</anchor>',
            'static/includes_map.json': "[{\"file\": \"__src__/index.md\", \"includes\": [\"__src__/sub/sub-1.md\"], \"anchors\": [\"anchor1\", \"anchor2\"]}, {\"file\": \"__src__/not_build.md\", \"includes\": [\"__src__/sub/sub-2.md\"], \"anchors\": [\"anchor3\", \"anchor4\"]}]",
            'not_build.md': """---
not_build: true
---

# Not built file

# Included 2 {#anchor3}\n\nContent 2\n\n<anchor>anchor4</anchor>""",
            'sub/sub-1.md': '# Included 1 {#anchor1}\n\nContent 1\n\n<anchor>anchor2</anchor>',
            'sub/sub-2.md': '# Included 2 {#anchor3}\n\nContent 2\n\n<anchor>anchor4</anchor>'
        }

        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_recursive_includes_in_not_build_file(self):
        '''Test recursive includes in files with not_build: true.'''
        self.ptf.options = {'includes_map': True, 'recursive': True }
        input_map = {
            'index.md': '# Main file\n\n<include src="not_build.md"></include>',
            'not_build.md': """---
not_build: true
---

# Not built file

<include src="level1.md"></include>""",
            'level1.md': '# Level 1\n\n<include src="level2.md"></include>',
            'level2.md': '# Level 2\n\nFinal content'
        }
        expected_map = {
            'index.md': '# Main file\n\n# Not built file\n\n# Level 1\n\n# Level 2\n\nFinal content',
            'static/includes_map.json': "[{\"file\": \"__src__/index.md\", \"includes\": [\"__src__/not_build.md\"]}, {\"file\": \"__src__/level1.md\", \"includes\": [\"__src__/level2.md\"]}, {\"file\": \"__src__/not_build.md\", \"includes\": [\"__src__/level1.md\"]}]",
            'not_build.md': """---
not_build: true
---

# Not built file

# Level 1\n\n# Level 2\n\nFinal content""",
            'level1.md': '# Level 1\n\n# Level 2\n\nFinal content',
            'level2.md': '# Level 2\n\nFinal content'
        }

        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_includes_map_with_from_to_in_not_build(self):
        '''Test includes_map with from/to parameters in not_build files.'''
        self.ptf.options = {'includes_map': True }
        input_map = {
            'not_build.md': """---
not_build: true
---

# Not built file

<include src="content.md" from_heading="Section 1" to_heading="Section 2"></include>""",
            'content.md': '# Section 1\n\nContent 1\n\n# Section 2\n\nContent 2\n\n# Section 3\n\nContent 3'
        }

        expected_map = {
            'static/includes_map.json': "[{\"file\": \"__src__/not_build.md\", \"includes\": [\"__src__/content.md\"]}]\n",
            'not_build.md': """---
not_build: true
---

# Not built file

# Section 1\n\nContent 1\n""",
            'content.md': '# Section 1\n\nContent 1\n\n# Section 2\n\nContent 2\n\n# Section 3\n\nContent 3'
        }

        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_includes_map_empty_file_with_not_build(self):
        '''Test includes_map with empty file that has not_build: true.'''
        self.ptf.options = {'includes_map': True }
        working_dir = self.ptf.context["project_path"].absolute()
        tmp_dir= self.ptf.context["config"]["tmp_dir"]

        input_map = {
            'not_build.md': """---
not_build: true
---

# Empty not built file

<include src="non_existent.md"></include>""",
        }

        self.ptf.options['allow_failure'] = True

        expected_map = {
            'static/includes_map.json': "[{\"file\": \"__src__/not_build.md\", \"includes\": [\"__src__/non_existent.md\"]}]",
            'not_build.md': f"""---
not_build: true
---

# Empty not built file

The url or repo_url link is not correct, file not found: {working_dir}/{tmp_dir}/non_existent.md""",
        }

        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )
