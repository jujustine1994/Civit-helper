import assert from 'node:assert/strict';
const local = {};
globalThis.chrome = {
  webRequest:{onBeforeSendHeaders:{addListener(){}}},
  storage:{session:{get:async()=>({}),set:async()=>{},remove:async()=>{}},
    local:{get:async key=>({[key]:local[key]}),set:async values=>Object.assign(local,values)}},
  runtime:{getURL:path=>'chrome-extension://'+'a'.repeat(32)+'/'+path,
    getManifest:()=>({version:'0.2.1'}),id:'a'.repeat(32),
    onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener(){}}},
  alarms:{create(){},onAlarm:{addListener(){}}}
};
let failure = 'network';
globalThis.fetch = async url => {
  if (String(url).endsWith('local-config.json')) return {ok:true,json:async()=>({port:43187,token:'SECRET_MUST_NOT_LEAK'})};
  if (failure === 'network') throw new TypeError('Failed to fetch');
  return {ok:false,status:403};
};
const {poll} = await import('../extension/worker.js');
await poll();
assert.equal(local.connectionStatus.state, 'connection_failed');
assert.equal(local.connectionStatus.stage, 'connect');
assert.match(local.connectionStatus.message, /Failed to fetch/);
assert(!JSON.stringify(local).includes('SECRET_MUST_NOT_LEAK'));
failure = 'auth';
await poll();
assert.equal(local.connectionStatus.state, 'authentication_failed');
assert(!JSON.stringify(local).includes('SECRET_MUST_NOT_LEAK'));
console.log('EXTENSION_CONNECTION_FIXTURE_OK');
