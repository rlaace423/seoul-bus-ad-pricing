"""
캡스톤: 모든 X 피처 + Y를 정류장(ARS) 기준으로 조립한 '모델 입력 테이블'.
산출: data/seoul/모델테이블.csv  (1행=1정류장, 식별자+좌표+Y+24피처)
실행: uv run python scripts/build_model_table.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FEAT = ROOT / "data/seoul/features"
MODEL = ROOT / "data/seoul/price/덕플레이스_서울_모델용.csv"
OUT = ROOT / "data/seoul/모델테이블.csv"


def norm_ars(s):
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(5)


# 식별자 + Y + 좌표
m = pd.read_csv(MODEL, dtype=str)
m["ARS"] = norm_ars(m["ARS"])
base = pd.DataFrame({
    "ARS": m["ARS"], "자치구": m["자치구"], "정류장이름": m["정류장이름"],
    "가격_원per면": pd.to_numeric(m["가격_원per면"], errors="coerce"),
})
coords = pd.read_csv(FEAT / "정류장_좌표.csv", dtype={"ARS": str})
coords["ARS"] = norm_ars(coords["ARS"])
df = base.merge(coords[["ARS", "경도", "위도"]], on="ARS", how="left")

# 피처 파일들(텍스트/추적 컬럼 제외)
DROP = {"자치구", "정류장이름", "PNU", "지번", "공시지가_주소", "공시연도", "최근접역명", "최근접역호선"}
for f in ["승하차_노선_3-4월", "공시지가", "중심지거리", "POI_상권", "지하철근접", "도로망"]:
    g = pd.read_csv(FEAT / f"{f}.csv", dtype={"ARS": str})
    g["ARS"] = norm_ars(g["ARS"])
    g = g.drop(columns=[c for c in DROP if c in g.columns])
    df = df.merge(g, on="ARS", how="left")

df.to_csv(OUT, index=False, encoding="utf-8-sig")

feat_cols = [c for c in df.columns if c not in ("ARS", "자치구", "정류장이름", "가격_원per면", "경도", "위도")]
print(f"● 출력: {OUT.relative_to(ROOT)}")
print(f"● {len(df):,}행 × {len(feat_cols)}피처 (+ 식별자·좌표·Y)")
print(f"● Y(가격_원per면): 중앙 {df['가격_원per면'].median():,.0f} (min {df['가격_원per면'].min():,.0f} ~ max {df['가격_원per면'].max():,.0f})")
print("\n● 피처별 결측(2,555 중):")
na = df[feat_cols].isna().sum().sort_values(ascending=False)
for c, n in na.items():
    if n:
        print(f"     {c:<22} {n:>4}  ({n/len(df):.1%})")
print(f"   (나머지 {(na == 0).sum()}개 피처는 결측 0)")
