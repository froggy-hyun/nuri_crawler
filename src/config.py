import os
from pathlib import Path

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# 디렉토리 자동 생성
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# 크롤링 설정
TARGET_URL = "https://nuri.g2b.go.kr/"
HEADLESS = False  # 브라우저 보임
TIMEOUT = 30 * 1000  # 30초