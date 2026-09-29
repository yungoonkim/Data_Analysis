"""
송파구 따릉이 시간대별/요일별 이용 패턴 분석 및 출퇴근용 vs 여가용 추정/시각화 스크립트
"""

import os
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CHARTS_DIR = os.path.join(BASE_DIR, 'charts')
os.makedirs(CHARTS_DIR, exist_ok=True)

# 한글 폰트 설정
plt.rc('font', family='Malgun Gothic')
plt.rc('axes', unicode_minus=False)

# 데이터 로드
trips_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_trips_sample.csv'))
stations_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_stations.csv'))
monthly_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_monthly_demand_2021_2026.csv'))

# -------------------------------------------------------------
# 1. 2021 ~ 2026 최근 5개년 송파구 월별 수요 추이 차트
# -------------------------------------------------------------
monthly_total = monthly_df.groupby('기준년월')['대여건수'].sum().reset_index()
monthly_total['기준년월'] = monthly_total['기준년월'].astype(str)
monthly_total['연도'] = monthly_total['기준년월'].str[:4]
monthly_total['월'] = monthly_total['기준년월'].str[4:6]

plt.figure(figsize=(14, 5))
plt.plot(monthly_total['기준년월'], monthly_total['대여건수'] / 10000, marker='o', color='#2b5c8f', linewidth=2, markersize=4)
plt.title('서울시 송파구 따릉이 월별 대여량 추이 (2021년 ~ 2026년)', fontsize=15, fontweight='bold', pad=15)
plt.xlabel('기준년월', fontsize=12)
plt.ylabel('월간 대여건수 (만 건)', fontsize=12)
plt.grid(True, linestyle='--', alpha=0.5)

# x축 레이블 간격 조절
step = max(len(monthly_total) // 12, 1)
plt.xticks(ticks=range(0, len(monthly_total), step), labels=monthly_total['기준년월'].iloc[::step], rotation=45)
plt.tight_layout()

chart1_path = os.path.join(CHARTS_DIR, 'monthly_trend_2021_2026.png')
plt.savefig(chart1_path, dpi=300)
plt.close()
print(f"5개년 월별 추이 차트 저장: {chart1_path}")

# -------------------------------------------------------------
# 2. 시간대별(0~23시) 평일 vs 주말 이용곡선 (출퇴근 M자 vs 주말 완만 곡선)
# -------------------------------------------------------------
hourly_pattern = trips_df.groupby(['대여시간대', '요일구분']).size().unstack(fill_value=0)
# 백분율 정규화 (패턴 비교)
hourly_pct = hourly_pattern.div(hourly_pattern.sum(axis=0), axis=1) * 100

plt.figure(figsize=(12, 6))
plt.plot(hourly_pct.index, hourly_pct['평일'], marker='o', linewidth=2.5, color='#e41a1c', label='평일 (출퇴근 M자형 피크)')
plt.plot(hourly_pct.index, hourly_pct['주말'], marker='s', linewidth=2.5, color='#377eb8', label='주말 (오후 여가/레저 단봉형 피크)')

# 출퇴근 및 여가 영역 강조
plt.axvspan(7, 9, color='#ffcccc', alpha=0.35, label='출근 시간대 (07~09시)')
plt.axvspan(17, 20, color='#ffe0b2', alpha=0.35, label='퇴근 시간대 (17~20시)')
plt.axvspan(13, 17, color='#cce5ff', alpha=0.35, label='주말 여가 피크 (13~17시)')

plt.title('송파구 시간대별 따릉이 이용 패턴 (평일 vs 주말)', fontsize=15, fontweight='bold', pad=15)
plt.xlabel('시간대 (0시 ~ 23시)', fontsize=12)
plt.ylabel('이용 비중 (%)', fontsize=12)
plt.xticks(range(0, 24))
plt.grid(True, linestyle='--', alpha=0.5)
plt.legend(fontsize=11, loc='upper left')
plt.tight_layout()

chart2_path = os.path.join(CHARTS_DIR, 'hourly_weekday_weekend_pattern.png')
plt.savefig(chart2_path, dpi=300)
plt.close()
print(f"시간대별 평일 vs 주말 패턴 차트 저장: {chart2_path}")

# -------------------------------------------------------------
# 3. 요일 x 시간대 24x7 히트맵
# -------------------------------------------------------------
day_order = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
heatmap_data = trips_df.pivot_table(index='요일한글', columns='대여시간대', values='대여일시', aggfunc='count', fill_value=0)
heatmap_data = heatmap_data.reindex(day_order)

plt.figure(figsize=(15, 6))
sns.heatmap(heatmap_data, cmap='YlOrRd', linewidths=0.5, cbar_kws={'label': '대여 건수'})
plt.title('송파구 요일 및 시간대별 따릉이 통행량 히트맵 (24x7 Heatmap)', fontsize=15, fontweight='bold', pad=15)
plt.xlabel('대여 시간대 (0시 ~ 23시)', fontsize=12)
plt.ylabel('요일', fontsize=12)
plt.tight_layout()

chart3_path = os.path.join(CHARTS_DIR, 'day_of_week_heatmap.png')
plt.savefig(chart3_path, dpi=300)
plt.close()
print(f"요일 x 시간대 히트맵 차트 저장: {chart3_path}")

# -------------------------------------------------------------
# 4. 출퇴근용 vs 여가용(간헐적 사용) 추정 분류 및 대여소별 프로파일링
# -------------------------------------------------------------
"""
[출퇴근용 vs 여가용 추정 기준]
1. 통행 단위 기준:
   - 출퇴근 통행(Commute):
     * 평일(월~금) & 출근시간(07~09시) 또는 퇴근시간(17~20시)
     * 제자리 반납이 아님 (편도 통행, A != B)
     * 평균 소요시간 25분 이내
   - 여가/레저 통행(Leisure):
     * 주말(토/일) 통행 OR 평일 낮(11~16시) / 야간(20시 이후)
     * 제자리 반납(A == B) 통행 (공원/호수 일주형)
     * 또는 한강공원, 석촌호수, 올림픽공원 인근 대여소 이용
     * 평균 소요시간 30분 이상 장시간 이용
"""

leisure_keywords = ['한강', '석촌호수', '올림픽공원', '탄천', '아시아공원', '근린공원', '체육공원', '유수지', '생태공원']
subway_keywords = ['역', '출구']

def is_leisure_place(name):
    return any(k in str(name) for k in leisure_keywords)

def is_subway_place(name):
    return any(k in str(name) for k in subway_keywords)

# 개별 통행 라벨링
def classify_trip(row):
    is_weekday = (row['요일구분'] == '평일')
    hour = row['대여시간대']
    is_rush_hour = is_weekday and ((7 <= hour <= 9) or (17 <= hour <= 20))
    is_round = (row['대여대여소번호'] == row['반납대여소번호'])
    leisure_station = is_leisure_place(row['대여 대여소명']) or is_leisure_place(row['반납대여소명'])
    subway_station = is_subway_place(row['대여 대여소명']) or is_subway_place(row['반납대여소명'])
    duration = row['이용시간(분)']
    
    # 여가용 조건
    if is_round or leisure_station or (row['요일구분'] == '주말' and 11 <= hour <= 18) or (duration >= 40 and not is_rush_hour):
        return '여가용(레저/간헐적)'
    # 출퇴근 조건
    elif is_rush_hour or (is_weekday and subway_station and duration <= 25):
        return '출퇴근용(통근/통학)'
    else:
        return '일반생활/기타'

trips_df['통행목적_추정'] = trips_df.apply(classify_trip, axis=1)

purpose_counts = trips_df['통행목적_추정'].value_counts()
print("\n[통행 목적별 추정 통계]")
for p, c in purpose_counts.items():
    print(f" - {p}: {c:,}건 ({c/len(trips_df)*100:.1f}%)")

# -------------------------------------------------------------
# 5. 대여소별 출퇴근 특화 vs 여가 특화 프로파일링
# -------------------------------------------------------------
st_purpose = trips_df.groupby(['대여대여소번호', '대여 대여소명', '통행목적_추정']).size().unstack(fill_value=0)
st_purpose['총대여건수'] = st_purpose.sum(axis=1)

# 최소 50건 이상 표본 대여소
st_purpose = st_purpose[st_purpose['총대여건수'] >= 50].copy()
st_purpose['출퇴근비율'] = (st_purpose.get('출퇴근용(통근/통학)', 0) / st_purpose['총대여건수']) * 100
st_purpose['여가비율'] = (st_purpose.get('여가용(레저/간헐적)', 0) / st_purpose['총대여건수']) * 100
st_purpose['제자리반납건수'] = trips_df[trips_df['대여대여소번호'] == trips_df['반납대여소번호']].groupby('대여대여소번호').size()
st_purpose['제자리반납건수'] = st_purpose['제자리반납건수'].fillna(0).astype(int)
st_purpose['제자리반납비율'] = (st_purpose['제자리반납건수'] / st_purpose['총대여건수']) * 100

def classify_station_type(r):
    if r['여가비율'] >= 50 or r['제자리반납비율'] >= 15:
        return '여가/레저 특화형'
    elif r['출퇴근비율'] >= 45:
        return '출퇴근 특화형'
    else:
        return '생활/복합형'

st_purpose['대여소_특성분류'] = st_purpose.apply(classify_station_type, axis=1)
st_purpose = st_purpose.reset_index()

st_purpose_path = os.path.join(DATA_DIR, 'songpa_station_commute_analysis.csv')
st_purpose.to_csv(st_purpose_path, index=False, encoding='utf-8-sig')
print(f"대여소별 출퇴근 vs 여가 프로파일 저장: {st_purpose_path}")

# 차트 4: 대여소 특성 분류 시각화 (산점도)
plt.figure(figsize=(11, 7))
palette = {'출퇴근 특화형': '#e41a1c', '여가/레저 특화형': '#377eb8', '생활/복합형': '#4daf4a'}

sns.scatterplot(
    data=st_purpose,
    x='출퇴근비율',
    y='여가비율',
    hue='대여소_특성분류',
    size='총대여건수',
    sizes=(40, 400),
    palette=palette,
    alpha=0.85
)

# 대표 대여소 텍스트 주석
for _, r in st_purpose.sort_values('여가비율', ascending=False).head(5).iterrows():
    plt.annotate(r['대여 대여소명'], (r['출퇴근비율'], r['여가비율']), fontsize=9, xytext=(4, 4), textcoords='offset points', color='#08519c', fontweight='bold')

for _, r in st_purpose.sort_values('출퇴근비율', ascending=False).head(5).iterrows():
    plt.annotate(r['대여 대여소명'], (r['출퇴근비율'], r['여가비율']), fontsize=9, xytext=(4, 4), textcoords='offset points', color='#a50f15', fontweight='bold')

plt.title('송파구 대여소별 출퇴근용 vs 여가용 특성 분포 (Classification)', fontsize=15, fontweight='bold', pad=15)
plt.xlabel('출퇴근 통행 비중 (%)', fontsize=12)
plt.ylabel('여가/레저 통행 비중 (%)', fontsize=12)
plt.grid(True, linestyle='--', alpha=0.5)
plt.legend(title='대여소 특성 분류', fontsize=10, title_fontsize=11)
plt.tight_layout()

chart4_path = os.path.join(CHARTS_DIR, 'station_type_classification.png')
plt.savefig(chart4_path, dpi=300)
plt.close()
print(f"대여소 특성 분류 산점도 차트 저장: {chart4_path}")

print("\n모든 시각화 및 출퇴근/여가 추정 분석이 완료되었습니다!")
