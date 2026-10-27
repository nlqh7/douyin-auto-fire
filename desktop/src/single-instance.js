const path = require('node:path');

function configureSingleInstance(app, root, smokeTest) {
  const userData = path.join(root, 'data', smokeTest ? 'electron-smoke' : 'electron');
  if (smokeTest) {
    app.setPath('userData', userData);
    return true;
  }

  // Electron scopes its lock to userData. Acquire a shared lock first so
  // portable copies in different directories cannot create duplicate trays.
  app.setPath('userData', path.join(app.getPath('temp'), 'SparkKeeperSingleton'));
  if (!app.requestSingleInstanceLock()) return false;
  app.setPath('userData', userData);
  return true;
}

module.exports = { configureSingleInstance };
