"""
중간 점검(예비 EDA): 지금까지 모은 피처들을 Y(광고가 원/면)에 조인하고
각 피처의 Spearman 상관을 본다. '수집한 피처가 가격을 설명하나?' 조기 검증.
(지하철·도로망은 아직 미수집 — 예비 점검이며 모델 평가 아님.)
실행: uv run python scripts/assemble_and_check.py
"""
from pathlib import Path
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
FEAT = ROOT / "data/seoul/features"
MODEL = ROOT / "data/seoul/price/덕플레이스_서울_모델용.csv"


def norm_ars(s):
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(5)


m = pd.read_csv(MODEL, dtype=str)
m["ARS"] = norm_ars(m["ARS"])
df = pd.DataFrame({"ARS": m["ARS"], "Y": pd.to_numeric(m["가격_원per면"], errors="coerce")})

FILES = ["승하차_노선_3-4월", "공시지가", "중심지거리", "POI_상권", "지하철근접", "도로망"]
for f in FILES:
    g = pd.read_csv(FEAT / f"{f}.csv", dtype={"ARS": str})
    g["ARS"] = norm_ars(g["ARS"])
    drop = [c for c in ["자치구", "정류장이름", "PNU", "지번", "공시지가_주소", "공시연도",
                        "최근접역명", "최근접역호선"] if c in g.columns]
    g = g.drop(columns=drop)
    df = df.merge(g, on="ARS", how="left")

print(f"● 조립 테이블: {len(df):,}행 × {df.shape[1]-2} 피처")
num_cols = [c for c in df.columns if c not in ("ARS", "Y")]
res = []
for c in num_cols:
    x = pd.to_numeric(df[c], errors="coerce")
    mask = x.notna() & df["Y"].notna()
    if mask.sum() > 50:
        rho, _ = spearmanr(x[mask], df.loc[mask, "Y"])
        res.append((c, rho, int(mask.sum())))

res.sort(key=lambda t: abs(t[1]), reverse=True)
print(f"\n{'피처':<26}{'Spearman ρ (vs 가격)':>20}{'  N':>7}")
print("─" * 56)
for c, rho, n in res:
    bar = "█" * int(abs(rho) * 30)
    print(f"{c:<26}{rho:>+12.3f}        {n:>6}  {bar}")
