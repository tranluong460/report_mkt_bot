# Hướng dẫn cài Bot làm Windows Service

Chạy bot làm Windows Service giúp:
- **Tự động khởi động** khi máy boot
- **Tự restart** khi bot crash
- **Chạy ngầm** không cần mở terminal
- **Log** được ghi ra file

## Bước 1: Tải NSSM

1. Truy cập https://nssm.cc/download
2. Tải `nssm-2.24.zip`
3. Giải nén, copy `win64/nssm.exe` vào `D:\Code\report_mkt_bot\scripts\` (hoặc thêm vào PATH)

## Bước 2: Cài service

Mở PowerShell/CMD **với quyền Administrator**, chạy:

```bash
cd D:\Code\report_mkt_bot
scripts\install_service.bat D:\Code\report_mkt_bot
```

Script sẽ:
- Xoá service cũ (nếu có)
- Cài service `ReportMktBot`
- Cấu hình auto-start + auto-restart
- Khởi động service ngay lập tức

## Bước 3: Quản lý service

### Qua lệnh

```bash
nssm status ReportMktBot       # Xem trạng thái
nssm stop ReportMktBot         # Dừng
nssm start ReportMktBot        # Chạy lại
nssm restart ReportMktBot      # Restart
nssm remove ReportMktBot confirm  # Xoá service
```

### Qua GUI

Mở `services.msc` → tìm **Report MKT Bot** → Right-click → Start/Stop/Restart.

## Bước 4: Xem log

Service chạy ngầm, log được ghi vào file:

```
D:\Code\report_mkt_bot\service-stdout.log    # stdout
D:\Code\report_mkt_bot\service-stderr.log    # stderr
```

Mở file log bằng notepad hoặc dùng PowerShell tail:

```powershell
Get-Content service-stdout.log -Wait -Tail 50
```

## Troubleshooting

### Service không start

```bash
nssm status ReportMktBot
```

Nếu STOPPED, xem log error:
```
type service-stderr.log
```

Thường do:
- File `.env` thiếu hoặc sai đường dẫn
- Python/dependencies chưa cài
- Redis URL sai

### Bot crash liên tục

Service sẽ tự restart sau 5 giây (cấu hình trong script). Kiểm tra log để tìm lỗi gốc:

```powershell
Get-Content service-stderr.log -Tail 100
```

### Đổi cấu hình

Sau khi sửa `.env`, restart service:

```bash
nssm restart ReportMktBot
```
