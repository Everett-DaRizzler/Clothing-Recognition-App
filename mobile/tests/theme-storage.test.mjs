import test from 'node:test';
import assert from 'node:assert/strict';
import { createLatestThemeWriter } from '../src/theme-storage.ts';

test('quick theme changes persist in order and only the latest reports success', async () => {
  const first = Promise.withResolvers();
  const calls = [], results = [];
  const persist = createLatestThemeWriter(async id => {
    calls.push(id);
    if (id === 'daylight') await first.promise;
  }, saved => results.push(saved));
  const a = persist('daylight');
  const b = persist('evergreen');
  await Promise.resolve();
  assert.deepEqual(calls, ['daylight']);
  first.resolve();
  await Promise.all([a, b]);
  assert.deepEqual(calls, ['daylight', 'evergreen']);
  assert.deepEqual(results, [true]);
});

test('an older failed write cannot leave an error after the latest succeeds', async () => {
  const first = Promise.withResolvers();
  const results = [];
  let stored;
  const persist = createLatestThemeWriter(async id => {
    if (id === 'daylight') await first.promise;
    stored = id;
  }, saved => results.push(saved));
  const a = persist('daylight');
  const b = persist('evergreen');
  first.reject(new Error('Storage temporarily unavailable'));
  await Promise.all([a, b]);
  assert.equal(stored, 'evergreen');
  assert.deepEqual(results, [true]);
});

test('latest failure is reported and a later selection can recover', async () => {
  const results = [];
  const persist = createLatestThemeWriter(async id => {
    if (id === 'daylight') throw new Error('Storage unavailable');
  }, saved => results.push(saved));
  await persist('daylight');
  await persist('midnight');
  assert.deepEqual(results, [false, true]);
});

test('an older success cannot clear a newer failure', async () => {
  const results = [];
  const persist = createLatestThemeWriter(async id => {
    if (id === 'evergreen') throw new Error('Storage unavailable');
  }, saved => results.push(saved));
  await Promise.all([persist('daylight'), persist('evergreen')]);
  assert.deepEqual(results, [false]);
});
