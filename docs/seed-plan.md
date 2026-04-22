# SURI 합성 데이터 생성 — 확정된 설계

## 파일 구조
data/seed/
├── __init__.py
├── config.py      # 분포·파라미터
├── generators.py  # baseline 생성 (이상 패턴 없음)
├── anomalies.py   # 이상 패턴 overlay (2단계)
├── checks.py      # 로드 후 자동 검증 SQL
└── load.py        # DB I/O: TRUNCATE → COPY → ANALYZE → 권한 재검증

## 분포 (Perplexity 기준)
- 채널: 방카 50 / 전속 20 / GA 20 / TM 7 / CM 3
- 상품유형: 보장성 65 / 저축성 25 / 변액 10
- 납입주기: 월납 85 / 연납 5 / 일시납 10
- 연령: 20대 7 / 30대 25 / 40대 30 / 50대 28 / 60대+ 10

## 이상 패턴 (GA subset에 주입)
1. GA 채널 13·25회차 유지율 낙차 (KIRI 기준 19%p)
2. 3월 절판 스파이크 (평월 × 1.8)
3. 특정 product_id 25회차 이상치 (교보생명 2023 사례)

## PII 포맷 (DLP 오탐 방지)
- 주민번호: `RRN-XXXXXX` (컬럼명: resident_id_dummy)
- 전화: `010-99XX-XXXX` (미할당 대역)
- 이메일: `@example.com` (IANA 예약)
- 주소: 시도 + 시군구만

## 상품-연령 정합성
- 건강: 25-70, 종신: 30-55, 연금: 40-65, 저축: 30-60, 정기: 30-55

## 성능
- psycopg 3 `cursor.copy()` + COPY FROM STDIN
- 로드 후 ANALYZE
- TRUNCATE RESTART IDENTITY CASCADE

## 유보 (Future Work)
- customer_id UUID 해시화
- CLI 플래그 (--dry-run, --small-sample)
- 37회차 유지율 anomaly
- surrendered/matured 상태 추가
