import json
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


class ExtensionTests(unittest.TestCase):
    def test_permissions_are_scoped(self):
        manifest = json.loads((ROOT / 'extension/manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(set(manifest['permissions']), {'scripting', 'storage', 'alarms', 'webRequest'})
        self.assertEqual(set(manifest['host_permissions']), {'https://civitai.red/*', 'http://127.0.0.1:43187/*'})
        self.assertNotIn('externally_connectable', manifest)

    def test_page_command_refuses_other_origin(self):
        source = (ROOT / 'extension/page.mjs').read_text(encoding='utf-8')
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='chrome', headless=True)
            try:
                page = browser.new_page()
                page.set_content('<button>Follow</button>')
                page.add_script_tag(content=source.replace('export async function runPageCommand', 'window.runPageCommand = async function'))
                result = page.evaluate("runPageCommand({op: 'action', kind: 'follow', target: '42'})")
                self.assertFalse(result['ok'])
                self.assertEqual(result['code'], 'WRONG_TAB')
            finally:
                browser.close()

    def test_wrong_target_button_cannot_send_mutation(self):
        source = (ROOT / 'extension/page.mjs').read_text(encoding='utf-8')
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='chrome', headless=True)
            try:
                page = browser.new_page()
                page.route('https://civitai.red/**', lambda route: route.fulfill(body='<button aria-label="Heart reaction">Heart</button>', content_type='text/html'))
                page.goto('https://civitai.red/images/42')
                page.evaluate('''() => {
                  window.mutationsSent = 0;
                  window.fetch = async (input, init) => {
                    const url = String(input);
                    let value;
                    if (url.includes('/api/auth/session')) value = {user:{id:7}};
                    else if (url.includes('getMyImageReactions')) value = {result:{data:{json:{}}}};
                    else { window.mutationsSent++; value = {result:{data:{json:'created'}}}; }
                    return new Response(JSON.stringify(value), {status:200,headers:{'content-type':'application/json'}});
                  };
                  document.querySelector('button').onclick = () => fetch('/api/trpc/reaction.toggle', {
                    method:'POST',body:JSON.stringify({json:{entityType:'image',entityId:43,reaction:'Heart'}})
                  }).catch(()=>{});
                }''')
                page.add_script_tag(content=source.replace('export async function runPageCommand', 'window.runPageCommand = async function'))
                page.evaluate("""() => {
                  window.runPageCommand({op:'action',kind:'heart',target:'42',accountId:'7',expiresAt:Date.now()+5000}).catch(()=>{});
                }""")
                page.wait_for_timeout(500)
                self.assertEqual(page.evaluate('window.mutationsSent'), 0)
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
