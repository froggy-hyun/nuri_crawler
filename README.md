# Nuri Marketplace Bid Crawler

누리장터(Nuri Marketplace)의 입찰 공고를 자동으로 수집하여 데이터베이스에 저장하는 크롤러입니다.
현재 '입찰 개시' 상태인 공고를 1달 이내 범위로 최신화해줍니다.

## 요구 사항 (Requirements)

* Python 3.9.6
* playwright==1.58.0
* schedule==1.2.2

## 설치 (Installation)

1.  패키지 설치
    ```bash
    pip install -r requirements.txt
    ```
2.  Playwright 브라우저 설치
    ```bash
    playwright install chromium
    ```

## 실행 방법 (Usage)

이 프로젝트는 `main.py`를 통해 실행하며, 3가지 모드를 지원합니다.

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