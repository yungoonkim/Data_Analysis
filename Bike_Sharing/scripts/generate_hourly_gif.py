"""
송파구 따릉이 24시간 시간대별 통행 흐름 타임랩스 GIF 생성 스크립트
- 개별 통행 경로를 시간대별(00시~23시)로 지도 위에 시각화
- CartoDB Dark Matter 타일 베이스맵 위에 개별 통행 라인 및 대여소 발광 효과
- 24시간 미니 막대그래프, 디지털 시계 HUD, 핵심 지표 오버레이
- Pillow 기반 최적화된 고화질 animated GIF 출력
"""

import os
import io
import math
import sys
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.collections import LineCollection
from PIL import Image

# 윈도우 UTF-8 콘솔 출력 보장
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CHARTS_DIR = os.path.join(BASE_DIR, 'charts')
os.makedirs(CHARTS_DIR, exist_ok=True)

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# 1. 데이터 로드
print("[1/4] 데이터 로드 중...")
stations_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_stations.csv'), encoding='utf-8')
trips_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_trips_sample.csv'), encoding='utf-8')

# 대여소 좌표 딕셔너리
st_dict = stations_df.set_index('대여소번호')[['위도', '경도', '대여소명']].to_dict('index')

# 통행 데이터에 출발/도착 위경도 매핑
trips_df['출발_위도'] = trips_df['대여대여소번호'].map(lambda x: st_dict.get(x, {}).get('위도'))
trips_df['출발_경도'] = trips_df['대여대여소번호'].map(lambda x: st_dict.get(x, {}).get('경도'))
trips_df['도착_위도'] = trips_df['반납대여소번호'].map(lambda x: st_dict.get(x, {}).get('위도'))
trips_df['도착_경도'] = trips_df['반납대여소번호'].map(lambda x: st_dict.get(x, {}).get('경도'))

# 결측치 및 왕복 통행(출발==도착) 제외한 유효 이동 경로
valid_trips = trips_df.dropna(subset=['출발_위도', '출발_경도', '도착_위도', '도착_경도']).copy()
diff_trips = valid_trips[valid_trips['대여대여소번호'] != valid_trips['반납대여소번호']].copy()

# 24시간 통계량 계산
hourly_totals = trips_df['대여시간대'].value_counts().sort_index().to_dict()
total_trips_count = len(trips_df)

print(f"  - 전체 통행: {total_trips_count:,}건, 편도 이동: {len(diff_trips):,}건")

# 2. CartoDB Dark Matter 베이스맵 타일 준비
print("[2/4] 베이스맵 타일 확인 및 스티칭...")
def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

def num2deg(xtile, ytile, zoom):
    n = 1 << zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg

def lat2y(lat):
    lat_rad = math.radians(lat)
    return math.log(math.tan(math.pi / 4 + lat_rad / 2))

zoom = 13
x_min, y_min = 6987, 3172
x_max, y_max = 6989, 3175

lat_top, lng_left = num2deg(x_min, y_min, zoom)
lat_bottom, lng_right = num2deg(x_max + 1, y_max + 1, zoom)

tile_cache_path = os.path.join(CHARTS_DIR, 'songpa_dark_basemap.png')
if os.path.exists(tile_cache_path):
    basemap_img = Image.open(tile_cache_path).convert('RGB')
    print("  - 캐시된 베이스맵 로드 완료")
else:
    width = (x_max - x_min + 1) * 256
    height = (y_max - y_min + 1) * 256
    basemap_img = Image.new('RGB', (width, height))
    headers = {'User-Agent': 'Mozilla/5.0'}
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            url = f'https://cartodb-basemaps-a.global.ssl.fastly.net/dark_all/{zoom}/{x}/{y}.png'
            try:
                r = requests.get(url, headers=headers, timeout=8)
                if r.status_code == 200:
                    tile = Image.open(io.BytesIO(r.content))
                    basemap_img.paste(tile, ((x - x_min) * 256, (y - y_min) * 256))
            except Exception as e:
                print(f"Tile fetch error {x},{y}: {e}")
    basemap_img.save(tile_cache_path)
    print("  - 신규 베이스맵 다운로드 및 저장 완료")

# 픽셀 변환 함수
img_w, img_h = basemap_img.size
y_top_m = lat2y(lat_top)
y_bottom_m = lat2y(lat_bottom)

def to_xy(lat, lng):
    x = (lng - lng_left) / (lng_right - lng_left) * img_w
    y = (y_top_m - lat2y(lat)) / (y_top_m - y_bottom_m) * img_h
    return x, y

# 대여소 픽셀 좌표 미리 계산
stations_df['px'] = stations_df.apply(lambda r: to_xy(r['위도'], r['경도'])[0], axis=1)
stations_df['py'] = stations_df.apply(lambda r: to_xy(r['위도'], r['경도'])[1], axis=1)
st_px_map = stations_df.set_index('대여소번호')[['px', 'py', '대여소명']].to_dict('index')

# 송파구 주요 랜드마크 픽셀 좌표
landmarks = [
    ("잠실역", 37.5133, 127.1001, "#38bdf8"),
    ("올림픽공원", 37.5209, 127.1213, "#4ade80"),
    ("가락시장역", 37.4925, 127.1182, "#facc15"),
    ("문정법조단지", 37.4855, 127.1220, "#c084fc"),
    ("석촌호수", 37.5090, 127.1030, "#67e8f9"),
    ("거여·마천", 37.4980, 127.1480, "#f87171"),
]
lm_pixels = [(name, to_xy(lat, lng)[0], to_xy(lat, lng)[1], color) for name, lat, lng, color in landmarks]

# 3. 시간대별 프레임 렌더링
print("[3/4] 24개 시간대 프레임 렌더링 중...")

def get_hour_desc(h):
    if 7 <= h <= 9:
        return "[아침 출근 피크] 주거지(거여·마천·방이) -> 주요 지하철역(잠실·가락·올림픽공원) 집중 유입", "#ef4444"
    elif 17 <= h <= 19:
        return "[저녁 퇴근 피크] 업무지구(잠실·문정) -> 주거지 역방향 대규모 분산 유출 (일 최대 통행)", "#f97316"
    elif 11 <= h <= 15:
        return "[주간 일상/레저] 올림픽공원·석촌호수·한강공원 주변 순환 및 상업지구 통행", "#22c55e"
    elif 21 <= h <= 23:
        return "[야간 귀가/심야] 주요 간선도로(송파대로) 및 지하철역 주변 단거리 이동", "#a855f7"
    elif 0 <= h <= 4:
        return "[새벽/심야 한산] 심야 대중교통 종료 후 송파대로 및 거여·마천 방면 귀가 통행", "#64748b"
    else:
        return "[이른 아침/등교] 조간 운동 및 학교·학원가 이동 서서히 증가", "#06b6d4"

frames = []

for h in range(24):
    sub = diff_trips[diff_trips['대여시간대'] == h]
    h_total = hourly_totals.get(h, 0)
    pct = (h_total / total_trips_count) * 100
    avg_dist = sub['이용거리(M)'].mean() if len(sub) > 0 else 0
    avg_dur = sub['이용시간(분)'].mean() if len(sub) > 0 else 0
    desc_text, badge_color = get_hour_desc(h)
    
    # 해당 시간대 대여소별 이용량
    dep_h = sub.groupby('대여대여소번호').size().to_dict()
    arr_h = sub.groupby('반납대여소번호').size().to_dict()
    
    # 상위 OD 통행 경로 Top 3
    top_od = sub.groupby(['대여 대여소명', '반납대여소명']).size().reset_index(name='건수').sort_values('건수', ascending=False).head(3)
    
    # Figure 생성
    fig = plt.figure(figsize=(15, 9.5), facecolor='#0b1120', dpi=110)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1.0], wspace=0.08)
    
    # [좌측 패널]: 지도 플롯
    ax_map = fig.add_subplot(gs[0])
    ax_map.set_facecolor('#0b1120')
    ax_map.imshow(basemap_img, aspect='equal')
    
    # 개별 이동 선 생성 (LineCollection으로 고속 렌더링)
    lines = []
    line_colors = []
    line_widths = []
    
    if 7 <= h <= 9 or 17 <= h <= 19:
        base_color = (1.0, 0.35, 0.1) # 네온 오렌지
    elif 10 <= h <= 16:
        base_color = (0.0, 0.9, 0.7) # 네온 시안
    else:
        base_color = (0.7, 0.4, 1.0) # 네온 퍼플
        
    for _, tr in sub.iterrows():
        st1 = st_px_map.get(tr['대여대여소번호'])
        st2 = st_px_map.get(tr['반납대여소번호'])
        if st1 and st2:
            lines.append([(st1['px'], st1['py']), (st2['px'], st2['py'])])
            line_widths.append(0.75)
            alpha = max(0.06, min(0.35, 120.0 / (len(sub) + 1)))
            line_colors.append((*base_color, alpha))
            
    if lines:
        lc = LineCollection(lines, colors=line_colors, linewidths=line_widths, zorder=3)
        ax_map.add_collection(lc)
        
    # 대여소 마커 플롯
    st_px = stations_df['px'].values
    st_py = stations_df['py'].values
    st_traffic = np.array([dep_h.get(sid, 0) + arr_h.get(sid, 0) for sid in stations_df['대여소번호']])
    
    # 기본 대여소 위치 (미세한 점)
    ax_map.scatter(st_px, st_py, s=6, c='#64748b', alpha=0.5, zorder=4)
    
    # 활성 대여소 발광 마커
    active_idx = st_traffic > 0
    if np.any(active_idx):
        sizes = 15 + np.sqrt(st_traffic[active_idx]) * 18
        nets = np.array([arr_h.get(sid, 0) - dep_h.get(sid, 0) for sid in stations_df.loc[active_idx, '대여소번호']])
        marker_colors = np.where(nets > 1, '#38bdf8', np.where(nets < -1, '#f97316', '#4ade80'))
        
        # 외부 글로우 링
        ax_map.scatter(st_px[active_idx], st_py[active_idx], s=sizes * 2.2, c=marker_colors, alpha=0.18, zorder=5)
        # 중심 코어
        ax_map.scatter(st_px[active_idx], st_py[active_idx], s=sizes, c=marker_colors, edgecolors='#ffffff', linewidths=0.6, alpha=0.9, zorder=6)
        
    # 주요 랜드마크 라벨 표시
    for name, lx, ly, col in lm_pixels:
        ax_map.scatter([lx], [ly], s=35, c=col, marker='^', zorder=8)
        ax_map.annotate(
            name, (lx, ly - 10),
            color='#f8fafc', fontsize=9.5, fontweight='bold', ha='center', va='top',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='#0f172a', edgecolor=col, alpha=0.85, lw=0.8),
            zorder=9
        )
        
    # 맵 영역 크롭
    ax_map.set_xlim(110, 690)
    ax_map.set_ylim(810, 260)
    ax_map.axis('off')
    
    # 맵 상단 캡션
    ax_map.text(
        130, 285, "송파구 따릉이 개별 이동 흐름 맵",
        color='#94a3b8', fontsize=11, fontweight='bold', va='top', zorder=10
    )
    
    # [우측 패널]: 대시보드 HUD
    ax_hud = fig.add_subplot(gs[1])
    ax_hud.set_facecolor('#0f172a')
    ax_hud.axis('off')
    
    am_pm = "오전" if h < 12 else "오후"
    disp_h = h if h <= 12 else h - 12
    if disp_h == 0: disp_h = 12
    clock_str = f"{h:02d}:00"
    period_str = f"{am_pm} {disp_h}시"
    
    ax_hud.text(0.04, 0.94, "[송파구 따릉이] 24시간 통행 흐름 분석", color='#38bdf8', fontsize=14, fontweight='bold', va='top')
    
    # 시계 배지 박스
    rect_clock = patches.FancyBboxPatch((0.04, 0.81), 0.92, 0.10, boxstyle="round,pad=0.015", fc='#1e293b', ec=badge_color, lw=1.8)
    ax_hud.add_patch(rect_clock)
    ax_hud.text(0.08, 0.885, f"TIME: {clock_str}", color='#f8fafc', fontsize=22, fontweight='bold', va='center')
    ax_hud.text(0.48, 0.885, f"({period_str})", color=badge_color, fontsize=15, fontweight='bold', va='center')
    ax_hud.text(0.08, 0.835, desc_text, color='#cbd5e1', fontsize=9.2, va='center')
    
    # 메트릭스 카드 3개
    c1 = patches.FancyBboxPatch((0.04, 0.66), 0.28, 0.12, boxstyle="round,pad=0.01", fc='#1e293b', ec='#334155', lw=1)
    ax_hud.add_patch(c1)
    ax_hud.text(0.06, 0.75, "시간대 통행량", color='#94a3b8', fontsize=9.5, va='top')
    ax_hud.text(0.06, 0.69, f"{h_total:,}건", color='#f8fafc', fontsize=14, fontweight='bold', va='center')
    ax_hud.text(0.06, 0.67, f"전체의 {pct:.1f}%", color=badge_color, fontsize=8.5, va='center')
    
    c2 = patches.FancyBboxPatch((0.36, 0.66), 0.28, 0.12, boxstyle="round,pad=0.01", fc='#1e293b', ec='#334155', lw=1)
    ax_hud.add_patch(c2)
    ax_hud.text(0.38, 0.75, "평균 이동거리", color='#94a3b8', fontsize=9.5, va='top')
    ax_hud.text(0.38, 0.69, f"{avg_dist/1000:.2f} km", color='#f8fafc', fontsize=14, fontweight='bold', va='center')
    ax_hud.text(0.38, 0.67, f"{avg_dist:.0f} m", color='#38bdf8', fontsize=8.5, va='center')
    
    c3 = patches.FancyBboxPatch((0.68, 0.66), 0.28, 0.12, boxstyle="round,pad=0.01", fc='#1e293b', ec='#334155', lw=1)
    ax_hud.add_patch(c3)
    ax_hud.text(0.70, 0.75, "평균 소요시간", color='#94a3b8', fontsize=9.5, va='top')
    ax_hud.text(0.70, 0.69, f"{avg_dur:.1f} 분", color='#f8fafc', fontsize=14, fontweight='bold', va='center')
    speed = (avg_dist / 1000) / (avg_dur / 60) if avg_dur > 0 else 0
    ax_hud.text(0.70, 0.67, f"시속 약 {speed:.1f}km/h", color='#4ade80', fontsize=8.5, va='center')
    
    # 24시간 통행량 미니 막대그래프
    ax_hud.text(0.04, 0.61, "[24시간 통행량 분포] - 현재 시간대 하이라이트", color='#94a3b8', fontsize=10, fontweight='bold', va='top')
    
    ax_bar = fig.add_axes([0.585, 0.36, 0.38, 0.17], facecolor='#1e293b')
    hours = list(range(24))
    counts = [hourly_totals.get(hr, 0) for hr in hours]
    bar_colors = [badge_color if hr == h else '#334155' for hr in hours]
    
    bars = ax_bar.bar(hours, counts, color=bar_colors, width=0.8, edgecolor='none')
    ax_bar.set_xlim(-0.8, 23.8)
    ax_bar.set_ylim(0, max(counts) * 1.15)
    ax_bar.set_xticks([0, 4, 8, 12, 16, 20, 23])
    ax_bar.set_xticklabels(['00', '04', '08', '12', '16', '20', '23시'], color='#94a3b8', fontsize=7.5)
    ax_bar.tick_params(colors='#94a3b8', labelsize=7.5, length=2)
    ax_bar.grid(axis='y', color='#334155', linestyle='--', alpha=0.5)
    for spine in ax_bar.spines.values():
        spine.set_color('#334155')
        
    curr_cnt = hourly_totals.get(h, 0)
    ax_bar.annotate(
        f"{curr_cnt:,}", (h, curr_cnt),
        textcoords="offset points", xytext=(0, 3), ha='center',
        color=badge_color, fontsize=8, fontweight='bold'
    )
    
    # 상위 통행 경로 Top 3 리스트 박스
    rect_top = patches.FancyBboxPatch((0.04, 0.08), 0.92, 0.23, boxstyle="round,pad=0.015", fc='#1e293b', ec='#334155', lw=1)
    ax_hud.add_patch(rect_top)
    ax_hud.text(0.07, 0.28, f"[TOP 3] {h:02d}시 최다 통행 경로 (출발 -> 도착)", color='#facc15', fontsize=10.5, fontweight='bold', va='center')
    
    y_pos = 0.23
    if len(top_od) > 0:
        for idx, (_, r_top) in enumerate(top_od.iterrows()):
            rank_col = ['#f59e0b', '#94a3b8', '#b45309'][idx]
            st_dep = r_top['대여 대여소명']
            st_arr = r_top['반납대여소명']
            if len(st_dep) > 13: st_dep = st_dep[:12] + "…"
            if len(st_arr) > 13: st_arr = st_arr[:12] + "…"
            cnt_val = r_top['건수']
            
            ax_hud.text(0.07, y_pos, f"#{idx+1}", color=rank_col, fontsize=10, fontweight='bold', va='center')
            ax_hud.text(0.13, y_pos, f"{st_dep} -> {st_arr}", color='#f8fafc', fontsize=9.2, va='center')
            ax_hud.text(0.88, y_pos, f"{cnt_val}건", color=badge_color, fontsize=9.5, fontweight='bold', ha='right', va='center')
            y_pos -= 0.045
    else:
        ax_hud.text(0.07, 0.21, "해당 시간대 유효 통행 기록 없음", color='#64748b', fontsize=9.5, va='center')
        
    ax_hud.text(
        0.04, 0.03,
        "● 파랑: 순유입 우세 대여소 | ● 빨강: 순유출 우세 대여소 | 선 밀도: 개별 따릉이 실시간 이동 궤적",
        color='#64748b', fontsize=8, va='center'
    )
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#0b1120', edgecolor='none')
    buf.seek(0)
    img_frame = Image.open(buf).convert('RGB')
    frames.append(img_frame)
    plt.close(fig)
    print(f"  - [{h+1:02d}/24] {h:02d}시 프레임 렌더링 완료 ({h_total:,}건)")

# 4. Animated GIF로 조합 및 저장
print("[4/4] 타임랩스 Animated GIF 생성 및 저장 중...")
gif_output_path = os.path.join(CHARTS_DIR, 'songpa_bike_hourly_flow_timelapse.gif')

durations = [950 if hr in [8, 18] else (750 if hr in [7, 9, 17, 19] else 550) for hr in range(24)]

frames[0].save(
    gif_output_path,
    save_all=True,
    append_images=frames[1:],
    duration=durations,
    loop=0,
    optimize=True
)

file_size_mb = os.path.getsize(gif_output_path) / (1024 * 1024)
print(f"성공! 24시간 따릉이 타임랩스 GIF 생성 완료: {gif_output_path} ({file_size_mb:.2f} MB)")
