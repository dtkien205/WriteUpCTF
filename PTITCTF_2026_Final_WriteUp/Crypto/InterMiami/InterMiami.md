# PTITCTF 2026

## 1. Crypto - InterMiami

### Mô tả bài

Đề bài chỉ cung cấp file [server.py](server.py) và một dịch vụ TCP mang tên **Blackbox encryption service**. Người chơi được lấy các cặp plaintext/ciphertext, sau đó phải tính ciphertext ứng với một plaintext do server đưa ra.

Target:

```text
144.79.188.39:47106
```

Hướng giải sử dụng nội suy Lagrange trên trường hữu hạn, kết hợp nghịch đảo giai thừa và tích tiền tố/hậu tố để tính giá trị cần tìm với chi phí tuyến tính theo số mẫu. [solve.py](solve.py) là script của người giải; [pairs.txt](pairs.txt) được tạo trong quá trình thu thập dữ liệu, không phải file đề cung cấp.

### Phân tích và khai thác

#### Phân tích source và dữ liệu công khai

Trong `server.py`, phần mã hóa được khởi tạo qua module bên ngoài:

```python
from algorithm import init_cipher
from setup import BULK_LIMIT, FLAG, HOST, PORT, TIMEOUT_SECONDS

CIPHER = init_cipher()
```

Đề không cung cấp `algorithm.py` và `setup.py`, nên source chỉ cho thấy cách dịch vụ sử dụng bộ mã hóa. Hai chức năng chính là nhận cặp plaintext/ciphertext và kiểm tra một ciphertext do người chơi tính.

Ở chức năng lấy mẫu, server thực hiện:

```python
p = self.pair_order.next_plaintext()
_, c = CIPHER.get_pair(p)
out.append(f"p = {p}\n")
out.append(f"c = {c}\n")
```

`RandomPairOrder` hoán vị thứ tự plaintext trong miền cho phép. Khi lấy đủ mẫu, ta nhận được toàn bộ miền, mỗi plaintext xuất hiện một lần. Việc xáo trộn không che giấu quan hệ đầu vào/đầu ra vì mỗi ciphertext vẫn được trả kèm plaintext tương ứng.

`CIPHER` được khởi tạo ở cấp module, còn mỗi kết nối tạo một `pair_order` riêng. Phần thay đổi theo kết nối trong source này là thứ tự lấy mẫu; source không khởi tạo lại bộ mã hóa trong handler.

Thông tin modulus và số cặp được công bố qua `CIPHER.public_info()`. Trong dữ liệu đã thu thập, script lưu:

```text
# q = 170141183460469231731687303715884105727
# pairs = 50001
```

Các plaintext bao phủ `0..50000`. Script đặt ciphertext vào đúng vị trí bằng `ys[p] = c`, nên sau khi thu thập ta có:

$$
y_i=f(i),\qquad i=0,1,\ldots,n,\qquad n=50000.
$$

Cách lưu này quan trọng: nếu nối ciphertext theo thứ tự nhận, chỉ số mảng sẽ không còn khớp plaintext và phép nội suy trên các điểm liên tiếp sẽ sai.

Ở chức năng kiểm tra, server lấy một plaintext mới và xác minh giá trị người chơi gửi bằng `CIPHER.verify(challenge_plaintext, submitted)`. Do đó, đại lượng cần tính là $f(x)$ tại điểm được hỏi.

#### Nội suy Lagrange từ các cặp đã biết

Modulus của bài là số nguyên tố Mersenne:

$$
q=170141183460469231731687303715884105727=2^{127}-1.
$$

Ta làm việc trên trường $\mathbb F_q$: mọi phép cộng, trừ, nhân đều lấy modulo $q$; phép chia cho $b\ne0$ được thay bằng nhân với $b^{-1}$. Theo định lý Fermat nhỏ:

$$
b^{-1}\equiv b^{q-2}\pmod q.
$$

Đây là cơ sở của `pow(b, q - 2, q)` trong script.

Lời giải dùng mô hình $f$ là đa thức bậc không quá $50000$. Khi đó, $50001$ điểm phân biệt xác định duy nhất $f$. Điều kiện bậc này là giả thiết của hướng nội suy đã dùng thành công; riêng `server.py` không chứa thuật toán bên trong để suy ra bậc chỉ từ source hoặc số mẫu.

Đặt cơ sở Lagrange:

$$
L_i(X)=
\prod_{\substack{0\le j\le n\\j\ne i}}
\frac{X-j}{i-j}.
$$

Tại $X=i$, tử và mẫu giống nhau nên $L_i(i)=1$. Tại một điểm mẫu $k\ne i$, tử số chứa thừa số $k-k=0$ nên $L_i(k)=0$. Vì vậy:

$$
f(x)=\sum_{i=0}^{n}y_iL_i(x)\pmod q.
$$

Tổng này đi qua đúng tất cả các mẫu. Tính duy nhất đến từ việc hai đa thức bậc không quá $n$ không thể trùng nhau ở $n+1$ điểm phân biệt, trừ khi hiệu của chúng là đa thức không.

Ta có thể tính trực tiếp $f(x)$ bằng công thức trên mà không cần khai triển toàn bộ hệ số. Tuy nhiên, tính riêng tích gồm $n$ thừa số cho từng $L_i(x)$ sẽ tốn $O(n^2)$ phép toán. Với $50001$ mẫu, script tận dụng các hoành độ liên tiếp để rút gọn phép tính.

#### Rút gọn mẫu số bằng nghịch đảo giai thừa

Mẫu số của cơ sở thứ $i$ là:

$$
D_i=\prod_{j\ne i}(i-j).
$$

Tách các chỉ số ở hai phía của $i$:

$$
D_i=
\underbrace{i(i-1)\cdots1}_{i!}
\underbrace{(-1)(-2)\cdots(-(n-i))}_{(-1)^{n-i}(n-i)!}
=(-1)^{n-i}i!(n-i)!.
$$

Suy ra:

$$
D_i^{-1}
=(-1)^{n-i}\operatorname{invfact}[i]
\operatorname{invfact}[n-i]\pmod q,
$$

với $\operatorname{invfact}[k]=(k!)^{-1}\bmod q$. Vì $n<q$, mọi giai thừa đang dùng đều khác 0 trong trường và có nghịch đảo.

Hàm `build_invfact()` tính $n!$, lấy nghịch đảo một lần rồi điền bảng theo chiều ngược:

$$
\operatorname{invfact}[n]=(n!)^{q-2}\bmod q,
\qquad
\operatorname{invfact}[k-1]
=k\operatorname{invfact}[k]\bmod q.
$$

Công thức truy hồi xuất phát từ $k!=k(k-1)!$. Nhờ đó, việc chuẩn bị bảng chỉ cần một phép lũy thừa modular và $O(n)$ phép nhân.

Hệ số $(-1)^{n-i}$ giải thích nhánh đổi dấu trong script: khi `n - i` lẻ, số hạng phải mang dấu âm.

#### Tính tử số bằng tích tiền tố và hậu tố

Với điểm $x$ không nằm trong bảng mẫu, đặt:

$$
A(x)=\prod_{j=0}^{n}(x-j).
$$

Tử số của $L_i(x)$ bằng $A(x)(x-i)^{-1}$. Script tính các nghịch đảo này thông qua một nghịch đảo dùng chung của $A(x)$.

Mảng tiền tố lưu:

$$
\operatorname{pref}[i]=\prod_{j=0}^{i-1}(x-j),
\qquad \operatorname{pref}[0]=1.
$$

Do đó, `pref[n + 1]` chính là $A(x)$. Trong vòng lặp duyệt từ $n$ về 0, biến `suff` lưu tích ở bên phải chỉ số đang xét:

$$
\operatorname{suff}=\prod_{j=i+1}^{n}(x-j).
$$

Nhân hai phần, ta có tích bỏ đúng thừa số $x-i$:

$$
\operatorname{pref}[i]\operatorname{suff}
=\prod_{j\ne i}(x-j).
$$

Vì thế, biến `inv_x_i` được tính bằng:

$$
\operatorname{pref}[i]\operatorname{suff}A(x)^{-1}
=(x-i)^{-1}\pmod q.
$$

Ghép tử số và nghịch đảo mẫu số:

$$
L_i(x)=A(x)(x-i)^{-1}
(-1)^{n-i}
\operatorname{invfact}[i]\operatorname{invfact}[n-i]
\pmod q.
$$

Mỗi vòng lặp cộng $y_iL_i(x)$ vào kết quả, rồi nhân `suff` với $x-i$ để chuẩn bị cho chỉ số tiếp theo. Cần cập nhật hậu tố sau khi tính số hạng hiện tại để tích vẫn bỏ đúng thừa số thứ $i$.

Nếu $x$ trùng điểm mẫu, hàm trả ngay `ys[x]`. Nhánh này vừa tận dụng kết quả đã biết, vừa tránh lấy nghịch đảo của $A(x)=0$. Lệnh `x %= q` ở đầu hàm bảo đảm các đại diện đồng dư được xử lý như cùng một phần tử của trường.

Với mỗi điểm mới, script cần $O(n)$ phép nhân modular và một phép lũy thừa để lấy nghịch đảo; tính theo số phép toán trường, chi phí là $O(n+\log q)$, bộ nhớ $O(n)$. Bảng nghịch đảo giai thừa được chuẩn bị một lần và dùng lại.

#### Script giải

Phần xử lý dữ liệu đọc lại `pairs.txt` nếu đã có đủ mẫu; nếu chưa, `collect_pairs()` thu thập và lưu các cặp theo plaintext. Việc kiểm tra chỉ số và đánh dấu các mẫu đã gặp giúp tránh đưa dữ liệu thiếu hoặc trùng vào phép nội suy.

```python
#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import socket
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "144.79.188.39"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 46786
PAIR_FILE = sys.argv[3] if len(sys.argv) > 3 else "pairs.txt"
DEFAULT_BULK = 1


class Tube:
    def __init__(self, host: str, port: int):
        self.sock = socket.create_connection((host, port))
        self.buf = b""

    def recv_until(self, token: bytes) -> bytes:
        while token not in self.buf:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise EOFError("connection closed")
            self.buf += chunk
        i = self.buf.index(token) + len(token)
        out, self.buf = self.buf[:i], self.buf[i:]
        return out

    def readline(self) -> bytes:
        while b"\n" not in self.buf:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise EOFError("connection closed")
            self.buf += chunk
        i = self.buf.index(b"\n") + 1
        out, self.buf = self.buf[:i], self.buf[i:]
        return out.strip()

    def sendline(self, s: str) -> None:
        self.sock.sendall(s.encode() + b"\n")


def grab_int(pattern: bytes, data: bytes, default: int | None = None) -> int:
    m = re.search(pattern, data)
    if not m:
        if default is not None:
            return default
        raise ValueError(f"missing field: {pattern!r}")
    return int(m.group(1).replace(b",", b""))


def collect_pairs() -> tuple[int, int, list[int]]:
    r = Tube(HOST, PORT)
    banner = r.recv_until(b"> ")
    q = grab_int(rb"q\s*=\s*([0-9,]+)", banner)
    need = grab_int(rb"available pairs\s*=\s*([0-9,]+)", banner)
    bulk = grab_int(rb"bulk\s*=\s*([0-9,]+)", banner, DEFAULT_BULK)

    ys = [0] * need
    seen = bytearray(need)
    collected = 0

    while collected < need:
        cnt = min(bulk, need - collected)
        r.sendline(f"1 {cnt}")
        for _ in range(cnt):
            p = int(r.readline().split(b"=", 1)[1])
            c = int(r.readline().split(b"=", 1)[1])
            if not 0 <= p < need:
                raise RuntimeError(f"plaintext outside expected range: {p}")
            if seen[p]:
                raise RuntimeError(f"server repeated plaintext p = {p}")
            seen[p] = 1
            ys[p] = c
            collected += 1

        print(f"[+] collected {collected}/{need}", end="\r", flush=True)
        r.recv_until(b"> ")

    with open(PAIR_FILE, "w", buffering=1024 * 1024) as f:
        f.write(f"# q = {q}\n# pairs = {need}\n")
        for p, c in enumerate(ys):
            f.write(f"{p} {c}\n")

    print(f"\n[+] saved to {PAIR_FILE}")
    return q, need, ys


def load_pairs() -> tuple[int | None, int | None, list[int]]:
    if not os.path.exists(PAIR_FILE):
        return None, None, []

    q: int | None = None
    need: int | None = None
    ys: list[int] = []
    seen = bytearray()
    loaded = 0

    with open(PAIR_FILE) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if line.startswith("# q"):
                q = int(line.split("=", 1)[1])
            elif line.startswith("# pairs"):
                need = int(line.split("=", 1)[1])
                ys = [0] * need
                seen = bytearray(need)
            elif line and not line.startswith("#"):
                if need is None:
                    raise RuntimeError("# pairs header must appear before pair data")
                p, c = map(int, line.split())
                if not 0 <= p < need:
                    raise RuntimeError(f"bad p on line {lineno}: {p}")
                if seen[p]:
                    raise RuntimeError(f"duplicate p on line {lineno}: {p}")
                seen[p] = 1
                ys[p] = c
                loaded += 1

    if need is not None and loaded != need:
        return q, need, []
    return q, need, ys


def build_invfact(n: int, q: int) -> list[int]:
    fact = 1
    for k in range(2, n + 1):
        fact = fact * k % q
    invfact = [1] * (n + 1)
    invfact[n] = pow(fact, q - 2, q)
    for k in range(n, 0, -1):
        invfact[k - 1] = invfact[k] * k % q
    return invfact


def lagrange_at(x: int, ys: list[int], q: int, invfact: list[int]) -> int:
    x %= q
    n = len(ys) - 1
    if 0 <= x <= n:
        return ys[x]

    pref = [1] * (n + 2)
    for i in range(n + 1):
        pref[i + 1] = pref[i] * ((x - i) % q) % q

    all_prod = pref[n + 1]
    inv_all = pow(all_prod, q - 2, q)
    ans, suff = 0, 1
    for i in range(n, -1, -1):
        inv_x_i = pref[i] * suff % q * inv_all % q
        term = all_prod * inv_x_i % q * invfact[i] % q * invfact[n - i] % q
        if (n - i) & 1:
            term = -term % q
        ans = (ans + ys[i] * term) % q
        suff = suff * ((x - i) % q) % q
    return ans


if __name__ == "__main__":
    q, need, ys = load_pairs()
    if q is None or need is None or len(ys) != need:
        q, need, ys = collect_pairs()
    else:
        print(f"[+] loaded {len(ys)} pairs from {PAIR_FILE}")

    print("[+] building interpolation helper")
    invfact = build_invfact(len(ys) - 1, q)

    while True:
        s = input("Plaintext p = ").strip()
        if not s:
            break
        print("Ciphertext c =", lagrange_at(int(s, 0), ys, q, invfact))

```

Sau khi chuẩn bị bảng, chương trình nhận plaintext qua lời nhắc `Plaintext p = ` và in giá trị tương ứng dưới dạng `Ciphertext c = ...`. Script thực hiện việc thu thập mẫu và tính ciphertext; phần nhập đáp án vào dịch vụ được thực hiện thủ công.

