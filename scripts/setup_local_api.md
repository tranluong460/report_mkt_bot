# Hướng dẫn cài đặt Local Telegram Bot API Server

Local API server cho phép gửi file lên đến **2GB** (thay vì 50MB của API chính).

## Yêu cầu

- Docker Desktop đã cài đặt và đang chạy
- Telegram account
- Bot token

---

## Bước 1: Lấy api_id và api_hash

1. Truy cập https://my.telegram.org
2. Đăng nhập bằng số điện thoại
3. Click **API development tools**
4. Điền form:
   - App title: `Api Telegram Local`
   - Short name: `ApiLocal`
   - Platform: **Desktop**
5. Click **Create application**
6. Ghi lại **api_id** (số) và **api_hash** (chuỗi hex)

---

## Bước 2: Logout bot khỏi API chính

**Quan trọng:** Chỉ làm 1 lần. Sau khi logout phải chờ 10 phút mới dùng được local server.

```bash
curl -X POST https://api.telegram.org/bot<BOT_TOKEN>/logOut
```

Thay `<BOT_TOKEN>` bằng token thật. Response phải là `{"ok":true,"result":true}`.

---

## Bước 3: Chạy Docker container

```bash
docker run -d ^
  --name telegram-bot-api ^
  --restart=always ^
  -p 8081:8081 ^
  -e TELEGRAM_API_ID=<api_id> ^
  -e TELEGRAM_API_HASH=<api_hash> ^
  -v telegram-bot-api-data:/var/lib/telegram-bot-api ^
  aiogram/telegram-bot-api:latest
```

Thay `<api_id>` và `<api_hash>` bằng giá trị từ bước 1.

`--restart=always` giúp container tự khởi động khi boot máy.

---

## Bước 4: Kiểm tra container

```bash
# Xem container đang chạy
docker ps

# Xem log
docker logs telegram-bot-api

# Test API
curl http://localhost:8081/bot<BOT_TOKEN>/getMe
```

Nếu `getMe` trả về JSON chứa thông tin bot → thành công.

---

## Bước 5: Cấu hình bot Python

Thêm vào file `.env`:

```env
TELEGRAM_LOCAL_API=http://localhost:8081
```

Restart bot:

```bash
python main.py
```

---

## Các lệnh Docker hữu ích

```bash
docker ps                          # Xem container đang chạy
docker logs telegram-bot-api       # Xem log
docker restart telegram-bot-api    # Restart
docker stop telegram-bot-api       # Dừng
docker start telegram-bot-api      # Chạy lại
docker rm -f telegram-bot-api      # Xoá hoàn toàn
```

---

## Switch về API chính (nếu cần)

1. Xoá dòng `TELEGRAM_LOCAL_API` trong `.env`
2. Logout khỏi local server:
   ```bash
   curl -X POST http://localhost:8081/bot<BOT_TOKEN>/logOut
   ```
3. Chờ 10 phút
4. Restart bot

---

## Troubleshooting

**Container không start:**
```bash
docker logs telegram-bot-api
```
Kiểm tra lỗi cụ thể.

**getMe báo lỗi "Unauthorized":**
- Token sai
- Bot chưa logout khỏi API chính
- Chưa chờ đủ 10 phút sau logout

**Bot không kết nối được:**
- Kiểm tra port 8081 có bị firewall chặn không
- Thử `curl http://localhost:8081` từ máy build

**File vẫn báo "Request Entity Too Large":**
- Kiểm tra `.env` có `TELEGRAM_LOCAL_API=http://localhost:8081`
- Restart bot Python
- Xem log bot có gọi `localhost:8081` không
