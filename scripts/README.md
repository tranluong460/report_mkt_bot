# Scripts

## 1. `setup_all.bat` - Cài bot làm Windows Service

Tự động tải NSSM + cài service auto-restart + auto-start khi boot.

### Cách dùng

Mở **PowerShell/CMD với quyền Administrator**, chạy:

```bash
cd D:\Code\report_mkt_bot
scripts\setup_all.bat
```

Hoặc chỉ định thư mục khác:

```bash
scripts\setup_all.bat D:\path\to\report_mkt_bot
```

### Script làm những gì

1. Check quyền Administrator
2. Tìm `main.py` hoặc `dist\report_mkt_bot.exe` (ưu tiên exe)
3. Check file `.env`
4. Tự tải NSSM từ `nssm.cc` nếu chưa có
5. Xoá service cũ (nếu có)
6. Cài service `ReportMktBot` với:
   - Auto start khi boot máy
   - Auto restart sau 5s nếu crash
   - Log rotate 10MB
   - Log ra `service-stdout.log`, `service-stderr.log`
7. Start service ngay

### Quản lý service

```bash
nssm status ReportMktBot       # Xem trạng thái
nssm stop ReportMktBot         # Dừng
nssm start ReportMktBot        # Chạy lại
nssm restart ReportMktBot      # Restart
nssm remove ReportMktBot confirm  # Xoá service
```

Hoặc GUI: `services.msc` → tìm **Report MKT Bot**.

### Xem log

```powershell
Get-Content service-stdout.log -Wait -Tail 50
```

### Troubleshooting

**Không tải được NSSM:**
- Thử lại sau vài phút
- Hoặc tải thủ công `https://nssm.cc/release/nssm-2.24.zip` → giải nén `win64/nssm.exe` vào `scripts/`

**Service không start:**
```bash
type service-stderr.log
```
Thường do `.env` thiếu biến hoặc Redis URL sai.

**Sửa `.env` xong:**
```bash
nssm restart ReportMktBot
```

---

## 2. `setup_local_api.bat` - Local Telegram Bot API Server

Cài Docker container telegram-bot-api để gửi file **đến 2GB** (API chính giới hạn 50MB).

### Yêu cầu

- **Docker Desktop** đã cài và đang chạy
- **api_id** và **api_hash** từ https://my.telegram.org → API development tools

### Cách dùng

```bash
scripts\setup_local_api.bat <api_id> <api_hash> <bot_token>
```

Ví dụ:
```bash
scripts\setup_local_api.bat 12345 abc123def456 8401156986:AAEldUr6DaJPuHgCOoLtIoD95ZHMGH5UFcc
```

### Script làm những gì

1. Check Docker đang chạy
2. Logout bot khỏi API chính (Telegram yêu cầu)
3. Dừng container cũ nếu có
4. Chờ 10 giây
5. Start container `aiogram/telegram-bot-api` với `--restart=always`
6. Lắng nghe trên port `8081`

### Sau khi chạy xong

1. **Chờ 10 phút** (Telegram yêu cầu sau logout)
2. Test API:
   ```bash
   curl http://localhost:8081/bot<TOKEN>/getMe
   ```
3. Thêm vào `.env`:
   ```
   TELEGRAM_LOCAL_API=http://localhost:8081
   ```
4. Restart bot

### Quản lý container

```bash
docker ps                        # Xem container
docker logs telegram-bot-api     # Xem log
docker restart telegram-bot-api  # Restart
docker stop telegram-bot-api     # Dừng
docker rm -f telegram-bot-api    # Xoá
```

### Switch về API chính

1. Xoá `TELEGRAM_LOCAL_API` khỏi `.env`
2. Logout khỏi local:
   ```bash
   curl -X POST http://localhost:8081/bot<TOKEN>/logOut
   ```
3. Chờ 10 phút
4. Restart bot
