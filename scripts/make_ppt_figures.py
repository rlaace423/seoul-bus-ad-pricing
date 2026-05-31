"""PPT용 그림 2종 → reports/.
① heatmap_seoul.png   : 격자 7,883칸 예측 광고가 색지도(서울 가격 분포)
② pred_vs_actual.png  : 예측 vs 실제 산점도(무작위 5-fold OOF, 정직한 일반화)
실행: uv run python scripts/make_ppt_figures.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.patheffects as pe
from sklearn.model_selection import cross_val_predict, KFold
from sklearn.metrics import r2_score, mean_absolute_error, mean_absolute_percentage_error
from model_utils import load_modeling_data, make_xgb, ALL_FEATURES, TARGET

plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False
os.makedirs('reports', exist_ok=True)
won = FuncFormatter(lambda v, _: f'{v/1e4:,.0f}만' if v >= 1e4 else f'{v:,.0f}')

# ── ① 히트맵 ───────────────────────────────────────────────
g = pd.read_csv('model/grid_250m.csv')
LAT0 = 37.55
vmax = float(g['예측가_원per면'].quantile(0.95))   # 강남 극값 클립 → 도시 전반 그라데이션 보존
vmin = float(g['예측가_원per면'].min())

fig, ax = plt.subplots(figsize=(9.5, 9))
sc = ax.scatter(g['경도'], g['위도'], c=g['예측가_원per면'], s=10, marker='s',
                cmap='plasma', vmin=vmin, vmax=vmax, linewidths=0)
ax.set_aspect(1 / np.cos(np.radians(LAT0)))
for nm, la, lo in [('강남역', 37.4979, 127.0276), ('시청', 37.5663, 126.9779), ('여의도', 37.5219, 126.9245)]:
    ax.plot(lo, la, 'o', mfc='none', mec='white', mew=2.0, ms=10,
            path_effects=[pe.withStroke(linewidth=3.2, foreground='black')])
    ax.annotate(nm, (lo, la), color='white', fontsize=12, fontweight='bold',
                xytext=(7, 6), textcoords='offset points',
                path_effects=[pe.withStroke(linewidth=2.8, foreground='black')])
ax.set_title('서울 버스정류장 광고가 예측 분포 (250m 격자 · 7,883칸)', fontsize=14, pad=12)
ax.set_xlabel('경도'); ax.set_ylabel('위도')
cb = fig.colorbar(sc, ax=ax, shrink=0.8, extend='max', pad=0.02)
cb.set_label('예측 광고가 (원/면, 상위 5% 클립)', fontsize=11)
cb.ax.yaxis.set_major_formatter(won)
fig.tight_layout(); fig.savefig('reports/heatmap_seoul.png', dpi=160, bbox_inches='tight'); plt.close(fig)
print('saved reports/heatmap_seoul.png')

# ── ② 예측-실측 산점도 (무작위 5-fold OOF) ─────────────────
df, _ = load_modeling_data()
X, y = df[ALL_FEATURES], df[TARGET]
oof = cross_val_predict(make_xgb(), X, y, cv=KFold(5, shuffle=True, random_state=42), n_jobs=1)
yv = y.to_numpy()
r2 = r2_score(yv, oof); mae = mean_absolute_error(yv, oof); mape = mean_absolute_percentage_error(yv, oof) * 100

fig, ax = plt.subplots(figsize=(7.4, 7.2))
ax.scatter(yv, oof, s=10, alpha=0.22, color='#2b6cb0', edgecolors='none')
lims = [yv.min() * 0.9, yv.max() * 1.1]
ax.plot(lims, lims, 'r--', lw=1.5, label='완벽 예측 (y = x)')
ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlim(lims); ax.set_ylim(lims)
ax.xaxis.set_major_formatter(won); ax.yaxis.set_major_formatter(won)
ax.set_xlabel('실제 광고가 (원/면)', fontsize=12)
ax.set_ylabel('예측 광고가 (원/면)', fontsize=12)
ax.set_title('예측 vs 실제 — 무작위 5-fold 교차검증(OOF)', fontsize=13, pad=10)
ax.text(0.04, 0.96, f'R² = {r2:.2f}\nMAE = {mae:,.0f}원\nMAPE = {mape:.0f}%',
        transform=ax.transAxes, va='top', fontsize=12,
        bbox=dict(boxstyle='round', fc='white', ec='gray', alpha=0.9))
ax.legend(loc='lower right', fontsize=11); ax.grid(True, which='both', alpha=0.2)
fig.tight_layout(); fig.savefig('reports/pred_vs_actual.png', dpi=160, bbox_inches='tight'); plt.close(fig)
print(f'saved reports/pred_vs_actual.png  (R²={r2:.3f}, MAE={mae:,.0f}, MAPE={mape:.1f}%)')
