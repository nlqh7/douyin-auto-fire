const WEBBRIDGE_INSTALL_URL = 'https://www.kimi.com/zh-cn/features/webbridge';

function openWebBridgeInstall(shell) {
  return shell.openExternal(WEBBRIDGE_INSTALL_URL);
}

module.exports = { WEBBRIDGE_INSTALL_URL, openWebBridgeInstall };
