"""좌표 → 버스정류장 월 광고가(원/면) 예측 + 오차범위 + 위치별 SHAP top-N(2층위).

라이브러리:
    from predict import PricePredictor
    p = PricePredictor()
    p.predict(37.4979, 127.0276)        # 강남역 부근
    p.predict_batch(lats, lons)         # 격자용(DataFrame)

CLI:
    uv run python model/predict.py 37.4979 127.0276
"""
from __future__ import annotations
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import joblib
import shap
from scipy.spatial import cKDTree
from feature_extractor import FeatureExtractor, ALL_FEATURES, _to_xy

ROOT = Path(__file__).resolve().parents[1]


class PricePredictor:
    def __init__(self, verbose: bool = False):
        d = joblib.load(ROOT / 'model/xgb_model.joblib')
        self.model = d['model']
        self.features = d['features']
        self.band = json.load(open(ROOT / 'model/error_band.json', encoding='utf-8'))
        self.q_lo = self.band['log_resid_quantiles'][self.band['lo_key']]
        self.q_hi = self.band['log_resid_quantiles'][self.band['hi_key']]
        self.fx = FeatureExtractor(verbose=verbose)
        self.explainer = shap.TreeExplainer(self.model.regressor_)
        # 신뢰도(외삽 정도)용 학습정류장 KDTree + 자치구 근사
        td = pd.read_csv(ROOT / 'data/seoul/모델테이블.csv', dtype={'ARS': str}).dropna(subset=['경도', '위도'])
        self._train_tree = cKDTree(_to_xy(td['경도'].to_numpy(), td['위도'].to_numpy()))
        self._train_gu = td['자치구'].to_numpy()

    def predict_batch(self, lats, lons, top_n: int = 5) -> pd.DataFrame:
        lats = np.asarray(lats, float); lons = np.asarray(lons, float)
        X = self.fx.transform(lats, lons)
        price = self.model.predict(X)
        logp = np.log1p(price)
        lo = np.expm1(logp + self.q_lo)
        hi = np.expm1(logp + self.q_hi)
        sv = self.explainer(X).values                      # (n, 32) log 공간 기여
        xy = _to_xy(lons, lats)
        dist, idx = self._train_tree.query(xy, k=1)
        res = pd.DataFrame({
            '위도': np.round(lats, 6), '경도': np.round(lons, 6),
            '자치구_근사': self._train_gu[idx],
            '예측가_원per면': np.round(price).astype(int),
            '하한_원': np.round(lo).astype(int), '상한_원': np.round(hi).astype(int),
            '최근접학습정류장_m': np.round(dist).astype(int),
        })
        feats = np.array(self.features)
        order = np.argsort(-np.abs(sv), axis=1)[:, :top_n]   # |기여| 내림차순
        rows = np.arange(len(sv))
        for k in range(top_n):
            j = order[:, k]
            res[f'top{k+1}_피처'] = feats[j]
            res[f'top{k+1}_효과%'] = np.round(np.expm1(sv[rows, j]) * 100, 1)
        return res

    def predict(self, lat: float, lon: float, top_n: int = 5) -> dict:
        r = self.predict_batch([lat], [lon], top_n).iloc[0]
        return {
            '예측가_원per면': int(r['예측가_원per면']),
            '오차범위_원': (int(r['하한_원']), int(r['상한_원'])),
            '자치구_근사': r['자치구_근사'],
            '최근접학습정류장_m': int(r['최근접학습정류장_m']),
            'top_factors': [(r[f'top{k+1}_피처'], float(r[f'top{k+1}_효과%'])) for k in range(top_n)],
        }


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        lat, lon = float(sys.argv[1]), float(sys.argv[2])
    else:
        lat, lon = 37.4979, 127.0276  # 강남역
    p = PricePredictor(verbose=True)
    out = p.predict(lat, lon)
    print(f'\n좌표 ({lat}, {lon})')
    print(f"  예측 광고가: {out['예측가_원per면']:,}원/면")
    print(f"  80% 구간:   {out['오차범위_원'][0]:,} ~ {out['오차범위_원'][1]:,}원")
    print(f"  자치구(근사): {out['자치구_근사']}  · 최근접 학습정류장 {out['최근접학습정류장_m']}m")
    print('  주요 요인(SHAP, %는 가격 배수효과):')
    for f, pct in out['top_factors']:
        print(f'    {f:<22} {pct:+.1f}%')
