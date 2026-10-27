# 火花

一个专门给抖音续火花的 Windows 桌面小工具。每天定时检查私信列表，给所有灰色火花各发一次设置的文字或抖音原生表情。

界面使用 Electron，浏览器操作通过 Kimi WebBridge 在你当前登录的 Chrome 中完成，不导出 Cookie，也不需要重新登录或开启 Chrome 调试端口。

## 下载即用

1. 从 Releases 下载 `SparkKeeper-x.x.x-win-x64.exe`。
2. 在 Chrome 中安装并启用 [Kimi WebBridge](https://www.kimi.com/zh-cn/features/webbridge)，确认本机桥接服务已开启。
3. 双击 EXE。无需安装 Python、Node.js 或额外浏览器。
4. 在“浏览器连接”中选择 **Kimi WebBridge**，先点“扫描火花”。扫描只会打开并核对会话，不发送消息。
5. 确认结果后设置时间、文字或原生表情，再开启“自动续火”。

便携版当前未做代码签名，Windows SmartScreen 可能显示安全提示；请确认文件来自本项目 Releases，再按需选择“更多信息”→“仍要运行”。

WebBridge 只在任务期间创建“火花管家”或“火花账号信息”受控标签；任务内复用，异常时在原标签刷新，结束后自动清理，不读取你的日常浏览器配置文件。

若个人资料页触发平台验证，软件不会尝试绕过；确认私信连接正常后会保留已有账号信息，首次使用则显示通用“抖音账号”，不影响扫描和自动任务。

软件启动后会在后台静默扫描一次，不锁定按钮、不弹提示、不主动切换浏览器焦点，也不会发送消息。

## 三种浏览器连接方案

| 方案 | 适合谁 | 登录与使用要求 |
| --- | --- | --- |
| **Kimi WebBridge（推荐）** | 已经在日常 Chrome 登录抖音 | 安装并启用 [Kimi WebBridge 官方扩展](https://www.kimi.com/zh-cn/features/webbridge)，保持 Chrome 和本机桥接服务运行；不导出 Cookie |
| **系统默认浏览器** | 希望直接复用系统默认 Chrome 或 Edge 的配置 | 自动识别 Windows 默认的 Chrome / Edge；先手动关闭对应浏览器的所有窗口再扫描或执行，配置被占用时会停止，不会强关浏览器或复制配置；其他默认浏览器请改用另外两种方案 |
| **独立浏览器** | 不想触碰日常 Chrome 配置 | 选择该方案后点击“登录抖音”，在弹出的专用浏览器中扫码；登录状态只保存在项目 `data/` 中 |

界面“浏览器连接”旁的 **WebBridge 官方安装 ↗** 会使用系统浏览器打开官方安装说明。

## 功能

- 扫描全部灰色火花，已点亮的跳过。
- 自定义每天执行时间。
- 自定义单行文字，或选择“晚上好”“比心”原生表情。
- Dry Run 不发送；每天每个对象最多处理一次；结果不确定不重发。
- 所有依赖已打入单个便携 EXE，无控制台窗口、无安装器、无开机启动。

## 使用和卸载

- 保持应用、电脑和 Chrome 运行。电脑睡眠会导致任务错过，错过后不补发。
- 已确认开启的自动续火会在应用重新启动后恢复；窗口关闭后仍在托盘运行，从托盘退出则停止任务。
- 配置和日志保存在 EXE 同目录的 `data/`、`logs/`。
- 删除 EXE 及这两个目录即可卸载；不会删除你的 Chrome 或 WebBridge。

## 本地开发

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python manage.py setup
cd desktop
npm install
npm test
npm start
```

完整测试：

```powershell
.venv\Scripts\python -m pytest -q
cd desktop
npm test
npm run smoke
```

## 构建便携版

```powershell
.venv\Scripts\pip install pyinstaller pillow
.venv\Scripts\python scripts/build_assets.py
.venv\Scripts\python -m PyInstaller --noconfirm --onefile --noconsole --name manage --collect-all playwright --collect-all tzdata --distpath build --workpath build/work --specpath build/spec manage.py
cd desktop
npm run dist
```

## 风险说明

网页自动化可能因抖音页面变化、登录失效或平台风控而停止。请仅用于本人账号和正常社交互动，不保证单方面发送一定能完成双方互动规则。遇到验证码或安全验证时应人工处理，本项目不尝试绕过。

## 来源与许可

基于 [unmev/douyin-auto-fire](https://github.com/unmev/douyin-auto-fire) 的浏览器自动化和发送确认逻辑，加入 Electron 界面、Kimi WebBridge 后端、受控配置和便携打包。保留原项目的 PolyForm Noncommercial 许可，仅限非商业用途，详见 `LICENSE`。
