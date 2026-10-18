"""Real Chrome fixture: no account and no external social actions."""
import unittest
from playwright.sync_api import sync_playwright
from civit_helper.site import ChromeSite


class BrowserFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel='chrome', headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def test_delayed_add_reaction_is_opened_before_waiting_for_heart(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_content('''<main id="reactions"></main><script>
            setTimeout(() => {
              const add = document.createElement('button');
              add.setAttribute('aria-label', 'Add reaction');
              add.onclick = () => {
                const heart = document.createElement('button');
                heart.setAttribute('aria-label', 'Heart reaction');
                heart.textContent='Heart';
                document.body.appendChild(heart);
              };
              document.body.appendChild(add);
            }, 300);
            </script>''')
        site = object.__new__(ChromeSite)
        site.page = page
        button = site._heart_button()
        self.assertTrue(button.is_visible())
        self.assertEqual(button.get_attribute('aria-label'), 'Heart reaction')


if __name__ == '__main__':
    unittest.main()
