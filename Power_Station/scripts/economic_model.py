"""
economic_model.py
=================
신재생에너지 발전소(태양광, 풍력 1MW 기준) 공학적 발전량 및 재무 경제성 분석 모듈.
"""

import os
import pandas as pd
import numpy as np

def calculate_discounted_payback(capex, annual_cf, discount_rate=0.045, max_years=35):
    """할인 투자회수기간 (DPB) 계산"""
    if annual_cf <= 0:
        return np.inf
    cumulative_pv = 0.0
    for t in range(1, max_years + 1):
        pv = annual_cf / ((1 + discount_rate) ** t)
        cumulative_pv += pv
        if cumulative_pv >= capex:
            prev_pv = cumulative_pv - pv
            fraction = (capex - prev_pv) / pv
            return round(t - 1 + fraction, 2)
    return round(float(max_years), 1)

def run_economic_analysis():
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    data_dir = os.path.join(base_dir, "data")
    
    weather_path = os.path.join(data_dir, "kma_weather_regional_resources.csv")
    market_path = os.path.join(data_dir, "kpx_kea_market_parameters.csv")
    
    df = pd.read_csv(weather_path)
    market = pd.read_csv(market_path).iloc[0].to_dict()
    
    # ----------------------------------------------------
    # 1. 태양광 발전소 (1,000 kW / 1 MW) 경제성 모델링
    # ----------------------------------------------------
    capacity_solar_kw = 1000.0
    solar_sys_capex = capacity_solar_kw * market["capex_solar_krw_kw"]  # 12억원
    solar_land_area = capacity_solar_kw * market["land_area_solar_m2_per_kw"]  # 12,000 m2
    solar_annual_opex = solar_sys_capex * market["opex_rate_solar"]  # 1,800만원
    
    df["solar_land_cost_krw"] = solar_land_area * df["land_price_m2"] * market["land_purchase_overhead"]
    df["solar_total_capex_krw"] = solar_sys_capex + df["solar_land_cost_krw"]
    
    # 경사면 일사량 보정(1.08) 및 성능비(PR 0.81) 적용 일평균 발전시간 (시간/일)
    # 1 kWh = 3.6 MJ
    df["solar_daily_gen_hours"] = ((df["solar_radiation_mj_year"] / 365.0 / 3.6) * 1.08 * market["solar_performance_ratio"]).round(3)
    df["solar_annual_gen_kwh"] = (capacity_solar_kw * df["solar_daily_gen_hours"] * 365.0).round(1)
    
    # 제주 출력제어 반영
    is_jeju = df["region_name"].str.contains("제주")
    df.loc[is_jeju, "solar_annual_gen_kwh"] = (df.loc[is_jeju, "solar_annual_gen_kwh"] * (1.0 - market["jeju_curtailment_risk_rate"])).round(1)
    
    # SMP 및 전력판매단가 (SMP + REC * 가중치)
    df["smp_krw_kwh"] = np.where(is_jeju, market["smp_jeju_krw_kwh"], market["smp_land_krw_kwh"])
    df["solar_tariff_krw_kwh"] = df["smp_krw_kwh"] + (market["rec_price_krw_kwh"] * market["rec_weight_solar"])
    
    df["solar_annual_revenue_krw"] = (df["solar_annual_gen_kwh"] * df["solar_tariff_krw_kwh"]).round(0)
    df["solar_annual_cf_krw"] = df["solar_annual_revenue_krw"] - solar_annual_opex
    
    # 단순 회수기간 및 20년 ROI
    df["solar_payback_years"] = (df["solar_total_capex_krw"] / df["solar_annual_cf_krw"]).round(2)
    df["solar_roi_20yr_pct"] = (((df["solar_annual_cf_krw"] * 20.0) - df["solar_total_capex_krw"]) / df["solar_total_capex_krw"] * 100.0).round(1)
    
    # 할인 회수기간 (DPB)
    df["solar_discounted_payback_years"] = df.apply(
        lambda r: calculate_discounted_payback(r["solar_total_capex_krw"], r["solar_annual_cf_krw"], market["discount_rate"]),
        axis=1
    )
    
    # LCOE (원/kWh) = (CAPEX + PV(OPEX)) / PV(Generation)
    discount_rate = market["discount_rate"]
    annuity_factor = sum(1.0 / ((1.0 + discount_rate) ** t) for t in range(1, 21))  # 약 13.0079
    pv_opex_solar = solar_annual_opex * annuity_factor
    df["solar_lcoe_krw_kwh"] = ((df["solar_total_capex_krw"] + pv_opex_solar) / (df["solar_annual_gen_kwh"] * annuity_factor)).round(1)

    # ----------------------------------------------------
    # 2. 육상 풍력 발전소 (1,000 kW / 1 MW) 경제성 모델링
    # ----------------------------------------------------
    capacity_wind_kw = 1000.0
    wind_sys_capex = capacity_wind_kw * market["capex_wind_krw_kw"]  # 24억원
    wind_land_area = capacity_wind_kw * market["land_area_wind_m2_per_kw"]  # 4,500 m2
    wind_annual_opex = wind_sys_capex * market["opex_rate_wind"]  # 6,000만원
    
    df["wind_land_cost_krw"] = wind_land_area * df["land_price_m2"] * market["land_purchase_overhead"]
    df["wind_total_capex_krw"] = wind_sys_capex + df["wind_land_cost_krw"]
    
    # 80m 상업용 허브 높이 풍속 기반 터빈 설비이용률 (Capacity Factor)
    # empirical fit: CF = 0.075 * v_80m - 0.20 (클램프: 0.05 ~ 0.45)
    cf_raw = 0.075 * df["wind_speed_80m"] - 0.20
    df["wind_capacity_factor"] = np.clip(cf_raw, 0.05, 0.45).round(4)
    
    df["wind_annual_gen_kwh"] = (capacity_wind_kw * 8760.0 * df["wind_capacity_factor"]).round(1)
    # 제주 출력제어 반영
    df.loc[is_jeju, "wind_annual_gen_kwh"] = (df.loc[is_jeju, "wind_annual_gen_kwh"] * (1.0 - market["jeju_curtailment_risk_rate"])).round(1)
    
    df["wind_tariff_krw_kwh"] = df["smp_krw_kwh"] + (market["rec_price_krw_kwh"] * market["rec_weight_wind"])
    df["wind_annual_revenue_krw"] = (df["wind_annual_gen_kwh"] * df["wind_tariff_krw_kwh"]).round(0)
    df["wind_annual_cf_krw"] = df["wind_annual_revenue_krw"] - wind_annual_opex
    
    # 단순 회수기간 및 20년 ROI
    df["wind_payback_years"] = np.where(
        df["wind_annual_cf_krw"] > 0,
        (df["wind_total_capex_krw"] / df["wind_annual_cf_krw"]).round(2),
        99.9
    )
    df["wind_roi_20yr_pct"] = np.where(
        df["wind_annual_cf_krw"] > 0,
        (((df["wind_annual_cf_krw"] * 20.0) - df["wind_total_capex_krw"]) / df["wind_total_capex_krw"] * 100.0).round(1),
        -100.0
    )
    
    # 할인 회수기간 (DPB)
    df["wind_discounted_payback_years"] = df.apply(
        lambda r: calculate_discounted_payback(r["wind_total_capex_krw"], r["wind_annual_cf_krw"], market["discount_rate"]),
        axis=1
    )
    
    # 풍력 LCOE (원/kWh)
    pv_opex_wind = wind_annual_opex * annuity_factor
    df["wind_lcoe_krw_kwh"] = np.where(
        df["wind_annual_gen_kwh"] > 0,
        ((df["wind_total_capex_krw"] + pv_opex_wind) / (df["wind_annual_gen_kwh"] * annuity_factor)).round(1),
        999.0
    )

    # ----------------------------------------------------
    # 3. 종합 투자 매력도 및 최적 기술 선정
    # ----------------------------------------------------
    df["optimal_tech"] = np.where(
        df["solar_payback_years"] < df["wind_payback_years"],
        "태양광(Solar)",
        "풍력(Wind)"
    )
    df["best_payback_years"] = np.minimum(df["solar_payback_years"], df["wind_payback_years"])

    # 통합 CSV 저장
    merged_path = os.path.join(data_dir, "merged_regional_analysis_data.csv")
    df.to_csv(merged_path, index=False, encoding="utf-8-sig")
    print(f"Economic modeling complete. Merged data saved to: {merged_path}")

    # 상위 랭킹 콘솔 출력
    top_solar = df.sort_values(by="solar_payback_years").iloc[0]
    top_wind = df.sort_values(by="wind_payback_years").iloc[0]
    
    print("\n================== [분석 결과 요약] ==================")
    print(f"★ [태양광 1위 지역]: {top_solar['region_name']} ({top_solar['sub_region']})")
    print(f"   - 연간 일사량: {top_solar['solar_radiation_mj_year']} MJ/m2/년 (일평균 {top_solar['solar_radiation_kwh_day']} kWh/m2/일)")
    print(f"   - 발전소 적합 토지 공시지가: {top_solar['land_price_m2']:,} 원/m2")
    print(f"   - 1MW 총투자비: {top_solar['solar_total_capex_krw'] / 1e8:.2f} 억원 (설비 12.0억 + 토지 2.66억)")
    print(f"   - 연간 순수익: {top_solar['solar_annual_cf_krw'] / 1e8:.2f} 억원/년")
    print(f"   - 단순 투자회수기간: {top_solar['solar_payback_years']:.2f} 년 (할인회수: {top_solar['solar_discounted_payback_years']:.2f}년)")
    print(f"   - 20년 ROI: {top_solar['solar_roi_20yr_pct']:.1f}% | LCOE: {top_solar['solar_lcoe_krw_kwh']} 원/kWh")

    print(f"\n★ [풍력 1위 지역]: {top_wind['region_name']} ({top_wind['sub_region']})")
    print(f"   - 80m 허브풍속: {top_wind['wind_speed_80m']} m/s (설비이용률: {top_wind['wind_capacity_factor']*100:.1f}%)")
    print(f"   - 발전소 적합 토지 공시지가: {top_wind['land_price_m2']:,} 원/m2")
    print(f"   - 1MW 총투자비: {top_wind['wind_total_capex_krw'] / 1e8:.2f} 억원 (설비 24.0억 + 토지 0.84억)")
    print(f"   - 연간 순수익: {top_wind['wind_annual_cf_krw'] / 1e8:.2f} 억원/년")
    print(f"   - 단순 투자회수기간: {top_wind['wind_payback_years']:.2f} 년 (할인회수: {top_wind['wind_discounted_payback_years']:.2f}년)")
    print(f"   - 20년 ROI: {top_wind['wind_roi_20yr_pct']:.1f}% | LCOE: {top_wind['wind_lcoe_krw_kwh']} 원/kWh")
    print("======================================================\n")

if __name__ == "__main__":
    run_economic_analysis()
