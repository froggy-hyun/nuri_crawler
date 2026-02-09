import asyncio
import time
from datetime import datetime
from playwright.async_api import async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from src.config import TARGET_URL, HEADLESS, TIMEOUT
from src.logger import get_logger
from src.storage import Storage

logger = get_logger("CRAWLER")

class NuriCrawler:
    def __init__(self):
        self.storage = Storage()

    async def _close_blocking_popups(self, page):
        """화면을 가리는 팝업/공지사항/모달 강제 삭제 (JS 실행)"""
        try:
            count = await page.evaluate("""() => {
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
                await asyncio.sleep(0.5)

        except Exception:
            pass

    async def _safe_click(self, page, selector: str, label: str, timeout: int = 5000, retries: int = 3, pre_hover_selector: str = None):
        """
        click 안정화 유틸
        - wait(attached) → scroll → visible이면 click(force)
        - 안 보이면 pre_hover_selector hover로 펼침 유도
        - 그래도 안 되면 JS click fallback
        """
        for attempt in range(retries):
            try:
                await self._close_blocking_popups(page)

                loc = page.locator(selector)
                await loc.wait_for(state="attached", timeout=timeout)

                # 먼저 보이도록 시도
                try:
                    await loc.scroll_into_view_if_needed(timeout=timeout)
                except:
                    pass

                # visible이면 클릭
                try:
                    if await loc.is_visible():
                        await loc.click(force=True, timeout=timeout)
                        return True
                except:
                    pass

                # 안 보이면 hover로 메뉴 펼침 유도 후 재시도
                if pre_hover_selector:
                    try:
                        await page.hover(pre_hover_selector)
                        await asyncio.sleep(0.3)
                        if await loc.is_visible():
                            await loc.click(force=True, timeout=timeout)
                            return True
                    except:
                        pass

                # JS click fallback
                try:
                    clicked = await page.evaluate("""(sel) => {
                        const el = document.querySelector(sel);
                        if (!el) return false;
                        el.scrollIntoView({block: 'center', inline: 'center'});
                        el.click();
                        return true;
                    }""", selector)

                    if clicked:
                        await asyncio.sleep(0.3)
                        return True
                except:
                    pass

            except PlaywrightTimeoutError:
                logger.info(f"   [주의] '{label}' 요소 대기 시간 초과 (시도 {attempt+1}/{retries})")
            except Exception as e:
                logger.info(f"   [주의] '{label}' 클릭 실패 (시도 {attempt+1}/{retries}): {e}")

            await asyncio.sleep(0.5)

        logger.info(f"   [오류] '{label}' 클릭 최종 실패: {selector}")
        return False

    async def run(self):
        start_time = time.time()
        self.storage.clean_old_data()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=HEADLESS, slow_mo=100)

            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )

            page = await context.new_page()

            try:
                await self._crawl_process(page)
            except Exception as e:
                logger.info(f"!!! 크롤링 중단: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.storage.close()
                await browser.close()

        duration = time.time() - start_time
        logger.info(f"== 크롤링 완료 (소요시간: {duration:.2f}초) ==")

    async def _crawl_process(self, page):
        logger.info(">>> [메인] 누리장터 접속")
        await page.goto(TARGET_URL, timeout=TIMEOUT)
        await page.wait_for_load_state("networkidle")

        await self._close_blocking_popups(page)

        # [메뉴] 입찰공고 이동 (Depth1)
        menu1_selector = "#mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_btn_menuLvl1"
        logger.info(">>> [메뉴] 입찰공고 이동")

        ok = await self._safe_click(page, menu1_selector, "입찰공고(Depth1)", timeout=10000, retries=4)
        if not ok:
            raise Exception("입찰공고(Depth1) 메뉴 클릭 실패")

        await asyncio.sleep(1.0)  # 메뉴 펼쳐짐 대기

        # Depth2가 있다면 먼저 펼침 시도 (없으면 무시)
        menu2_selector = "#mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_btn_menuLvl2"
        try:
            if await page.locator(menu2_selector).count() > 0:
                logger.info(">>> [메뉴] (보조) Depth2 펼침 시도")
                await self._safe_click(
                    page,
                    menu2_selector,
                    "입찰공고(Depth2)",
                    timeout=5000,
                    retries=2,
                    pre_hover_selector=menu1_selector
                )
                await asyncio.sleep(0.5)
        except:
            pass

        # [메뉴] 입찰공고목록 이동 (Depth3)
        menu3_selector = "#mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_genDepth3_0_btn_menuLvl3"
        logger.info(">>> [메뉴] 입찰공고목록 이동")

        ok = await self._safe_click(
            page,
            menu3_selector,
            "입찰공고목록(Depth3)",
            timeout=7000,
            retries=4,
            pre_hover_selector=menu1_selector
        )
        if not ok:
            raise Exception("입찰공고목록(Depth3) 메뉴 클릭 실패")

        # 2. 필터 설정
        search_btn_selector = "#mf_wfm_container_btnS0001"
        await page.wait_for_selector(search_btn_selector, state="visible", timeout=TIMEOUT)

        try:
            logger.info(">>> [필터] '입찰개시' 상태 선택")
            await page.select_option("#mf_wfm_container_sbxPrgrsStts", label="입찰개시")
        except Exception as e:
            logger.info(f"   [주의] 필터 설정 실패: {e}")

        # 3. 검색 수행
        logger.info(">>> [목록] 검색 수행")
        await self._close_blocking_popups(page)
        await page.click(search_btn_selector, force=True)

        row_selector = "#mf_wfm_container_grdBidPbancList_body_tbody tr.grid_body_row"
        await page.wait_for_selector(row_selector, state="attached", timeout=TIMEOUT)
        await asyncio.sleep(2)

        try:
            total_cnt_selector = "#mf_wfm_container_tbxTotCnt"
            if await page.is_visible(total_cnt_selector):
                total_count = (await page.inner_text(total_cnt_selector)).strip()
                logger.info(f">>> [정보] 전체 조회 결과: Total {total_count} 건")
        except:
            pass

        # 4. 페이지네이션 순회
        while True:
            await self._close_blocking_popups(page)

            try:
                active_page_el = await page.query_selector(".w2pageList_label_selected")
                current_page_num = int((await active_page_el.inner_text()).strip()) if active_page_el else 1
            except:
                current_page_num = 1

            logger.info(f"\n>>> [페이지] {current_page_num}페이지 수집 중...")

            old_first_bid_no = await self._get_first_bid_no(page, row_selector)

            has_next_items = await self._process_current_page(page, row_selector, search_btn_selector)
            if not has_next_items:
                break

            # 페이지 이동 로직
            target_next_num = current_page_num + 1
            await asyncio.sleep(1)

            next_num_btn = await page.query_selector(f".w2pageList_ul a[title='{target_next_num}']")
            clicked_btn = None

            if next_num_btn:
                logger.info(f">>> [이동] {target_next_num} 페이지 클릭 시도")
                clicked_btn = next_num_btn
            else:
                next_arrow_btn = await page.query_selector(".w2pageList_control_next a")
                if next_arrow_btn:
                    logger.info(">>> [이동] 다음 구간(화살표) 이동 시도")
                    clicked_btn = next_arrow_btn
                else:
                    logger.info(">>> [종료] 다음 페이지 버튼 없음 (마지막 페이지)")
                    break

            await clicked_btn.click(force=True)

            is_changed = await self._wait_for_grid_update(page, row_selector, old_first_bid_no)

            if not is_changed:
                logger.info(">>> [경고] 페이지 클릭 후 데이터가 변경되지 않았습니다. (마지막이거나 통신 장애)")
                if not next_num_btn:
                    logger.info(">>> [완료] 모든 데이터 탐색 완료")
                    break

    async def _get_first_bid_no(self, page, row_selector):
        """현재 리스트의 첫 번째 공고번호 반환"""
        try:
            first_row = await page.query_selector(row_selector)
            if first_row:
                bid_el = await first_row.query_selector("td[col_id='bidPbancNum']")
                return (await bid_el.inner_text()).strip() if bid_el else ""
        except:
            pass
        return ""

    async def _wait_for_grid_update(self, page, row_selector, old_bid_no, timeout=15):
        """페이지 이동 후 그리드 내용이 바뀔 때까지 대기"""
        start = time.time()
        while time.time() - start < timeout:
            await asyncio.sleep(0.5)
            new_bid_no = await self._get_first_bid_no(page, row_selector)
            if new_bid_no and new_bid_no != old_bid_no:
                return True
        return False

    async def _process_current_page(self, page, row_selector, search_btn_selector):
        """현재 페이지의 목록을 순회하며 상세 수집"""
        rows = await page.query_selector_all(row_selector)
        count = len(rows)

        if count == 0:
            return False

        logger.info(f"   [발견] {count}건의 공고")

        for i in range(count):
            try:
                await asyncio.sleep(1)

                rows = await page.query_selector_all(row_selector)
                if i >= len(rows):
                    break

                current_row = rows[i]

                link_element = await current_row.query_selector("td[col_id='bidPbancNm'] a")
                bid_no_element = await current_row.query_selector("td[col_id='bidPbancNum']")
                status_element = await current_row.query_selector("td[col_id='pbancSttsGridCdNm']")
                deadline_element = await current_row.query_selector("td[col_id='slprRcptDdlnDt']")

                if not link_element:
                    continue

                bid_no = (await bid_no_element.inner_text()).strip() if bid_no_element else f"UNKNOWN-{i}"
                web_status = (await status_element.inner_text()).strip() if status_element else ""
                bid_title = (await link_element.inner_text()).strip()

                deadline_txt = ""
                deadline_dt = None

                # 마감일시 체크
                if deadline_element:
                    deadline_txt = (await deadline_element.inner_text()).strip()
                    if deadline_txt:
                        try:
                            deadline_dt = datetime.strptime(deadline_txt, "%Y/%m/%d %H:%M")
                        except ValueError:
                            deadline_dt = None

                # 1) 목록 기준 만료 공고 스킵
                if deadline_dt and deadline_dt <= datetime.now():
                    logger.info(f"   [만료] 마감된 공고입니다. (마감: {deadline_txt}) -> 스킵")
                    continue

                # 2) DB 메타 확인 (status, end_date)
                db_status, db_end_date = self.storage.get_meta(bid_no)
                db_end_date = (db_end_date or "").strip()

                # 2-1) 상태 변경이면: 삭제만 하고 재수집(상세 진입) 안 함
                if db_status and db_status != web_status:
                    logger.info(f"   [변경] 상태 변경 ({db_status} -> {web_status}). DB 삭제(재수집 없음): {bid_no}")
                    self.storage.delete(bid_no)
                    continue

                # 2-2) DB end_date가 비어있고, 목록에서 deadline이 새로 확인되면 동기화
                if db_status and not db_end_date and deadline_dt:
                    if deadline_dt <= datetime.now():
                        logger.info(f"   [정리] DB 마감일시 공백 + 웹 마감일시 만료({deadline_txt}) -> DB 삭제: {bid_no}")
                        self.storage.delete(bid_no)
                        continue
                    else:
                        logger.info(f"   [갱신] DB 마감일시 공백 + 웹 마감일시 신규({deadline_txt}) -> end_date 업데이트: {bid_no}")
                        self.storage.update_end_date(bid_no, deadline_txt)
                        continue

                # 2-3) 이미 수집된 공고(상태 동일)면 스킵
                if db_status:
                    logger.info(f"   [스킵] 이미 수집된 공고: {bid_no}")
                    continue

                # 3) 신규 공고만 상세 진입/수집
                logger.info(f"   [진입] {bid_title}")

                await self._close_blocking_popups(page)
                await link_element.click(force=True)
                await asyncio.sleep(3)

                info, files = await self.extract_detail_info(page)

                info['입찰공고번호'] = bid_no
                info['입찰공고명'] = bid_title
                info['진행상태'] = web_status
                if files:
                    info['첨부파일_목록'] = ", ".join(files)

                self.print_result(info, files)
                self.storage.save(info)

                await self._return_to_list(page, row_selector, search_btn_selector)

            except Exception as e:
                logger.info(f"   [오류] 상세 처리 실패 ({i+1}번): {e}")
                try:
                    await self._return_to_list(page, row_selector, search_btn_selector)
                except:
                    pass

        return True

    async def extract_detail_info(self, target_page):
        """상세 페이지 데이터 추출 (비동기)"""
        extracted_data = {}
        files = []
        logger.info("      [수집] 상세 정보 파싱 중...")

        try:
            await target_page.wait_for_selector("table.w2tb", state="visible", timeout=5000)
            tables = await target_page.query_selector_all("table.w2tb")

            for tbl in tables:
                rows = await tbl.query_selector_all("tbody tr")
                for row in rows:
                    ths = await row.query_selector_all("th")
                    tds = await row.query_selector_all("td")
                    count = min(len(ths), len(tds))
                    for i in range(count):
                        key = (await ths[i].inner_text()).strip().replace("\n", " ").replace("\r", "")
                        val = (await tds[i].inner_text()).strip().replace("\n", " ").replace("\r", "")
                        if key and key not in extracted_data:
                            extracted_data[key] = val
        except:
            pass

        try:
            file_rows = await target_page.query_selector_all(".w2grid_dataLayer tbody tr")
            for row in file_rows:
                cells = await row.query_selector_all("td")
                if len(cells) >= 6:
                    fname = (await cells[4].inner_text()).strip()
                    fsize = (await cells[5].inner_text()).strip()
                    if fname:
                        files.append(f"{fname} ({fsize})")
        except:
            pass

        return extracted_data, files

    async def _return_to_list(self, page, row_selector, search_btn_selector):
        """목록 버튼으로 리스트 복귀 (JS 활용, 목록 버튼만 찾음)"""
        await self._close_blocking_popups(page)
        await asyncio.sleep(1)

        # JS로 '눈에 보이는' 목록 버튼만 찾아서 클릭
        try:
            result = await page.evaluate("""() => {
                const listSelectors = ["input[value='목록']", ".btn_cm.list", "a.btn_cm.list"];
                const listCandidates = document.querySelectorAll(listSelectors.join(','));

                for (const btn of listCandidates) {
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

        # 목록 화면 복구 확인
        try:
            await page.wait_for_selector(row_selector, state="visible", timeout=10000)
            logger.info("      [확인] 목록 복구됨")
        except:
            logger.info("      [복구] 목록 재로딩 실패. 검색 재실행")
            await self._close_blocking_popups(page)
            await page.click(search_btn_selector, force=True)
            await page.wait_for_selector(row_selector, state="visible", timeout=10000)

    def print_result(self, info, files):
        logger.info(f"      [결과] 필드 {len(info)}개, 파일 {len(files)}개")
        if files:
            logger.info(f"      - 첨부파일: {', '.join(files)}")