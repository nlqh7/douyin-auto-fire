const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { configureSingleInstance } = require('../src/single-instance');

function fakeApp(lockAcquired = true) {
  const calls = [];
  return {
    calls,
    getPath: (name) => {
      assert.equal(name, 'temp');
      return 'C:\\Temp';
    },
    setPath: (name, value) => calls.push(['setPath', name, value]),
    requestSingleInstanceLock: () => {
      calls.push(['lock']);
      return lockAcquired;
    },
  };
}

test('all portable copies share one lock before using their own data directory', () => {
  for (const root of ['D:\\first', 'E:\\second']) {
    const app = fakeApp();
    assert.equal(configureSingleInstance(app, root, false), true);
    assert.deepEqual(app.calls, [
      ['setPath', 'userData', path.join('C:\\Temp', 'SparkKeeperSingleton')],
      ['lock'],
      ['setPath', 'userData', path.join(root, 'data', 'electron')],
    ]);
  }
});

test('a duplicate exits before switching to another data directory', () => {
  const app = fakeApp(false);
  assert.equal(configureSingleInstance(app, 'D:\\second', false), false);
  assert.deepEqual(app.calls, [
    ['setPath', 'userData', path.join('C:\\Temp', 'SparkKeeperSingleton')],
    ['lock'],
  ]);
});

test('smoke tests stay isolated and do not block the real application', () => {
  const app = fakeApp(false);
  assert.equal(configureSingleInstance(app, 'D:\\smoke', true), true);
  assert.deepEqual(app.calls, [
    ['setPath', 'userData', path.join('D:\\smoke', 'data', 'electron-smoke')],
  ]);
});
