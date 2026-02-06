from playwright.sync_api import sync_playwright
import time
import random

def extract_detail_info(target_page):
    """상세 페이지 데이터 추출"""
    extracted_data = {}
    files = []
    
    print("      [수집] 상세 정보 파싱 중...")
    
    try:
        # 테이블 데이터 로딩 대기
        target_page.wait_for_selector("table.w2tb", state="visible", timeout=10000)
        
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

def print_result(info, files):
    """결과 출력"""
    print(f"      [결과] 필드 {len(info)}개, 파일 {len(files)}개")
    for k, v in info.items():
        print(f"      - {k}: {v}")
    
    if files:
        print(f"      - 첨부파일: {', '.join(files)}")

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        
        try:
            # 1. 페이지 이동 및 메뉴 진입
            print(">>> [메인] 누리장터 접속")
            page.goto("https://nuri.g2b.go.kr/", timeout=60000)
            page.wait_for_load_state("networkidle")

            print(">>> [메뉴] 입찰공고 이동")
            page.click("#mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_btn_menuLvl1")
            time.sleep(0.5)
            
            print(">>> [메뉴] 입찰공고목록 이동")
            page.click("#mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_genDepth3_0_btn_menuLvl3")
            
            search_btn_selector = "#mf_wfm_container_btnS0001"
            page.wait_for_selector(search_btn_selector, state="visible", timeout=20000)
            
            # 2. 검색 및 목록 대기
            print(">>> [목록] 검색 수행")
            page.click(search_btn_selector)
            
            row_selector = "#mf_wfm_container_grdBidPbancList_body_tbody tr.grid_body_row"
            page.wait_for_selector(row_selector, state="attached", timeout=20000)
            time.sleep(2) 

            # 3. 목록 순회
            rows = page.query_selector_all(row_selector)
            count = len(rows)
            print(f">>> [목록] {count}건 발견. 상위 3건 수집 시작.")

            for i in range(min(3, count)):
                print(f"\n--- 항목 {i+1} 처리 ---")
                
                # DOM 갱신 대응을 위한 재조회
                current_row = page.query_selector_all(row_selector)[i]
                link_element = current_row.query_selector("td[col_id='bidPbancNm'] a")
                
                if not link_element:
                    print("   [!] 링크 없음. 건너뜀")
                    continue
                    
                bid_title = link_element.inner_text().strip()
                print(f"   [대상] {bid_title}")

                # 상세 페이지 진입 (SPA/모달)
                link_element.click()
                time.sleep(3) # 데이터 로딩 대기
                
                try:
                    # 데이터 추출
                    info, files = extract_detail_info(page)
                    print_result(info, files)
                    
                    # 목록 복귀 (닫기 또는 목록 버튼)
                    close_btn = page.query_selector("input[value='닫기'], .btn_cm.close")
                    list_btn = page.query_selector("input[value='목록'], .btn_cm.list")

                    if close_btn and close_btn.is_visible():
                        print("   [동작] '닫기' 클릭")
                        close_btn.click()
                    elif list_btn and list_btn.is_visible():
                        print("   [동작] '목록' 클릭")
                        list_btn.click()
                    else:
                        print("   [동작] 버튼 못 찾음. 뒤로가기 실행")
                        page.go_back()

                    # 목록 복구 확인 (필수)
                    try:
                        page.wait_for_selector(row_selector, state="visible", timeout=10000)
                        print("   [확인] 목록 복구됨")
                    except:
                        print("   [경고] 목록 재로딩 실패. 검색 재실행")
                        page.click(search_btn_selector)
                        page.wait_for_selector(row_selector, state="visible", timeout=10000)

                except Exception as e:
                    print(f"   [오류] 상세 처리 중 에러: {e}")
                    page.go_back()
                    time.sleep(2)

        except Exception as e:
            print(f"!!! 치명적 오류: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            print(">>> 브라우저 종료")
            browser.close()

if __name__ == "__main__":
    run()