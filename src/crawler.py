import time
from playwright.sync_api import sync_playwright
from src.config import TARGET_URL, HEADLESS, TIMEOUT
from src.logger import get_logger
from src.storage import Storage

logger = get_logger("CRAWLER")

class NuriCrawler:
    def __init__(self):
        self.storage = Storage()

    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS, slow_mo=100)
            
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )
            
            page = context.new_page()
            
            try:
                # 1. 페이지 이동 및 메뉴 진입
                logger.info(">>> [메인] 누리장터 접속")
                page.goto(TARGET_URL, timeout=60000)
                page.wait_for_load_state("networkidle")

                logger.info(">>> [메뉴] 입찰공고 이동")
                page.click("#mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_btn_menuLvl1")
                time.sleep(0.5)
                
                logger.info(">>> [메뉴] 입찰공고목록 이동")
                page.click("#mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_genDepth3_0_btn_menuLvl3")
                
                search_btn_selector = "#mf_wfm_container_btnS0001"
                page.wait_for_selector(search_btn_selector, state="visible", timeout=TIMEOUT)
                
                # 2. 검색 및 목록 대기
                logger.info(">>> [목록] 검색 수행")
                page.click(search_btn_selector)
                
                row_selector = "#mf_wfm_container_grdBidPbancList_body_tbody tr.grid_body_row"
                page.wait_for_selector(row_selector, state="attached", timeout=TIMEOUT)
                time.sleep(2) 

                # 3. 목록 순회
                rows = page.query_selector_all(row_selector)
                count = len(rows)
                logger.info(f">>> [목록] {count}건 발견. 수집 시작.")

                for i in range(min(5, count)):
                    logger.info(f"\n--- 항목 {i+1} 처리 ---")
                    
                    # DOM 갱신 대응을 위한 재조회
                    current_row = page.query_selector_all(row_selector)[i]
                    link_element = current_row.query_selector("td[col_id='bidPbancNm'] a")
                    bid_no_element = current_row.query_selector("td[col_id='bidPbancNum']")
                    
                    if not link_element:
                        logger.info("   [!] 링크 없음. 건너뜀")
                        continue

                    # 공고번호 추출 및 중복 체크
                    bid_no = bid_no_element.inner_text().strip() if bid_no_element else f"UNKNOWN-{i}"
                    
                    if self.storage.is_crawled(bid_no):
                        logger.info(f"   [스킵] 이미 수집된 공고: {bid_no}")
                        continue
                        
                    bid_title = link_element.inner_text().strip()
                    logger.info(f"   [대상] {bid_title}")

                    # 상세 페이지 진입 (SPA/모달)
                    link_element.click()
                    time.sleep(3) # 데이터 로딩 대기
                    
                    try:
                        # 데이터 추출
                        info, files = self.extract_detail_info(page)
                        
                        # 데이터 보정 (DB 저장용)
                        info['입찰공고번호'] = bid_no
                        info['입찰공고명'] = bid_title
                        info['첨부파일'] = files
                        
                        self.print_result(info, files)
                        self.storage.save(info)
                        
                        # 목록 복귀 (닫기 또는 목록 버튼)
                        close_btn = page.query_selector("input[value='닫기'], .btn_cm.close")
                        list_btn = page.query_selector("input[value='목록'], .btn_cm.list")

                        if close_btn and close_btn.is_visible():
                            logger.info("   [동작] '닫기' 클릭")
                            close_btn.click()
                        elif list_btn and list_btn.is_visible():
                            logger.info("   [동작] '목록' 클릭")
                            list_btn.click()
                        else:
                            logger.info("   [동작] 버튼 못 찾음. 뒤로가기 실행")
                            page.go_back()

                        # 목록 복구 확인 (필수)
                        try:
                            page.wait_for_selector(row_selector, state="visible", timeout=10000)
                            logger.info("   [확인] 목록 복구됨")
                        except:
                            logger.info("   [경고] 목록 재로딩 실패. 검색 재실행")
                            page.click(search_btn_selector)
                            page.wait_for_selector(row_selector, state="visible", timeout=10000)

                    except Exception as e:
                        logger.info(f"   [오류] 상세 처리 중 에러: {e}")
                        page.go_back()
                        time.sleep(2)

            except Exception as e:
                logger.info(f"!!! 치명적 오류: {e}")
                import traceback
                traceback.print_exc()
                
            finally:
                self.storage.close()
                logger.info(">>> 브라우저 종료")
                browser.close()

    def extract_detail_info(self, target_page):
        """상세 페이지 데이터 추출"""
        extracted_data = {}
        files = []
        
        logger.info("      [수집] 상세 정보 파싱 중...")
        
        try:
            # 테이블 데이터 로딩 대기
            target_page.wait_for_selector("table.w2tb", state="visible", timeout=5000)
            
            tables = target_page.query_selector_all("table.w2tb")
            for tbl in tables:
                rows = tbl.query_selector_all("tbody tr")
                for row in rows:
                    ths = row.query_selector_all("th")
                    tds = row.query_selector_all("td")
                    
                    count = min(len(ths), len(tds))
                    for i in range(count):
                        key = ths[i].inner_text().strip().replace("\n", " ").replace("\r", "")
                        val = tds[i].inner_text().strip().replace("\n", " ").replace("\r", "")
                        
                        if key and key not in extracted_data:
                            extracted_data[key] = val
        except Exception:
            pass

        try:
            # 첨부파일 그리드 파싱
            file_rows = target_page.query_selector_all(".w2grid_dataLayer tbody tr")
            for row in file_rows:
                cells = row.query_selector_all("td")
                # HTML 구조상 4: 파일명, 5: 크기
                if len(cells) >= 6: 
                    fname = cells[4].inner_text().strip()
                    fsize = cells[5].inner_text().strip()
                    if fname:
                        files.append(f"{fname} ({fsize})")
        except Exception:
            pass
            
        return extracted_data, files

    def print_result(self, info, files):
        """결과 출력"""
        logger.info(f"      [결과] 필드 {len(info)}개, 파일 {len(files)}개")

        for k, v in info.items():
            logger.info(f"      - {k}: {v}")
        
        if files:
            logger.info(f"      - 첨부파일: {', '.join(files)}")