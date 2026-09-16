# PTITAD 2026

## 1. AD - round_receipt

### Mô tả bài

Đề cung cấp một dịch vụ ở cổng `13375` cho phép tạo các note được mã hóa bằng AES-CTR, mỗi note khi tạo ra được cấp một `id` công khai và một `secret` bí mật; về nguyên tắc chỉ người giữ `secret` mới đọc lại được nội dung note qua đường `GET /api/notes/<id>?secret=...`. Nhiệm vụ của mình là khôi phục nội dung note chỉ từ `id`, không có `secret`.

Hướng giải khai thác hai bản rõ khác nhau bằng cùng một cặp `(key, nonce)` trong CTR, đồng thời một trong hai bản rõ (biên lai - receipt) là đoán được hoàn toàn và cả hai bản mã đều bị công khai. Đây là lỗi two-time pad của stream cipher, cho phép suy ra keystream rồi giải mã flag mà không cần khóa hay secret.

### Phân tích và khai thác

Toàn bộ logic mã hóa nằm trong hàm `encrypt_ctr`:

```python
def encrypt_ctr(key, nonce, data):
    cipher = AES.new(key, AES.MODE_CTR, nonce=nonce, initial_value=0)
    return cipher.encrypt(data)
```

Điểm cần chú ý là `initial_value=0` được cố định. Trong chế độ CTR, AES không mã hóa bản rõ trực tiếp mà sinh ra một chuỗi keystream từ bộ đếm rồi XOR với bản rõ:

$$
\mathrm{KS}=\mathrm{AES}(k,\ \mathrm{nonce}\Vert 0)\ \Vert\ \mathrm{AES}(k,\ \mathrm{nonce}\Vert 1)\ \Vert\ \cdots,\qquad C=P\oplus\mathrm{KS}.
$$

Keystream chỉ phụ thuộc vào bộ ba `(key, nonce, initial_value)`, hoàn toàn độc lập với bản rõ. Vì `initial_value` bị đặt cứng bằng 0, mọi lời gọi `encrypt_ctr` với cùng `(key, nonce)` sẽ tạo ra **đúng cùng một keystream**, bắt đầu từ bộ đếm 0.

Khi tạo note, hàm `create_note` sinh khóa và nonce một lần rồi dùng lại cho cả hai lần mã hóa:

```python
round_key   = secrets.token_bytes(32)
round_nonce = secrets.token_bytes(8)

message_bytes = message.encode()
flag_ct     = encrypt_ctr(round_key, round_nonce, message_bytes)   # (1)

receipt_pt  = make_receipt(note_id)
receipt_ct  = encrypt_ctr(round_key, round_nonce, receipt_pt)      # (2)
```

Cả `(1)` và `(2)` dùng chung `round_key` và `round_nonce`. Đặt keystream chung là $\mathrm{KS}$, ta có:

$$
\texttt{flag\_ct}=\texttt{message}\oplus\mathrm{KS},\qquad
\texttt{receipt\_ct}=\texttt{receipt\_pt}\oplus\mathrm{KS}.
$$

Cả hai bản mã đều bị rò rỉ ra ngoài mà không cần `secret`. Endpoint `/api/notes/<id>/public` trả về `flag_ct`, còn `/api/receipts/<id>` trả về `receipt_ct`:

```python
@app.get("/api/notes/<note_id>/public")
def public_note(note_id):
    ...
    return jsonify({
        "id": note_id,
        "nonce": b64d(row["nonce_b64"]).hex(),
        "flag_ct": b64d(row["flag_ct_b64"]).hex(),
        "receipt_url": f"/api/receipts/{note_id}",
    })

@app.get("/api/receipts/<note_id>")
def public_receipt(note_id):
    ...
    return jsonify({"id": note_id, "receipt_ct": b64d(row["receipt_ct_b64"]).hex()})
```

Trong khi đó, đường đọc lại được bảo vệ bằng `secret`:

```python
@app.get("/api/notes/<note_id>")
def read_note(note_id):
    ...
    if request.args.get("secret") != row["secret"]:
        return jsonify({"error": "forbidden"}), 403
```

Như vậy `secret` chỉ bảo vệ một trong nhiều lối vào; nội dung thực tế của note đã lộ gián tiếp qua cặp bản mã công khai.

Nội dung biên lai được sinh bởi `make_receipt`:

```python
def make_receipt(note_id):
    prefix = f"ROUND-RECEIPT|{note_id}|".encode()
    return prefix + (b"A" * 256)
```

Bản rõ `receipt_pt` gồm chuỗi cố định `ROUND-RECEIPT|` (14 byte), `note_id` (16 ký tự hex, công khai), một dấu `|` (1 byte), và 256 byte `A`. Tất cả các thành phần này người tấn công đều biết, nên `receipt_pt` là **known-plaintext dài 287 byte**.

Vì bản rõ của biên lai đã biết và nó dùng chung keystream với message, ta khôi phục được keystream trực tiếp:

$$
\mathrm{KS}=\texttt{receipt\_ct}\oplus\texttt{receipt\_pt}.
$$

Message bị giới hạn `MAX_MESSAGE_LEN = 160` byte, nhỏ hơn nhiều so với 287 byte keystream tái tạo được, nên phần keystream này luôn phủ trọn `flag_ct`. Từ đó:

$$
\texttt{message}=\texttt{flag\_ct}\oplus\mathrm{KS}[:\,\lvert\texttt{flag\_ct}\rvert].
$$

Viết gộp, trên phần chồng lấn ta có $\texttt{message}=\texttt{flag\_ct}\oplus\texttt{receipt\_ct}\oplus\texttt{receipt\_pt}$, đúng dạng two-time pad khi một bản rõ đã biết. Quá trình này không đụng tới `round_key` và không cần `secret`.

Với một `note_id` bất kỳ, các bước là:

1. Gọi `GET /api/notes/<id>/public` lấy `flag_ct`.
2. Gọi `GET /api/receipts/<id>` lấy `receipt_ct`.
3. Dựng lại `receipt_pt = "ROUND-RECEIPT|<id>|" + "A"*256`.
4. Tính keystream `KS = receipt_ct XOR receipt_pt`.
5. Giải mã `message = flag_ct XOR KS[:len(flag_ct)]`.

#### Script giải

```python
import sys
import requests

def xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))

def solve(base: str, note_id: str) -> str:
    # flag_ct công khai, không cần secret
    pub = requests.get(f"{base}/api/notes/{note_id}/public").json()
    flag_ct = bytes.fromhex(pub["flag_ct"])

    # receipt_ct công khai
    rc = requests.get(f"{base}/api/receipts/{note_id}").json()
    receipt_ct = bytes.fromhex(rc["receipt_ct"])

    # biên lai đoán được 100%
    receipt_pt = f"ROUND-RECEIPT|{note_id}|".encode() + b"A" * 256

    # khôi phục keystream chung
    keystream = xor(receipt_ct, receipt_pt)

    # message dùng chung keystream với biên lai
    message = xor(flag_ct, keystream[: len(flag_ct)])
    return message.decode(errors="replace")


if __name__ == "__main__":
    base = sys.argv[1].rstrip("/")
    note_id = sys.argv[2]
    print(solve(base, note_id))
```

#### Nguyên nhân gốc và hướng vá

Gốc rễ là việc tái sử dụng cùng `(key, nonce)` cho hai bản rõ khác nhau trong AES-CTR, cộng với việc một bản rõ (biên lai) đoán được và cả hai bản mã đều công khai. Hướng vá đúng bản chất là cấp cho biên lai một nonce độc lập:

```python
round_nonce   = secrets.token_bytes(8)
receipt_nonce = secrets.token_bytes(8)          # nonce riêng cho biên lai

flag_ct    = encrypt_ctr(round_key, round_nonce,   message_bytes)
receipt_ct = encrypt_ctr(round_key, receipt_nonce, receipt_pt)   # nonce khác
```

kèm việc thêm cột `receipt_nonce_b64` để lưu nonce mới. Khi hai keystream khác nhau, phép XOR hai bản mã không còn triệt tiêu về $P_1\oplus P_2$, chuỗi khai thác trên bị vô hiệu. Về lâu dài, nên chuyển sang AEAD (AES-GCM) với nonce ngẫu nhiên duy nhất mỗi lần mã hóa để có thêm cả toàn vẹn dữ liệu.
