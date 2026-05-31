"""
게이트 후속 진단: 승하차 데이터에 없는 정류장 76개의 정체를 분류한다.
- ✈️(공항버스 추정) 표시 여부
- 3월(202603)에는 잡히는지 → 3~4월 합집합 커버리지
- 좌표 마스터에 좌표가 있는지 → 없으면 어차피 spatial join에서 제외
실행: uv run python scripts/diag_unmatched.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "seoul" / "raw"
MODEL_CSV = ROOT / "data" / "seoul" / "price" / "덕플레이스_서울_모델용.csv"
MASTER_XLSX = ROOT / "data" / "seoul" / "서울시버스정류소위치정보(20260506).xlsx"


def norm_ars(s):
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(5)


def load_board_ars(name):
    df = pd.read_csv(RAW / name, encoding="cp949", usecols=["버스정류장ARS번호"], dtype=str)
    return set(norm_ars(df["버스정류장ARS번호"]))


model = pd.read_csv(MODEL_CSV, dtype=str)
model["_ARS"] = norm_ars(model["ARS"])

apr = load_board_ars("BUS_STATION_BOARDING_MONTH_202604.csv")
mar = load_board_ars("BUS_STATION_BOARDING_MONTH_202603.csv")
union = apr | mar

master = pd.read_excel(MASTER_XLSX, dtype=str)
# ARS_ID 컬럼 탐색
ars_master_col = next(c for c in master.columns if "ARS" in c.upper())
master_ars = set(norm_ars(master[ars_master_col]))

model["in_apr"] = model["_ARS"].isin(apr)
model["in_union"] = model["_ARS"].isin(union)
model["has_coord"] = model["_ARS"].isin(master_ars)
model["is_air"] = model["정류장이름"].str.contains("✈", na=False)

print(f"모델 정류장: {len(model):,}")
print(f"✈️ 표시 정류장: {model['is_air'].sum():,}")

print("\n── 4월 단일 기준 ──")
print(f"매칭 {model['in_apr'].sum():,} / 미매칭 {(~model['in_apr']).sum():,}")
print("\n── 3~4월 합집합 기준 ──")
print(f"매칭 {model['in_union'].sum():,} / 미매칭 {(~model['in_union']).sum():,}")

unm = model[~model["in_union"]].copy()
print(f"\n■ 합집합으로도 미매칭: {len(unm)} 개")
print(f"   - 그중 ✈️ 표시: {unm['is_air'].sum()}")
print(f"   - 그중 좌표 있음(spatial join 대상): {unm['has_coord'].sum()}")
print(f"   - 그중 좌표 없음(어차피 제외): {(~unm['has_coord']).sum()}")

print("\n■ ✈️ 표시 정류장의 승하차 매칭률(공항버스 가설 검증):")
air = model[model["is_air"]]
non = model[~model["is_air"]]
print(f"   ✈️ 있음: 매칭 {air['in_union'].sum()}/{len(air)} = {air['in_union'].mean():.1%}")
print(f"   ✈️ 없음: 매칭 {non['in_union'].sum()}/{len(non)} = {non['in_union'].mean():.1%}")

print("\n■ '진짜 문제'(좌표 있는데 승하차 없음) 목록:")
real = unm[unm["has_coord"]][["ARS", "자치구", "정류장이름", "is_air"]]
for _, r in real.iterrows():
    tag = "✈️" if r["is_air"] else "  "
    print(f"   {tag} {r['ARS']}  {r['자치구']}  {r['정류장이름']}")
print(f"\n   → 좌표 있고 승하차 없는 정류장: {len(real)} 개 "
      f"(✈️ {real['is_air'].sum()} / 일반 {(~real['is_air']).sum()})")
