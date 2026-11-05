"""Candidate manifests are explicit metadata, not fake live news or DVB reception."""
import json
import unittest
from pathlib import Path

DATA=Path(__file__).parents[1]/"data"

class RegionAndNewsSeedsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.regions=json.loads((DATA/"region_profiles.json").read_text(encoding="utf-8"))
        cls.news=json.loads((DATA/"news_sources_candidates.json").read_text(encoding="utf-8"))

    def test_country_region_count_and_uniqueness(self):
        countries={country["iso"]:country for country in self.regions["countries"]}
        self.assertEqual(set(countries),{"DE","TR"})
        for code,count in [("DE",16),("TR",81)]:
            region_list=countries[code]["regions"]
            self.assertEqual(len(region_list),count)
            self.assertEqual(len(set(region_list)),count)

    def test_region_does_not_claim_actual_tv_coverage(self):
        self.assertEqual(self.regions["operational_status"],"design_seed_only")
        for c in self.regions["countries"]:
            self.assertNotIn("frequencies",c)
            self.assertNotIn("available_channels",c)
        self.assertFalse(self.regions["scan_policy"]["automatic_on_region_change"])
        self.assertTrue(self.regions["scan_policy"]["do_not_interrupt_active_recording"])

    def test_unverified_news_is_never_marked_live_or_approved(self):
        self.assertEqual(self.news["verified_live_feeds"],0)
        self.assertFalse(self.news["background_enabled_by_default"])
        self.assertFalse(self.news["startup_enabled_by_default"])
        self.assertEqual(self.news["published_content_ttl_seconds"],86400)
        self.assertFalse(self.news["media_download_default"])
        for s in self.news["sources"]:
            self.assertEqual(s["feed_status"],"candidate_not_verified")
            self.assertIsNone(s["official_account_uri"])
            self.assertIsNone(s["live_stream_uri"])

    def test_requested_parties_and_figure_in_candidate_catalog(self):
        names={s["name"] for s in self.news["sources"]}
        for required in ["HKP — Halkın Kurtuluş Partisi","Halkın Kurtuluş Yolu",
                         "Nurullah Efe Ankut","Ümit Özdağ","Zafer Partisi",
                         "DKP — Deutsche Kommunistische Partei","MLPD","AfD"]:
            self.assertIn(required,names)

    def test_no_political_source_ranking_and_no_delete_user_forum(self):
        self.assertFalse(self.news["clear_saved_user_posts"])
        self.assertTrue(self.news["preserve_original_recordings"])
        self.assertNotIn("rank",self.news["sources"][0])
        self.assertTrue(all(s["kind"] in {
            "newsroom_candidate","party_self_publication_candidate",
            "political_figure_candidate","newsroom_or_research_candidate",
            "institution_candidate"
        } for s in self.news["sources"]))

if __name__=="__main__":
    unittest.main()
