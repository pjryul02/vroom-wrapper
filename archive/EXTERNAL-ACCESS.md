# 외부 접근 설정 가이드

현재 PC를 서버로 사용하여 외부에서 VROOM Wrapper API를 호출하는 방법입니다.

## 📍 현재 설정

- **내부 IP**: `172.19.149.67` (WSL)
- **Wrapper 포트**: `8000`
- **VROOM 포트**: `3000`
- **OSRM 포트**: `5000`

## 🌐 외부 접근 설정 단계

### 1. Windows 방화벽 설정

#### 방법 A: PowerShell (관리자 권한)

```powershell
# Wrapper 포트 열기
New-NetFirewallRule -DisplayName "VROOM Wrapper" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow

# VROOM 포트 열기 (선택사항)
New-NetFirewallRule -DisplayName "VROOM Engine" -Direction Inbound -LocalPort 3000 -Protocol TCP -Action Allow

# OSRM 포트 열기 (선택사항)
New-NetFirewallRule -DisplayName "OSRM Engine" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
```

#### 방법 B: GUI

1. Windows 검색: "고급 보안이 포함된 Windows Defender 방화벽"
2. 왼쪽: "인바운드 규칙"
3. 오른쪽: "새 규칙..."
4. 규칙 종류: "포트" 선택
5. TCP, 특정 로컬 포트: `8000` 입력
6. 연결 허용
7. 이름: "VROOM Wrapper"

### 2. 공유기 포트포워딩 (외부 인터넷에서 접근하려면)

공유기 관리 페이지 접속 (보통 192.168.0.1 또는 192.168.1.1):

```
포트포워딩 설정:
외부 포트: 8000 → 내부 IP: 172.19.149.67 → 내부 포트: 8000
```

⚠️ **보안 주의사항**:
- 인증 없이 외부에 노출하면 위험합니다
- 프로덕션 사용 시 API Key, HTTPS 필수!

### 3. WSL 포트 포워딩 (Windows → WSL)

WSL2에서는 자동으로 포트포워딩되지만, 문제 있으면:

**PowerShell (관리자 권한)**:
```powershell
# WSL IP 확인
wsl hostname -I

# 포트포워딩 추가 (WSL IP가 172.19.149.67일 때)
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=172.19.149.67

# 확인
netsh interface portproxy show all

# 삭제하려면
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
```

## 🧪 테스트

### 로컬 네트워크에서 테스트

```bash
# 다른 PC에서 (같은 WiFi/LAN)
curl http://172.19.149.67:8000/health

# 또는 Windows PC의 IP로 (예: 192.168.0.10)
curl http://192.168.0.10:8000/health
```

### 외부 인터넷에서 테스트

```bash
# 외부 IP 확인
curl https://api.ipify.org

# 외부에서 접근 (포트포워딩 설정 후)
curl http://YOUR_PUBLIC_IP:8000/health
```

## 🔒 보안 강화 (프로덕션 사용 시)

### 1. API Key 인증 추가

```python
# vroom_wrapper.py에 추가
from fastapi import Header, HTTPException

API_KEY = "your-secret-key-here"  # 환경변수로 관리

@app.post("/optimize")
async def optimize_with_reasons(
    vrp_input: Dict[str, Any],
    x_api_key: str = Header(None)
):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # 기존 코드...
```

사용:
```bash
curl -X POST http://YOUR_IP:8000/optimize \
  -H "X-API-Key: your-secret-key-here" \
  -H "Content-Type: application/json" \
  -d @input.json
```

### 2. HTTPS (Let's Encrypt + Nginx)

```bash
# Nginx 설치 (Ubuntu/WSL)
sudo apt install nginx certbot python3-certbot-nginx

# SSL 인증서 발급
sudo certbot --nginx -d yourdomain.com

# Nginx 설정
sudo nano /etc/nginx/sites-available/vroom-wrapper
```

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. Rate Limiting

```python
# vroom_wrapper.py에 추가
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/optimize")
@limiter.limit("10/minute")  # 분당 10회 제한
async def optimize_with_reasons(request: Request, vrp_input: Dict[str, Any]):
    # 기존 코드...
```

### 4. IP 화이트리스트

```python
ALLOWED_IPS = ["1.2.3.4", "5.6.7.8"]  # 허용할 IP 목록

@app.post("/optimize")
async def optimize_with_reasons(request: Request, vrp_input: Dict[str, Any]):
    client_ip = request.client.host
    if client_ip not in ALLOWED_IPS:
        raise HTTPException(status_code=403, detail="IP not allowed")

    # 기존 코드...
```

## 📊 접근 URL

### 로컬 네트워크 (같은 WiFi/LAN)

```
Wrapper: http://192.168.x.x:8000/optimize
Health:  http://192.168.x.x:8000/health
```

### 외부 인터넷 (포트포워딩 후)

```
Wrapper: http://YOUR_PUBLIC_IP:8000/optimize
Health:  http://YOUR_PUBLIC_IP:8000/health

또는 도메인 사용:
Wrapper: https://yourdomain.com/optimize
Health:  https://yourdomain.com/health
```

## 🚀 빠른 시작 (외부 접근)

```bash
# 1. 서비스 시작
cd /home/shawn/vroom-wrapper-project
docker-compose up -d
python3 vroom_wrapper.py &

# 2. Windows 방화벽 열기 (PowerShell 관리자)
New-NetFirewallRule -DisplayName "VROOM Wrapper" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow

# 3. 외부에서 테스트
# 다른 PC/폰에서:
curl http://YOUR_WINDOWS_IP:8000/health
```

## ⚠️ 주의사항

1. **보안**: 인증 없이 외부 노출은 위험 (프로덕션에서 API Key 필수)
2. **포트**: 공유기 포트포워딩 시 8000번 포트가 이미 사용 중일 수 있음
3. **동적 IP**: 공인 IP가 변경될 수 있음 (DDNS 사용 권장)
4. **방화벽**: 회사/학교 네트워크에서는 제한될 수 있음
5. **성능**: 개인 PC는 24/7 운영에 적합하지 않을 수 있음

## 🔧 문제 해결

### "Connection refused" 에러

```bash
# Wrapper 실행 확인
ps aux | grep vroom_wrapper

# 포트 리스닝 확인
netstat -an | grep 8000

# 방화벽 확인 (Windows)
Get-NetFirewallRule -DisplayName "VROOM Wrapper"
```

### WSL 포트 접근 안됨

```powershell
# PowerShell에서 WSL IP 확인
wsl hostname -I

# 포트포워딩 재설정
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=<WSL_IP>
```

## 📱 모바일에서 접근

```bash
# 같은 WiFi에 연결된 폰에서
# iPhone/Android 브라우저:
http://192.168.x.x:8000/health

# 앱에서 API 호출:
fetch('http://192.168.x.x:8000/optimize', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({vehicles: [...], jobs: [...]})
})
```

## 🌍 실전 예시

### Python 클라이언트 (외부 PC)

```python
import requests

# 로컬 네트워크
WRAPPER_URL = "http://192.168.0.10:8000"

# 또는 외부 인터넷
# WRAPPER_URL = "http://your-public-ip:8000"

response = requests.post(f"{WRAPPER_URL}/optimize", json={
    "vehicles": [{"id": 1, "start": [126.9780, 37.5665]}],
    "jobs": [{"id": 101, "location": [127.0276, 37.4979]}]
})

print(response.json())
```

### JavaScript 클라이언트 (웹앱)

```javascript
// React/Vue/Angular 등에서
const WRAPPER_URL = 'http://192.168.0.10:8000';

async function optimizeRoute(vehicles, jobs) {
  const response = await fetch(`${WRAPPER_URL}/optimize`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({vehicles, jobs})
  });

  return await response.json();
}
```

---

**준비 완료!** 이제 외부에서 접근 가능합니다! 🚀

## 🔐 보안 설정 선택

### 옵션 A: Wrapper만 외부 노출 (권장)

```bash
# docker-compose.yml 수정
ports:
  - "127.0.0.1:3000:3000"  # VROOM
  - "127.0.0.1:5000:5000"  # OSRM

# 재시작
docker-compose down
docker-compose up -d
```

**결과**:
- ✅ Wrapper: `http://YOUR_IP:8000` (외부 접근 가능)
- ❌ VROOM: `http://YOUR_IP:3000` (접근 거부)
- ❌ OSRM: `http://YOUR_IP:5000` (접근 거부)

### 옵션 B: 모두 외부 노출 (현재 설정)

```yaml
# docker-compose.yml (기본값)
ports:
  - "3000:3000"  # VROOM
  - "5000:5000"  # OSRM
```

**결과**:
- ✅ Wrapper: `http://YOUR_IP:8000`
- ✅ VROOM: `http://YOUR_IP:3000`
- ✅ OSRM: `http://YOUR_IP:5000`

**보안 강화 필요**: 각 서비스에 방화벽 규칙 추가

## 💡 권장 사용 방식

### 외부 클라이언트

```python
# Wrapper만 호출 (이유 분석 포함)
response = requests.post('http://YOUR_IP:8000/optimize', json={
    "vehicles": [...],
    "jobs": [...]
})

result = response.json()
# unassigned에 reasons 자동 포함됨!
```

### 내부 개발/테스트

```bash
# VROOM 직접 호출 (로컬에서만)
curl http://localhost:3000/ -d @input.json

# OSRM 직접 호출 (로컬에서만)
curl http://localhost:5000/route/v1/driving/126.9,37.5;127.0,37.5
```

