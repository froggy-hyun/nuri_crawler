import argparse
import time
import schedule
import datetime
import json
import asyncio
from src.crawler import NuriCrawler
from src.logger import get_logger
from src.storage import Storage

logger = get_logger("MAIN")

def run_crawler_job():
    """크롤러 실행 작업 래퍼 함수"""
    logger.info(">> 스케줄러에 의해 크롤링 작업 시작")
    try:
        crawler = NuriCrawler()
        # 비동기 함수 실행을 위해 asyncio.run 사용
        asyncio.run(crawler.run())
    except Exception as e:
        logger.error(f"작업 실행 중 오류 발생: {e}")
    
    # 작업 종료 로그 및 구분선 추가
    logger.info(">> 크롤링 작업 종료")
    logger.info("-" * 60 + "\n") 
    
    # 다음 실행 시간 로깅
    try:
        next_run = schedule.next_run()
        if next_run:
            logger.info(f"== 다음 실행 예정 시간: {next_run.strftime('%Y-%m-%d %H:%M:%S')} ==\n")
    except:
        pass

def main():
    parser = argparse.ArgumentParser(description="누리장터 입찰공고 수집기")
    
    # 실행 모드 설정 (기본값: single)
    parser.add_argument(
        "--mode", 
        type=str, 
        default="single", 
        choices=["single", "interval", "cron", "export"],
        help="실행 모드 (single: 1회, interval: 반복, cron: 예약, export: JSON파일추출)"
    )
    
    # 시간/간격 설정 값
    parser.add_argument(
        "--value", 
        type=str, 
        help="interval 모드일 경우 '분' 단위(예: 30), cron 모드일 경우 'HH:MM' (예: 09:00,18:00)"
    )

    args = parser.parse_args()

    # 1. 단일 실행 (Single Mode)
    if args.mode == "single":
        logger.info("=== [모드] 단일 실행 ===")
        run_crawler_job()

    # 2. 주기적 반복 (Interval Mode)
    elif args.mode == "interval":
        if not args.value:
            logger.error("interval 모드는 --value (분 단위)가 필요합니다.")
            return
        
        minutes = int(args.value)
        logger.info(f"=== [모드] 인터벌 실행 (매 {minutes}분 마다) ===")
        
        # 즉시 1회 실행 후 스케줄 등록
        run_crawler_job()
        
        schedule.every(minutes).minutes.do(run_crawler_job)
        
        # 다음 실행 시간 안내
        next_run = schedule.next_run()
        logger.info(f"== 대기 중... 다음 실행: {next_run.strftime('%Y-%m-%d %H:%M:%S')} ==\n")
        
        while True:
            schedule.run_pending()
            time.sleep(1)

    # 3. 정해진 시간 실행 (Cron Mode)
    elif args.mode == "cron":
        if not args.value:
            logger.error("cron 모드는 --value (HH:MM 형식)가 필요합니다.")
            return

        target_times = [t.strip() for t in args.value.split(',')]
        logger.info(f"=== [모드] 예약 실행 (매일 {target_times}) ===")

        for t in target_times:
            schedule.every().day.at(t).do(run_crawler_job)

        next_run = schedule.next_run()
        if next_run:
            logger.info(f"== 대기 중... 다음 실행: {next_run.strftime('%Y-%m-%d %H:%M:%S')} ==\n")

        while True:
            schedule.run_pending()
            time.sleep(1)
    
    # 4. 데이터 추출 모드 (Export Mode)
    elif args.mode == "export":
        logger.info("=== [모드] DB 데이터 JSON 파일 추출 ===")
        try:
            storage = Storage()
            all_data = storage.fetch_all()
            storage.close()

            if not all_data:
                logger.info(">> 저장된 데이터가 없습니다.")
                return

            # 파일명 생성: YYYYMMDD_HHMMSS_nuri_bids.json
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_nuri_bids.json"

            # JSON 파일 저장
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=4)
            
            logger.info(f">> 추출 완료: {filename} (총 {len(all_data)}건)")
            
        except Exception as e:
            logger.error(f"데이터 추출 중 오류 발생: {e}")

if __name__ == "__main__":
    main()