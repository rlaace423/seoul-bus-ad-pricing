"""오차범위 산출: 무작위 KFold OOF 잔차(log 공간) 분위 → model/error_band.json.
예측 구간: lower=expm1(log1p(pred)+q10), upper=expm1(log1p(pred)+q90)  (80% 경험적 구간).
실행: uv run python scripts/build_error_band.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from sklearn.model_selection import cross_val_predict, KFold
from model_utils import load_modeling_data, make_xgb, ALL_FEATURES, TARGET

df, _ = load_modeling_data()
X, y = df[ALL_FEATURES], df[TARGET]
oof = cross_val_predict(make_xgb(), X, y, cv=KFold(5, shuffle=True, random_state=42), n_jobs=1)
r = np.log1p(y.to_numpy()) - np.log1p(oof)        # log 공간 잔차
ps = [5, 10, 25, 50, 75, 90, 95]
q = {str(p): float(np.quantile(r, p / 100)) for p in ps}
band = {'log_resid_quantiles': q, 'lo_key': '10', 'hi_key': '90', 'interval_level': 0.8,
        'note': 'lower=expm1(log1p(pred)+q10), upper=expm1(log1p(pred)+q90)'}
os.makedirs('model', exist_ok=True)
json.dump(band, open('model/error_band.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('log 잔차 분위:', {k: round(v, 3) for k, v in q.items()})
print(f'→ 80% 구간 배수: ×{np.expm1(q["10"])+1:.2f} ~ ×{np.expm1(q["90"])+1:.2f} (예측가 대비)')
print('saved model/error_band.json')
