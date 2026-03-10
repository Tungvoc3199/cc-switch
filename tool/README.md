# Flow Local Automation Tool (Windows 11, BYOA)

Tool Python chạy local để tự động thao tác Google Labs Flow qua **UI browser** bằng Playwright.

## Nguyên tắc
- BYOA: dùng chính account Google của user, đăng nhập thủ công trên browser do tool mở.
- Không dùng API private, không reverse network.
- Mặc định `headless: false` để giảm rủi ro anti-bot.
- Nếu gặp captcha/verify/2FA: tool chuyển `PAUSED_NEEDS_HUMAN`, chờ user xác minh rồi tiếp tục.

## Cấu trúc
```
tool/
  main.py
  config.py
  storage.py
  queue.py
  runner.py
  selectors.py
  adapters/flow_adapter.py
assets/
  selectors.json
  config.example.yaml
  prompts.example.txt
```

## Cài đặt
### 1) Python 3.11+
Cài Python 3.11+ trên Windows, bật Add Python to PATH.

### 2) Cài dependencies (ưu tiên script có fallback)
```bash
python scripts/install_deps.py
```

Nếu có proxy chặn PyPI, chuẩn bị `wheelhouse/` (chứa sẵn file wheel) rồi chạy:
```bash
python scripts/install_deps.py --wheelhouse wheelhouse
```

### 3) Cài browser cho Playwright
```bash
python -m playwright install chromium
```

### 4) Kiểm tra môi trường trước khi chạy
```bash
python -m tool.main doctor -c assets/config.example.yaml
```

## Chạy tool
### 1) Chuẩn bị config
Copy `assets/config.example.yaml` thành file riêng, ví dụ `config.yaml`, sửa mode/model/ratio/output.

### 2) Chạy doctor
```bash
python -m tool.main doctor -c config.yaml
```

### 3) Init DB
```bash
python -m tool.main init -c config.yaml
```

### 4) Enqueue prompts
```bash
python -m tool.main enqueue -c config.yaml
```

### 5) Run queue
```bash
python -m tool.main run -c config.yaml
```
Lần đầu chạy, browser mở ra và bạn đăng nhập Google thủ công.

### 6) Resume paused jobs
```bash
python -m tool.main resume -c config.yaml
python -m tool.main run -c config.yaml
```

## Output
- Video: `output/yyyy-mm-dd/{job_id}/video.mp4` (hoặc `.webm`)
- Metadata: `output/yyyy-mm-dd/{job_id}/metadata.json`
- Lỗi: `logs/job_{id}_{timestamp}/error.png`, `snapshot.html`, `error.txt`
- SQLite queue: file `flow_jobs.sqlite3`

## Build EXE (PyInstaller)
```bash
pyinstaller tool/flow_tool.spec --noconfirm
```
Kết quả EXE ở `dist/flow-tool.exe`.

## Trạng thái queue
- `PENDING`
- `RUNNING`
- `PAUSED_NEEDS_HUMAN`
- `DONE`
- `FAILED`
- `RETRYABLE`

## Lưu ý selector
Tất cả locator nằm ở `assets/selectors.json` (ưu tiên role/text/aria + fallback).
Khi UI Flow đổi, chỉnh selector JSON, không cần sửa code core.



## Bootstrap offline trên Windows (1 lệnh)
Dùng script PowerShell để chạy toàn bộ pipeline:
- kiểm tra Python >= 3.11
- cài dependency từ wheelhouse
- cài/kiểm tra Playwright Chromium
- chạy doctor
- build PyInstaller

Ví dụ:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_offline.ps1 -PythonExe py -Wheelhouse wheelhouse -ConfigPath config.yaml
```

Tuỳ chọn:
- `-SkipBrowserInstall`: bỏ qua bước cài/check Chromium
- `-SkipBuild`: bỏ qua bước build exe

## Smoke test (không cần đăng nhập/browser thật)
```bash
python -m unittest discover -s tests_py -v
```


## Chuẩn bị wheelhouse (máy có Internet)
Trên một máy có Internet, chạy:
```bash
python -m pip download -d wheelhouse -r tool/requirements.txt
```
Sau đó copy thư mục `wheelhouse/` sang máy build nội bộ và cài:
```bash
python scripts/install_deps.py --wheelhouse wheelhouse
```
