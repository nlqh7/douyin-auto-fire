const test = require('node:test');
const assert = require('node:assert/strict');
const { StatusCache } = require('../src/status-cache');

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

test('concurrent initial reads share one load', async () => {
  const loading = deferred();
  let loads = 0;
  const cache = new StatusCache(() => {
    loads += 1;
    return loading.promise;
  });

  const first = cache.get();
  const second = cache.get();
  loading.resolve({ value: 1 });

  assert.deepEqual(await first, { value: 1 });
  assert.deepEqual(await second, { value: 1 });
  assert.equal(loads, 1);
});

test('cached state returns immediately and expired state refreshes in background', async () => {
  let now = 1000;
  const originalNow = Date.now;
  Date.now = () => now;
  try {
    const loading = deferred();
    let loads = 0;
    const updates = [];
    const cache = new StatusCache(() => {
      loads += 1;
      return loads === 1 ? Promise.resolve({ value: 1 }) : loading.promise;
    }, 30, (state) => updates.push(state));

    assert.deepEqual(await cache.get(), { value: 1 });
    now = 1031;
    assert.deepEqual(await cache.get(), { value: 1 });
    assert.equal(loads, 2);
    loading.resolve({ value: 2 });
    await loading.promise;
    await new Promise((resolve) => setImmediate(resolve));

    assert.deepEqual(updates, [{ value: 1 }, { value: 2 }]);
    assert.deepEqual(await cache.get(), { value: 2 });
    assert.equal(loads, 2);
  } finally {
    Date.now = originalNow;
  }
});

test('invalidate keeps old state available while fetching the replacement', async () => {
  const loading = deferred();
  let loads = 0;
  const cache = new StatusCache(() => {
    loads += 1;
    return loads === 1 ? Promise.resolve('old') : loading.promise;
  }, 60_000);

  assert.equal(await cache.get(), 'old');
  cache.invalidate();
  assert.equal(await cache.get(), 'old');
  loading.resolve('new');
  await loading.promise;
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(await cache.get(), 'new');
});

test('a failed background refresh preserves the last good state', async () => {
  let loads = 0;
  const cache = new StatusCache(() => {
    loads += 1;
    if (loads === 1) return Promise.resolve('old');
    return Promise.reject(new Error('offline'));
  }, 0);

  assert.equal(await cache.get(), 'old');
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(await cache.get(), 'old');
});
