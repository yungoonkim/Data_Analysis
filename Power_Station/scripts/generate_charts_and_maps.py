"""
generate_charts_and_maps.py
===========================
전국 태양광/풍력 최적 입지 분석 시각화 차트 및 Folium 인터랙티브 지도 생성기.
"""

import os
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import folium
from folium.plugins import MiniMap

# 스타일 설정 후 한글 폰트 적용 (스타일이 폰트를 리셋하지 않도록 순서 보장)
if 'seaborn-v0_8-whitegrid' in plt.style.available:
    plt.style.use('seaborn-v0_8-whitegrid')
else:
    plt.style.use('default')

matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False
plt.rc('font', family='Malgun Gothic')

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")
MAPS_DIR = os.path.join(BASE_DIR, "maps")

os.makedirs(CHARTS_DIR, exist_ok=True)
os.makedirs(MAPS_DIR, exist_ok=True)

df = pd.read_csv(os.path.join(DATA_DIR, "merged_regional_analysis_data.csv"))
df["label"] = df["region_name"] + " (" + df["sub_region"] + ")"

# ----------------------------------------------------
# 1. 태양광 투자 회수 기간 랭킹 차트 (Solar Payback Ranking)
# ----------------------------------------------------
plt.figure(figsize=(12, 8), dpi=300)
df_solar_sorted = df.sort_values(by="solar_payback_years", ascending=True).copy()

colors_solar = ['#e65100' if i == 0 else '#fb8c00' if i < 3 else '#ffa726' if i < 7 else '#78909c' if v < 15 else '#d32f2f' 
                for i, v in enumerate(df_solar_sorted["solar_payback_years"])]

bars = plt.barh(df_solar_sorted["label"], df_solar_sorted["solar_payback_years"], color=colors_solar, height=0.65)
plt.xlabel("단순 투자회수기간 (Simple Payback Period, 년)", fontsize=12, fontweight='bold', labelpad=10)
plt.title("전국 시도별 1MW 태양광 발전소 투자 회수 기간 랭킹 (공공기관 공시지가 & 일사량 반영)", fontsize=14, fontweight='bold', pad=15)
plt.gca().invert_yaxis()
plt.axvline(x=7.0, color='#2e7d32', linestyle='--', linewidth=1.5, label='우수 투자 기준선 (7.0년 이내)')
plt.axvline(x=10.0, color='#c62828', linestyle=':', linewidth=1.5, label='한계 투자 기준선 (10.0년)')

for bar in bars:
    width = bar.get_width()
    text = f"{width:.2f}년" if width < 30 else f"{width:.1f}년 (투자비과다)"
    plt.text(min(width + 0.3, 38.0), bar.get_y() + bar.get_height()/2.0, text,
             ha='left', va='center', fontsize=9, fontweight='bold', color='#212121')

plt.xlim(0, 42)
plt.legend(loc='lower right', fontsize=10)
plt.tight_layout()
solar_chart_path = os.path.join(CHARTS_DIR, "solar_payback_ranking.png")
plt.savefig(solar_chart_path)
plt.close()
print(f"Chart saved: {solar_chart_path}")

# ----------------------------------------------------
# 2. 육상 풍력 투자 회수 기간 랭킹 차트 (Wind Payback Ranking)
# ----------------------------------------------------
plt.figure(figsize=(12, 8), dpi=300)
df_wind_valid = df[df["wind_payback_years"] <= 35.0].sort_values(by="wind_payback_years", ascending=True).copy()

colors_wind = ['#00695c' if i == 0 else '#00897b' if i < 3 else '#26a69a' if i < 6 else '#78909c' 
               for i in range(len(df_wind_valid))]

bars_w = plt.barh(df_wind_valid["label"], df_wind_valid["wind_payback_years"], color=colors_wind, height=0.65)
plt.xlabel("단순 투자회수기간 (Simple Payback Period, 년)", fontsize=12, fontweight='bold', labelpad=10)
plt.title("전국 시도별 1MW 육상 풍력 발전소 투자 회수 기간 랭킹 (80m 허브풍속 & 공시지가 반영)", fontsize=14, fontweight='bold', pad=15)
plt.gca().invert_yaxis()
plt.axvline(x=6.0, color='#00695c', linestyle='--', linewidth=1.5, label='최우수 투자 기준선 (6.0년 이내)')
plt.axvline(x=10.0, color='#c62828', linestyle=':', linewidth=1.5, label='한계 투자 기준선 (10.0년)')

for bar in bars_w:
    width = bar.get_width()
    plt.text(width + 0.3, bar.get_y() + bar.get_height()/2.0, f"{width:.2f}년",
             ha='left', va='center', fontsize=9, fontweight='bold', color='#212121')

plt.xlim(0, max(df_wind_valid["wind_payback_years"]) + 4)
plt.legend(loc='lower right', fontsize=10)
plt.tight_layout()
wind_chart_path = os.path.join(CHARTS_DIR, "wind_payback_ranking.png")
plt.savefig(wind_chart_path)
plt.close()
print(f"Chart saved: {wind_chart_path}")

# ----------------------------------------------------
# 3. 4분면 매트릭스 산점도: 기상 자원 vs 토지 가격 (Matrix Analysis)
# ----------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7), dpi=300)

scatter1 = ax1.scatter(
    df["solar_radiation_mj_year"],
    df["land_price_m2"] / 1000.0,
    s=df["solar_annual_cf_krw"] / 1e6 * 0.8,
    c=df["solar_payback_years"],
    cmap='viridis_r',
    alpha=0.85,
    edgecolors='black',
    linewidth=1.2
)
ax1.set_xlabel("연간 누적 수평면 일사량 (MJ/m2/년)", fontsize=11, fontweight='bold')
ax1.set_ylabel("발전소 적합 토지 공시지가 (천원/m2, Log scale)", fontsize=11, fontweight='bold')
ax1.set_yscale('log')
ax1.set_title("[태양광] 일사량 vs 토지비용 4분면 매트릭스\n(원 크기: 연간 순이익, 색상: 회수기간)", fontsize=12, fontweight='bold')
ax1.axvline(x=5100, color='gray', linestyle=':', alpha=0.7)
ax1.axhline(y=40, color='gray', linestyle=':', alpha=0.7)
cbar1 = fig.colorbar(scatter1, ax=ax1)
cbar1.set_label("투자회수기간 (년)", fontsize=10)

for _, r in df.iterrows():
    if r["region_code"] in ["JEONNAM_WEST", "GANGWON_MT", "GYEONGBUK_COAST", "SEOUL", "GYEONGGI", "JEJU_WIND", "CHUNGNAM"]:
        ax1.annotate(r["region_name"].split()[0], 
                     (r["solar_radiation_mj_year"], r["land_price_m2"] / 1000.0),
                     xytext=(6, 4), textcoords='offset points', fontsize=9, fontweight='bold')

scatter2 = ax2.scatter(
    df["wind_speed_80m"],
    df["land_price_m2"] / 1000.0,
    s=np.maximum(df["wind_annual_cf_krw"] / 1e6 * 0.5, 20),
    c=np.clip(df["wind_payback_years"], 4, 25),
    cmap='plasma_r',
    alpha=0.85,
    edgecolors='black',
    linewidth=1.2
)
ax2.set_xlabel("80m 상업용 허브 높이 평균 풍속 (m/s)", fontsize=11, fontweight='bold')
ax2.set_ylabel("발전소 적합 토지 공시지가 (천원/m2, Log scale)", fontsize=11, fontweight='bold')
ax2.set_yscale('log')
ax2.set_title("[육상풍력] 풍속 vs 토지비용 4분면 매트릭스\n(원 크기: 연간 순이익, 색상: 회수기간)", fontsize=12, fontweight='bold')
ax2.axvline(x=5.5, color='gray', linestyle=':', alpha=0.7)
ax2.axhline(y=40, color='gray', linestyle=':', alpha=0.7)
cbar2 = fig.colorbar(scatter2, ax=ax2)
cbar2.set_label("투자회수기간 (년, 25년 클램프)", fontsize=10)

for _, r in df.iterrows():
    if r["region_code"] in ["JEONNAM_WEST", "GANGWON_MT", "GYEONGBUK_COAST", "SEOUL", "JEJU_WIND", "CHUNGNAM", "BUSAN"]:
        ax2.annotate(r["region_name"].split()[0], 
                     (r["wind_speed_80m"], r["land_price_m2"] / 1000.0),
                     xytext=(6, 4), textcoords='offset points', fontsize=9, fontweight='bold')

plt.tight_layout()
matrix_chart_path = os.path.join(CHARTS_DIR, "solar_vs_wind_matrix.png")
plt.savefig(matrix_chart_path)
plt.close()
print(f"Chart saved: {matrix_chart_path}")

# ----------------------------------------------------
# 4. 태양광 vs 풍력 상위 10개 지역 회수기간 비교 바 차트
# ----------------------------------------------------
top_candidates = df.sort_values(by="best_payback_years").head(10).copy()
x = np.arange(len(top_candidates))
width = 0.35

plt.figure(figsize=(13, 7), dpi=300)
plt.bar(x - width/2, top_candidates["solar_payback_years"], width, label="태양광(Solar)", color="#fb8c00", alpha=0.9)
plt.bar(x + width/2, np.clip(top_candidates["wind_payback_years"], 0, 25), width, label="풍력(Wind)", color="#00897b", alpha=0.9)

plt.xlabel("최적 유망 지역 (시도 및 세부권역)", fontsize=12, fontweight='bold', labelpad=10)
plt.ylabel("단순 투자회수기간 (년)", fontsize=12, fontweight='bold', labelpad=10)
plt.title("전국 유망 지역별 1MW 태양광 vs 육상풍력 투자 회수 속도 정밀 비교", fontsize=14, fontweight='bold', pad=15)
plt.xticks(x, top_candidates["label"], rotation=25, ha='right', fontsize=9, fontweight='bold')
plt.axhline(y=6.0, color='red', linestyle='--', linewidth=1.2, label='초고속 회수 기준선 (6.0년)')
plt.ylim(0, 16)
plt.legend(fontsize=11)
plt.tight_layout()

comparison_chart_path = os.path.join(CHARTS_DIR, "payback_period_comparison.png")
plt.savefig(comparison_chart_path)
plt.close()
print(f"Chart saved: {comparison_chart_path}")

# ----------------------------------------------------
# 5. Folium 전국 인터랙티브 최적 입지 지도 생성 (OpenStreetMap 기본 타일 사용)
# ----------------------------------------------------
center_lat, center_lon = 36.2, 127.8
m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="OpenStreetMap")

# 태양광/풍력 최적지 원형 마커 레이어는 기본 활성화(show=True), 전국 핀 마커는 겹침 방지를 위해 기본 비활성화(show=False)
fg_wind = folium.FeatureGroup(name="💨 풍력 최적지 (Wind Optimal, ≤8.0년)", show=True)
fg_solar = folium.FeatureGroup(name="☀️ 태양광 최적지 (Solar Optimal, ≤6.5년)", show=True)
fg_all = folium.FeatureGroup(name="⚡ 전국 관측지점 종합 (All Stations)", show=False)

def create_popup_html(row):
    return f"""
    <div style="font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; width: 280px; padding: 6px;">
        <h4 style="margin: 0 0 8px 0; color: #1a237e; border-bottom: 2px solid #3f51b5; padding-bottom: 4px;">
            {row['region_name']} <span style="font-size: 12px; color: #666;">({row['sub_region']})</span>
        </h4>
        <table style="width: 100%; font-size: 11px; border-collapse: collapse; line-height: 1.5;">
            <tr style="background: #f5f5f5;"><td style="padding: 3px;"><b>토지 공시지가:</b></td><td style="text-align: right;"><b>{row['land_price_m2']:,} 원/㎡</b></td></tr>
            <tr><td style="padding: 3px;"><b>연간 일사량:</b></td><td style="text-align: right;">{row['solar_radiation_mj_year']:,.1f} MJ/㎡</td></tr>
            <tr style="background: #f5f5f5;"><td style="padding: 3px;"><b>80m 허브풍속:</b></td><td style="text-align: right;">{row['wind_speed_80m']:.1f} m/s (이용률 {row['wind_capacity_factor']*100:.1f}%)</td></tr>
            <tr><td style="padding: 3px;"><b>태양광 회수기간:</b></td><td style="text-align: right; color: #e65100; font-weight: bold;">{row['solar_payback_years']:.2f} 년</td></tr>
            <tr style="background: #f5f5f5;"><td style="padding: 3px;"><b>풍력 회수기간:</b></td><td style="text-align: right; color: #00695c; font-weight: bold;">{row['wind_payback_years']:.2f} 년</td></tr>
            <tr><td style="padding: 3px;"><b>추천 최적 발전:</b></td><td style="text-align: right; color: #b71c1c; font-weight: bold;">{row['optimal_tech']}</td></tr>
            <tr style="background: #e8eaf6;"><td style="padding: 3px;"><b>최단 회수기간:</b></td><td style="text-align: right; color: #1a237e; font-weight: bold; font-size: 12px;">{row['best_payback_years']:.2f} 년</td></tr>
        </table>
    </div>
    """

for _, row in df.iterrows():
    # 1) 풍력 유망 지점 (회수기간 8.0년 이하 - 바깥쪽 대형 청록색 원형 마커, radius=24)
    if row["wind_payback_years"] <= 8.0:
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=24,
            color="#004d40",
            weight=3,
            fill=True,
            fill_color="#00897b",
            fill_opacity=0.55,
            popup=folium.Popup(create_popup_html(row), max_width=320),
            tooltip=f"💨 [풍력 최우수] {row['region_name']} ({row['sub_region']}): 회수 {row['wind_payback_years']:.2f}년"
        ).add_to(fg_wind)

    # 2) 태양광 유망 지점 (회수기간 6.5년 이하 - 안쪽 선명한 주황색 원형 마커, radius=15)
    # 복합 우수 지역에서는 청록색 외부 원 안에 주황색 내부 원이 동심원으로 중첩 표시됨
    if row["solar_payback_years"] <= 6.5:
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=15,
            color="#bf360c",
            weight=3,
            fill=True,
            fill_color="#ff6f00",
            fill_opacity=0.85,
            popup=folium.Popup(create_popup_html(row), max_width=320),
            tooltip=f"☀️ [태양광 최우수] {row['region_name']} ({row['sub_region']}): 회수 {row['solar_payback_years']:.2f}년"
        ).add_to(fg_solar)

    # 3) 전국 종합 지점 핀 마커 (독립된 Popup 할당)
    marker_color = "orange" if row["optimal_tech"] == "태양광(Solar)" else "cadetblue"
    folium.Marker(
        location=[row["lat"], row["lon"]],
        icon=folium.Icon(color=marker_color, icon="bolt", prefix="fa"),
        popup=folium.Popup(create_popup_html(row), max_width=320),
        tooltip=f"⚡ {row['region_name']} ({row['optimal_tech']})"
    ).add_to(fg_all)

# 순서: 풍력(큰 원) -> 태양광(작은 원) -> 전체 핀
fg_wind.add_to(m)
fg_solar.add_to(m)
fg_all.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
MiniMap().add_to(m)

# 플로팅 범례 (Legend)
legend_html = '''
<div style="
    position: fixed; 
    bottom: 30px; 
    left: 30px; 
    width: 250px; 
    height: auto; 
    background-color: rgba(255, 255, 255, 0.93);
    box-shadow: 0 0 15px rgba(0,0,0,0.2);
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 12px;
    font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
    z-index: 9999;
    border: 1px solid #ddd;
    line-height: 1.6;
">
    <div style="font-weight: bold; font-size: 13px; margin-bottom: 8px; color: #1a237e; border-bottom: 2px solid #3f51b5; padding-bottom: 4px;">
        신재생 최적 입지 범례
    </div>
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="display: inline-block; width: 16px; height: 16px; border-radius: 50%; background: #ff6f00; border: 2px solid #bf360c; margin-right: 8px;"></span>
        <span><b>태양광 최적지</b> (회수 ≤ 6.5년)</span>
    </div>
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="display: inline-block; width: 20px; height: 20px; border-radius: 50%; background: #00897b; border: 2px solid #004d40; opacity: 0.7; margin-right: 6px;"></span>
        <span><b>풍력 최적지</b> (회수 ≤ 8.0년)</span>
    </div>
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="position: relative; display: inline-block; width: 22px; height: 22px; margin-right: 6px;">
            <span style="position: absolute; width: 20px; height: 20px; border-radius: 50%; background: #00897b; border: 2px solid #004d40; opacity: 0.6; top: 0; left: 0;"></span>
            <span style="position: absolute; width: 12px; height: 12px; border-radius: 50%; background: #ff6f00; border: 2px solid #bf360c; top: 4px; left: 4px;"></span>
        </span>
        <span><b>태양광·풍력 복합 최적지</b></span>
    </div>
    <div style="font-size: 11px; color: #666; margin-top: 6px; border-top: 1px dashed #ccc; padding-top: 4px;">
        💡 우측 상단 레이어 컨트롤에서<br/>종합 핀 마커 및 발전원별 토글 가능
    </div>
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

map_path = os.path.join(MAPS_DIR, "optimal_power_plant_map.html")
m.save(map_path)
print(f"Interactive Map saved: {map_path}")
print("All charts and maps generated cleanly without font warnings!")
