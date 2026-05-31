# 서울 버스정류장 광고가 예측 — 모델 산출물

좌표(위도·경도) → 그 위치 버스정류장의 **월 광고 단가(원/면)** 예측 + 오차범위 + "왜 그 가격인가"(위치별 SHAP). 회귀 모델은 **XGBoost**(log1p 타깃), 해석은 **SHAP 2층위**.

> 학습·평가·해석 전체 맥락은 `../CLAUDE.md`. 데이터 출처 `../data/seoul/raw/README.md`, 피처 사전 `../data/seoul/features/README.md`.

---

## 1. 파일

| 파일 | 내용 |
|---|---|
| `xgb_model.joblib` | 적합된 모델(`{model, features, target, log_target}`). 전체 2,553정류장 학습. |
| `xgb_best_params.json` | RandomizedSearch 튜닝 하이퍼파라미터. |
| `error_band.json` | OOF 잔차(log) 분위 → 80% 예측구간 산출용. |
| `predict.py` | ⭐ `PricePredictor`: 좌표→예측가+오차+SHAP top-N+신뢰도. (라이브러리·CLI) |
| `feature_extractor.py` | 임의 좌표 → 32피처 재계산(빌드 스크립트 로직 재현). `predict`가 사용. |
| `grid_250m.csv` | ⭐ **격자 사전계산 테이블** 7,883칸(250m). 웹 조회용 캐시. |
| `shap_global_beeswarm.png` / `_bar.png` / `_importance.csv` | SHAP 1층위(전체 경향, 보고서용). |

---

## 2. 사용법

### (A) 격자 조회만 — 파이썬·모델 불필요
`grid_250m.csv`에서 입력 좌표에 가장 가까운 칸을 찾아 `예측가_원per면`·`하한_원`·`상한_원`·`top1~5_피처/효과%` 읽기. 가장 가벼운 인계 형태(웹팀 권장 기본).

### (B) 임의 좌표 온디맨드 예측 — 전체 스택
```python
import sys; sys.path.insert(0, 'model')
from predict import PricePredictor
p = PricePredictor()                       # 1회 로드(상가·역·도로망 인덱스)
p.predict(37.4979, 127.0276)               # 강남역
# {'예측가_원per면': 1135600, '오차범위_원': (673898, 1838911),
#  '자치구_근사': '강남구', '최근접학습정류장_m': 95,
#  'top_factors': [('거리_강남_km', 22.7), ('최근접지하철_거리_m', 15.3), ...]}
```
CLI: `uv run python model/predict.py 37.4979 127.0276`

배치(격자 재생성 등): `p.predict_batch(lats, lons, top_n=5)` → DataFrame.

---

## 3. 격자 테이블 스키마 (`grid_250m.csv`, 18열)

| 열 | 의미 |
|---|---|
| `위도`, `경도` | 칸 중심 좌표 |
| `자치구_근사` | 최근접 학습정류장의 자치구(좌표→구 근사) |
| `예측가_원per면` | 예측 광고 단가(원/면) |
| `하한_원`, `상한_원` | 80% 예측구간(예측가 대비 ×0.59 ~ ×1.62) |
| `최근접학습정류장_m` | 가장 가까운 학습정류장 거리 = **외삽 정도** |
| `신뢰도` | 상(<250m) / 중(<700m) / 하(≥700m) |
| `top1~5_피처`, `top1~5_효과%` | 위치별 SHAP top5(2층위). 효과%=가격 배수효과(+면 상승, −면 하락) |

격자: 마스터 정류소(11,250) **400m 이내 칸만** 7,883개. 강·산 등 정류장 없는 곳은 제외.

---

## 4. 성능 (5-fold CV, 원 단위)

| split | 모델 | MAE | RMSE | MAPE | R² |
|---|---|--:|--:|--:|--:|
| 무작위 KFold | Dummy → Linear → RF → **XGB(튜닝)** | 296k→229k→196k→**192k** | … | 59%→…→**33.1%** | -0.05→0.42→0.56→**0.58** |
| 자치구 GroupKFold | **XGB(튜닝)** | **234k** | 332k | **39.9%** | **0.32** |

- **무작위 R² 0.58 ↔ 자치구 0.32**: 본 적 있는 지역 보간은 잘하나, **학습에 없던 구 일반화는 어려움**(외곽·희소지역 신뢰도 한계 = `신뢰도` 열로 표시).
- 튜닝 개선폭 미미 → 한계는 하이퍼파라미터가 아니라 **피처 정보량**.

## 5. 해석 (SHAP·ablation)

- **중심지거리(특히 강남)가 지배적** — 단독 R² 0.45, 빼면 R² 가장 큰 하락. SHAP 1위.
- **지하철 접근성·버스 승하차**가 그다음. POI·공시지가는 단독은 강하나 거리와 중복(한계기여 작음).
- **승하차는 단독 R²≈0**(혼자선 가격 예측 불가) → "유동인구로 가격 역산" 우려 완화 근거.
- **도로망은 거의 무기여**(단독 0.08, 새 구에선 빼는 게 미세하게 나음). 도시형태 축은 검증했으나 중심성·상권 외 추가 설명력 거의 없음.

---

## 6. 피처 32개 (좌표산출 도시구조 + 결측 플래그 3)

| 군 | 피처 |
|---|---|
| 승하차(버스 수요) | 승하차_일평균, 경유노선수, flag_버스결측 |
| 공시지가 | 공시지가_원per㎡, flag_공시지가결측 |
| POI 상권(13) | total_100/300/500m + 300m 업종 10(음식·소매·과학기술·수리개인·교육·부동산·시설관리임대·예술스포츠·보건의료·숙박) |
| 중심지거리 | 거리_{시청,강남,여의도}_km, 거리_도심최근접_km |
| 지하철 | 최근접지하철_거리_m, 최근접역_승하차_일평균, flag_역승하차결측 |
| 도로망(7) | 교차로수·가로망연장·간선도로연장(300/500m), 간선도로거리_m |

- **원시 경도/위도는 피처 아님**(도시구조 해석·새 지역 일반화 목적). 격자/지도 좌표로만 사용.
- **결측 정책**: XGBoost는 NaN 네이티브. **임의 좌표 예측 시** 좌표산출 불가 피처(버스 승하차·경유노선수·공시지가)는 **최근접 학습정류장 값으로 대체**(공간 NN) → "이웃과 비슷한 수요·지가의 정류장이 여기 있다면"의 의미.

## 7. 재현 파이프라인
```
uv run python scripts/train_eval.py        # baseline 사다리 + 두 CV
uv run python scripts/tune_xgb.py          # RandomizedSearch → xgb_best_params.json
uv run python scripts/ablation.py          # 피처군 기여
uv run python scripts/shap_analyze.py      # 최종 모델 적합·저장 + SHAP 1층위
uv run python scripts/build_error_band.py  # error_band.json
uv run python scripts/build_subway_master.py  # (1회) 역마스터 캐시 — API 키 필요
uv run python scripts/build_grid.py        # grid_250m.csv
```
공통 로직: `scripts/model_utils.py`(피처군·모델·CV).

## 8. 서빙 의존 (웹팀 인계)
- **격자만 쓰면**(A) → `grid_250m.csv` 하나면 충분.
- **온디맨드**(B) → `predict.py`+`feature_extractor.py`+`xgb_model.joblib`+`error_band.json` **및** 다음 데이터:
  `../data/seoul/raw/소상공인_상가_서울_202603.csv`, `../data/seoul/raw/osm_seoul_drive.graphml`,
  `../data/seoul/features/지하철_역마스터.csv`, `../data/seoul/모델테이블.csv`.
  파이썬 의존: xgboost·scikit-learn·shap·scipy·pandas·numpy·osmnx·shapely·pyproj·networkx·joblib.

## 9. 알려진 한계 (보고서 명시)
- 수집가는 실거래가 아닌 **호가**일 수 있음 / Y에 제작·설치비 포함(입지 무관 고정비) / 가격이 대행사 **단가표 계단값**(연속 아님).
- **외곽·데이터 희소 지역 예측 신뢰도 낮음**(자치구 CV R² 0.32, `신뢰도=하`).
- 버스 승하차·공시지가는 임의 좌표에서 NN 대체값(실측 아님).
