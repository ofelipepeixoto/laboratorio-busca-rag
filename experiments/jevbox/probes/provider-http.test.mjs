// Copyright (c) 2026 Carlos Felipe. SPDX-License-Identifier: MIT
// Original audit regression tests. No network or provider credentials.
import assert from 'node:assert/strict';
import test from 'node:test';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
const { jsonRequest } = await import(pathToFileURL(resolve(process.env.AUDIT_TARGET || '.', 'server/provider-http.ts')).href);
const request = (fetcher, maxResponseBytes=32) => jsonRequest(fetcher, 'https://provider.invalid/test', {}, {maxResponseBytes});
const excessive = error => error.status === 502 && error.retryable === false && /byte limit/.test(error.message);

test('accepts ordinary JSON and disables redirects', async () => {
  assert.deepEqual(await request(async (url, options) => {
    assert.equal(options.redirect, 'error');
    assert.ok(options.signal);
    return new Response('{"ok":true}');
  }), {ok:true});
});
test('accepts JSON at the exact byte boundary', async () => {
  const body='{"a":"á"}';
  assert.deepEqual(await request(async()=>new Response(body),Buffer.byteLength(body)),{a:'á'});
});
test('rejects declared oversized body and cancels it', async () => {
  let cancelled=false;
  const body=new ReadableStream({pull(c){c.enqueue(new TextEncoder().encode('{}'));c.close();},cancel(){cancelled=true;}},{highWaterMark:0});
  await assert.rejects(request(async()=>new Response(body,{headers:{'content-length':'33'}})), excessive);
  assert.equal(cancelled,true);
});
test('bounds streamed bytes without content-length', async () => {
  let cancelled=false;
  let sent=false;
  const body=new ReadableStream({pull(c){if(sent)c.close();else{c.enqueue(new TextEncoder().encode('"'+'x'.repeat(40)+'"'));sent=true;}},cancel(){cancelled=true;}},{highWaterMark:0});
  await assert.rejects(request(async()=>new Response(body)), excessive);
  assert.equal(cancelled,true);
});
test('counts actual bytes despite misleading content-length', async () => {
  await assert.rejects(request(async()=>new Response('"'+'x'.repeat(40)+'"',{headers:{'content-length':'1'}})),excessive);
});
test('adds lengths across chunks before JSON assembly', async()=>{
  const pieces=['"','x'.repeat(20),'x'.repeat(20),'"'];
  const body=new ReadableStream({start(c){for(const p of pieces)c.enqueue(new TextEncoder().encode(p));c.close();}});
  await assert.rejects(request(async()=>new Response(body)),excessive);
});
test('rejects invalid byte policies before calling a provider',async()=>{
  for(const max of [0,-1,NaN,Infinity,1.1,Number.MAX_SAFE_INTEGER+1]) {
    let called=false;
    await assert.rejects(request(async()=>{called=true;return new Response('{}');},max),RangeError);
    assert.equal(called,false);
  }
});
test('does not disclose provider error bodies',async()=>{
  await assert.rejects(request(async()=>new Response('secret-provider-content',{status:400})),e=>e.status===502&&!e.message.includes('secret-provider-content'));
});
