import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from src.config import TARGET_URL, HEADLESS, TIMEOUT
from src.logger import get_logger
from src.storage import Storage

logger = get_logger("CRAWLER")

class NuriCrawler:
    def __init__(self):
        self.storage = Storage()

    def _close_blocking_popups(self, page):
        """화면을 가리는 팝업/공지사항/모달 강제 삭제 (JS 실행)"""
        try:
            count = page.evaluate("""() => {
                let removedCount = 0;
                
                // 1. 팝업창 요소 (w2window, w2popup_window 등) 찾아서 제거
                const popups = document.querySelectorAll('.w2window, .w2popup_window');
                popups.forEach(el => {
                    // 보이는 요소라면 삭제
                    if (el.style.display !== 'none' && el.offsetParent !== null) {
                        el.remove(); // DOM에서 아예 삭제
                        removedCount++;
                    }
                });

                // 2. 배경 어둠 처리(Modal) 레이어 제거
                const modals = document.querySelectorAll('.w2modal');
                modals.forEach(el => {
                    el.remove();
                });
                
                return removedCount;
            }""")
            
            if count > 0:
                logger.info(f">>> [팝업] 방해 요소 {count}개 강제 삭제 완료")
                time.sleep(0.5) 
            
        except Exception:
            pass

    def run(self):
        start_time = time.time()
        self.storage.clean_old_data()
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS, slow_mo=100)
            
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )
            
            page = context.new_page()
            
            try:
                self._crawl_process(page)
            except Exception as e:
                logger.info(f"!!! 크롤링 중단: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.storage.close()
                browser.close()
                
        duration = time.time() - start_time
        logger.info(f"== 크롤링 완료 (소요시간: {duration:.2f}초) ==")

    def _crawl_process(self, page):
        logger.info(">>> [메인] 누리장터 접속")
        page.goto(TARGET_URL, timeout=TIMEOUT)
        page.wait_for_load_state("networkidle")

        self._close_blocking_popups(page)

        logger.info(">>> [메뉴] 입찰공고 이동")
        page.click("#mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_btn_menuLvl1", force=True)
        time.sleep(0.5)
        
        logger.info(">>> [메뉴] 입찰공고목록 이동")
        page.click("#mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_genDepth3_0_btn_menuLvl3", force=True)
        
        # 2. 필터 설정
        search_btn_selector = "#mf_wfm_container_btnS0001"
        page.wait_for_selector(search_btn_selector, state="visible", timeout=TIMEOUT)
        
        try:
            logger.info(">>> [필터] '입찰개시' 상태 선택")
            page.select_option("#mf_wfm_container_sbxPrgrsStts", label="입찰개시")
        except Exception as e:
            logger.info(f"   [주의] 필터 설정 실패: {e}")

        # 3. 검색 수행
        logger.info(">>> [목록] 검색 수행")
        self._close_blocking_popups(page)
        page.click(search_btn_selector, force=True)
        
        row_selector = "#mf_wfm_container_grdBidPbancList_body_tbody tr.grid_body_row"
        page.wait_for_selector(row_selector, state="attached", timeout=TIMEOUT)
        time.sleep(2) 

        try:
            total_cnt_selector = "#mf_wfm_container_tbxTotCnt"
            if page.is_visible(total_cnt_selector):
                total_count = page.inner_text(total_cnt_selector).strip()
                logger.info(f">>> [정보] 전체 조회 결과: Total {total_count} 건")
        except:
            pass

        # 4. 페이지네이션 순회
        while True:
            self._close_blocking_popups(page)

            try:
                active_page_el = page.query_selector(".w2pageList_label_selected")
                current_page_num = int(active_page_el.inner_text().strip()) if active_page_el else 1
            except:
                current_page_num = 1

            logger.info(f"\n>>> [페이지] {current_page_num}페이지 수집 중...")
            
            old_first_bid_no = self._get_first_bid_no(page, row_selector)

            has_next_items = self._process_current_page(page, row_selector, search_btn_selector)
            if not has_next_items:
                break
            
            # 페이지 이동 로직
            target_next_num = current_page_num + 1
            time.sleep(1)
            
            next_num_btn = page.query_selector(f".w2pageList_ul a[title='{target_next_num}']")
            clicked_btn = None

            if next_num_btn:
                logger.info(f">>> [이동] {target_next_num} 페이지 클릭 시도")
                clicked_btn = next_num_btn
            else:
                next_arrow_btn = page.query_selector(".w2pageList_control_next a")
                if next_arrow_btn:
                    logger.info(f">>> [이동] 다음 구간(화살표) 이동 시도")
                    clicked_btn = next_arrow_btn
                else:
                    logger.info(">>> [종료] 다음 페이지 버튼 없음 (마지막 페이지)")
                    break
            
            clicked_btn.click(force=True)
            
            is_changed = self._wait_for_grid_update(page, row_selector, old_first_bid_no)
            
            if not is_changed:
                logger.info(">>> [경고] 페이지 클릭 후 데이터가 변경되지 않았습니다. (마지막이거나 통신 장애)")
                if not next_num_btn: 
                    break

    def _get_first_bid_no(self, page, row_selector):
        """현재 리스트의 첫 번째 공고번호 반환"""
        try:
            first_row = page.query_selector(row_selector)
            if first_row:
                bid_el = first_row.query_selector("td[col_id='bidPbancNum']")
                return bid_el.inner_text().strip() if bid_el else ""
        except:
            pass
        return ""

    def _wait_for_grid_update(self, page, row_selector, old_bid_no, timeout=15):
        """페이지 이동 후 그리드 내용이 바뀔 때까지 대기"""
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(0.5)
            new_bid_no = self._get_first_bid_no(page, row_selector)
            if new_bid_no and new_bid_no != old_bid_no:
                return True
        return False

    def _process_current_page(self, page, row_selector, search_btn_selector):
        """현재 페이지의 목록을 순회하며 상세 수집"""
        rows = page.query_selector_all(row_selector)
        count = len(rows)
        
        if count == 0:
            return False

        logger.info(f"   [발견] {count}건의 공고")

        for i in range(count):
            try:
                time.sleep(1)
                rows = page.query_selector_all(row_selector)
                if i >= len(rows): break
                current_row = rows[i]

                link_element = current_row.query_selector("td[col_id='bidPbancNm'] a")
                bid_no_element = current_row.query_selector("td[col_id='bidPbancNum']")
                status_element = current_row.query_selector("td[col_id='pbancSttsGridCdNm']")
                deadline_element = current_row.query_selector("td[col_id='slprRcptDdlnDt']")

                if not link_element: continue

                bid_no = bid_no_element.inner_text().strip() if bid_no_element else f"UNKNOWN-{i}"
                web_status = status_element.inner_text().strip() if status_element else ""
                bid_title = link_element.inner_text().strip()
                
                # 마감일시 체크
                if deadline_element:
                    deadline_txt = deadline_element.inner_text().strip()
                    if deadline_txt:
                        try:
                            deadline_dt = datetime.strptime(deadline_txt, "%Y/%m/%d %H:%M")
                            if deadline_dt < datetime.now():
                                logger.info(f"   [만료] 마감된 공고입니다. (마감: {deadline_txt}) -> 스킵")
                                continue
                        except ValueError:
                            pass

                # DB 상태 확인
                db_status = self.storage.get_status(bid_no)
                if db_status:
                    if db_status != web_status:
                        logger.info(f"   [변경] 상태 변경 ({db_status} -> {web_status}). DB 삭제 후 재수집: {bid_no}")
                        self.storage.delete(bid_no)
                    else:
                        logger.info(f"   [스킵] 이미 수집된 공고: {bid_no}")
                        continue

                logger.info(f"   [진입] {bid_title}")

                self._close_blocking_popups(page)
                link_element.click(force=True)
                time.sleep(3)
                
                info, files = self.extract_detail_info(page)
                
                info['입찰공고번호'] = bid_no
                info['입찰공고명'] = bid_title
                info['진행상태'] = web_status
                if files:
                    info['첨부파일_목록'] = ", ".join(files)
                
                self.print_result(info, files)
                self.storage.save(info)
                
                self._return_to_list(page, row_selector, search_btn_selector)

            except Exception as e:
                logger.info(f"   [오류] 상세 처리 실패 ({i+1}번): {e}")
                try:
                    page.go_back()
                    time.sleep(1)
                except:
                    pass
        
        return True
    
    def extract_detail_info(self, target_page):
        extracted_data = {}
        files = []
        logger.info("      [수집] 상세 정보 파싱 중...")
        try:
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
        except: pass

        try:
            file_rows = target_page.query_selector_all(".w2grid_dataLayer tbody tr")
            for row in file_rows:
                cells = row.query_selector_all("td")
                if len(cells) >= 6: 
                    fname = cells[4].inner_text().strip()
                    fsize = cells[5].inner_text().strip()
                    if fname:
                        files.append(f"{fname} ({fsize})")
        except: pass
        return extracted_data, files

    def _return_to_list(self, page, row_selector, search_btn_selector):
        """목록 버튼으로 리스트 복귀 (JS 활용, 목록 버튼만 찾음)"""
        # 1. 팝업 정리
        self._close_blocking_popups(page)
        
        time.sleep(1) # 버튼 렌더링 대기

        # 2. JS로 '눈에 보이는' 목록 버튼만 찾아서 클릭
        try:
            result = page.evaluate("""() => {
                // 오직 목록 버튼만 탐색
                const listSelectors = ["input[value='목록']", ".btn_cm.list", "a.btn_cm.list"];
                const listCandidates = document.querySelectorAll(listSelectors.join(','));
                
                for (const btn of listCandidates) {
                    // 화면에 보이고 숨겨지지 않은 버튼 확인
                    if (btn.offsetWidth > 0 && btn.offsetHeight > 0 && window.getComputedStyle(btn).visibility !== 'hidden') {
                        btn.click();
                        return "목록";
                    }
                }
                return null;
            }""")
            
            if result:
                logger.info(f"      [동작] '{result}' 버튼 클릭 완료")
            else:
                logger.info("      [오류] 클릭 가능한 '목록' 버튼을 찾을 수 없음 (검색 재실행 예정)")

        except Exception as e:
            logger.info(f"      [오류] 복귀 버튼 처리 중 에러: {e}")

        # 3. 목록 화면 복구 확인
        try:
            # 버튼 클릭 후 목록이 뜰 때까지 잠시 대기
            page.wait_for_selector(row_selector, state="visible", timeout=10000)
            logger.info("      [확인] 목록 복구됨")
        except:
            # 실패 시 검색 버튼을 눌러서 강제 복구
            logger.info("      [복구] 목록 재로딩 실패. 검색 재실행")
            self._close_blocking_popups(page)
            page.click(search_btn_selector, force=True)
            page.wait_for_selector(row_selector, state="visible", timeout=10000)

    def print_result(self, info, files):
        logger.info(f"      [결과] 필드 {len(info)}개, 파일 {len(files)}개")
        if files:
            logger.info(f"      - 첨부파일: {', '.join(files)}")