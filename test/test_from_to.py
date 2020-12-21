import logging
from pathlib import Path
from unittest import TestCase
from foliant_test.preprocessor import PreprocessorTestFramework
from .utils import data_file_content


logging.disable(logging.CRITICAL)


class TestFromTo(TestCase):
    def setUp(self):
        self.ptf = PreprocessorTestFramework('includes')
        self.ptf.context['project_path'] = Path('.')

    def test_from_heading(self):
        sub = data_file_content('data/multi_title.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" from_heading="My subtitle"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_heading.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_to_heading(self):
        sub = data_file_content('data/multi_title.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" to_heading="My subtitle"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/to_heading.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_from_to_heading(self):
        sub = data_file_content('data/multi_title.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" from_heading="My subtitle" to_heading="My sub-subtitle"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_to_heading.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_from_customid(self):
        sub = data_file_content('data/with_ids.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" from_id="my_subtitle_id"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_customid.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_to_customid(self):
        sub = data_file_content('data/with_ids.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" to_id="my_subtitle_id"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/to_customid.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_from_to_customid(self):
        sub = data_file_content('data/with_ids.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" from_id="my_subtitle_id" to_id="my_sub-subtitle_id"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_to_customid.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_from_anchor(self):
        sub = data_file_content('data/with_ids.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" from_id="anchor_1"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_anchor.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_to_anchor(self):
        sub = data_file_content('data/with_ids.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" to_id="anchor_2"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/to_anchor.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_from_to_anchor(self):
        sub = data_file_content('data/with_ids.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" from_id="anchor_2" to_id="anchor_4"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_to_anchor.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_from_heading_to_anchor(self):
        sub = data_file_content('data/with_ids.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" from_heading="My subtitle {#my_subtitle_id}" to_id="anchor_4"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_heading_to_anchor.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_from_anchor_to_heading(self):
        sub = data_file_content('data/with_ids.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" from_id="anchor_1" to_heading="My sub-subtitle {#my_sub-subtitle_id}"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_anchor_to_heading.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_from_heading_to_end(self):
        sub = data_file_content('data/multi_title.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" from_heading="My subtitle" to_end="true"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_heading_to_end.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_from_anchor_to_end(self):
        sub = data_file_content('data/with_ids.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" from_id="anchor_1" to_end="true"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_anchor_to_end.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )

    def test_from_customid_to_end(self):
        sub = data_file_content('data/with_ids.md')
        input_map = {
            'index.md': '# My title\n\n<include src="sub/sub.md" from_id="my_subtitle_id" to_end="true"></include>',
            'sub/sub.md': sub
        }
        expected_map = {
            'index.md': f'# My title\n\n{data_file_content("data/from_to/from_customid_to_end.md")}',
            'sub/sub.md': sub
        }
        self.ptf.test_preprocessor(
            input_mapping=input_map,
            expected_mapping=expected_map,
        )
