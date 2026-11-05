# SPDX-License-Identifier: AGPL-3.0-only
import unittest
from pathlib import Path

from tihulu_runtime.text_data_browser import (
    TextDataNavigator, BroadcastTextPage, TextPortal
)

DATA=Path(__file__).parents[1]/"data"/"text_data_portals.json"

class TextDataTests(unittest.TestCase):
    def setUp(self):
        self.nav=TextDataNavigator.from_json(DATA)
        self.page=BroadcastTextPage("ard_text",100,0,"ARD Text",
            "Documented content received by a real tuner", "de",
            "2026-11-05T12:00:00Z","WDR",514000000,(110,120))

    def test_teletext_is_never_interactive_radio_chat(self):
        for p in self.nav.portals.values():
            if p.transport=="dvb_teletext":
                self.assertFalse(p.interactive)
                self.assertIsNone(p.link)

    def test_pages_navigation_and_original_provenance(self):
        found=self.nav.open_page(self.page,chosen_page=100)
        self.assertEqual(found.content,self.page.content)
        self.assertEqual(self.nav.linked_page_numbers(found),(110,120))
        article=self.nav.to_news_text(found)
        self.assertEqual(article.language,"de")
        self.assertEqual(article.source_id,"tv_antenna:ard_text")
        self.assertIn("514000000",article.provenance)

    def test_missing_or_other_page_is_not_invented(self):
        with self.assertRaises(RuntimeError):
            self.nav.open_page(self.page,chosen_page=111)
        for p in [0,99,900,5000]:
            with self.assertRaises(ValueError):
                self.nav.validate_page_number(p)
        with self.assertRaises(ValueError):
            self.nav.validate_page_number(100,100)

    def test_real_web_forum_can_open_in_browser_but_not_dvb_page(self):
        forum=self.nav.portals["lk0nod_forum"]
        self.assertTrue(forum.interactive)
        self.assertTrue(self.nav.browser_url(forum).startswith("https://"))
        with self.assertRaises(RuntimeError):
            self.nav.browser_url(self.nav.portals["ard_text"])
        with self.assertRaises(ValueError):
            TextDataNavigator([TextPortal("unsafe","Unsafe","web_https",True,
                True,"candidate","javascript:alert(1)",None)])

    def test_local_bbs_is_not_claimed_installed(self):
        local=self.nav.portals["tihulu_local_bbs"]
        self.assertEqual(local.availability,"planned_unavailable")
        self.assertIsNone(local.link)
        self.assertTrue(local.interactive)

    def test_translator_inputs_keep_selected_transport_permission(self):
        text=self.nav.to_news_text(self.page)
        good=self.nav.selection_for_page(text)
        self.assertIn("tv_antenna:ard_text",good.selected_source_ids)
        with self.assertRaises(PermissionError):
            self.nav.selection_for_page(text,enabled_media=frozenset({"internet"}))


if __name__=="__main__":
    unittest.main()
