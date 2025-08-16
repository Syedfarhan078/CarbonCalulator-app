# app.py
import math
import io
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

# ---------- CONFIG ----------
st.set_page_config(layout="wide", page_title="Personal Carbon Calculator (India-ready)", page_icon="🖩")

# ---------- CONSTANTS (with citation notes shown in the About page) ----------
COUNTRIES = ["India"]  # Designed India-first; structure ready to add more countries.

ELECTRICITY_EF = {
    # CEA CO2 Baseline Database (FY 2022–23): 0.716 tCO2/MWh = 0.716 kgCO2/kWh
    "India": 0.716
}

TRANSPORT_EF_PAXKM = {
    # WRI India (2024 scenario report): Car ~170 gCO2e/pkm; Bus ~97 gCO2e/pkm
    # India GHG Programme (Rail): ~0.008 kgCO2/pkm
    "car": 0.170,     # kg CO2e per passenger-km
    "bus": 0.097,     # kg CO2e per passenger-km
    "rail": 0.008,    # kg CO2e per passenger-km (suburban / non-suburban similar order)
}

# Diet presets (Scarborough et al., Climatic Change 2014; kgCO2e/day)
DIET_DAILY = {
    "High meat": 7.19,
    "Medium meat": 5.63,
    "Low meat": 4.67,
    "Fish-based": 3.91,
    "Vegetarian": 3.81,
    "Vegan": 2.89,
}

# Waste treatment factors (kgCO2e per kg of mixed residual waste)
# These vary by landfill gas capture & composition. We offer options and explain caveats in About.
WASTE_EF = {
    "Landfill (typical managed)": 0.45,  # ~UK DEFRA order of magnitude; proxy only
    "Incineration (energy recovery)": 1.10,  # CO2 biogenic share debated; lifecycle context needed
    "Composting/AD (food/green fractions)": 0.10,  # can be near-zero/negative with credits; this is conservative
}

# India per-capita (benchmark)
INDIA_PER_CAPITA_T_CO2 = 2.0  # around 2 tCO2 per person in 2023 (we show exact citation on About page)

# ---------- UI ----------
st.title("🖩 Personal Carbon Calculator")
st.caption("India-ready, research-backed, and scenario-friendly. See the About page for methods & sources.")

with st.sidebar:
    st.header("🌎 Context")
    country = st.selectbox("Country", COUNTRIES, index=0)
    st.write("Grid factor assumed for calculations:")
    st.metric("Electricity EF", f"{ELECTRICITY_EF[country]:.3f} kg CO₂e/kWh")

    st.header("⚙️ Options")
    show_advanced = st.toggle("Show advanced options", value=False)
    st.write("Use the **About/Methods** page for assumptions & citations.")

tabs = st.tabs(["Calculator", "What-if & Insights", "Download", "About / Methods"])

# ---------- TAB 1: CALCULATOR ----------
with tabs[0]:
    st.subheader("👤 Your Activity Inputs")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### 🚗 Daily Commute")
        mode = st.selectbox("Primary mode", ["car", "bus", "rail"], index=0, help="Passenger-km factors applied")
        daily_commute_km = st.slider("Average distance per day (km)", 0.0, 200.0, 15.0, step=1.0)
        commute_days = st.slider("Commute days per year", 0, 365, 240, step=5)

        if show_advanced and mode == "car":
            st.info("For cars, the default 170 gCO₂e/pkm reflects average Indian conditions; set ‘Car occupancy’ if carpooling.")
        car_occupancy = 1 if mode != "car" else st.number_input("Car occupancy (people per car)", min_value=1.0, value=1.0, step=0.5)

        st.markdown("#### ⚡ Electricity Use")
        monthly_kwh = st.slider("Monthly electricity consumption (kWh)", 0.0, 2000.0, 250.0, step=10.0)
        annual_kwh = monthly_kwh * 12

    with c2:
        st.markdown("#### 🍽️ Diet")
        diet_type = st.selectbox("Diet type (daily average GHG)", list(DIET_DAILY.keys()), index=1)
        if show_advanced:
            diet_meals = st.slider("Meals per day (cosmetic; diet values are daily totals)", 1, 5, 3)

        st.markdown("#### 🗑️ Waste")
        weekly_waste_kg = st.slider("Mixed residual waste (kg/week)", 0.0, 100.0, 4.0, step=0.5,
                                    help="Exclude well-segregated recyclables/compostables if handled separately.")
        waste_treatment = st.selectbox("Treatment pathway", list(WASTE_EF.keys()))
        segregation = st.slider("Recycling/composting rate (%)", 0, 100, 20,
                                help="Reduces residual waste sent to treatment.")

    # ---------- CALCULATIONS ----------
    # Commute
    annual_commute_km = daily_commute_km * commute_days
    pax_km = annual_commute_km  # single person unless carpooling
    if mode == "car" and car_occupancy > 0:
        pax_km = annual_commute_km  # per passenger already; we apply occupancy by dividing vehicle-km by occupancy
        transport_ef = TRANSPORT_EF_PAXKM["car"]
        transport_emissions_kg = pax_km * transport_ef
    else:
        transport_ef = TRANSPORT_EF_PAXKM[mode]
        transport_emissions_kg = pax_km * transport_ef

    # Electricity
    electricity_emissions_kg = annual_kwh * ELECTRICITY_EF[country]

    # Diet (convert daily -> annual)
    diet_emissions_kg = DIET_DAILY[diet_type] * 365.0

    # Waste (apply segregation then EF)
    residual_weekly = weekly_waste_kg * (1 - segregation / 100.0)
    annual_residual_kg = residual_weekly * 52.0
    waste_emissions_kg = annual_residual_kg * WASTE_EF[waste_treatment]

    # Totals in tonnes
    category_tonnes = {
        "Transportation": round(transport_emissions_kg / 1000.0, 3),
        "Electricity": round(electricity_emissions_kg / 1000.0, 3),
        "Diet": round(diet_emissions_kg / 1000.0, 3),
        "Waste": round(waste_emissions_kg / 1000.0, 3),
    }
    total_tonnes = round(sum(category_tonnes.values()), 3)

    st.markdown("---")
    st.subheader("📊 Results")
    c3, c4 = st.columns([1.2, 1])

    with c3:
        st.markdown("##### By Category (tCO₂e/year)")
        for k, v in category_tonnes.items():
            st.info(f"**{k}**: {v} tCO₂e/yr")

        bench = INDIA_PER_CAPITA_T_CO2
        delta_vs_india = total_tonnes - bench
        st.success(f"**Total**: {total_tonnes} tCO₂e/yr")
        st.caption(f"Benchmark: India per-capita ≈ {bench:.1f} tCO₂/yr")

    with c4:
        # Pie chart
        fig, ax = plt.subplots()
        labels = list(category_tonnes.keys())
        sizes = list(category_tonnes.values())
        # Avoid zero-sum crash
        if sum(sizes) <= 0:
            sizes = [1e-6] * len(sizes)
        ax.pie(sizes, labels=labels, autopct=lambda p: f"{p:.0f}%" if p >= 5 else "")
        ax.set_title("Your footprint breakdown")
        st.pyplot(fig)

    with st.expander("See calculation details"):
        st.json({
            "Inputs": {
                "country": country,
                "commute_mode": mode,
                "daily_commute_km": daily_commute_km,
                "commute_days": commute_days,
                "car_occupancy": car_occupancy if mode == "car" else None,
                "monthly_kwh": monthly_kwh,
                "diet_type": diet_type,
                "weekly_waste_kg": weekly_waste_kg,
                "segregation_percent": segregation,
                "waste_treatment": waste_treatment,
            },
            "Emission factors (kgCO2e per unit)": {
                "transport": {k: float(v) for k, v in TRANSPORT_EF_PAXKM.items()},
                "electricity": ELECTRICITY_EF[country],
                "diet_daily": DIET_DAILY[diet_type],
                "waste": {k: float(v) for k, v in WASTE_EF.items()},
            },
            "Results (tCO2e/year)": category_tonnes | {"Total": total_tonnes}
        })

# ---------- TAB 2: WHAT-IF ----------
with tabs[1]:
    st.subheader("🧪 What-if: Fast ways to lower your footprint")
    st.caption("Adjust sliders to see instant impact.")

    ww1, ww2, ww3 = st.columns(3)
    with ww1:
        alt_mode = st.selectbox("Switch commute mode to:", ["car", "bus", "rail"], index=1)
        alt_occupancy = st.number_input("If car, occupancy", min_value=1.0, value=2.0, step=0.5)
    with ww2:
        kwh_cut = st.slider("Reduce monthly kWh by (%)", 0, 100, 20, step=5)
    with ww3:
        diet_switch = st.selectbox("Switch diet to:", list(DIET_DAILY.keys()), index=5)
        extra_segregation = st.slider("Increase recycling/composting by (+% points)", 0, 100, 20, step=5)

    # compute deltas
    # Transport
    new_transport_ef = TRANSPORT_EF_PAXKM[alt_mode]
    new_paxkm = (daily_commute_km * commute_days)
    new_trans_kg = new_paxkm * new_transport_ef
    if alt_mode == "car" and alt_occupancy > 0:
        # still using pax-km EF; occupancy matters mainly if you were calculating per-vehicle; here it's already per passenger-km.
        pass

    # Electricity
    new_monthly_kwh = monthly_kwh * (1 - kwh_cut / 100.0)
    new_elec_kg = new_monthly_kwh * 12 * ELECTRICITY_EF[country]

    # Diet
    new_diet_kg = DIET_DAILY[diet_switch] * 365.0

    # Waste
    new_segregation = min(100, segregation + extra_segregation)
    new_residual_weekly = weekly_waste_kg * (1 - new_segregation / 100.0)
    new_waste_kg = new_residual_weekly * 52.0 * WASTE_EF[waste_treatment]

    new_total_t = round((new_trans_kg + new_elec_kg + new_diet_kg + new_waste_kg)/1000.0, 3)
    delta_t = round(new_total_t - sum([v for v in [category_tonnes["Transportation"], category_tonnes["Electricity"], category_tonnes["Diet"], category_tonnes["Waste"]]]), 3)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("New total (tCO₂e/yr)", new_total_t, delta=f"{delta_t} vs current")
    with c2:
        saved = -delta_t
        st.metric("Potential reduction (tCO₂e/yr)", saved if saved > 0 else 0.0)

    # Simple recommendations
    st.markdown("#### 🎯 Quick wins")
    recs = []
    if alt_mode in ["bus", "rail"] and mode == "car":
        recs.append("Shift more commute days to **bus/rail**.")
    if kwh_cut >= 10:
        recs.append("Adopt **efficient appliances**, **LED lighting**, and **AC setpoint 24–26°C**.")
    if DIET_DAILY[diet_switch] < DIET_DAILY[diet_type]:
        recs.append(f"Move toward **{diet_switch.lower()}** patterns (batch cooking, legumes, millets).")
    if new_segregation > segregation:
        recs.append("Improve **segregation at source**; compost wet waste; keep recyclables clean/dry.")
    if recs:
        for r in recs:
            st.write("• " + r)
    else:
        st.write("• Your scenario already looks optimized—nice!")

# ---------- TAB 3: DOWNLOAD ----------
with tabs[2]:
    st.subheader("📥 Export your results")
    df = pd.DataFrame([
        {"Category": k, "tCO2e/yr": v} for k, v in category_tonnes.items()
    ] + [{"Category": "Total", "tCO2e/yr": sum(category_tonnes.values())}])

    st.dataframe(df, use_container_width=True)

    @st.cache_data
    def _csv_bytes(_df: pd.DataFrame) -> bytes:
        return _df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download CSV",
        data=_csv_bytes(df),
        file_name="personal_carbon_results.csv",
        mime="text/csv",
        use_container_width=True
    )

    # Simple JSON export
    export_payload = {
        "country": country,
        "inputs": {
            "commute": {"mode": mode, "daily_km": daily_commute_km, "days": commute_days},
            "electricity_monthly_kwh": monthly_kwh,
            "diet_type": diet_type,
            "waste_weekly_kg": weekly_waste_kg,
            "waste_treatment": waste_treatment,
            "segregation_percent": segregation,
        },
        "results_tCO2e": category_tonnes | {"Total": sum(category_tonnes.values())}
    }
    st.download_button(
        "Download JSON",
        data=json.dumps(export_payload, indent=2),
        file_name="personal_carbon_results.json",
        mime="application/json",
        use_container_width=True
    )

# ---------- TAB 4: ABOUT / METHODS ----------
with tabs[3]:
    st.subheader("📚 Methods, Assumptions & Sources")
    st.markdown("""
**Electricity (India):** Grid emission factor set to **0.716 kgCO₂/kWh** (CEA *CO₂ Baseline Database* FY 2022–23).  
**Transport (passenger-km):**  
• Car: **0.170 kgCO₂e/pkm**, Bus: **0.097 kgCO₂e/pkm** (WRI India, 2024 scenario analysis).  
• Rail: **~0.008 kgCO₂/pkm** (India GHG Programme rail methodology using Indian Railways data).  

**Diet:** Daily diet footprints from Scarborough et al. (2014, UK EPIC-Oxford cohort):  
High meat 7.19; Medium 5.63; Low 4.67; Fish 3.91; Vegetarian 3.81; Vegan 2.89 kgCO₂e/day.  
We use these as relative *patterns* (India food systems differ; this still provides useful directional insights).

**Waste:** Residual mixed waste factors vary widely by site, methane capture, moisture, and composition.  
We provide: Landfill (typical managed) **0.45 kgCO₂e/kg** as an order-of-magnitude proxy based on DEFRA conversion factors; Incineration **~1.10 kgCO₂/kg** (lifecycle context sensitive); Compost/AD **~0.10 kgCO₂e/kg** (conservative—can be lower with credits). For India’s open or unmanaged dumps, real-world emissions can be **higher** due to methane leakage; segregation/composting of wet waste is critical.

**Benchmark:** India per-capita energy-related CO₂ emissions ≈ **~2 tCO₂/person in 2023** (IEA overview; see sources).  

### Primary Sources
- **CEA, India — CO₂ Baseline Database (FY 2022–23):** grid intensity ≈ **0.716 kgCO₂/kWh**.  
- **WRI India (2024)** transport scenario analysis: car ≈ **170 gCO₂e/pkm**, bus ≈ **97 gCO₂e/pkm**.  
- **India GHG Programme (Rail factors)**: rail ≈ **0.008 kgCO₂/pkm** derived from Indian Railways data.  
- **Scarborough et al., *Climatic Change* (2014):** diet footprints by pattern (kgCO₂e/day).  
- **DEFRA/UK Gov GHG Conversion Factors (2024–25):** waste treatment reference factors.  
- **IEA (2023 emissions update):** India per-capita ~**2 t** in 2023.
""")
    st.markdown("See live links below for full details.")

    # Clickable links
    st.markdown("""
- CEA CO₂ Baseline Database (User Guide, v19, FY 2022–23): https://cea.nic.in/wp-content/uploads/baseline/2024/01/User_Guide__Version_19.0-1.pdf  
- WRI India report (transport): https://wri-india.org/sites/default/files/Pathways-to-decarbonize-India%E2%80%99s-transport-sector.pdf  
- India GHG Programme (Rail EF): https://indiaghgp.org/sites/default/files/Rail%20Transport%20Emission.pdf  
- Scarborough et al. (2014) open access: https://pmc.ncbi.nlm.nih.gov/articles/PMC4372775/  
- UK Gov DEFRA conversion factors (2024 collection): https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting  
- IEA — CO₂ emissions in 2023: https://www.iea.org/reports/co2-emissions-in-2023/the-changing-landscape-of-global-emissions
""")

    st.markdown("### Notes & Caveats")
    st.info("All results are **estimates**. Emissions vary by occupancy, vehicle/fuel type, local grid mix, waste management practices, and diet specifics. For city/company reporting, use local factors and methodologies (GHG Protocol).")
