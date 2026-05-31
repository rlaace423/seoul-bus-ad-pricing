"""
게이트: 승하차 데이터(OA-12912 월별 CSV)의 ARS 키가
모델용 2,555 정류장과 매칭되는지 검증한다.

0단계(가격↔좌표 매칭)와 동일한 철학: 본격 집계 전에 '키 정합성'만 소량 확인하는 게이트.
- 조인 키 = ARS (이름 매칭 금지)
- ID는 항상 텍스트, leading zero 보존. 일부 원천 ARS가 4자리일 수 있어 zfill(5)로 정규화.
- 한국 공공 CSV 인코딩(cp949/utf-8-sig 혼재) 자동 감지.

실행:  uv run python scripts/gate_boarding.py
"""
from __future__ import annotations
import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "seoul" / "raw"
MODEL_CSV = ROOT / "data" / "seoul" / "price" / "덕플레이스_서울_모델용.csv"

PASS_THRESHOLD = 0.95  # 매칭률이 이 미만이면 게이트 실패로 표시


# ---------- 입출력 유틸 ----------
def find_boarding_csvs() -> list[str]:
    pats = ["BUS_STATION_BOARDING_MONTH_*.csv", "*BOARDING*.csv", "*승하차*.csv"]
    found: list[str] = []
    for p in pats:
        found += glob.glob(str(RAW / p))
    # 중복 제거 + 정렬(최신 월이 뒤로)
    return sorted(dict.fromkeys(found))


def detect_encoding(path: str) -> str:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            with open(path, encoding=enc) as f:
                f.readline()
            return enc
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"인코딩 감지 실패: {path}")


def pick_col(cols: list[str], *, must: list[str], exclude: list[str] | None = None) -> str | None:
    exclude = exclude or []
    for c in cols:
        u = c.upper().replace(" ", "")
        if all(m.upper() in u for m in must) and not any(e.upper() in u for e in exclude):
            return c
    return None


def normalize_ars(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(5)


# ---------- 메인 ----------
def main() -> int:
    csvs = find_boarding_csvs()
    if not csvs:
        print("✗ 승하차 CSV를 찾지 못했습니다.")
        print(f"  → {RAW} 에 BUS_STATION_BOARDING_MONTH_YYYYMM.csv 를 저장해주세요.")
        return 2

    path = csvs[-1]  # 게이트는 가장 최신 한 개로 충분
    print(f"● 대상 파일: {Path(path).name}")
    enc = detect_encoding(path)
    print(f"● 인코딩 감지: {enc}")

    # 1) 헤더만 읽어 컬럼 파악
    header = pd.read_csv(path, encoding=enc, nrows=0)
    cols = list(header.columns)
    print(f"● 컬럼({len(cols)}): {cols}")

    ars_col = pick_col(cols, must=["ARS"])
    board_col = pick_col(cols, must=["승차"], exclude=["하차"])
    alight_col = pick_col(cols, must=["하차"])
    date_col = pick_col(cols, must=["사용", "일자"]) or pick_col(cols, must=["YMD"], exclude=["REG", "등록"])
    route_col = pick_col(cols, must=["노선", "ID"]) or pick_col(cols, must=["노선번호"]) or pick_col(cols, must=["노선"])

    print(f"● 매핑 → ARS={ars_col!r}  승차={board_col!r}  하차={alight_col!r}  "
          f"날짜={date_col!r}  노선={route_col!r}")
    if ars_col is None:
        print("✗ ARS 컬럼을 못 찾았습니다. 컬럼명을 확인하세요.")
        return 2

    # 2) 필요한 컬럼만 전체 로드(메모리 절약)
    usecols = [c for c in {ars_col, board_col, alight_col, date_col, route_col} if c]
    board = pd.read_csv(path, encoding=enc, usecols=usecols, dtype=str)
    print(f"● 로드: {len(board):,} 행")

    board["_ARS"] = normalize_ars(board[ars_col])
    for c in (board_col, alight_col):
        if c:
            board[c] = pd.to_numeric(board[c], errors="coerce")

    # 3) 모델용 정류장 로드
    model = pd.read_csv(MODEL_CSV, dtype=str)
    model["_ARS"] = normalize_ars(model["ARS"])
    model_ars = set(model["_ARS"])
    board_ars = set(board["_ARS"])

    # 4) 커버리지(게이트 핵심)
    matched = model_ars & board_ars
    missing = sorted(model_ars - board_ars)
    rate = len(matched) / len(model_ars)
    print("\n========== 게이트: ARS 커버리지 ==========")
    print(f"모델 정류장 ARS(고유): {len(model_ars):,}")
    print(f"승하차 데이터 ARS(고유): {len(board_ars):,}")
    print(f"매칭: {len(matched):,} / {len(model_ars):,}  =  {rate:.2%}")
    print(f"미매칭: {len(missing)} 개")
    if missing:
        sample = model[model["_ARS"].isin(missing[:15])][["ARS", "정류장이름", "자치구"]]
        print("  미매칭 예시:")
        for _, r in sample.iterrows():
            print(f"    {r['ARS']}  {r['자치구']}  {r['정류장이름']}")

    # 5) 2차 피처 사전검증: 정류장별 집계 미리보기(승하차 일평균 + 경유 노선 수)
    if board_col and alight_col:
        n_days = board[date_col].nunique() if date_col else None
        g = board.groupby("_ARS").agg(
            board_sum=(board_col, "sum"),
            alight_sum=(alight_col, "sum"),
            n_routes=(route_col, "nunique") if route_col else (board_col, "size"),
        )
        g["onoff_sum"] = g["board_sum"] + g["alight_sum"]
        if n_days:
            g["onoff_daily"] = g["onoff_sum"] / n_days
        print("\n========== 집계 미리보기(2차 피처 사전검증) ==========")
        print(f"이 파일의 일수(고유 사용일자): {n_days}")
        ours = g.loc[g.index.isin(matched)]
        if "onoff_daily" in g and len(ours):
            d = ours["onoff_daily"].describe(percentiles=[0.1, 0.5, 0.9])
            print("우리 정류장 일평균 승하차(명/일) 분포:")
            print(f"    min {d['min']:.0f} | p10 {d['10%']:.0f} | 중앙 {d['50%']:.0f} "
                  f"| p90 {d['90%']:.0f} | max {d['max']:.0f}")
        if route_col and len(ours):
            r = ours["n_routes"].describe()
            print(f"우리 정류장 경유 노선 수: 중앙 {r['50%']:.0f} | max {r['max']:.0f}")

    # 6) 판정
    ok = rate >= PASS_THRESHOLD
    print("\n========== 판정 ==========")
    print("✓ 게이트 통과" if ok else "✗ 게이트 미달 — 키 정합성 점검 필요")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
