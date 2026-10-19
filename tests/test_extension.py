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

    def test_read_decodes_devalue_feed_to_regular_json(self):
        source = (ROOT / 'extension/page.mjs').read_text(encoding='utf-8')
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='chrome', headless=True)
            try:
                page = browser.new_page()
                page.route('https://civitai.red/**', lambda route: route.fulfill(body='<main></main>', content_type='text/html'))
                page.goto('https://civitai.red/images')
                page.evaluate('''() => {
                  window.fetch = async () => new Response(JSON.stringify({result:{data:
                    '[{"items":1,"nextCursor":7},[2],{"id":3,"userId":4,"user":5},42,7,{"id":4,"username":6},"creator",null]'
                  }}), {status:200,headers:{'content-type':'application/json'}});
                }''')
                page.add_script_tag(content=source.replace('export async function runPageCommand', 'window.runPageCommand = async function'))
                result = page.evaluate("runPageCommand({op:'read',path:'/api/trpc/image.getInfinite',expiresAt:Date.now()+5000})")
                self.assertTrue(result['ok'])
                decoded = result['result']['data']['result']['data']
                self.assertIsInstance(decoded, dict)
                self.assertEqual(decoded['json']['items'][0]['id'], 42)
                self.assertEqual(decoded['json']['items'][0]['user']['id'], 7)
                self.assertIsNone(decoded['json']['nextCursor'])
            finally:
                browser.close()

    def test_devalue_heart_and_follow_acknowledgments_confirm_exactly_once(self):
        source = (ROOT / 'extension/page.mjs').read_text(encoding='utf-8')
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='chrome', headless=True)
            try:
                for kind in ('heart', 'follow'):
                    with self.subTest(kind=kind):
                        page = browser.new_page()
                        markup = '<button aria-label="Heart reaction">Heart</button>' if kind == 'heart' else '<button>Follow</button>'
                        page.route('https://civitai.red/**', lambda route: route.fulfill(body=markup, content_type='text/html'))
                        page.goto('https://civitai.red/images/42' if kind == 'heart' else 'https://civitai.red/user/creator')
                        page.evaluate('''kind => {
                          window.mutationsSent = 0;
                          window.originalFetch = window.fetch = async (input, init) => {
                            const url = String(input);
                            let value;
                            if (url.includes('/api/auth/session')) value = {user:{id:7}};
                            else if (url.includes('getMyImageReactions')) value = {result:{data:'[{}]'}};
                            else if (url.includes('getFollowingUsers')) value = {result:{data:'[[]]'}};
                            else { window.mutationsSent++; value = {result:{data:kind==='heart'?'["created"]':'[{"following":1},true]'}}; }
                            return new Response(JSON.stringify(value), {status:200,headers:{'content-type':'application/json'}});
                          };
                          document.querySelector('button').onclick = () => fetch('/api/trpc/'+(kind==='heart'?'reaction.toggle':'user.toggleFollow'), {
                            method:'POST',body:JSON.stringify({json:kind==='heart'?{entityType:'image',entityId:42,reaction:'Heart'}:{targetUserId:42}})
                          }).catch(()=>{});
                        }''', kind)
                        page.add_script_tag(content=source.replace('export async function runPageCommand', 'window.runPageCommand = async function'))
                        result = page.evaluate("kind => runPageCommand({op:'action',kind,target:'42',username:'creator',accountId:'7',expiresAt:Date.now()+5000})", kind)
                        self.assertTrue(result['ok'], result)
                        self.assertTrue(result['result']['accepted'])
                        self.assertEqual(page.evaluate('window.mutationsSent'), 1)
                        self.assertTrue(page.evaluate('window.fetch === window.originalFetch'))
                        page.close()
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
