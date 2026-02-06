import logging
import sys
from logging.handlers import RotatingFileHandler
from src.config import LOG_DIR

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # 1. 콘솔 핸들러: 메시지만 출력
        console_fmt = logging.Formatter('%(message)s')
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(console_fmt)
        logger.addHandler(sh)
        
        # 2. 파일 핸들러: 시각 및 레벨 기록
        file_fmt = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
        fh = RotatingFileHandler(
            LOG_DIR / "crawler.log", maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        fh.setFormatter(file_fmt)
        logger.addHandler(fh)
        
    return logger