import sqlite3
import json
from src.config import DB_PATH
from src.logger import get_logger

logger = get_logger("STORAGE")

class Storage:
    def __init__(self):
        """DB 연결 및 테이블 초기화"""
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self._init_schema()

    def _init_schema(self):
        """스키마 정의: 공고번호 PK"""
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS bids (
                    bid_no TEXT PRIMARY KEY,
                    title TEXT,
                    raw_data JSON,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
        except Exception as e:
            logger.info(f"   [DB에러] 초기화 실패: {e}")

    def is_crawled(self, bid_no: str) -> bool:
        """이미 수집된 공고인지 확인"""
        try:
            self.cursor.execute("SELECT 1 FROM bids WHERE bid_no = ?", (bid_no,))
            return self.cursor.fetchone() is not None
        except Exception:
            return False

    def save(self, data: dict):
        """데이터 저장"""
        try:
            bid_no = data.get('입찰공고번호', 'UNKNOWN')
            title = data.get('입찰공고명', 'No Title')
            
            self.cursor.execute('''
                INSERT OR IGNORE INTO bids (bid_no, title, raw_data)
                VALUES (?, ?, ?)
            ''', (bid_no, title, json.dumps(data, ensure_ascii=False)))
            
            self.conn.commit()
            if self.cursor.rowcount > 0:
                logger.info(f"      [저장] DB 저장 완료: {bid_no}")
            else:
                logger.info(f"      [중복] 이미 수집된 공고: {bid_no}")
                
        except Exception as e:
            logger.info(f"      [DB에러] 저장 실패: {e}")

    def close(self):
        if self.conn:
            self.conn.close()