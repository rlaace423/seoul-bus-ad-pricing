"""
좌표 베이스 테이블: 모델용 2,555 정류장에 마스터 좌표(경도/위도)를 ARS로 붙인다.
이후 모든 좌표 기반 피처(공시지가·POI·지하철·도로망)가 이 파일을 공유.
실행: uv run python scripts/build_stop_coords.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "data/seoul/price/덕플레이스_서울_모델용.csv"
MASTER = ROOT / "data/seoul/서울시버스정류소위치정보(20260506).xlsx"
OUT = ROOT / "data/seoul/features/정류장_좌표.csv"


def norm_ars(s):
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(5)


model = pd.read_csv(MODEL, dtype=str)
model["ARS"] = norm_ars(model["ARS"])

master = pd.read_excel(MASTER, dtype=str)
ars_col = next(c for c in master.columns if "ARS" in c.upper())
x_col = next(c for c in master.columns if ("X" in c.upper() and "좌표" in c) or c.upper() == "X" or "경도" in c)
y_col = next(c for c in master.columns if ("Y" in c.upper() and "좌표" in c) or c.upper() == "Y" or "위도" in c)
master["ARS"] = norm_ars(master[ars_col])
master = master.drop_duplicates("ARS")

out = model[["ARS", "자치구", "정류장이름"]].merge(
    master[["ARS", x_col, y_col]], on="ARS", how="left"
).rename(columns={x_col: "경도", y_col: "위도"})

OUT.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT, index=False, encoding="utf-8-sig")

n = len(out)
has = out["경도"].notna().sum()
print(f"● 출력: {OUT.relative_to(ROOT)}  ({n:,}행)")
print(f"● 좌표 보유: {has:,} / 결측 {n - has}")
if n - has:
    miss = out[out["경도"].isna()][["ARS", "자치구", "정류장이름"]]
    for _, r in miss.iterrows():
        print(f"   (좌표없음) {r['ARS']} {r['자치구']} {r['정류장이름']}")
print(f"● 경도 범위 {out['경도'].astype(float).min():.4f}~{out['경도'].astype(float).max():.4f} / "
      f"위도 {out['위도'].astype(float).min():.4f}~{out['위도'].astype(float).max():.4f}")
