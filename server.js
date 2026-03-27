/**
 * NewsFlow 本地静态服务器
 * 用法: node server.js [端口]
 * 默认端口 3000，访问 http://localhost:3000
 *
 * 将 public/ 作为网站根目录，同时将 data/ 挂载到 /data/ 路径
 * 解决浏览器 file:// 协议下 fetch 跨域的问题
 */

const http = require('http');
const fs   = require('fs');
const path = require('path');

const PORT    = parseInt(process.argv[2]) || 3000;
const ROOT    = path.join(__dirname, 'public');   // 前端根目录
const DATA    = path.join(__dirname, 'data');      // 数据目录

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'application/javascript; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png':  'image/png',
  '.jpg':  'image/jpeg',
  '.svg':  'image/svg+xml',
  '.ico':  'image/x-icon',
};

function serveFile(filePath, res) {
  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('404 Not Found');
      return;
    }
    const ext  = path.extname(filePath).toLowerCase();
    const mime = MIME[ext] || 'application/octet-stream';

    // HTML 文件：读取并剥离 UTF-8 BOM，避免浏览器解析异常
    if (ext === '.html') {
      fs.readFile(filePath, (err2, buf) => {
        if (err2) { res.writeHead(500); res.end('Server Error'); return; }
        // 去掉 BOM (EF BB BF)
        const data = (buf[0] === 0xEF && buf[1] === 0xBB && buf[2] === 0xBF)
          ? buf.slice(3) : buf;
        res.writeHead(200, {
          'Content-Type': mime,
          'Access-Control-Allow-Origin': '*',
          'Cache-Control': 'no-cache',
          'Content-Length': data.length,
        });
        res.end(data);
      });
    } else {
      res.writeHead(200, {
        'Content-Type': mime,
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'no-cache',
      });
      fs.createReadStream(filePath).pipe(res);
    }
  });
}

const server = http.createServer((req, res) => {
  // 解析 URL，去掉 query string
  const urlPath = decodeURIComponent(req.url.split('?')[0]);

  let filePath;

  if (urlPath.startsWith('/data/')) {
    filePath = path.join(DATA, urlPath.slice('/data/'.length));
  } else if (urlPath === '/' || urlPath === '') {
    filePath = path.join(ROOT, 'index.html');
  } else {
    filePath = path.join(ROOT, urlPath);
  }

  // 安全检查：防止路径穿越
  const rootReal = path.resolve(__dirname);
  const fileReal = path.resolve(filePath);
  if (!fileReal.startsWith(rootReal)) {
    res.writeHead(403, { 'Content-Type': 'text/plain' });
    res.end('403 Forbidden');
    return;
  }

  serveFile(filePath, res);

  // 请求日志
  res.on('finish', () => {
    const ts = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    console.log(`[${ts}] ${res.statusCode} ${req.method} ${urlPath}`);
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`\n✅ NewsFlow 本地服务器已启动`);
  console.log(`   访问地址: http://localhost:${PORT}`);
  console.log(`   静态目录: ${ROOT}`);
  console.log(`   数据目录: ${DATA}  → /data/`);
  console.log(`\n按 Ctrl+C 停止服务器\n`);
});
