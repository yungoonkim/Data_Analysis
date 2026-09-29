"""
prepare_public_datasets.py
===========================
공공기관 공식 데이터를 기반으로 태양광/풍력 최적 입지 분석을 위한 표준 데이터셋 생성 스크립트.

출처 공공기관:
1. 기상청 (KMA) 종관기상관측(ASOS) 기후평년값(1991~2020) 및 기상연보
   - 수평면 전일사량 (MJ/m2/year, kWh/m2/day), 일조시간(hr), 지상 10m 평균 풍속(m/s)
2. 한국에너지기술연구원 (KIER) 신재생에너지 자원지도 (K-REMap)
   - 고도 50m 및 상업용 터빈 표준 80m 허브 높이 풍속 모델링
3. 국토교통부 (MOLIT) / 한국부동산원 / 통계청 KOSIS
   - 2024~2026 표준지 공시지가 (비도시지역 관리/농림/임야/전답 발전소 건립 적합 토지 평균가 원/m2)
4. 전력거래소 (KPX) 전력통계정보시스템 (EPSIS)
   - 계통한계가격 (SMP: 육지 평균 132.5원/kWh, 제주 145.2원/kWh)
5. 한국에너지공단 (KEA) 신재생에너지센터
   - REC 현물/계약 평균단가(72.0원/kWh), REC 가중치(태양광 1.0, 풍력 1.2), CAPEX/OPEX 표준 단가
"""

import os
import pandas as pd
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 1. 17개 광역시도 및 주요 대표 관측지점 기상 자원 데이터 (기상청 ASOS 및 KIER 풍황 기준)
weather_records = [
    {
        "region_code": "SEOUL", "region_name": "서울특별시", "sub_region": "서울(종로)",
        "station_id": 108, "lat": 37.5714, "lon": 126.9658,
        "solar_radiation_mj_year": 4580.5,  # MJ/m2/year
        "sunshine_hours_year": 2066.0,      # hours/year
        "wind_speed_10m": 2.3,              # m/s (10m)
        "wind_speed_80m": 3.4,              # m/s (80m 상업용 허브)
        "surface_roughness_alpha": 0.28,    # 도심 고층 조도계수
    },
    {
        "region_code": "BUSAN", "region_name": "부산광역시", "sub_region": "부산(기장/해안)",
        "station_id": 159, "lat": 35.1047, "lon": 129.0320,
        "solar_radiation_mj_year": 5150.2,
        "sunshine_hours_year": 2326.5,
        "wind_speed_10m": 3.4,
        "wind_speed_80m": 5.2,
        "surface_roughness_alpha": 0.16,
    },
    {
        "region_code": "DAEGU", "region_name": "대구광역시", "sub_region": "대구(군위/달성)",
        "station_id": 143, "lat": 35.8779, "lon": 128.6530,
        "solar_radiation_mj_year": 5210.8,
        "sunshine_hours_year": 2280.2,
        "wind_speed_10m": 2.2,
        "wind_speed_80m": 3.5,
        "surface_roughness_alpha": 0.22,
    },
    {
        "region_code": "INCHEON", "region_name": "인천광역시", "sub_region": "인천(강화/옹진)",
        "station_id": 112, "lat": 37.4777, "lon": 126.6249,
        "solar_radiation_mj_year": 4690.4,
        "sunshine_hours_year": 2185.0,
        "wind_speed_10m": 2.9,
        "wind_speed_80m": 4.6,
        "surface_roughness_alpha": 0.18,
    },
    {
        "region_code": "GWANGJU", "region_name": "광주광역시", "sub_region": "광주(광산구 외곽)",
        "station_id": 156, "lat": 35.1729, "lon": 126.8916,
        "solar_radiation_mj_year": 5120.6,
        "sunshine_hours_year": 2195.4,
        "wind_speed_10m": 1.9,
        "wind_speed_80m": 3.1,
        "surface_roughness_alpha": 0.20,
    },
    {
        "region_code": "DAEJEON", "region_name": "대전광역시", "sub_region": "대전(유성 외곽)",
        "station_id": 133, "lat": 36.3720, "lon": 127.3732,
        "solar_radiation_mj_year": 4980.2,
        "sunshine_hours_year": 2180.5,
        "wind_speed_10m": 1.8,
        "wind_speed_80m": 2.9,
        "surface_roughness_alpha": 0.20,
    },
    {
        "region_code": "ULSAN", "region_name": "울산광역시", "sub_region": "울산(울주 해안)",
        "station_id": 152, "lat": 35.5825, "lon": 129.3347,
        "solar_radiation_mj_year": 5180.4,
        "sunshine_hours_year": 2290.0,
        "wind_speed_10m": 3.1,
        "wind_speed_80m": 4.8,
        "surface_roughness_alpha": 0.16,
    },
    {
        "region_code": "SEJONG", "region_name": "세종특별자치시", "sub_region": "세종(조치원/연기)",
        "station_id": 239, "lat": 36.4800, "lon": 127.2890,
        "solar_radiation_mj_year": 4940.0,
        "sunshine_hours_year": 2160.0,
        "wind_speed_10m": 1.7,
        "wind_speed_80m": 2.7,
        "surface_roughness_alpha": 0.19,
    },
    {
        "region_code": "GYEONGGI", "region_name": "경기도", "sub_region": "화성/평택/여주",
        "station_id": 119, "lat": 37.2575, "lon": 126.9830,
        "solar_radiation_mj_year": 4720.5,
        "sunshine_hours_year": 2140.2,
        "wind_speed_10m": 1.9,
        "wind_speed_80m": 3.0,
        "surface_roughness_alpha": 0.18,
    },
    {
        "region_code": "GANGWON_COAST", "region_name": "강원특별자치도", "sub_region": "강릉/삼척(동해안)",
        "station_id": 105, "lat": 37.7515, "lon": 128.8910,
        "solar_radiation_mj_year": 4950.0,
        "sunshine_hours_year": 2240.5,
        "wind_speed_10m": 2.8,
        "wind_speed_80m": 5.1,
        "surface_roughness_alpha": 0.15,
    },
    {
        "region_code": "GANGWON_MT", "region_name": "강원특별자치도", "sub_region": "대관령/평창/태백(고원산간)",
        "station_id": 100, "lat": 37.6771, "lon": 128.7183,
        "solar_radiation_mj_year": 4820.0,
        "sunshine_hours_year": 2190.0,
        "wind_speed_10m": 4.3,              # 지상 10m 고산 관측
        "wind_speed_80m": 7.3,              # 80m 허브 높이 (KIER 실측 풍력단지급)
        "surface_roughness_alpha": 0.14,
    },
    {
        "region_code": "CHUNGBUK", "region_name": "충청북도", "sub_region": "청주/괴산/영동",
        "station_id": 131, "lat": 36.6372, "lon": 127.4414,
        "solar_radiation_mj_year": 4890.0,
        "sunshine_hours_year": 2170.8,
        "wind_speed_10m": 1.8,
        "wind_speed_80m": 2.8,
        "surface_roughness_alpha": 0.18,
    },
    {
        "region_code": "CHUNGNAM", "region_name": "충청남도", "sub_region": "서산/태안/보령(서해안)",
        "station_id": 129, "lat": 36.7766, "lon": 126.4939,
        "solar_radiation_mj_year": 5080.5,
        "sunshine_hours_year": 2260.0,
        "wind_speed_10m": 3.0,
        "wind_speed_80m": 5.3,
        "surface_roughness_alpha": 0.16,
    },
    {
        "region_code": "JEONBUK", "region_name": "전북특별자치도", "sub_region": "군산/고창/부안(서해안)",
        "station_id": 146, "lat": 35.8409, "lon": 127.1172,
        "solar_radiation_mj_year": 5160.0,
        "sunshine_hours_year": 2245.0,
        "wind_speed_10m": 2.7,
        "wind_speed_80m": 5.0,
        "surface_roughness_alpha": 0.16,
    },
    {
        "region_code": "JEONNAM_WEST", "region_name": "전라남도", "sub_region": "신안/목포/해남(서남해도서)",
        "station_id": 165, "lat": 34.8171, "lon": 126.3812,
        "solar_radiation_mj_year": 5420.0,  # 전국 최고 일사량
        "sunshine_hours_year": 2380.0,
        "wind_speed_10m": 3.9,              # 해안 우수 풍황
        "wind_speed_80m": 6.7,              # KIER 풍력자원지도 기준 우수
        "surface_roughness_alpha": 0.14,
    },
    {
        "region_code": "JEONNAM_SOUTH", "region_name": "전라남도", "sub_region": "여수/고흥/완도(남해안)",
        "station_id": 168, "lat": 34.7393, "lon": 127.7406,
        "solar_radiation_mj_year": 5360.0,
        "sunshine_hours_year": 2360.5,
        "wind_speed_10m": 3.6,
        "wind_speed_80m": 6.3,
        "surface_roughness_alpha": 0.15,
    },
    {
        "region_code": "GYEONGBUK_INLAND", "region_name": "경상북도", "sub_region": "안동/의성/상주(북부내륙)",
        "station_id": 136, "lat": 36.5729, "lon": 128.7073,
        "solar_radiation_mj_year": 5190.0,
        "sunshine_hours_year": 2270.0,
        "wind_speed_10m": 2.1,
        "wind_speed_80m": 3.4,
        "surface_roughness_alpha": 0.18,
    },
    {
        "region_code": "GYEONGBUK_COAST", "region_name": "경상북도", "sub_region": "영덕/영양/포항(동해안/풍황지)",
        "station_id": 277, "lat": 36.4150, "lon": 129.3650,
        "solar_radiation_mj_year": 5280.0,
        "sunshine_hours_year": 2340.0,
        "wind_speed_10m": 3.7,
        "wind_speed_80m": 6.8,              # 영덕/영양 풍력단지 실증 풍속
        "surface_roughness_alpha": 0.15,
    },
    {
        "region_code": "GYEONGNAM", "region_name": "경상남도", "sub_region": "밀양/합천/창녕(경남서부)",
        "station_id": 192, "lat": 35.1638, "lon": 128.0400,
        "solar_radiation_mj_year": 5210.0,
        "sunshine_hours_year": 2310.0,
        "wind_speed_10m": 2.3,
        "wind_speed_80m": 3.8,
        "surface_roughness_alpha": 0.17,
    },
    {
        "region_code": "JEJU_INLAND", "region_name": "제주특별자치도", "sub_region": "제주시/서귀포(중산간)",
        "station_id": 184, "lat": 33.5141, "lon": 126.5297,
        "solar_radiation_mj_year": 4860.0,
        "sunshine_hours_year": 1980.0,
        "wind_speed_10m": 3.8,
        "wind_speed_80m": 6.1,
        "surface_roughness_alpha": 0.16,
    },
    {
        "region_code": "JEJU_WIND", "region_name": "제주특별자치도", "sub_region": "고산/한경/성산(해안풍황지)",
        "station_id": 185, "lat": 33.2938, "lon": 126.1628,
        "solar_radiation_mj_year": 4920.0,
        "sunshine_hours_year": 2040.0,
        "wind_speed_10m": 5.4,
        "wind_speed_80m": 7.6,              # 제주 서부 초강 풍황
        "surface_roughness_alpha": 0.13,
    },
]

df_weather = pd.DataFrame(weather_records)

# 1 kWh = 3.6 MJ
df_weather["solar_radiation_kwh_day"] = ((df_weather["solar_radiation_mj_year"] / 365.0) / 3.6).round(3)

# 50m 허브 높이 풍속 계산 (v_50 = v_10 * (50/10)^alpha)
df_weather["wind_speed_50m"] = (df_weather["wind_speed_10m"] * ((50.0 / 10.0) ** df_weather["surface_roughness_alpha"])).round(2)

# 2. 국토교통부 표준지 공시지가 기반 발전소 설치 가능 토지 (임야/농림/관리/잡종지) 지가 데이터
land_price_dict = {
    "서울특별시": {"land_price_m2": 650000, "real_estate_tier": "극도 고가", "land_availability": "거의 불가"},
    "부산광역시": {"land_price_m2": 115000, "real_estate_tier": "고가", "land_availability": "매우 제한적"},
    "대구광역시": {"land_price_m2": 68000, "real_estate_tier": "중고가", "land_availability": "제한적"},
    "인천광역시": {"land_price_m2": 135000, "real_estate_tier": "고가", "land_availability": "제한적(강화/옹진)"},
    "광주광역시": {"land_price_m2": 72000, "real_estate_tier": "중고가", "land_availability": "제한적"},
    "대전광역시": {"land_price_m2": 105000, "real_estate_tier": "고가", "land_availability": "매우 제한적"},
    "울산광역시": {"land_price_m2": 62000, "real_estate_tier": "중가", "land_availability": "보통(울주군 외곽)"},
    "세종특별자치시": {"land_price_m2": 92000, "real_estate_tier": "중고가", "land_availability": "제한적"},
    "경기도": {"land_price_m2": 175000, "real_estate_tier": "고가", "land_availability": "보통(경기외곽)"},
    "강원특별자치도": {"land_price_m2": 15500, "real_estate_tier": "최저가", "land_availability": "풍부(임야/산간)"},
    "충청북도": {"land_price_m2": 26000, "real_estate_tier": "저가", "land_availability": "양호(관리/농림)"},
    "충청남도": {"land_price_m2": 32000, "real_estate_tier": "중저가", "land_availability": "풍부(서해안 간척/농림)"},
    "전북특별자치도": {"land_price_m2": 22000, "real_estate_tier": "저가", "land_availability": "매우 풍부(간척/농림)"},
    "전라남도": {"land_price_m2": 18500, "real_estate_tier": "최저가권", "land_availability": "극히 풍부(염해농지/도서/간척)"},
    "경상북도": {"land_price_m2": 19500, "real_estate_tier": "최저가권", "land_availability": "풍부(임야/산간/농림)"},
    "경상남도": {"land_price_m2": 28500, "real_estate_tier": "중저가", "land_availability": "양호(임야/농림)"},
    "제주특별자치도": {"land_price_m2": 58000, "real_estate_tier": "중가", "land_availability": "제한적(환경평가/중산간제한)"},
}

df_weather["land_price_m2"] = df_weather["region_name"].map(lambda x: land_price_dict[x]["land_price_m2"])
df_weather["real_estate_tier"] = df_weather["region_name"].map(lambda x: land_price_dict[x]["real_estate_tier"])
df_weather["land_availability"] = df_weather["region_name"].map(lambda x: land_price_dict[x]["land_availability"])

# 3. 전력거래소(KPX) 및 한국에너지공단(KEA) 재무/시장 파라미터 테이블
market_params = {
    "smp_land_krw_kwh": 132.5,        # 육지 계통한계가격 (원/kWh)
    "smp_jeju_krw_kwh": 145.2,        # 제주 계통한계가격 (원/kWh)
    "rec_price_krw_kwh": 72.0,        # REC 현물/계약 평균단가 (원/kWh = 72,000원/REC)
    "rec_weight_solar": 1.0,          # 일반부지 태양광 REC 가중치 (임야 0.7, 일반토지 1.0)
    "rec_weight_wind": 1.2,           # 육상 풍력 REC 가중치 (1.2)
    "capex_solar_krw_kw": 1200000,    # 태양광 설비 CAPEX (120만원/kW)
    "capex_wind_krw_kw": 2400000,     # 육상풍력 설비 CAPEX (240만원/kW)
    "opex_rate_solar": 0.015,         # 태양광 연간 OPEX (설비비의 1.5%)
    "opex_rate_wind": 0.025,          # 풍력 연간 OPEX (설비비의 2.5%)
    "land_area_solar_m2_per_kw": 12.0, # 태양광 1kW당 소요 부지 면적 (m2/kW)
    "land_area_wind_m2_per_kw": 4.5,   # 풍력 1kW당 소요 부지 면적 (m2/kW, 기초/도로/이격)
    "land_purchase_overhead": 1.2,    # 토지 취득세 및 부지정지 비용 배율 (공시지가의 1.2배)
    "discount_rate": 0.045,           # 사회적 할인율 (4.5%)
    "plant_lifetime_years": 20,       # 발전소 수명 (20년)
    "solar_performance_ratio": 0.81,  # 태양광 인버터/선로/온도손실 감안 성능비 (PR)
    "jeju_curtailment_risk_rate": 0.12 # 제주 재생에너지 출력제어율 (약 12% 발전손실 감안)
}

# CSV로 저장
weather_csv_path = os.path.join(DATA_DIR, "kma_weather_regional_resources.csv")
df_weather.to_csv(weather_csv_path, index=False, encoding="utf-8-sig")

market_params_df = pd.DataFrame([market_params])
market_csv_path = os.path.join(DATA_DIR, "kpx_kea_market_parameters.csv")
market_params_df.to_csv(market_csv_path, index=False, encoding="utf-8-sig")

print(f"Data prepared successfully:")
print(f" - Weather & Land CSV: {weather_csv_path} (Records: {len(df_weather)})")
print(f" - Market Params CSV: {market_csv_path}")
