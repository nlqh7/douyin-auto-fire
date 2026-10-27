const { app, BrowserWindow, ipcMain, Menu, Tray, shell } = require('electron');
const path = require('node:path');
const fs = require('node:fs/promises');
const fsSync = require('node:fs');
const { ProcessRunner } = require('./process-runner');
const { avatarData } = require('./avatar-data');
const { StatusCache } = require('./status-cache');
const { openWebBridgeInstall } = require('./external-links');

const isUnpacked = app.isPackaged && path.basename(path.resolve(process.resourcesPath, '..')) === 'win-unpacked';
const root = app.isPackaged ? (process.env.PORTABLE_EXECUTABLE_DIR || (isUnpacked ? path.resolve(process.resourcesPath, '..', '..', '..') : path.dirname(process.execPath))) : path.resolve(__dirname, '..', '..');
if (isUnpacked) {
  const legacyData = path.resolve(process.resourcesPath, '..', 'data');
  for (const name of ['control.json', 'account.json', 'scan-status.json', 'douyin-avatar.jpg']) {
    const source = path.join(legacyData, name);
    const destination = path.join(root, 'data', name);
    if (fsSync.existsSync(source) && !fsSync.existsSync(destination)) {
      fsSync.mkdirSync(path.dirname(destination), { recursive: true });
      fsSync.copyFileSync(source, destination);
    }
  }
}
const smokeTest = process.argv.includes('--smoke-test');
app.setPath('userData', path.join(root, 'data', smokeTest ? 'electron-smoke' : 'electron'));
const runner = new ProcessRunner(root, undefined, { managePath: app.isPackaged ? path.join(process.resourcesPath, 'manage.exe') : null });
let window;
let tray;

function showWindow() {
  if (!window) createWindow();
  window.show();
  window.focus();
}

if (!smokeTest && !app.requestSingleInstanceLock()) process.exit(0);
app.on('second-instance', () => {
  if (window) {
    if (window.isMinimized()) window.restore();
    window.focus();
  }
});

function sendLog(message) {
  if (window && !window.isDestroyed()) window.webContents.send('log', message);
}

function createWindow() {
  window = new BrowserWindow({
    width: 1080,
    height: 800,
    minWidth: 900,
    minHeight: 760,
    backgroundColor: '#f4f4f2',
    title: '火花',
    icon: path.join(__dirname, '..', 'assets', 'icon.ico'),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      additionalArguments: [smokeTest ? '--smoke-test' : '--auto-scan'],
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  window.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  window.on('close', (event) => {
    if (!smokeTest) {
      event.preventDefault();
      window.hide();
    }
  });
  window.on('minimize', (event) => {
    event.preventDefault();
    window.hide();
  });
  window.on('closed', () => { window = null; });
}

function createTray() {
  tray = new Tray(path.join(__dirname, '..', 'assets', 'icon.ico'));
  tray.setToolTip('火花');
  tray.on('click', showWindow);
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: '打开火花', click: showWindow },
    { type: 'separator' },
    { label: '退出', click: () => app.quit() },
  ]));
}

app.on('will-quit', () => {
  if (tray) tray.destroy();
});

async function loadStatus() {
  const [result, configResult, accountResult] = await Promise.all([
    runner.run('status'),
    runner.run('config'),
    runner.run('accountStatus'),
  ]);
  const config = JSON.parse(configResult.output);
  const accountStatus = JSON.parse(accountResult.output);
  return {
    raw: result.output,
    loggedIn: ['webbridge', 'default'].includes(config.browser_mode) || result.output.includes('独立登录状态: 已保存'),
    enabled: result.output.includes('自动发送: 已启用'),
    watching: runner.watching,
    config,
    account: accountStatus.account,
    avatar: await avatarData(root, accountStatus.account),
    scan: accountStatus.scan,
  };
}

const statusCache = new StatusCache(loadStatus, 30_000, (state) => {
  if (window && !window.isDestroyed()) window.webContents.send('status', state);
});

async function afterAction(action) {
  const result = await action();
  statusCache.invalidate();
  return result;
}

function handleWatchExit() {
  statusCache.invalidate();
  sendLog('常驻监视已停止');
}

ipcMain.handle('status', () => statusCache.get());
ipcMain.handle('open-webbridge-install', () => openWebBridgeInstall(shell));
ipcMain.handle('save-config', async (_event, settings) => {
  const result = await afterAction(() => runner.saveConfig(settings));
  if (settings.browserMode !== 'webbridge') return { ...result, webbridgeAvailable: null };
  if (smokeTest) return { ...result, webbridgeAvailable: false };
  try {
    const check = await runner.run('webbridgeStatus');
    return { ...result, webbridgeAvailable: JSON.parse(check.output).available === true };
  } catch {
    return { ...result, webbridgeAvailable: false };
  }
});
ipcMain.handle('login', () => afterAction(() => runner.run('login')));
let scanPromise = null;
ipcMain.handle('dry-run', () => {
  if (scanPromise) return scanPromise;
  scanPromise = (async () => {
    try {
      return await afterAction(() => runner.run('dryRun'));
    } finally {
      scanPromise = null;
      refreshAccountIfDue();
    }
  })();
  return scanPromise;
});
ipcMain.handle('watch', async (_event, confirmation) => {
  if (confirmation !== true) throw new Error('需要确认后才能开启');
  const status = await runner.run('status');
  const config = JSON.parse((await runner.run('config')).output);
  if (!['webbridge', 'default'].includes(config.browser_mode) && !status.output.includes('独立登录状态: 已保存')) throw new Error('请先登录抖音');
  runner.startWatch(sendLog, handleWatchExit);
  statusCache.invalidate();
  return { watching: true };
});
ipcMain.handle('pause', () => afterAction(() => runner.stopWatch()));
ipcMain.handle('logs', async () => {
  const sections = [];
  for (const [label, name] of [['定时任务', 'watch.log'], ['续火执行', 'run.log']]) {
    try {
      const content = await fs.readFile(path.join(root, 'logs', name), 'utf8');
      if (content.trim()) sections.push(`【${label}】\n${content.trim()}`);
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  return sections.join('\n\n').split(/\r?\n/).slice(-80).join('\n') || '还没有运行日志。';
});

let accountRefreshRunning = false;
async function refreshAccountIfDue() {
  if (accountRefreshRunning || scanPromise) return;
  try {
    const state = await statusCache.get();
    if (state.config.browser_mode !== 'webbridge') return;
    const refreshedAt = Date.parse(state.account?.refreshed_at || '');
    if (Number.isFinite(refreshedAt) && Date.now() - refreshedAt < 6 * 60 * 60 * 1000) return;
    accountRefreshRunning = true;
    await runner.run('accountRefresh');
    statusCache.invalidate();
    statusCache.refresh().catch(() => {});
  } catch (error) {
    console.error(`账号后台刷新失败: ${error.message}`);
  } finally {
    accountRefreshRunning = false;
  }
}

app.whenReady().then(() => {
  createWindow();
  if (!smokeTest) {
    createTray();
    window.webContents.once('did-finish-load', () => {
      runner.restoreWatch(sendLog, handleWatchExit).catch((error) => sendLog(`自动续火恢复失败: ${error.message}`));
    });
    setInterval(() => statusCache.refresh().catch(() => {}), 60_000);
    setInterval(refreshAccountIfDue, 30 * 60 * 1000);
  }
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('before-quit', (event) => {
  if (!runner.watching) return;
  event.preventDefault();
  runner.stopWatch().finally(() => app.exit(0));
});

if (process.argv.includes('--smoke-test')) {
  app.whenReady().then(async () => {
    window.setSize(400, 520);
    await new Promise((resolve) => setTimeout(resolve, 1200));
    const result = await window.webContents.executeJavaScript(`({
      title: document.title,
      heading: document.querySelector('h1')?.textContent,
      dryRun: document.querySelector('#scan')?.textContent,
      scanDisabled: document.querySelector('#scan')?.disabled,
      loginRequired: document.querySelector('#login-status')?.textContent.includes('需要登录'),
      clientHeight: document.documentElement.clientHeight,
      scrollHeight: document.documentElement.scrollHeight,
      storage: ${JSON.stringify({ root, isUnpacked, resourcesPath: process.resourcesPath })},
      correctStorageRoot: ${!isUnpacked || path.join(root, 'data') === path.resolve(process.resourcesPath, '..', '..', '..', 'data')},
      node: typeof require,
      api: typeof window.spark?.status,
      webbridgeInstallApi: typeof window.spark?.openWebBridgeInstall,
      webbridgeInstallLabel: document.querySelector('#webbridge-install')?.textContent,
      startupScanDisabled: window.spark?.scanOnStartup === false
    })`);
    console.log(JSON.stringify(result));
    const interaction = await window.webContents.executeJavaScript(`(async () => {
      for (let i = 0; i < 300 && !settingsLoaded; i++) await new Promise(resolve => setTimeout(resolve, 100));
      loggedIn = true;
      updateControls();
      const enabledAfterLogin = !document.querySelector('#scan').disabled;
      const webbridgeMode = currentConfig.browser_mode === 'webbridge';
      if (!webbridgeMode) document.querySelector('#scan').click();
      for (let i = 0; i < 300 && busy; i++) await new Promise(resolve => setTimeout(resolve, 100));
      const scanFeedback = webbridgeMode ? 'WebBridge 由独立真实页面测试覆盖' : document.querySelector('#toast').textContent;
      document.querySelector('#settings-form').requestSubmit();
      for (let i = 0; i < 300 && busy; i++) await new Promise(resolve => setTimeout(resolve, 100));
      const webbridgeWarning = !webbridgeMode || document.querySelector('#webbridge-dialog').open;
      if (webbridgeMode) document.querySelector('#webbridge-later').click();
      const webbridgeWarningClosed = !document.querySelector('#webbridge-dialog').open;
      document.querySelector('input[name="message-type"][value="sticker"]').click();
      document.querySelector('#sticker-current').click();
      const stickerCount = document.querySelectorAll('#sticker-options button').length;
      document.querySelector('#sticker-options button[data-name="续火花"]').click();
      await new Promise(resolve => setTimeout(resolve, 300));
      const selectedSticker = document.querySelector('#sticker-current-name').textContent;
      const stickerImageLoaded = document.querySelector('#sticker-current-image').naturalWidth > 0;
      document.querySelector('[data-view="logs"]').click();
      await new Promise(resolve => setTimeout(resolve, 150));
      const logsVisible = !document.querySelector('#logs-view').hidden && document.querySelector('#page-title').textContent === '运行记录';
      document.querySelector('[data-view="overview"]').click();
      await new Promise(resolve => setTimeout(resolve, 150));
      displayedAvatar = null;
      requestedAvatar = null;
      avatarLoaded = false;
      elements.accountAvatar.removeAttribute('src');
      renderAccount({account: {name: '测试账号'}, avatar: null, scan: {count: 2, targets: ['甲', '乙']}});
      const pendingState = document.querySelector('#scan-summary').classList.contains('pending') && document.querySelector('#gray-count').textContent === '2';
      const avatarFallback = !document.querySelector('#account-avatar-fallback').hidden;
      const initiallyCollapsed = !document.querySelector('#pending-drawer').open;
      const settingsTop = document.querySelector('.settings').getBoundingClientRect().top;
      document.querySelector('#scan-summary').click();
      const disclosureExpanded = document.querySelector('#pending-drawer').open && document.querySelector('#gray-names').textContent.includes('甲') && document.querySelector('#scan-summary').getAttribute('aria-expanded') === 'true' && document.querySelector('.settings').getBoundingClientRect().top === settingsTop && document.querySelector('#pending-drawer').closedBy === 'any';
      document.querySelector('#close-pending').click();
      const disclosureCollapsed = !document.querySelector('#pending-drawer').open;
      const settingsFit = document.querySelector('.settings').getBoundingClientRect().bottom <= document.documentElement.clientHeight;
      renderAccount({account: {name: '测试账号'}, avatar: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', scan: {count: 0, targets: []}});
      await new Promise(resolve => setTimeout(resolve, 150));
      const avatarVisible = document.querySelector('#account-avatar-image').naturalWidth > 0;
      renderAccount({account: {name: '测试账号'}, avatar: null, scan: {count: 0, targets: []}});
      await new Promise(resolve => setTimeout(resolve, 50));
      const avatarRetained = !document.querySelector('#account-avatar-image').hidden && document.querySelector('#account-avatar-image').naturalWidth > 0 && document.querySelector('#account-avatar-fallback').hidden;
      const completedState = document.querySelector('#scan-summary').classList.contains('complete');
      return {
        enabledAfterLogin,
        feedback: document.querySelector('#toast').textContent,
        scanFeedback,
        settingsSaved: document.querySelector('#settings-status').textContent,
        scheduleTime: document.querySelector('#schedule-time').textContent,
        webbridgeWarning,
        webbridgeWarningClosed,
        logsVisible,
        stickerCount,
        selectedSticker,
        stickerImageLoaded,
        pendingState,
        initiallyCollapsed,
        disclosureExpanded,
        disclosureCollapsed,
        settingsFit,
        avatarFallback,
        avatarLoaded: avatarVisible,
        avatarRetained,
        completedState,
      };
    })()`);
    console.log(JSON.stringify(interaction));
    await fs.mkdir(path.join(root, 'artifacts'), { recursive: true });
    await window.webContents.executeJavaScript(`renderAccount({account: {name: '测试账号'}, avatar: null, scan: {count: 2, targets: ['甲', '乙']}}); document.querySelector('#scan-summary').click();`);
    window.show();
    window.focus();
    await new Promise((resolve) => setTimeout(resolve, 300));
    const screenshot = await window.webContents.capturePage();
    if (screenshot.isEmpty()) throw new Error('窗口截图失败');
    await fs.writeFile(path.join(root, 'artifacts', 'desktop-smoke.png'), screenshot.toPNG());
    const failed = result.scrollHeight > result.clientHeight || !result.correctStorageRoot || result.node !== 'undefined' || result.api !== 'function' || result.webbridgeInstallApi !== 'function' || result.webbridgeInstallLabel !== 'WebBridge 官方安装 ↗' || !result.startupScanDisabled || (result.loginRequired && !result.scanDisabled) || !interaction.enabledAfterLogin || !(interaction.scanFeedback.includes('尚未完成独立浏览器登录') || interaction.scanFeedback.includes('WebBridge')) || !interaction.feedback.includes('发送设置已保存') || interaction.settingsSaved !== '已保存' || !interaction.webbridgeWarning || !interaction.webbridgeWarningClosed || !interaction.logsVisible || interaction.stickerCount !== 12 || interaction.selectedSticker !== '续火花' || !interaction.stickerImageLoaded || !interaction.pendingState || !interaction.initiallyCollapsed || !interaction.disclosureExpanded || !interaction.disclosureCollapsed || !interaction.settingsFit || !interaction.avatarFallback || !interaction.avatarLoaded || !interaction.avatarRetained || !interaction.completedState;
    await fs.writeFile(path.join(root, 'artifacts', 'smoke-result.json'), JSON.stringify({ result, interaction, failed }));
    app.exit(failed ? 1 : 0);
  }).catch((error) => {
    console.error(error);
    app.exit(1);
  });
}
