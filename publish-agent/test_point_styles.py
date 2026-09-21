import re
import unittest
from html_clipboard import cf_html
from plan import plan_rich_blocks
from rich_editor import rgb


class PointStyleTests(unittest.TestCase):
    def test_clipboard_offsets_are_bytes_for_korean_text(self):
        fragment='<table><tr><td>중요한 기준</td></tr></table>'
        data=cf_html(fragment)
        offsets={key.decode():int(value) for key,value in re.findall(rb'(StartHTML|EndHTML|StartFragment|EndFragment):(\d+)',data)}
        self.assertEqual(data[offsets['StartFragment']:offsets['EndFragment']].decode('utf8'),fragment)
        self.assertTrue(data[offsets['StartHTML']:offsets['EndHTML']].startswith(b'<html>'))
        self.assertEqual(data[offsets['EndHTML']:],b'\0')

    def test_mixed_plain_and_rich_blocks_do_not_drop_paragraphs(self):
        ops=plan_rich_blocks([{'type':'text','content':'일반 문단'}, {'type':'text','spans':[{'t':'강조','background':'#fff8b2'}]}])
        self.assertEqual(''.join(op.payload for op in ops if op.kind=='text'),'일반 문단강조')
        self.assertEqual(ops[-1].attrs,{'background':'#fff8b2'})

    def test_color_is_validated_before_html_paste(self):
        self.assertEqual(rgb('#C00000'),'rgb(192, 0, 0)')
        with self.assertRaises(ValueError):rgb('red;display:none')


if __name__=='__main__':unittest.main()
