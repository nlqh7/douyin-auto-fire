const path = require('node:path');
const fs = require('node:fs/promises');

const AVATAR_NAME = 'douyin-avatar.jpg';

async function avatarData(root, account, readFile = fs.readFile) {
  if (account?.avatar !== AVATAR_NAME) return null;
  try {
    const content = await readFile(path.join(root, 'data', AVATAR_NAME));
    return `data:image/jpeg;base64,${content.toString('base64')}`;
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

module.exports = { avatarData };
