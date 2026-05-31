"""5·6단계: baseline 사다리 + 두 CV(무작위 KFold / 자치구 GroupKFold) 평가.
실행: uv run python scripts/train_eval.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sklearn.model_selection import KFold, GroupKFold
from model_utils import load_modeling_data, make_models, cv_evaluate, ALL_FEATURES, TARGET

df, dropped = load_modeling_data()
X, y, groups = df[ALL_FEATURES], df[TARGET], df['자치구']
print(f'n={len(df)} (좌표없는 {dropped}행 제외)  features={len(ALL_FEATURES)}  '
      f'groups(자치구)={groups.nunique()}  Y중앙={y.median():,.0f}원')

schemes = {
    '무작위 KFold(5)': (KFold(n_splits=5, shuffle=True, random_state=42), None),
    '자치구 GroupKFold(5)': (GroupKFold(n_splits=5), groups),
}
models = make_models()

for sname, (cv, grp) in schemes.items():
    print('\n' + '=' * 70)
    print(sname)
    print('-' * 70)
    print(f'{"model":<16}{"MAE(원)":>13}{"RMSE(원)":>13}{"MAPE%":>9}{"R2(±std)":>16}')
    for mname, model in models.items():
        r = cv_evaluate(model, X, y, cv, grp)
        print(f'{mname:<16}{r["MAE"][0]:>13,.0f}{r["RMSE"][0]:>13,.0f}'
              f'{r["MAPE"][0]:>9.1f}   {r["R2"][0]:>6.3f}±{r["R2"][1]:.3f}')
