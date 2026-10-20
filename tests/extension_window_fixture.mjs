import assert from 'node:assert/strict';

let stored = {};
let marker;
let extraTab = false;
let closedWindows = [];
let closedTabs = [];
let requestObserver;
let options;
let windowState = 'normal';  // Chrome ignored the requested minimized state.
let windowUpdates = [];
globalThis.sessionStorage = {getItem: () => marker, setItem: (key, value) => {marker = value;}};
globalThis.chrome = {
  webRequest: {onBeforeSendHeaders: {addListener: fn => {requestObserver = fn;}}},
  storage: {session: {
    get: async key => ({[key]: stored[key]}),
    set: async values => Object.assign(stored, values),
    remove: async key => {delete stored[key];}
  }},
  windows: {
    create: async value => {options = value; return {id: 100, tabs: [{id: 200, windowId: 100}]};},
    get: async id => ({id, state: windowState}),
    update: async (id, value) => {windowUpdates.push([id, value]); windowState = value.state;},
    remove: async id => closedWindows.push(id)
  },
  tabs: {
    get: async id => ({id, windowId: 100, url: 'https://civitai.red/images', status: 'complete'}),
    update: async () => {},
    reload: async () => requestObserver({tabId: 200,
      url: 'https://civitai.red/api/trpc/image.getInfinite?input=' + encodeURIComponent(JSON.stringify({json:{browsingLevel:1}})),
      requestHeaders: [{name:'x-client',value:'web'},{name:'x-client-version',value:'fixture'}]}),
    query: async () => extraTab ? [{id:200},{id:201}] : [{id:200}],
    remove: async id => closedTabs.push(id)
  },
  scripting: {executeScript: async request => [{result: await request.func(...(request.args || []))}]},
  runtime: {onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener(){}}},
  alarms: {create(){},onAlarm:{addListener(){}}}
};
const {dispatch} = await import('../extension/worker.js');
const cmd = op => ({id:'fixture',op,expiresAt:Date.now()+5000});
await dispatch(cmd('init'));
assert.equal(options.state, 'minimized');
assert.equal(options.focused, false);
assert.equal(options.type, 'normal');
assert.deepEqual(windowUpdates, [[100, {state: 'minimized', focused: false}]]);
windowState = 'normal';  // Simulate Chrome restoring the window during navigation.
await dispatch({...cmd('navigate'), path: '/images/42'});
assert.equal(windowUpdates.length, 2);
await dispatch(cmd('close'));
assert.deepEqual(closedWindows, [100]);
assert.deepEqual(closedTabs, []);
stored = {}; marker = undefined; closedWindows = []; extraTab = true;
await dispatch(cmd('init'));
await dispatch(cmd('close'));
assert.deepEqual(closedWindows, []);
assert.deepEqual(closedTabs, [200]);
console.log('EXTENSION_WINDOW_FIXTURE_OK');
