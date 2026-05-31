"""5단계: 주력 XGBoost 집중 RandomizedSearch 튜닝.
- 내부 KFold(4)로 ~80후보 탐색(scoring=MAE, 원 단위).
- best params를 model/xgb_best_params.json 에 저장(ablation·SHAP·격자가 자동 사용).
- 튜닝/기본값을 두 outer CV(무작위·자치구)로 동일 비교 보고.
실행: uv run python scripts/tune_xgb.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from sklearn.model_selection import RandomizedSearchCV, KFold, GroupKFold
from sklearn.compose import TransformedTargetRegressor
from xgboost import XGBRegressor
from model_utils import load_modeling_data, cv_evaluate, make_xgb, ALL_FEATURES, TARGET

df, dropped = load_modeling_data()
X, y, groups = df[ALL_FEATURES], df[TARGET], df['자치구']
print(f'n={len(df)}  features={len(ALL_FEATURES)}  탐색 시작...')

# 탐색 동안엔 XGB n_jobs=1, search n_jobs=-1 (중첩 병렬 과구독 방지)
base = TransformedTargetRegressor(
    regressor=XGBRegressor(tree_method='hist', random_state=42, n_jobs=1),
    func=np.log1p, inverse_func=np.expm1)

param_dist = {
    'regressor__max_depth':        [3, 4, 5, 6, 8],
    'regressor__learning_rate':    [0.02, 0.03, 0.05, 0.08, 0.1],
    'regressor__n_estimators':     [300, 500, 800, 1200],
    'regressor__subsample':        [0.6, 0.7, 0.8, 0.9, 1.0],
    'regressor__colsample_bytree': [0.6, 0.7, 0.8, 0.9, 1.0],
    'regressor__min_child_weight': [1, 3, 5, 10, 20],
    'regressor__reg_lambda':       [0.1, 0.5, 1.0, 2.0, 5.0],
    'regressor__reg_alpha':        [0, 0.1, 0.5, 1.0],
    'regressor__gamma':            [0, 0.1, 0.5],
}
search = RandomizedSearchCV(
    base, param_dist, n_iter=80, scoring='neg_mean_absolute_error',
    cv=KFold(n_splits=4, shuffle=True, random_state=42),
    n_jobs=-1, random_state=42, verbose=1, refit=True)
search.fit(X, y)

best = {k.replace('regressor__', ''): v for k, v in search.best_params_.items()}
print(f'\nbest 내부CV MAE = {-search.best_score_:,.0f}원')
print('best params:', json.dumps(best, ensure_ascii=False))

os.makedirs('model', exist_ok=True)
with open('model/xgb_best_params.json', 'w', encoding='utf-8') as f:
    json.dump(best, f, ensure_ascii=False, indent=2)
print('→ saved model/xgb_best_params.json')

# 두 outer CV로 튜닝 vs 기본값 비교(baseline 표와 동일 기준)
schemes = {
    '무작위 KFold(5)': (KFold(n_splits=5, shuffle=True, random_state=42), None),
    '자치구 GroupKFold(5)': (GroupKFold(n_splits=5), groups),
}
variants = {'XGBoost(기본)': make_xgb(tuned=False), 'XGBoost(튜닝)': make_xgb(tuned=True)}
for sname, (cv, grp) in schemes.items():
    print('\n' + '=' * 70)
    print(sname)
    print('-' * 70)
    print(f'{"model":<16}{"MAE(원)":>13}{"RMSE(원)":>13}{"MAPE%":>9}{"R2(±std)":>16}')
    for mname, model in variants.items():
        r = cv_evaluate(model, X, y, cv, grp)
        print(f'{mname:<16}{r["MAE"][0]:>13,.0f}{r["RMSE"][0]:>13,.0f}'
              f'{r["MAPE"][0]:>9.1f}   {r["R2"][0]:>6.3f}±{r["R2"][1]:.3f}')
