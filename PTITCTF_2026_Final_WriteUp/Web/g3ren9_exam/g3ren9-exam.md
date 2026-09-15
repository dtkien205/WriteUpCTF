# PTITCTF 2026

## 3. Web - g3ren9 Exam

### Mô tả bài

Challenge cung cấp một web app có chức năng đăng ký, đăng nhập và làm bài kiểm tra kiến thức web pentest. Mục tiêu là hoàn thành bài thi với điểm 10/10 để nhận flag.

Bài này không yêu cầu khai thác SQL Injection, XSS hay bypass authentication. Hướng giải là đăng ký tài khoản, đăng nhập và làm bài trực tiếp trên giao diện web. Điểm cần chú ý là đọc kỹ nội dung câu hỏi và trả lời đúng 10/10 là có flag, thế mà lại hay.

### Phân tích và khai thác

Trang chủ hiển thị form đăng nhập và link đăng ký tài khoản, có thể thấy ứng dụng sử dụng PHP và session cookie:

![alt text](image-2.png)

Form login gửi dữ liệu tới `/login.php`, đồng thời có link đăng ký tại `/register.php`.

Form `/register.php` yêu cầu ba trường:

```text
display_name
username
password
```

![alt text](image-3.png)

Username phải khớp pattern:

```text
[A-Za-z0-9_]{3,32}
```

Trên giao diện web, vào `/register.php`, điền `display_name`, `username`, `password` hợp lệ rồi submit form đăng ký. Sau đó quay lại trang login, nhập username/password vừa tạo để đăng nhập.

Khi đăng nhập thành công, trình duyệt tự lưu và gửi kèm cookie `g3ren9_session` cho các request tiếp theo, nên không cần xử lý session thủ công.

Sau khi đăng nhập, menu hiển thị các route:

```text
/profile.php
/exam.php
/scoreboard.php
/logout.php
```

![alt text](image-4.png)

Session này được dùng để truy cập trang làm bài và xem kết quả.

- `/profile.php` chỉ hiển thị thông tin tài khoản, số lần làm bài, điểm hiện tại và form cập nhật profile/avatar, ô `Display Name` không có dấu hiệu của các lổ hổng như XSS/HTML injection, SSTI, đồng thời chức năng upload avatar với các loại file và payload bất thường cũng không thu được kết quả.

- `/scoreboard.php` hiển thị bảng xếp hạng và có tham số tìm kiếm `q`, không có dấu hiệu XSS trực tiếp hay SQLi.

- `/logout.php` chỉ kết thúc session.

Vì vậy route đáng chú ý còn lại là `/exam.php`.

Sau khi đăng nhập, chọn mục `/exam.php` trên menu để vào trang làm bài.

Trang hiển thị 10 câu hỏi kiến thức web pentest dưới dạng radio button. Tiếp theo mình thử submit đáp án của các câu hỏi này để xem chức năng của trang này có hoạt động hay không.

![alt text](image-5.png)

Lúc này mình nghĩ sẽ như nào nếu chọn đủ đúng 10/10, đáp án các câu lần lượt là: `404`, `GET`, `XSS`, `SQLi`, `CSRF`, `IDOR`, `SSRF`, `LFI`, `HttpOnly`, `Repeater`.


Sau khi chọn đủ 10 đáp án trên giao diện, nhấn nút submit của form. Trình duyệt gửi request `POST /submit.php` kèm session hiện tại và các đáp án đã chọn.

Trình duyệt tự chuyển tới `/result.php`. Khi đạt 10/10, trang kết quả hiển thị flag:

![alt text](image-1.png)

**Flag:**

```text
PTITCTF{w0w_y0u_d1d_it_c0ngr4tUlaTI0n_g000ddJ0b}
```
