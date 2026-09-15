# PTITCTF 2026

## 1. Crypto - Stranger Papers Revenge

### Mô tả bài

Đề cung cấp một file `chall.zip`, bên trong có 7 ảnh JPG dạng giấy cũ:

```text
Stranger Paper Revenge/
├── 1.jpg
├── 2.jpg
├── 3.jpg
├── 4.jpg
├── 5.jpg
├── 6.jpg
└── 7.jpg
```

Hai ảnh đầu là tài liệu hướng dẫn, 5 ảnh còn lại là các trang `ROTTING PAPER 01` đến `ROTTING PAPER 05`, mỗi trang chứa nhiều số có 3 chữ số. Hướng giải chính là đọc các hint trong giấy, biến dãy số thành chuỗi Base64 rồi decode lấy flag.

### Phân tích và khai thác

#### Đọc hint từ hai trang đầu

Ảnh `1.jpg` là cover. Các dòng chỉ dẫn ở cuối trang có chữ cái đầu lần lượt là:

```text
Under
Papers
Subject
Internal
Do
Entry
```

Ghép lại được filing word:

```text
UPSIDE
```

Ảnh `2.jpg` cho các hint quan trọng hơn:

```text
The correction wheel did not stop where it started. It had sixty-seven teeth.
The archive staff filed every scar by what remained after complete turns.
The catalog began with old Roman capitals, then their smaller shadows, then ten digits, then slash, cross, and the padding mark.
Some scars were only mold and never came from the machine.
```

Từ đó suy ra:

- `sixty-seven teeth` nghĩa là lấy mỗi số modulo `67`.
- `what remained after complete turns` cũng xác nhận lấy phần dư.
- Catalog gồm `A-Z`, `a-z`, `0-9`, `/`, `+`, `=`.
- Catalog chỉ có `26 + 26 + 10 + 3 = 65` ký tự, trong khi wheel có 67 răng, nên hai residue còn lại là `mold` và cần bỏ qua.

#### OCR các trang ledger

Các ảnh `3.jpg` đến `7.jpg` chứa bảng số. Có thể OCR bằng Windows OCR, Tesseract, hoặc nhập tay sau khi zoom. Điều quan trọng là giữ đúng thứ tự:

```text
ROTTING PAPER 01
ROTTING PAPER 02
ROTTING PAPER 03
ROTTING PAPER 04
ROTTING PAPER 05
```

Mỗi dòng thường có 16 số. Dòng cuối của trang cuối ngắn hơn. Sau khi OCR, mình lưu toàn bộ số vào một text file, ví dụ `ledger_ocr.txt`.

Một đoạn đầu sau OCR có dạng:

```text
825 238 488 105 687 661 218 475 874 144 551 006 356 352 018 956
421 598 355 214 669 153 774 017 290 691 629 623 644 431 804 475
612 892 937 899 625 966 771 565 211 294 420 764 519 762 632 536
...
```

#### Decode dãy số

Sau khi có dãy số, decode theo đúng hint:

1. Với mỗi số `n`, tính `r = n % 67`.
2. Nếu `r < 65`, map `r` vào catalog:

```text
ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/+=
```

3. Nếu `r` là `65` hoặc `66`, bỏ qua vì đó là mold.
4. Chuỗi thu được là Base64, decode để lấy flag.

Script solve:

```python
#!/usr/bin/env python3
import base64
import re

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/+="

with open("ledger_ocr.txt", "r", encoding="utf-8") as f:
    data = f.read()

nums = [int(x) for x in re.findall(r"\b\d{3}\b", data)]

encoded = []
for n in nums:
    r = n % 67
    if r < len(ALPHABET):
        encoded.append(ALPHABET[r])
    # r = 65 hoặc 66 là mold, bỏ qua

b64 = "".join(encoded)
b64 += "=" * ((4 - len(b64) % 4) % 4)

print(base64.b64decode(b64).decode())
```

**Flag:**

```text
PTITCTF{r3v3ng3_fr0m_th3_ups1d3_d0wn}
```
