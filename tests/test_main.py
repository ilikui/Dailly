import unittest

from Src.main import (
    build_weather_payload,
    fetch_all_feeds,
    filter_by_keywords,
    parse_json_feed,
    parse_xml_feed,
)


class FeedParserTests(unittest.TestCase):
    def test_parse_rss_xml(self):
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel><item>
          <title>Example headline</title>
          <link>https://example.com/story</link>
          <description>Short summary</description>
        </item></channel></rss>"""
        items = parse_xml_feed(xml)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Example headline")
        self.assertEqual(items[0]["url"], "https://example.com/story")

    def test_parse_atom_xml(self):
        xml = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
          <title>Atom story</title>
          <link href="https://example.com/atom" rel="alternate" />
          <summary>Summary</summary>
        </entry></feed>"""
        items = parse_xml_feed(xml)
        self.assertEqual(items[0]["url"], "https://example.com/atom")

    def test_parse_json_feed(self):
        payload = """{"version":"https://jsonfeed.org/version/1.1","items":[
          {"title":"JSON story","url":"https://example.com/json","summary":"Summary"}
        ]}"""
        items = parse_json_feed(payload)
        self.assertEqual(items[0]["title"], "JSON story")
        self.assertEqual(items[0]["content_text"], "Summary")

    def test_deduplicate_across_feeds(self):
        sources = [
            {"url": "feed-a", "type": "Tech", "name": "A"},
            {"url": "feed-b", "type": "News", "name": "B"},
        ]
        original = {
            "feed-a": [{"title": "Same", "url": "https://example.com/a"}],
            "feed-b": [{"title": "Same", "url": "https://example.com/a"}],
        }
        from unittest.mock import patch
        with patch("Src.main.fetch_feed", side_effect=lambda url: original[url]):
            items = fetch_all_feeds(sources)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "A")

    def test_keyword_filter_is_case_insensitive(self):
        items = [
            {"title": "Python Guide", "content_text": "Basics"},
            {"title": "Other topic", "content_text": "nothing"},
        ]
        self.assertEqual(len(filter_by_keywords(items, ["python"])), 1)
        self.assertEqual(len(filter_by_keywords(items, [])), 2)

    def test_weather_payload_handles_missing_optional_fields(self):
        payload = {
            "result": {
                "realtime": {"temperature": 21, "skycon": "CLEAR_DAY"},
                "daily": {"temperature": [{"date": "2026-10-24", "min": 16, "max": 25}]},
            }
        }
        weather = build_weather_payload(payload)
        self.assertEqual(weather["desc"], "晴")
        self.assertEqual(len(weather["forecast"]), 1)
        self.assertEqual(weather["forecast"][0]["desc"], "未知")


if __name__ == "__main__":
    unittest.main()
