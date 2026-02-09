# Nuri Marketplace Bid Crawler

누리장터(Nuri Marketplace)의 입찰 공고를 자동으로 수집하여 데이터베이스에 저장하는 크롤러입니다.  
현재 **'입찰 개시'** 상태이면서 **만료되지 않은 공고**를 **최근 1달 범위**로 최신화하여 사용자가 **응찰할 수 있는 데이터**만 유지합니다.
<br><br>

## 주요 기능 (Key Features)

- **응찰 가능한 공고만 유지**
    - '입찰개시' 상태 공고 중 **마감되지 않은 공고**만 db에 남기도록 자동으로 정리합니다.

- **중복 저장 방지**
    - 이미 저장된 공고는 다시 저장하지 않아 데이터가 깔끔하게 유지됩니다.

- **상태가 바뀐 공고 자동 정리**
    - 저장된 공고의 **진행상태가 변경되면 기존 레코드를 삭제**하여 응찰할 수 없는 데이터를 삭제합니다.

- **데이터 최신화**
    - 저장된 데이터 중 오래된 항목(수집 후 31일 초과)은 자동으로 정리됩니다.
    - 마감일시가 확인된 공고는 **마감 시각이 지난 경우 자동으로 삭제**됩니다.

- **마감일시 누락 데이터 자동 보정**
    - DB에 마감일시가 비어있던 공고가 목록에서 마감일시가 새로 확인되면:
        - 마감일시가 **오늘/과거**면 DB에서 삭제(이미 만료)
        - 마감일시가 **미래**면 DB의 마감일시와 저장 데이터(원본 데이터)도 함께 보정 업데이트합니다.

- **불필요한 수집 최소화**
    - 아래 항목은 상세 페이지에 들어가지 않고 건너뜁니다.
        - 마감된 공고(목록에서 마감일시 기준)
        - 이미 DB에 존재하고 진행상태가 동일한 공고
        - 목록에서 상세 링크를 찾을 수 없는 공고

- **오류가 나도 계속 진행**
    - 일부 공고 처리 중 문제가 발생해도 전체 작업이 멈추지 않고 다음 공고로 넘어갑니다.
    - 상세 화면에서 목록으로 복귀가 실패하면, 목록을 복구한 뒤 계속 진행합니다.

- **로그 기록**
    - 실행 과정/오류/정리 내역을 로그로 남겨 추적할 수 있습니다.

- **실행 모드 지원(운영 관점)**
  - **single**: 1회 실행 후 종료
  - **interval**: N분 간격으로 반복 실행
  - **cron**: 매일 지정된 시각(HH:MM) 실행(여러 시각 지원)
  - **export**: DB 데이터를 JSON으로 내보내기
<br><br>

## 디렉터리 구조 및 파일 역할

```text
.
├─ main.py                  # 실행 진입점: 모드(single/interval/cron/export) 처리, 스케줄러 구동
├─ README.md
├─ requirements.txt
└─ src/
   ├─ config.py             # 설정값(TARGET_URL/HEADLESS/TIMEOUT/DB_PATH, data/logs 디렉터리 생성)
   ├─ crawler.py            # 크롤링 로직(Playwright 비동기): 메뉴 이동, 목록/상세 수집, 페이지네이션, 복구 루틴
   ├─ storage.py            # SQLite 저장/조회/정리, end_date 동기화 보정(update_end_date)
   └─ logger.py             # 콘솔 + 회전 파일 로그(crawler.log) 로거 생성
```
<br><br>

## 요구 사항 (Requirements)

- **Python**: 3.9.6 이상
- **라이브러리**
  - `playwright==1.58.0`
  - `schedule==1.2.2`
<br><br>

## 설치 (Installation)

1. 패키지 설치
   ```bash
   pip install -r requirements.txt
    ```
2.  Playwright 브라우저 설치
    ```bash
    playwright install chromium
    ```
<br><br>

## 실행 방법 (Usage)

이 프로젝트는 `main.py`를 통해 실행하며, 4가지 모드(single/interval/cron/export)를 지원합니다.

### 1. 단일 실행 (Single Mode)  
스크립트를 1회 실행하고 즉시 종료합니다. 테스트용이나 수동 실행 시 사용합니다.
```bash
# 기본값은 single입니다
python main.py

# 또는 명시적으로
python main.py --mode single
```

### 2. 주기적 반복 실행 (Interval Mode)  
지정된 분(Minute) 간격으로 크롤링을 무한 반복합니다.

```bash
# 30분마다 실행
python main.py --mode interval --value 30

# 60분(1시간)마다 실행
python main.py --mode interval --value 60
```

### 3. 정해진 시간 실행 (Cron Mode)  
매일 정해진 시간(HH:MM)에 크롤링을 수행합니다. 여러 시간을 콤마(,)로 구분하여 지정할 수 있습니다.

```bash
# 매일 오전 9시에 실행
python main.py --mode cron --value "09:00"

# 매일 오전 9시와 오후 6시에 실행
python main.py --mode cron --value "09:00,18:00"
```

### 4. 데이터 추출 (Export Mode)  
현재 데이터베이스에 저장된 모든 데이터를 JSON 파일로 내보냅니다.  
파일명은 YYYYMMDD_HHMMSS_nuri_bids.json 형식으로 생성됩니다.

```bash
python main.py --mode export
```
<br><br>

## 설계 및 기술적 특징

### 가정 및 설계 (Assumptions & Design)

- **수집 범위: 최근 1달 내 데이터 최신화**
  - DB 정리 로직에서 “마감일이 지났거나 수집 후 1달이 지난 데이터”를 삭제하여 최신 상태를 유지합니다.
  - **검색 범위를 1달로 잡은 이유**: 누리장터 입찰 공고는 **공고게시일시부터 입찰마감일시까지 기간이 대부분 1달 이내**인 경우가 많아, 운영 관점에서 데이터 최신성을 유지하면서도 불필요한 장기 데이터 축적을 줄이기 위함입니다.

- **오류로 인한 중단 후 재실행 시 빠른 수집**
  - 본 구현은 체크포인트 대신, **DB 중복 방지(PK 기반 스킵)**를 핵심 전략으로 사용합니다.
  - 크롤링 도중 오류로 중단되어 재실행하더라도, **이미 DB에 저장된 공고는 즉시 건너뛰므로** 빠르게 기존 진행 지점까지 재도달합니다.
  - 즉, 재개 기능을 별도로 복잡하게 만들기보다, **반복 실행해도 결과가 안정적인 수집 구조**를 우선한 설계입니다.

- **SPA 특성 반영**
  - 누리장터는 SPA 성격이 강하므로, 단순한 URL 기반 페이지 이동보다 **메뉴 클릭/검색 버튼/그리드 갱신 감지** 등 UI 이벤트 중심으로 흐름을 구성합니다.

- **안정성 우선**
  - “최대 속도”보다 “중단 없이 오래 도는 운영 안정성”을 우선합니다.
  - 팝업 제거, 목록 복귀 실패 시 검색 재실행, DOM 갱신 재획득 등 **현장 노이즈를 전제로 한 복구 루틴**을 포함합니다.

### 기술적 특징 (Technical Highlights)

- **Playwright 기반 SPA 크롤링(비동기)**
  - `playwright.async_api`(async_playwright)를 사용합니다.
  - 메뉴(Depth1/2/3) 이동은 사이트 상태에 따라 숨김/접힘이 발생할 수 있어 `_safe_click()` 유틸로 안정화합니다.

- **클릭 안정화 유틸(_safe_click)**
  - wait(attached) → scroll_into_view → visible이면 click(force)
  - 필요 시 hover(pre_hover_selector)로 메뉴 펼침 유도
  - 최종 fallback으로 JS click 수행
  - `TimeoutError as PlaywrightTimeoutError`를 별도로 처리하여 재시도 로그를 남깁니다.

- **대기 전략**
  - `wait_for_load_state("networkidle")`: 초기 로딩 안정화
  - `wait_for_selector(..., state="visible"/"attached")`: 필수 DOM 렌더링 확인
  - `_wait_for_grid_update`: 페이지 이동 후 데이터가 실제 바뀌었는지 첫 번째 공고번호를 비교해서 확인

- **DOM 갱신/핸들 무효화 대응**
  - 목록 순회 중 DOM이 업데이트되면 기존 ElementHandle이 무효화될 수 있어, **루프마다 rows를 재획득**합니다.

- **수집/스킵 정책(목록 기반)**
  - 목록의 `slprRcptDdlnDt`(입찰서접수마감일시)를 `YYYY/MM/DD HH:MM`로 파싱합니다.
  - 파싱 성공 + 현재 시각 이하(오늘/과거)면 만료로 판단하여 스킵합니다.
  - 목록 행에 상세 링크(`td[col_id='bidPbancNm'] a`)가 없으면 스킵합니다.

- **DB 기반 중복 방지 및 변경/보정 처리**
  - bids 테이블에서 `bid_no`를 PK로 사용합니다.
  - DB 메타 조회는 `Storage.get_meta(bid_no)`로 (status, end_date)를 함께 확인합니다.
  - `status`(진행상태) 변경 감지 시: **레코드 삭제 후 재수집하지 않고 continue**(코드 기준 동작).
  - DB에 이미 저장되어 있고 status 동일이면 스킵합니다.
  - DB `end_date`가 비어 있고, 목록에서 마감일시가 새로 확인되면:
    - 마감일시가 오늘/과거: 레코드 삭제
    - 마감일시가 미래: `Storage.update_end_date()`로 `end_date` 및 `raw_data["입찰서접수마감일시"]` 보정 업데이트(상세 재수집 없이)

- **DB 자동 정리(clean_old_data)**
  - 실행 시작 시 `Storage.clean_old_data()` 수행
  - 삭제 조건(코드 기준):
    - `end_date < now` AND `end_date != ''` AND `end_date IS NOT NULL`
    - OR `collected_at < (now - 31일)`

- **장애 복구**
  - 상세 처리 오류 시 전체 중단 대신 다음 항목으로 진행합니다.
  - 목록 복귀 실패 시 “목록 버튼 클릭 → 실패 시 검색 재실행 → 리스트 다시 로딩”의 복구 루틴을 사용합니다.

- **운영 모드(스케줄)**
  - `schedule` 라이브러리로 interval/cron 모드를 구성하고, 각 작업은 `asyncio.run()`으로 격리 실행합니다.
  - export 모드로 DB 데이터를 JSON으로 내보낼 수 있어, 후속 처리/분석 파이프라인 연계가 쉽습니다.

- **로깅**
  - 콘솔: 메시지 중심 출력
  - 파일: `logs/crawler.log`에 RotatingFileHandler(최대 10MB, 백업 5개)
<br><br>

## 한계 및 개선 아이디어 (Limitations & Future Work)
### 탐지 회피 고도화
- **브라우저 지문(Fingerprint) 위조**: 현재는 기본적인 User-Agent만 설정되어 있습니다. 추후 `playwright-stealth` 플러그인을 도입하여 `navigator.webdriver` 속성을 숨기고, Canvas/WebGL 지문을 일반 브라우저처럼 위장해야 합니다.
- **프록시 로테이션**: 단일 IP에서 지속적인 요청 시 WAF(웹 방화벽)에 의해 차단될 수 있습니다. 이를 방지하기 위해 주거용 프록시(Residential Proxy) 풀을 연동하여 매 요청 또는 세션마다 IP를 교체하는 로직이 필요합니다.