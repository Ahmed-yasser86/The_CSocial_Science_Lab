import unittest
from unittest.mock import Mock
import requests

from gpt_researcher.scraper.beautiful_soup.beautiful_soup import BeautifulSoupScraper


class BeautifulSoupScraperTimeoutTests(unittest.TestCase):
    def test_fetch_uses_extended_timeout(self):
        session = Mock()
        session.get.side_effect = requests.exceptions.ReadTimeout("read timeout")

        scraper = BeautifulSoupScraper("https://example.com/article", session=session)
        response = scraper._fetch()

        self.assertIsNone(response)
        session.get.assert_called_with("https://example.com/article", timeout=30)


if __name__ == "__main__":
    unittest.main()
