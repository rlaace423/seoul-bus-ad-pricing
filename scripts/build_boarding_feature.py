"""
피처 빌드 #1: 정류장별 승하차 일평균 + 경유 노선 수 (3~4월 평균).
출처: OA-12912 월별 CSV (202603, 202604).

집계 정의:
- 승차/하차_일평균 = (해당 ARS의 두 달 전체 승차/하차 합) ÷ (두 달 고유 사용일자 수)
  · 3월·4월 날짜는 서로 겹치지 않으므로 일수는 단순 합산(31+30=61 등).
- 승하차_일평균 = 승차_일평균 + 하차_일평균
- 경유노선수 = 두 달에 걸쳐 그 정류장을 지난 고유 노선번호 수(합집합)

조인 키 = ARS. 모델용 2,555 정류장 전부에 left join(미매칭은 NaN — 공항/광역버스 정류장).
실행: uv run python scripts/build_boarding_feature.py
"""
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "seoul" / "raw"
MODEL_CSV = ROOT / "data" / "seoul" / "price" / "덕플레이스_서울_모델용.csv"
OUT_DIR = ROOT / "data" / "seoul" / "features"
OUT_CSV = OUT_DIR / "승하차_노선_3-4월.csv"

MONTHS = ["BUS_STATION_BOARDING_MONTH_202603.csv",
          "BUS_STATION_BOARDING_MONTH_202604.csv"]
COLS = ["사용일자", "노선번호", "버스정류장ARS번호", "승차총승객수", "하차총승객수"]


def norm_ars(s):
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(5)


# ARS별 누적기
board_sum = defaultdict(float)
alight_sum = defaultdict(float)
n_days = defaultdict(int)          # 두 달 일수 합(날짜 disjoint)
route_set = defaultdict(set)       # 고유 노선번호 합집합

for fn in MONTHS:
    df = pd.read_csv(RAW / fn, encoding="cp949", usecols=COLS, dtype=str)
    df["_ARS"] = norm_ars(df["버스정류장ARS번호"])
    df["_b"] = pd.to_numeric(df["승차총승객수"], errors="coerce").fillna(0.0)
    df["_a"] = pd.to_numeric(df["하차총승객수"], errors="coerce").fillna(0.0)

    g = df.groupby("_ARS")
    for ars, v in g["_b"].sum().items():
        board_sum[ars] += v
    for ars, v in g["_a"].sum().items():
        alight_sum[ars] += v
    for ars, v in g["사용일자"].nunique().items():
        n_days[ars] += int(v)
    for ars, arr in g["노선번호"].unique().items():
        route_set[ars].update(arr)
    print(f"  {fn}: {len(df):,}행, ARS {df['_ARS'].nunique():,}개")

# 정류장별 피처 테이블
rows = []
for ars in board_sum:
    d = n_days[ars]
    bd = board_sum[ars] / d if d else float("nan")
    ad = alight_sum[ars] / d if d else float("nan")
    rows.append({
        "ARS": ars,
        "승차_일평균": round(bd, 1),
        "하차_일평균": round(ad, 1),
        "승하차_일평균": round(bd + ad, 1),
        "경유노선수": len(route_set[ars]),
    })
feat = pd.DataFrame(rows)

# 모델 정류장에 left join (전체 2,555 보존, 미매칭 NaN)
model = pd.read_csv(MODEL_CSV, dtype=str)
model["ARS"] = norm_ars(model["ARS"])
out = model[["ARS", "자치구", "정류장이름"]].merge(feat, on="ARS", how="left")

OUT_DIR.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

# ---- 리포트 ----
n = len(out)
miss = out["승하차_일평균"].isna().sum()
print(f"\n● 출력: {OUT_CSV.relative_to(ROOT)}  ({n:,}행)")
print(f"● 피처 결측(공항/광역버스 추정): {miss}개 ({miss/n:.1%})")
desc = out["승하차_일평균"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9])
print("\n승하차_일평균(명/일) 분포:")
for k in ["min", "10%", "25%", "50%", "75%", "90%", "max"]:
    print(f"   {k:>4}: {desc[k]:>10,.0f}")
print(f"\n경유노선수: 중앙 {out['경유노선수'].median():.0f} | "
      f"평균 {out['경유노선수'].mean():.1f} | max {out['경유노선수'].max():.0f}")
print("\n상위 5개(승하차 일평균):")
top = out.nlargest(5, "승하차_일평균")[["ARS", "자치구", "정류장이름", "승하차_일평균", "경유노선수"]]
for _, r in top.iterrows():
    print(f"   {r['ARS']} {r['자치구']:<5} {r['정류장이름'][:22]:<22} "
          f"{r['승하차_일평균']:>9,.0f}명/일  노선{r['경유노선수']:>3}")
