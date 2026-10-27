const test = require('node:test');
const assert = require('node:assert/strict');
const { WEBBRIDGE_INSTALL_URL, openWebBridgeInstall } = require('../src/external-links');

test('WebBridge install help opens only the official Kimi page', async () => {
  const opened = [];
  await openWebBridgeInstall({ openExternal: async (url) => opened.push(url) });
  assert.equal(WEBBRIDGE_INSTALL_URL, 'https://www.kimi.com/zh-cn/features/webbridge');
  assert.deepEqual(opened, ['https://www.kimi.com/zh-cn/features/webbridge']);
});
