# 원천 데이터 출처 (provenance ledger)

> 이 프로젝트가 받아온 **모든 입력 데이터의 출처·수집 방법·일자·라이선스** 기록.
> 재현·인용·보고서 출처표시용. (파생 피처 설명은 `../features/README.md`, Y 가격은 `../README.md`)

## 한눈에

| # | 데이터 | 용도 | 출처기관 | 포털/API | 수집방법 | 수집일 | 형식·키 |
|---|---|---|---|---|---|---|---|
| 1 | 버스 정류장별 승하차 인원 | 피처 1-A,B | 서울특별시 | 열린데이터광장 OA-12912 | 월별 CSV 다운로드(로그인X) | 2026-05-31 | cp949 / ARS |
| 2 | 버스정류소 위치(좌표 마스터) | 좌표·Y매칭 | 서울특별시 | 열린데이터광장 OA-15067 | xlsx 다운로드 | 2026-05-06 | xlsx / ARS_ID |
| 3 | 개별공시지가 | 피처 2 | 국토교통부 | V-World 데이터 API | 좌표 point 질의(인증키) | 2026-05-31 | JSON / 좌표 |
| 4 | 상가(상권)정보 | 피처 3(POI) | 소상공인시장진흥공단 | 공공데이터포털 15083033 | 전국 ZIP→서울만 이동 | 2026-05-31 | UTF-8 / 경위도 |
| 5 | 카카오 로컬(장소) | 피처 3 보강·검증 | 카카오 | Kakao Local API | 인증키 호출 | 2026-05-31 | JSON / 좌표 |
| 6 | 광고가(Y) | 타깃 Y | 덕플레이스 | dukplace.com | 브라우저 fetch | 2026-05-31 | → `../README.md` |
| 7 | 3도심 좌표 | 피처 5 | (2030 서울도시기본계획) | 하드코딩 | 스크립트 내 상수 | — | 시청·강남·여의도 |
| 8 | 지하철 역 좌표·승하차 | 피처 1-C | 서울특별시 | 열린데이터광장 API(OA-21232·OA-12914) | 인증키 호출 | 2026-05-31 | JSON / 역명·좌표 |
| 9 | 도로망(OSM) | 피처 4·6 | OpenStreetMap | Overpass(osmnx) | bbox+버퍼 1회 fetch | 2026-05-31 | graphml / 좌표 |

---

## raw/ 폴더의 다운로드 파일

### 1. `BUS_STATION_BOARDING_MONTH_202603.csv`, `_202604.csv`
- **데이터셋**: 서울시 버스노선별 정류장별 승하차 인원 정보 (OA-12912)
- **출처**: 서울 열린데이터광장 — https://data.seoul.go.kr/dataList/OA-12912/F/1/datasetView.do
- **받은 법**: [파일] 탭에서 월별 CSV 직접 다운로드(로그인 불필요). 2026년 3·4월분.
- **인코딩**: cp949 · **조인 키**: `버스정류장ARS번호`(4자리는 zfill(5)) · 각 ~125만 행.
- **갱신**: 매일 3일전 데이터 적재, File은 월별 과거분 제공.

### 4. `소상공인_상가_서울_202603.csv`
- **데이터셋**: 소상공인시장진흥공단_상가(상권)정보 (기준일 20260331, **서울** 시도파일)
- **출처**: 공공데이터포털 — https://www.data.go.kr/data/15083033/fileData.do (제공: 소상공인시장진흥공단)
- **받은 법**: 전국 ZIP 다운로드(로그인 불필요) → 압축해제 → **서울 시도파일만** 프로젝트로 이동(나머지 16개 시도·세종은 미사용).
- **원본 파일명**: `소상공인시장진흥공단_상가(상권)정보_서울_202603.csv` → 리네임.
- **인코딩**: UTF-8 · **537,489 업소** · 39컬럼.
- **핵심 컬럼**: `경도`,`위도`,`상권업종대분류명`(10종)/`중분류명`(75)/`소분류명`(247),`시군구명`,`행정동명`,`지번주소`.

> 좌표 마스터 `서울시버스정류소위치정보(20260506).xlsx`(OA-15067)는 `data/seoul/`에 위치 — Y매칭·좌표 출처. https://data.seoul.go.kr/dataList/OA-15067/S/1/datasetView.do

### 9. `osm_seoul_drive.graphml`
- **데이터셋**: OpenStreetMap 도로망(drive 네트워크) — 서울 정류장 bbox(126.78~127.19E · 37.42~37.71N) + ~2km 버퍼.
- **출처**: © OpenStreetMap contributors — https://www.openstreetmap.org (osmnx 2.1 Overpass API).
- **받은 법**: `scripts/build_road_feature.py`가 `ox.graph_from_polygon(..., network_type="drive")`로 **1회 fetch** → graphml 캐시(노드 86,397 · 무방향엣지 130,023 · 총연장 11,979km · 간선 3,834km). 정류장마다 재fetch 안 함(Overpass 부하 방지). 이후 실행은 캐시 재사용.
- **라이선스**: **ODbL**(Open Database License) — 출처표시 + 동일조건변경허락(share-alike). 보고서·산출물에 "© OpenStreetMap contributors" 명시.

---

## API로 수집(raw 파일 없음)

### 3. 개별공시지가 — V-World 데이터 API
- **엔드포인트**: `https://api.vworld.kr/req/data` (service=data, `data=LP_PA_CBND_BUBUN` 연속지적도)
- **출처**: 국토교통부 공간정보 오픈플랫폼(V-World) — https://www.vworld.kr
- **인증**: 인증키(회원가입 발급). `.env`의 `V_WORLD_DEVELOPER_KEY`로만 사용(코드 하드코딩·커밋 금지).
- **수집**: 정류장 좌표마다 point 질의 → 속성 `jiga`(원/㎡) 직접 취득. 2,553곳, 2026-05-31.
- 스크립트: `scripts/build_jiga_feature.py`

### 5. 카카오 로컬 API (POI 보강·검증)
- **엔드포인트**: `https://dapi.kakao.com/v2/local/search/category.json` 등
- **출처**: Kakao Developers — https://developers.kakao.com (제품: 카카오맵)
- **인증**: REST 키. `.env`의 `KAKAO_DEVELOPER_PLATFORM_KEY`. (상권 밀도 주력은 #4 소상공인, 카카오는 지하철역·대형마트 등 앵커 보강 후보.)

### 8. 지하철 역 좌표 + 역 승하차 — 서울 열린데이터광장 API
- **엔드포인트**: `http://openapi.seoul.go.kr:8088/{KEY}/json/subwayStationMaster/...`(역 좌표 783개) + `.../CardSubwayStatsNew/.../{YYYYMMDD}/`(역별 일별 승하차).
- **출처**: 서울 열린데이터광장 — 역사마스터 **OA-21232** / 지하철 승하차 **OA-12914**. (좌표는 파일 다운로드 미제공 → API.)
- **인증**: 인증키. `.env`의 `SEOUL_OPENAPI_KEY`. 2026-05-31, 3~4월 61일분.
- 스크립트: `scripts/build_subway_feature.py`

---

## 라이선스·인용 메모(보고서용)
- 열린데이터광장·공공데이터포털·V-World: 대체로 **출처표시** 조건 자유이용. 보고서에 기관·데이터셋명·기준일 명시.
- 카카오 로컬: 카카오 약관 준수, 출처표시.
- OpenStreetMap: **ODbL** — "© OpenStreetMap contributors" 출처표시 필수, 파생 DB는 동일조건(share-alike).
- 광고가(덕플레이스): 호가일 수 있음(실거래가 아님) — 한계 명시. 상세 `../README.md`.
