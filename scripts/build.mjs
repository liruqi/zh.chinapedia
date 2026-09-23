#!/usr/bin/env node
// 跨平台构建入口。
//
// 为什么需要
// ----------
// npm 在 Windows 上用 cmd.exe 跑 package.json 里的 scripts，而
//
//     SKIP_WOW=1 docusaurus build --out-dir build-slim
//
// 这种 POSIX 环境变量前缀会被 cmd 当成**命令名**：
//
//     'SKIP_WOW' is not recognized as an internal or external command
//
// 于是 `build:slim` / `build:big` / `build:faster` 在 Windows 上全部跑不起来
// （Mac/Linux 正常，所以一直没被发现）。这里改成「Node 设好环境变量再 spawn
// docusaurus」，两边行为一致，也不用引 cross-env 那种额外依赖。
//
// 用法（和原来的 npm script 一一对应）
// -----------------------------------
//     node scripts/build.mjs                  # 等价 npm run build
//     node scripts/build.mjs --slim           # 等价 npm run build:slim（跳过 wow/，输出 build-slim/）
//     node scripts/build.mjs --big            # 等价 npm run build:big（8G 堆）
//     node scripts/build.mjs --faster         # 等价 npm run build:faster（需要 @docusaurus/faster）
//
// 也接受原样透传给 docusaurus 的参数：
//     node scripts/build.mjs --slim --out-dir build-preview
//
// 注意 `--big` / `--faster` 只是**合并** NODE_OPTIONS，不会覆盖你已有的设置。
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';
import process from 'node:process';

const require = createRequire(import.meta.url);

/** 解析 docusaurus CLI 的真实入口（读 bin 字段，别硬编码路径） */
function resolveCli() {
  const pkgPath = require.resolve('@docusaurus/core/package.json');
  const bin = require(pkgPath).bin;
  const rel = typeof bin === 'string' ? bin : bin && bin.docusaurus;
  if (!rel) throw new Error('@docusaurus/core 的 package.json 里没有 bin.docusaurus');
  return path.join(path.dirname(pkgPath), rel);
}

/** 往 NODE_OPTIONS 里追加一项，已存在就不重复加 */
function withNodeOption(current, option) {
  const parts = (current || '').split(/\s+/).filter(Boolean);
  if (parts.some((p) => p.startsWith('--max-old-space-size='))) {
    return parts.join(' '); // 用户已经指定了堆大小，尊重它
  }
  return [...parts, option].join(' ');
}

const argv = process.argv.slice(2);
const env = { ...process.env };
const cliArgs = ['build'];

for (const arg of argv) {
  if (arg === '--slim') {
    env.SKIP_WOW = '1';
    cliArgs.push('--out-dir', 'build-slim');
  } else if (arg === '--big') {
    env.NODE_OPTIONS = withNodeOption(env.NODE_OPTIONS, '--max-old-space-size=8192');
  } else if (arg === '--faster') {
    env.FASTER = '1';
    env.NODE_OPTIONS = withNodeOption(env.NODE_OPTIONS, '--max-old-space-size=8192');
  } else {
    cliArgs.push(arg);
  }
}

if (env.SKIP_WOW === '1') {
  console.log('[build] SKIP_WOW=1（跳过 docs/wow/，9711 篇）');
}
if (env.FASTER === '1') {
  console.log('[build] FASTER=1（Rspack + SWC，需要 @docusaurus/faster）');
}
if (env.NODE_OPTIONS && env.NODE_OPTIONS !== process.env.NODE_OPTIONS) {
  const heap = /--max-old-space-size=(\d+)/.exec(env.NODE_OPTIONS);
  if (heap) console.log('[build] 堆上限 %s MB', heap[1]);
}

const child = spawn(process.execPath, [resolveCli(), ...cliArgs], {
  env,
  stdio: 'inherit',
});

child.on('error', (err) => {
  console.error('[build] 启动 docusaurus 失败:', err.message);
  process.exit(1);
});
child.on('exit', (code, signal) => {
  if (signal) {
    console.error('[build] docusaurus 被信号终止:', signal);
    process.exit(1);
  }
  process.exit(code ?? 1);
});
