# PTITAD 2026

## 2. AD - ticketproof

### Mô tả bài

Đề cung cấp một dịch vụ kiểm chứng vé VIP ở cổng `8333`, dùng RSA làm bằng chứng sở hữu vé. Mỗi vé (`ticket`) có một cặp khóa RSA riêng với modulus `n` và số mũ công khai `e`, nội dung bí mật của vé - `vip_secret` (đây chính là flag) - được cất trong cột `v` và chỉ được server trả về qua đường `POST /api/tickets/<id>/unlock` sau khi client chứng minh được mình sở hữu khóa riêng của vé.

Quy trình hợp lệ là: client gọi `GET /api/tickets/<id>/challenge` để nhận một thách thức ngẫu nhiên `y`, ký `y` bằng khóa riêng (`z = y^d mod n`) rồi gửi chữ ký `z` lên `unlock`; server verify `z^e ≡ y` để mở khóa và trả flag. Nhiệm vụ của mình là mở khóa một vé bất kỳ mà không có khóa riêng `d`.


### Phân tích và khai thác

Cấu hình RSA của bài:

```python
E = 65539          # public exponent
M = 65537          # dùng trong hàm so khớp same()
B = 1024           # số bit modulus
```

#### Lỗ hổng #1 - Signing oracle qua tham số `code` (đường khai thác chính)

Endpoint `receipt/sign` được dùng để server ký một biên lai của vé. Bản rõ cần ký được quyết định bởi hàm `msg`:

```python
def msg(i, a, n):
    if "code" in a:
        return ni(a.get("code")) % n     # ← attacker toàn quyền chọn giá trị này
    return h(i, a, n)                     # đường "đúng": hash các field biên lai

@app.post("/api/tickets/<i>/receipt/sign")
def receipt(i):
    r = row(i)
    ...
    m = msg(i, a, n)
    z = pow(m, int(r["d"]), n)            # ← ký m bằng khóa riêng d của vé
    return jsonify(..., receipt_message=str(m), receipt_signature=str(z), ...)
```

Ý định của `msg` là luôn ký giá trị băm `h(i, a, n)` - một giá trị attacker không điều khiển được. Nhưng vì có nhánh `if "code" in a`, chỉ cần gửi kèm trường `code`, ta ép server ký đúng số mà mình chọn. Nói cách khác, `receipt/sign` là một oracle ký RSA thô cho khóa riêng của vé: với mọi `m`, ta lấy được `z = m^d mod n`.

Trong khi đó `unlock` verify như sau:

```python
@app.post("/api/tickets/<i>/unlock")
def unlock(i):
    ...
    c = ... # challenge row, c["x"] là thách thức y đã cấp
    y = pow(ni(z), E, int(r["n"]))       # y = z^e mod n
    if same(y, c["x"]):
        return jsonify(ok=True, qr=r["v"])   # ← trả flag (vip_secret)
```

Để mở khóa ta cần một `z` sao cho `z^e ≡ y (mod n)` với `y` là thách thức được cấp. Đây đúng là "ký `y`" - mà oracle làm được ngay. Gọi `receipt/sign` với `code = y`:

$$
z = y^{d} \bmod n .
$$

Khi nộp `z` lên `unlock`, server tính:

$$
z^{e} = \left(y^{d}\right)^{e} = y^{\,d e} \equiv y \pmod{n},
$$

vì `d·e ≡ 1 (mod φ(n))`. Điều kiện `same(y, y)` hiển nhiên đúng, server trả `qr` = flag. Toàn bộ quá trình không cần biết `d`, chỉ mượn khóa riêng của server thông qua oracle.

Các bước với một `ticket_id` bất kỳ:

1. `GET /api/tickets/<id>/challenge` → lấy `challenge` (`y`), `challenge_id`, `n`.
2. `POST /api/tickets/<id>/receipt/sign` với body `{"code": y}` → lấy `receipt_signature` (`z = y^d mod n`).
3. `POST /api/tickets/<id>/unlock` với `{"challenge_id": ..., "signature": z}` → server trả `qr` = flag.

`challenge_id` có thời hạn `TTL = 120s` và chỉ dùng một lần (`u=0`), nên phải chạy ba bước liên tục.

#### Lỗ hổng #2 - Shared prime factorization (đường thay thế, không cần oracle)

Khóa của vé được sinh trong `kk`, nhưng một trong hai số nguyên tố đến từ `a0`:

```python
def a0():
    p = os.path.join(..., "k.dat")
    if os.path.exists(p):
        with open(p) as f:
            return int(f.read().strip())    # ← đọc lại prime đã cache
    x = rn(B // 2)
    with open(p, "w") as f:
        f.write(str(x))                     # ← cache prime lần đầu
    return x

def kk():
    p = a0()                                # ← MỌI vé dùng chung p này
    while True:
        q = rn(B // 2)
        if p == q:
            continue
        f = (p - 1) * (q - 1)
        if gg(E, f) == 1:
            return p * q, pow(E, -1, f)
```

Vì `p` được cache trong `k.dat` và tái sử dụng cho mọi vé, mọi modulus có dạng `n_i = p · q_i` với cùng một `p`. Chỉ cần lấy `n` của hai vé bất kỳ (qua `GET /api/tickets/<id>`), ta khôi phục `p`:

$$
p = \gcd(n_1,\ n_2),\qquad q_i = n_i / p,\qquad d_i = e^{-1} \bmod (p-1)(q_i-1).
$$

Có `d_i` là có toàn quyền ký cho vé đó, tự tính `z = y^{d} mod n` và mở khóa mà không cần đến oracle. (Trường hợp chỉ có một vé duy nhất trên box, ta có thể tự tạo thêm một vé bằng `POST /api/tickets` - endpoint tạo vé trả luôn cả `key = d` và `n` - rồi lấy `p = gcd(n_own, n_target)`.)

#### Lỗ hổng #3 - Weak verification (chỉ so khớp `mod 65537`)

Hàm so khớp trong `unlock` không kiểm tra bằng nhau tuyệt đối:

```python
def same(a, b):
    try:
        return (int(a) - int(b)) % M == 0   # M = 65537, chỉ so khớp mod M
    except Exception:
        return False
```

Đáng lẽ verify phải là `pow(z, e, n) == y` (đẳng thức đầy đủ theo `mod n`). Ở đây điều kiện chấp nhận bị nới lỏng thành:

$$
z^{e} \equiv y \pmod{M},\qquad M = 65537,
$$

tức chỉ cần trùng phần dư khi chia cho 65537. Không gian nghiệm rộng hơn `n` rất nhiều lần, nên vô số `z` "sai" vẫn được chấp nhận - làm suy yếu nghiêm trọng độ khó của việc forge và cộng hưởng với hai lỗ hổng trên. Ngay cả khi nhánh `code` bị bịt, `same` yếu này vẫn giảm mạnh chi phí forge.

#### Script giải

Script dưới đây dùng đường khai thác chính (signing oracle), là cách gọn và chắc chắn nhất - không cần tính toán số học, chỉ mượn khóa riêng của server:

```python
import sys
import requests

def solve(base: str, ticket_id: str) -> str:
    s = requests.Session()

    # Lấy thách thức ngẫu nhiên y
    ch = s.get(f"{base}/api/tickets/{ticket_id}/challenge").json()
    y = ch["challenge"]
    challenge_id = ch["challenge_id"]

    # Ép server tự ký y giúp mình: z = y^d mod n  (signing oracle qua "code")
    sig = s.post(
        f"{base}/api/tickets/{ticket_id}/receipt/sign",
        json={"code": y},
    ).json()["receipt_signature"]

    # Nộp chữ ký để mở khóa: server verify z^e == y -> trả flag (qr)
    r = s.post(
        f"{base}/api/tickets/{ticket_id}/unlock",
        json={"challenge_id": challenge_id, "signature": sig},
    ).json()
    return r.get("qr", r)


if __name__ == "__main__":
    base = sys.argv[1].rstrip("/")    # http://localhost:8333
    ticket_id = sys.argv[2]           # ticket_xxxxxxxxxxxxxxxx
    print(solve(base, ticket_id))
```

Lấy danh sách `ticket_id` mục tiêu từ `GET /events` hoặc `GET /api/tickets/<id>`. Nếu cần tự chuẩn bị vé (cho đường shared-prime), gọi `POST /api/tickets` với body `{"vip_secret": "x"}`.

### Nguyên nhân gốc và hướng vá

Ba lỗ hổng phải vá đồng thời, vì mỗi cái đều đủ để forge:

1. Bịt signing oracle - không bao giờ ký giá trị do client chọn; luôn ký giá trị băm nội bộ:

```python
def msg(i, a, n):
    return h(i, a, n)        # bỏ hẳn nhánh `if "code" in a`
```

2. Sinh khóa độc lập cho mỗi vé - loại bỏ cache `k.dat`, sinh cả hai số nguyên tố mới mỗi lần:

```python
def kk():
    while True:
        p = rn(B // 2)
        q = rn(B // 2)       # prime độc lập, không dùng a0()
        if p == q:
            continue
        f = (p - 1) * (q - 1)
        if gg(E, f) == 1:
            return p * q, pow(E, -1, f)
```

Khi hai vé không còn chung thừa số, `gcd(n_1, n_2) = 1`, chuỗi phân tích thất bại.

3. Verify bằng đẳng thức đầy đủ - so khớp toàn phần theo `mod n`, không rút gọn theo `M`:

```python
def same(a, b):
    try:
        return int(a) == int(b)
    except Exception:
        return False
```
