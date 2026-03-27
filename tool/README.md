# Google Labs Flow Local Automation (Windows 11, BYOA)

Tool Python chạy local để tự động tạo video trên Google Labs Flow bằng **UI automation qua Playwright**.

## Tuân thủ bắt buộc
- **BYOA**: user tự đăng nhập tài khoản Google trong browser do tool mở.
- Không lưu mật khẩu, không dùng API/private endpoint/reverse network.
- Mặc định `headless: false` (headful). `headless: true` có thể bị anti-bot chặn.
- Nếu gặp captcha/verify/2FA/unusual traffic: tool chuyển trạng thái `PAUSED_NEEDS_HUMAN` và yêu cầu xử lý thủ công.

## Cấu trúc

```
tool/
  main.py
  config.py
  storage.py
  queue.py
  runner.py
  adapters/flow_adapter.py
  selectors.py
assets/
  selectors.json
  config.example.yaml
  prompts.example.txt
```

## Yêu cầu
- Python 3.11+
- Windows 11

## Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate
pip install playwright typer pydantic pyyaml
python -m playwright install chromium
```

## Chuẩn bị file cấu hình

```bash
copy assets\config.example.yaml assets\config.yaml
copy assets\prompts.example.txt assets\prompts.txt
```

Nếu dùng mode `components` hoặc `frames`, đặt ảnh vào thư mục `assets/images`.

## Chạy

### 1) Enqueue prompts vào SQLite

```bash
python -m tool.main enqueue -c assets/config.yaml
```

### 2) Run queue

```bash
python -m tool.main run -c assets/config.yaml
```

### 3) Resume sau khi kill/crash

```bash
python -m tool.main resume -c assets/config.yaml
```

### 4) Xem trạng thái queue

```bash
python -m tool.main status -c assets/config.yaml
```

## Output
- Video: `output/{yyyy-mm-dd}/{job_id}/video.mp4` (hoặc `.webm`).
- Metadata: `output/{yyyy-mm-dd}/{job_id}/metadata.json`.
- Log: `runtime/logs/app.log`.
- Khi lỗi/verify: tự lưu screenshot + HTML snapshot trong thư mục job.

## Quy trình verify/captcha
Khi phát hiện challenge:
1. Tool pause job -> `PAUSED_NEEDS_HUMAN`.
2. User xử lý xác minh trong browser.
3. Quay lại terminal nhấn Enter để tiếp tục.
4. Job chưa done sẽ retry/resume theo queue state machine.

## Build EXE (PyInstaller)

```bash
pip install pyinstaller
pyinstaller --name flow-local-automation --onefile --collect-all playwright tool/main.py
```

Exe output tại `dist\flow-local-automation.exe`.

> Lưu ý: lần chạy đầu trên máy user vẫn cần browser profile đăng nhập Google.
