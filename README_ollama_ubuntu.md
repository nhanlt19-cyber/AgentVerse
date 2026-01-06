## 1. Giới thiệu

Dự án này sử dụng AgentVerse làm backend mô phỏng, với LLM chạy qua **Ollama** (model `llama3.1:latest`) thay vì OpenAI API.

Cấu trúc triển khai:
- **LLM**: Ollama chạy local trên máy Ubuntu (OpenAI-compatible API).
- **Backend**: FastAPI (`pokemon_server.py`) chạy bằng `uvicorn`.
- **Client / Laptop**: Truy cập backend qua IP của máy Ubuntu (ví dụ `10.0.12.81`).

---

## 2. Yêu cầu hệ thống

- **Hệ điều hành**: Ubuntu 20.04+ (hoặc tương đương).
- **Python**: 3.9+ (khuyên dùng 3.10).
- **Git** đã cài đặt.
- **Ollama** cài trên máy Ubuntu (có GPU càng tốt nhưng không bắt buộc).
- Cổng mạng:
  - Backend: cổng `10002` (có thể đổi được).
  - Ollama: mặc định cổng `11434`.

---

## 3. Clone mã nguồn

```bash
# Vào thư mục nơi bạn muốn đặt dự án
cd /path/to/workspace

# Clone repo (thay URL nếu bạn dùng repo riêng)
git clone <URL_repo_AgentVerse>
cd AgentVerse
```

> **Lưu ý**: Nếu bạn đã copy mã nguồn sang Ubuntu bằng cách khác (USB, SCP, v.v.) chỉ cần đảm bảo bạn đang `cd` đúng tới thư mục gốc dự án.

---

## 4. Tạo môi trường Python và cài đặt thư viện

### 4.1. Tạo virtualenv (khuyến nghị)

```bash
# Cài venv nếu chưa có
sudo apt-get update
sudo apt-get install -y python3-venv

# Tạo môi trường ảo
python3 -m venv .venv

# Kích hoạt
source .venv/bin/activate
```

Mỗi khi mở terminal mới để chạy dự án, hãy kích hoạt lại:

```bash
cd /path/to/AgentVerse
source .venv/bin/activate
```

### 4.2. Cài dependencies

```bash
# Cập nhật pip lên version mới nhất (quan trọng để có prebuilt wheels)
pip install --upgrade pip setuptools wheel

# Cài dependencies
pip install -r requirements.txt
```

**Lưu ý về lỗi `tiktoken`:**

Nếu bạn gặp lỗi khi cài `tiktoken` (ví dụ: "can't find Rust compiler"), hãy thử các bước sau:

1. **Cập nhật pip và thử lại** (thường giải quyết được vì pip mới có thể tìm thấy prebuilt wheel):
   ```bash
   pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt
   ```

2. **Nếu vẫn lỗi, cài Rust compiler** (chỉ khi cần build từ source):
   ```bash
   # Cài Rust qua rustup (khuyến nghị)
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   source $HOME/.cargo/env
   
   # Hoặc cài qua package manager
   sudo apt-get update
   sudo apt-get install -y rustc cargo
   
   # Sau đó thử cài lại
   pip install -r requirements.txt
   ```

3. **Hoặc cài tiktoken riêng với version mới hơn**:
   ```bash
   pip install "tiktoken>=0.7.0"
   pip install -r requirements.txt
   ```

> **Ghi chú**: File `requirements.txt` đã được cập nhật để dùng `tiktoken>=0.7.0` (thay vì `tiktoken==0.5.1`) để tương thích tốt hơn với Python 3.12 và có prebuilt wheels.

---

## 5. Cài đặt và cấu hình Ollama

### 5.1. Cài Ollama trên Ubuntu

Tham khảo hướng dẫn chính thức của Ollama cho Ubuntu. Ví dụ (có thể thay đổi theo thời điểm):

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

> Nếu script thay đổi, hãy xem hướng dẫn mới nhất trên trang chủ Ollama.

### 5.2. Tải model `llama3.1:latest`

Sau khi cài xong Ollama:

```bash
ollama pull llama3.1:latest
```

### 5.3. Khởi chạy Ollama

Thông thường Ollama sẽ chạy như service. Nếu cần tự chạy:

```bash
ollama serve
```

Mặc định Ollama lắng nghe ở `http://127.0.0.1:11434`.

---

## 6. Cấu hình biến môi trường cho backend

Dự án đã được chỉnh sửa để:

- **Nếu KHÔNG có** `OPENAI_API_KEY` và `AZURE_OPENAI_API_KEY`:
  - Tự động dùng Ollama qua OpenAI-compatible API.

Bạn chỉ cần đặt thêm các biến môi trường cho rõ ràng:

```bash
# Trong terminal đã kích hoạt .venv và ở thư mục gốc AgentVerse

export OLLAMA_BASE_URL="http://127.0.0.1:11434/v1"
export OLLAMA_MODEL="llama3.1:latest"

# Model dùng cho LLM chính (AgentVerse)
export LLM_MODEL="llama3.1:latest"

# Model dùng cho embeddings (vector memory)
export EMBEDDING_MODEL="llama3.1:latest"

# Đảm bảo KHÔNG đặt các biến sau (hoặc để trống) nếu bạn không dùng OpenAI/Azure:
unset OPENAI_API_KEY
unset OPENAI_BASE_URL
unset AZURE_OPENAI_API_KEY
unset AZURE_OPENAI_API_BASE
```

Nếu muốn tiện lợi hơn, bạn có thể tạo file `env.sh`:

```bash
cat > env.sh << 'EOF'
export OLLAMA_BASE_URL="http://127.0.0.1:11434/v1"
export OLLAMA_MODEL="llama3.1:latest"
export LLM_MODEL="llama3.1:latest"
export EMBEDDING_MODEL="llama3.1:latest"

unset OPENAI_API_KEY
unset OPENAI_BASE_URL
unset AZURE_OPENAI_API_KEY
unset AZURE_OPENAI_API_BASE
EOF
```

Sau đó mỗi lần chỉ cần:

```bash
source env.sh
```

---

## 7. Chạy backend FastAPI (AgentVerse server)

Backend chính nằm ở file `pokemon_server.py`.

### 7.1. Chạy server

Đảm bảo:
- Đã `cd` vào thư mục gốc dự án.
- Đã `source .venv/bin/activate`.
- Đã `source env.sh` (hoặc set biến môi trường như ở trên).
- Ollama đang chạy (`ollama serve`).

Chạy:

```bash
uvicorn pokemon_server:app --host 0.0.0.0 --port 10002
```

Giải thích:
- `--host 0.0.0.0`: Cho phép truy cập từ các máy khác trong LAN.
- `--port 10002`: Cổng server; bạn có thể đổi nếu muốn.

Nếu muốn chạy nền (background) tạm thời bạn có thể dùng `tmux`, `screen`, hoặc systemd service tùy nhu cầu.

---

## 8. Truy cập từ laptop qua IP Ubuntu (VD: `10.0.12.81`)

Giả sử:
- Máy Ubuntu có IP LAN: `10.0.12.81`.
- Backend đang chạy trên `0.0.0.0:10002` như ở trên.

### 8.1. Kiểm tra từ máy Ubuntu

```bash
curl http://127.0.0.1:10002/
```

Nếu OK, bạn sẽ thấy JSON:

```json
{"status": "ok"}
```

### 8.2. Truy cập từ laptop

Trên laptop (cùng mạng LAN), mở trình duyệt hoặc dùng `curl`:

```bash
curl http://10.0.12.81:10002/
```

Bạn cũng có thể gọi các endpoint khác:

- **Chat**:

  - Endpoint: `POST http://10.0.12.81:10002/chat`
  - Body JSON ví dụ:

    ```json
    {
      "content": "Xin chào",
      "sender": "Brendan",
      "receiver": "May",
      "receiver_id": 0
    }
    ```

- **Make decision**:

  - Endpoint: `POST http://10.0.12.81:10002/make_decision`
  - Body:

    ```json
    {
      "agent_ids": [0, 1]
    }
    ```

- **Update location**:

  - Endpoint: `POST http://10.0.12.81:10002/update_location`
  - Body:

    ```json
    {
      "agent_locations": {
        "Brendan": "Pokémon Center",
        "May": "Route 101"
      }
    }
    ```

---

## 9. Chạy các Simulation Cases khác

Ngoài Pokemon game, AgentVerse còn hỗ trợ nhiều simulation cases khác. Bạn có thể chạy chúng với Ollama.

### 9.1. Framework Required Modules

Simulation framework sử dụng các modules sau:
```
- agentverse 
  - agents
    - simulation_agent
  - environments
    - simulation_env
```

### 9.2. CLI Example (Command Line Interface)

Bạn có thể tạo các môi trường multi-agent được cung cấp sẵn. Ví dụ với classroom scenario, có 9 agents: 1 giáo sư và 8 sinh viên.

```bash
# Đảm bảo đã kích hoạt .venv và set biến môi trường
source .venv/bin/activate
source env.sh

# Chạy simulation qua CLI
agentverse-simulation --task simulation/nlp_classroom_9players
```

### 9.3. GUI Example (Giao diện Web)

AgentVerse cũng cung cấp một demo website local cho các môi trường này. Bạn có thể khởi chạy với:

```bash
# Đảm bảo đã kích hoạt .venv và set biến môi trường
source .venv/bin/activate
source env.sh

# Chạy simulation qua GUI (Gradio)
agentverse-simulation-gui --task simulation/nlp_classroom_9players
```

Sau khi khởi chạy thành công, bạn có thể truy cập:
- **Từ máy Ubuntu**: [http://127.0.0.1:7860/](http://127.0.0.1:7860/)
- **Từ laptop**: [http://10.0.12.81:7860/](http://10.0.12.81:7860/) (nếu Gradio được cấu hình để bind `0.0.0.0`)

> **Lưu ý**: Mặc định Gradio có thể chỉ bind `127.0.0.1`. Nếu bạn muốn truy cập từ laptop, có thể cần chỉnh sửa code hoặc dùng SSH tunnel.

### 9.4. Cài đặt BMTools (Tùy chọn)

Nếu bạn muốn chạy các simulation cases có sử dụng tools (ví dụ: `simulation/nlp_classroom_3players_withtool`), bạn cần cài BMTools:

```bash
cd /path/to/workspace  # Thoát khỏi thư mục AgentVerse nếu đang ở trong đó

git clone https://github.com/OpenBMB/BMTools.git
cd BMTools
pip install -r requirements.txt
python setup.py develop

# Quay lại thư mục AgentVerse
cd /path/to/AgentVerse
```

> **Ghi chú**: Việc cài BMTools là tùy chọn. Nếu bạn không cài BMTools, các simulation cases không dùng tools vẫn chạy bình thường.

### 9.5. Các Simulation Cases có sẵn

Bạn có thể xem danh sách các simulation cases trong thư mục `agentverse/tasks/simulation/`. Một số ví dụ:

- `simulation/nlp_classroom_9players`: Lớp học NLP với 9 agents
- `simulation/nlp_classroom_3players`: Lớp học NLP với 3 agents
- `simulation/prisoner_dilemma`: Prisoner's Dilemma game
- `simulation/sde_team/sde_team_2players`: Software development team với 2 players
- `simulation/db_diag`: Database diagnosis scenario

Để xem chi tiết các simulation cases, tham khảo file `README_simulation_cases.md` trong dự án.

---

## 10. Ghi chú về cấu hình model

- `LLM_MODEL`:
  - Điều khiển model mà AgentVerse sẽ dùng cho chat chính.
  - Mặc định đã đặt là `llama3.1:latest` (Ollama).

- `EMBEDDING_MODEL`:
  - Model dùng cho embeddings phía `get_embedding` (vector memory).
  - Mặc định cũng là `llama3.1:latest`.
  - Bạn có thể tách riêng nếu sử dụng model embeddings khác trong Ollama.

Nếu sau này bạn muốn quay lại dùng OpenAI:
1. Cài đặt thư viện `openai` (đã có trong `requirements.txt`).
2. Đặt:
   ```bash
   export OPENAI_API_KEY="sk-..."
   export OPENAI_BASE_URL="https://api.openai.com/v1"
   ```
3. Bỏ/không set `OLLAMA_BASE_URL` và các biến liên quan (hoặc vẫn để, nhưng ưu tiên OpenAI khi có key).

---

## 11. Khắc phục một số lỗi thường gặp

- **Lỗi kết nối tới Ollama**:
  - Kiểm tra `ollama serve` có đang chạy không.
  - Kiểm tra `OLLAMA_BASE_URL` đúng cổng (`11434`) và có `/v1`.
  - Test:
    ```bash
    curl http://127.0.0.1:11434/v1/models
    ```

- **Lỗi không tìm thấy model `llama3.1:latest`**:
  - Đảm bảo đã `ollama pull llama3.1:latest`.
  - Kiểm tra lại biến `OLLAMA_MODEL`, `LLM_MODEL`, `EMBEDDING_MODEL`.

- **Lỗi khi import Python** (module not found):
  - Đảm bảo đã kích hoạt `.venv` và cài `requirements.txt`.
  - Chạy lại:
    ```bash
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

- **Lỗi khi cài `tiktoken`** (ví dụ: "can't find Rust compiler"):
  - **Giải pháp 1** (khuyến nghị): Cập nhật pip và thử lại:
    ```bash
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
    ```
  - **Giải pháp 2**: Nếu vẫn lỗi, cài Rust compiler:
    ```bash
    # Cài Rust qua rustup (khuyến nghị)
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
    source $HOME/.cargo/env
    
    # Hoặc cài qua package manager
    sudo apt-get update
    sudo apt-get install -y rustc cargo
    
    # Sau đó thử cài lại
    pip install -r requirements.txt
    ```
  - **Giải pháp 3**: Cài tiktoken riêng với version mới hơn:
    ```bash
    pip install "tiktoken>=0.7.0"
    pip install -r requirements.txt
    ```

- **Lỗi `TypeError: type 'typing.TypeVar' is not an acceptable base type`** (khi chạy uvicorn):
  - **Nguyên nhân**: `typing-extensions==4.5.0` không tương thích với Python 3.12.
  - **Giải pháp**: Cập nhật `typing-extensions` lên phiên bản mới hơn:
    ```bash
    # Cập nhật typing-extensions
    pip install --upgrade "typing-extensions>=4.8.0"
    
    # Hoặc cài lại toàn bộ requirements
    pip install -r requirements.txt --upgrade
    ```
  - **Lưu ý**: File `requirements.txt` đã được cập nhật để dùng `typing-extensions>=4.8.0` thay vì `typing-extensions==4.5.0` để tương thích với Python 3.12.

- **Lỗi `TypeError: Simulation.from_task() missing 1 required positional argument: 'tasks_dir'`**:
  - **Nguyên nhân**: Phiên bản mới của AgentVerse yêu cầu tham số `tasks_dir` khi gọi `Simulation.from_task()`.
  - **Giải pháp**: File `pokemon_server.py` đã được cập nhật để tự động tính toán đường dẫn `tasks_dir`. Nếu bạn gặp lỗi này, đảm bảo bạn đang dùng phiên bản mới nhất của `pokemon_server.py` hoặc cập nhật code như sau:
    ```python
    import os
    # ...
    tasks_dir = os.path.join(os.path.dirname(__file__), "agentverse", "tasks")
    agent_verse = Simulation.from_task("simulation/pokemon", tasks_dir)
    ```

- **Lỗi `ValueError: Task pokemon not found` hoặc `Task __init__.py not found`**:
  - **Nguyên nhân**: Task name phải bao gồm cả thư mục cha. Ví dụ: `"simulation/pokemon"` thay vì chỉ `"pokemon"`.
  - **Giải pháp**: Đảm bảo bạn dùng đúng format task name:
    ```python
    # Đúng
    agent_verse = Simulation.from_task("simulation/pokemon", tasks_dir)
    
    # Sai
    agent_verse = Simulation.from_task("pokemon", tasks_dir)
    ```
  - **Lưu ý**: File `pokemon_server.py` đã được cập nhật để dùng `"simulation/pokemon"`.

---

## 12. Tóm tắt nhanh quy trình triển khai

1. **Clone dự án**:
   ```bash
   git clone <URL_repo_AgentVerse>
   cd AgentVerse
   ```

2. **Tạo & kích hoạt môi trường ảo**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Cài Python packages**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Cài và khởi động Ollama**, kéo model:
   ```bash
   ollama pull llama3.1:latest
   ollama serve
   ```

5. **Thiết lập biến môi trường**:
   ```bash
   source env.sh   # hoặc export các biến như ở phần 6
   ```

6. **Chạy backend**:
   ```bash
   uvicorn pokemon_server:app --host 0.0.0.0 --port 10002
   ```

7. **Từ laptop truy cập**:
   - Kiểm tra: `http://10.0.12.81:10002/`
   - Gọi các API `/chat`, `/make_decision`, `/update_location` qua IP `10.0.12.81`.

---


