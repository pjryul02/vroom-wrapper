FROM python:3.10-slim

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    httpx \
    pydantic \
    redis

# 소스 복사
COPY src/ ./src/
COPY vroom_wrapper.py ./

# 로그 디렉토리
RUN mkdir -p /app/logs

# 포트 노출
EXPOSE 8000

# 실행
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
