"""공용 모델링 유틸 — 데이터 로드·피처군 정의·모델 정의·CV 평가.

train_eval.py / ablation.py / shap_analyze.py / build_grid.py 가 공유.
- Y: log1p 변환(예측은 expm1로 원 단위 자동 역변환).
- 결측: 트리(XGB)는 NaN 네이티브 / 선형·RF는 median 임퓨트 + 결측 플래그 3종.
- 원시 경도/위도는 피처에서 제외(격자·지도용). 도시구조 해석 + 새 구 일반화가 목표.
- 승하차_일평균 = 승차+하차 이므로 승차·하차 개별 컬럼은 제외(완전공선성).
"""
from __future__ import annotations
import json, os
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.dummy import DummyRegressor
from sklearn.compose import TransformedTargetRegressor
from sklearn.metrics import (mean_absolute_error, mean_squared_error,
                             mean_absolute_percentage_error, r2_score)
from xgboost import XGBRegressor

TABLE_PATH = 'data/seoul/모델테이블.csv'
TARGET = '가격_원per면'

# 피처군 — 결측 플래그는 의미상 같은 군에 묶어 ablation 시 함께 빠지게 함.
FEATURE_GROUPS = {
    '승하차':   ['승하차_일평균', '경유노선수', 'flag_버스결측'],
    '공시지가': ['공시지가_원per㎡', 'flag_공시지가결측'],
    'POI상권':  ['POI_total_100m', 'POI_total_300m', 'POI_음식_300m', 'POI_소매_300m',
                'POI_과학·기술_300m', 'POI_수리·개인_300m', 'POI_교육_300m', 'POI_부동산_300m',
                'POI_시설관리·임대_300m', 'POI_예술·스포츠_300m', 'POI_보건의료_300m', 'POI_숙박_300m',
                'POI_total_500m'],
    '중심지거리': ['거리_시청_km', '거리_강남_km', '거리_여의도_km', '거리_도심최근접_km'],
    '지하철':   ['최근접지하철_거리_m', '최근접역_승하차_일평균', 'flag_역승하차결측'],
    '도로망':   ['교차로수_300m', '가로망연장_300m', '간선도로연장_300m',
                '교차로수_500m', '가로망연장_500m', '간선도로연장_500m', '간선도로거리_m'],
}
ALL_FEATURES = [c for cols in FEATURE_GROUPS.values() for c in cols]

# (플래그명, 결측 판정 원본컬럼) — 결측 자체가 신호(공항·광역버스 등)
FLAG_SPECS = [
    ('flag_버스결측', '승하차_일평균'),
    ('flag_공시지가결측', '공시지가_원per㎡'),
    ('flag_역승하차결측', '최근접역_승하차_일평균'),
]


def load_modeling_data(path: str = TABLE_PATH):
    """모델테이블 로드 → 좌표없는 행 제외 → 결측 플래그 부착. (df, dropped_count) 반환."""
    df = pd.read_csv(path, dtype={'ARS': str})
    before = len(df)
    df = df.dropna(subset=['경도', '위도']).reset_index(drop=True)
    dropped = before - len(df)
    for flag, src in FLAG_SPECS:
        df[flag] = df[src].isna().astype(int)
    return df, dropped


# XGBoost 기본값(튜닝 전 baseline). 튜닝 결과는 TUNED_PATH(json)에 저장 → make_xgb가 덮어씀.
DEFAULT_XGB = dict(n_estimators=400, learning_rate=0.05, max_depth=5,
                   subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
                   reg_lambda=1.0, tree_method='hist', random_state=42, n_jobs=-1)
TUNED_PATH = 'model/xgb_best_params.json'


def _wrap(reg):
    """log1p 타깃 변환(예측은 expm1로 원 단위 자동 역변환)."""
    return TransformedTargetRegressor(regressor=reg, func=np.log1p, inverse_func=np.expm1)


def make_xgb(tuned: bool = True):
    """주력 XGBoost(log1p 래핑). tuned=True면 TUNED_PATH의 튜닝값을 기본값 위에 덮어씀."""
    p = dict(DEFAULT_XGB)
    if tuned and os.path.exists(TUNED_PATH):
        with open(TUNED_PATH, encoding='utf-8') as f:
            p.update(json.load(f))
    p.update(tree_method='hist', random_state=42, n_jobs=-1)  # 항상 고정
    return _wrap(XGBRegressor(**p))


def make_models() -> dict:
    """baseline 사다리: Dummy → Linear → RandomForest → XGBoost(기본값·튜닝 전)."""
    imp = lambda: SimpleImputer(strategy='median')
    return {
        'Dummy(median)': _wrap(DummyRegressor(strategy='median')),
        'Linear': _wrap(Pipeline([('impute', imp()), ('scale', StandardScaler()),
                                  ('reg', LinearRegression())])),
        'RandomForest': _wrap(Pipeline([('impute', imp()),
                                        ('reg', RandomForestRegressor(
                                            n_estimators=400, n_jobs=-1, random_state=42))])),
        'XGBoost': make_xgb(tuned=False),  # NaN 네이티브 → 임퓨트 없음
    }


def cv_evaluate(model, X, y, cv, groups=None) -> dict:
    """fold별로 학습·예측 후 원 단위 4지표 집계. 각 지표 (mean, std) 반환."""
    maes, rmses, mapes, r2s = [], [], [], []
    for tr, te in cv.split(X, y, groups):
        m = clone(model)
        m.fit(X.iloc[tr], y.iloc[tr])
        p = m.predict(X.iloc[te])
        yt = y.iloc[te].to_numpy()
        maes.append(mean_absolute_error(yt, p))
        rmses.append(np.sqrt(mean_squared_error(yt, p)))
        mapes.append(mean_absolute_percentage_error(yt, p) * 100)
        r2s.append(r2_score(yt, p))
    agg = lambda v: (float(np.mean(v)), float(np.std(v)))
    return {'MAE': agg(maes), 'RMSE': agg(rmses), 'MAPE': agg(mapes), 'R2': agg(r2s)}
