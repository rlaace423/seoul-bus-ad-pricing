"""6단계: 피처군 ablation — 각 군의 실제 기여 정량화.
- leave-one-group-out: 군을 하나씩 빼고 성능 변화(ΔR²) → 클수록 그 군이 중요.
- single-group-only: 군 하나만으로 학습 → 단독 설명력 순위.
주력 = 튜닝된 XGBoost. 두 CV(무작위·자치구) 모두.
실행: uv run python scripts/ablation.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sklearn.model_selection import KFold, GroupKFold
from model_utils import (load_modeling_data, make_xgb, cv_evaluate,
                         FEATURE_GROUPS, ALL_FEATURES, TARGET)

df, dropped = load_modeling_data()
y, groups = df[TARGET], df['자치구']
schemes = {
    '무작위 KFold(5)': (KFold(n_splits=5, shuffle=True, random_state=42), None),
    '자치구 GroupKFold(5)': (GroupKFold(n_splits=5), groups),
}


def excluding(g):
    drop = set(FEATURE_GROUPS[g])
    return [c for c in ALL_FEATURES if c not in drop]


print(f'n={len(df)}  features={len(ALL_FEATURES)}  groups={list(FEATURE_GROUPS)}')

for sname, (cv, grp) in schemes.items():
    print('\n' + '=' * 66)
    print(f'leave-one-group-out  |  {sname}')
    print('-' * 66)
    base = cv_evaluate(make_xgb(), df[ALL_FEATURES], y, cv, grp)
    base_r2 = base['R2'][0]
    print(f'{"config":<18}{"MAE(원)":>13}{"R2":>9}{"ΔR2(빼면)":>12}')
    print(f'{"ALL(32)":<18}{base["MAE"][0]:>13,.0f}{base_r2:>9.3f}{"—":>12}')
    rows = []
    for g in FEATURE_GROUPS:
        r = cv_evaluate(make_xgb(), df[excluding(g)], y, cv, grp)
        rows.append((g, r['MAE'][0], r['R2'][0], r['R2'][0] - base_r2))
    for g, mae, r2, d in sorted(rows, key=lambda t: t[3]):  # ΔR² 오름차순(가장 중요한 군 먼저)
        print(f'{"−"+g:<18}{mae:>13,.0f}{r2:>9.3f}{d:>+12.3f}')

print('\n' + '=' * 66)
print('single-group-only (군 하나만)  |  무작위 KFold(5)')
print('-' * 66)
print(f'{"group":<18}{"n_feat":>7}{"MAE(원)":>13}{"R2":>9}')
solo = []
for g, cols in FEATURE_GROUPS.items():
    r = cv_evaluate(make_xgb(), df[cols], y, KFold(5, shuffle=True, random_state=42), None)
    solo.append((g, len(cols), r['MAE'][0], r['R2'][0]))
for g, nf, mae, r2 in sorted(solo, key=lambda t: -t[3]):
    print(f'{g:<18}{nf:>7}{mae:>13,.0f}{r2:>9.3f}')
