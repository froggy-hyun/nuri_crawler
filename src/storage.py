import sqlite3
import json
from datetime import datetime, timedelta
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
        """스키마 정의: 공고번호 PK, 상태 컬럼"""
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS bids (
                    bid_no TEXT PRIMARY KEY,
                    title TEXT,
                    status TEXT,
                    end_date TEXT,
                    raw_data JSON,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
        except Exception as e:
            logger.info(f"   [DB에러] 초기화 실패: {e}")

    def clean_old_data(self):
        """마감일 지났거나 1개월 초과 데이터 삭제 (단, 마감일이 빈 값인 경우는 날짜 비교 삭제 제외)"""
        try:
            now = datetime.now()
            month_ago = (now - timedelta(days=31)).strftime("%Y-%m-%d %H:%M")
            now_str = now.strftime("%Y-%m-%d %H:%M")
            
            # 1. (end_date < now) AND (end_date != '') AND (end_date IS NOT NULL)
            #    => 마감일이 존재하고, 현재 시간보다 과거인 경우만 삭제
            # 2. OR (collected_at < month_ago)
            #    => 수집한 지 1달이 넘은 데이터는 무조건 삭제
            
            self.cursor.execute('''
                DELETE FROM bids 
                WHERE (end_date < ? AND end_date != '' AND end_date IS NOT NULL) 
                   OR collected_at < ?
            ''', (now_str, month_ago))
            
            deleted = self.cursor.rowcount
            self.conn.commit()
            if deleted > 0:
                logger.info(f"   [정리] 만료(날짜확인됨)/오래된 데이터 {deleted}건 삭제 완료")
        except Exception as e:
            logger.info(f"   [DB에러] 데이터 정리 실패: {e}")

    def get_status(self, bid_no: str):
        """DB에 저장된 상태 반환 (없으면 None)"""
        try:
            self.cursor.execute("SELECT status FROM bids WHERE bid_no = ?", (bid_no,))
            res = self.cursor.fetchone()
            return res[0] if res else None
        except:
            return None

    def delete(self, bid_no: str):
        """특정 공고 삭제"""
        self.cursor.execute("DELETE FROM bids WHERE bid_no = ?", (bid_no,))
        self.conn.commit()

    def save(self, data: dict):
        """데이터 저장"""
        try:
            bid_no = data.get('입찰공고번호', 'UNKNOWN')
            title = data.get('입찰공고명', 'No Title')
            status = data.get('진행상태', '')
            
            # 마감일시 추출 (YYYY/MM/DD HH:MM)
            end_date_str = data.get('입찰서접수마감일시', '')
            
            self.cursor.execute('''
                INSERT OR REPLACE INTO bids (bid_no, title, status, end_date, raw_data, collected_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (bid_no, title, status, end_date_str, json.dumps(data, ensure_ascii=False)))
            
            self.conn.commit()
            logger.info(f"      [저장] DB 저장 완료: {bid_no}")
                
        except Exception as e:
            logger.info(f"      [DB에러] 저장 실패: {e}")

    def close(self):
        if self.conn:
            self.conn.close()