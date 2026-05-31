"""6단계 ⭐: SHAP 1층위(전체 경향) + 최종 모델 저장.
- 전체 데이터(n=2553)에 튜닝 XGBoost 적합 → model/xgb_model.joblib.
- TreeExplainer로 SHAP(log1p-가격 단위 = 곱셈/% 효과) → beeswarm·bar PNG + 중요도 CSV.
- 위치별 2층위는 build_grid.py에서 칸마다 산출.
실행: uv run python scripts/shap_analyze.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import joblib
import shap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'AppleGothic'   # 한글 라벨
plt.rcParams['axes.unicode_minus'] = False
from model_utils import load_modeling_data, make_xgb, ALL_FEATURES, TARGET

df, _ = load_modeling_data()
X, y = df[ALL_FEATURES], df[TARGET]

model = make_xgb()          # 튜닝값 로드
model.fit(X, y)
os.makedirs('model', exist_ok=True)
joblib.dump({'model': model, 'features': ALL_FEATURES, 'target': TARGET, 'log_target': True},
            'model/xgb_model.joblib')
print(f'saved model/xgb_model.joblib  (n={len(df)}, {len(ALL_FEATURES)}피처)')

reg = model.regressor_      # 적합된 XGBRegressor (log1p 공간)
expl = shap.TreeExplainer(reg)(X)
base = float(np.atleast_1d(expl.base_values)[0])
print(f'SHAP base(log1p) = {base:.3f}  →  ~{np.expm1(base):,.0f}원 (평균 출발선)')

imp = pd.Series(np.abs(expl.values).mean(0), index=ALL_FEATURES).sort_values(ascending=False)
print('\nTop15 mean|SHAP|  (log-가격 단위, 클수록 영향 큼):')
for k, v in imp.head(15).items():
    print(f'  {k:<24}{v:.4f}')
imp.to_csv('model/shap_global_importance.csv', encoding='utf-8-sig',
           header=['mean_abs_shap_log'])

shap.plots.beeswarm(expl, max_display=20, show=False)
plt.title('SHAP 전체 경향 (beeswarm) — 가로축: log-가격 영향')
plt.tight_layout(); plt.savefig('model/shap_global_beeswarm.png', dpi=130, bbox_inches='tight'); plt.close()

shap.plots.bar(expl, max_display=20, show=False)
plt.title('SHAP 평균 절대기여 (bar)')
plt.tight_layout(); plt.savefig('model/shap_global_bar.png', dpi=130, bbox_inches='tight'); plt.close()
print('saved model/shap_global_beeswarm.png, model/shap_global_bar.png, model/shap_global_importance.csv')
