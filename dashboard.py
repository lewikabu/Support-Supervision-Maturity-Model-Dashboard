import streamlit as st
import pandas as pd
import plotly.express as px
import re
from typing import Optional, Dict, Any

# ---------- CONFIG ----------

DATA_FILE = "Combined Data Embu Kwale.csv"
DD_FILE = "SupportSupervisionMaturityMode_DataDictionary_2025-12-03.csv"

FACILITY_COL = "Select the Facility Being Supervised"
COUNTY_COL = "County"
SUBCOUNTY_COL = "Subcounty"  # only used if present in the data

OVERALL_MATURITY_COL = "Overall Maturity (1=Bronze, 2=Silver, 3=Gold)"
OVERALL_SCORE_COL = "Overall Total Score (%)"

# Mapping from tab name / theme to score & maturity columns
THEME_SCORE_COLS = {
    "Summary": OVERALL_SCORE_COL,
    "Service Delivery": "Service Delivery Score (%)",
    "Logistics and Cold Chain": "Cold Chain & Logistics Score (%)",
    "Data Quality": "Data Quality & Reporting Score (%)",
    "Community Linkage": "Community Linkages Score (%)",
    "HRH": "Human Resources & Training Score (%)",
    "Support Supervision": "Support Supervision Score (%)",
}

THEME_MATURITY_COLS = {
    "Summary": OVERALL_MATURITY_COL,
    "Service Delivery": "Service Delivery Maturity (1=Bronze, 2=Silver, 3=Gold)",
    "Logistics and Cold Chain": "Cold Chain & Logistics Maturity (1=Bronze, 2=Silver, 3=Gold)",
    "Data Quality": "Data Quality & Reporting Maturity (1=Bronze, 2=Silver, 3=Gold)",
    "Community Linkage": "Community Linkages Maturity (1=Bronze, 2=Silver, 3=Gold)",
    "HRH": "Human Resources & Training Maturity (1=Bronze, 2=Silver, 3=Gold)",
    "Support Supervision": "Support Supervision Maturity (1=Bronze, 2=Silver, 3=Gold)",
}

MATURITY_COLORS = {
    "Bronze": "#cd7f32",
    "Silver": "#c0c0c0",
    "Gold": "#ffd700",
    None: "#e0e0e0",
}

MATURITY_ICONS = {
    "Bronze": "🥉 Bronze",
    "Silver": "🥈 Silver",
    "Gold": "🥇 Gold",
}


# ---------- HELPERS ----------

def clean_label(s: Optional[str]) -> Optional[str]:
    if pd.isna(s):
        return None
    s = re.sub("<.*?>", "", str(s))
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def infer_theme(var_name: str) -> Optional[str]:
    if not isinstance(var_name, str):
        return None
    if var_name.startswith("sd_"):
        return "Service Delivery"
    if var_name.startswith("cc_"):
        return "Logistics & Cold Chain"
    if var_name.startswith("dq_"):
        return "Data Quality"
    if var_name.startswith("cl_"):
        return "Community Linkage"
    if var_name.startswith("hr_"):
        return "HRH"
    if var_name.startswith("ss_"):
        return "Support Supervision"
    if "maturity" in var_name.lower() or "score_pct" in var_name.lower():
        return "Summary"
    return None


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_FILE)
    dd = pd.read_csv(DD_FILE)

    dd["label_clean"] = dd["Field Label"].apply(clean_label)
    dd["Theme"] = dd["Variable / Field Name"].apply(infer_theme)

    dd_map = (
        dd.set_index("label_clean")[["Field Type", "Theme"]]
        .dropna(how="all")
        .to_dict(orient="index")
    )

    meta_rows = []
    for col in df.columns:
        if col in [
            COUNTY_COL,
            FACILITY_COL,
            SUBCOUNTY_COL,
            "Unnamed: 0",
            "Survey Identifier",
            "Survey Timestamp",
            "Please enter your initials as the data collector",
            "Date of data collection",
        ]:
            continue

        base = str(col).split("(choice=")[0].strip()
        info = dd_map.get(base) or dd_map.get(col)

        field_type = info["Field Type"] if info and isinstance(info.get("Field Type"), str) else None
        theme = info["Theme"] if info else None

        is_cat = field_type in ["yesno", "radio", "dropdown", "checkbox"]
        is_text = field_type in ["text", "notes"]

        meta_rows.append(
            {
                "column": col,
                "base_label": base,
                "field_type": field_type,
                "theme": theme,
                "is_categorical": is_cat,
                "is_open_ended": is_text,
            }
        )

    meta = pd.DataFrame(meta_rows)
    return df, meta


def filter_data(df, county, subcounty, facility):
    df_filtered = df.copy()

    if county != "All":
        df_filtered = df_filtered[df_filtered[COUNTY_COL] == county]

    if SUBCOUNTY_COL in df_filtered.columns and subcounty != "All":
        df_filtered = df_filtered[df_filtered[SUBCOUNTY_COL] == subcounty]

    if facility != "All":
        df_filtered = df_filtered[df_filtered[FACILITY_COL] == facility]

    return df_filtered


def maturity_label(x):
    mapping = {1: "Bronze", 2: "Silver", 3: "Gold", 1.0: "Bronze", 2.0: "Silver", 3.0: "Gold"}
    return mapping.get(x)


# ---------- YES/NO COLOR-CHART HERE ----------

def show_categorical_chart(df, col):
    st.subheader(col)
    series = df[col].dropna()
    if series.empty:
        st.info("No data for this question.")
        return

    def normalize(resp):
        if pd.isna(resp):
            return None
        s = str(resp).strip().lower()
        if s in ["yes", "y", "1"]:
            return "Yes"
        if s in ["no", "n", "0"]:
            return "No"
        if s == "":
            return None
        return resp

    counts = series.apply(normalize).value_counts().reset_index()
    counts.columns = ["Label", "Count"]

    counts = counts[counts["Label"].notna()]
    if counts.empty:
        st.info("Only blanks in this question.")
        return

    fig = px.pie(
        counts,
        values="Count",
        names="Label",
        hole=0.3,
        color="Label",
        color_discrete_map={
            "Yes": "green",
            "No": "red",
        },
    )
    st.plotly_chart(fig, use_container_width=True, key=f"cat_{col}")


# ---------- OPEN-ENDED TABLE ----------

def show_open_ended_table(df, col):
    st.subheader(col)
    sub = df[col].dropna()
    if sub.empty:
        st.info("No responses.")
        return
    cols = [COUNTY_COL, SUBCOUNTY_COL, FACILITY_COL]
    cols = [c for c in cols if c in df.columns]
    st.dataframe(df[cols + [col]].dropna(subset=[col]), use_container_width=True)


# ---------- SUMMARY BANNERS ----------

def render_scope_summary(theme, label, score_series, mat_series, key):
    score = score_series.dropna().mean() if not score_series.dropna().empty else None
    maturity = None
    if not mat_series.dropna().empty:
        maturity = maturity_label(round(mat_series.dropna().astype(float).mean()))

    color = MATURITY_COLORS.get(maturity)
    score_str = f"{score:.1f}%" if score is not None else "N/A"
    mat_str = MATURITY_ICONS.get(maturity, "N/A")

    st.markdown(
        f"""
        <div style='padding:10px;border-radius:8px;background:{color};border:1px solid #bbb;'>
            <b>{theme} — {label}</b><br>
            Score: <b>{score_str}</b><br>
            Maturity: <b>{mat_str}</b>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_theme_summary_banner(df, theme, county, subcounty):
    s_col = THEME_SCORE_COLS[theme]
    m_col = THEME_MATURITY_COLS[theme]

    c1, c2 = st.columns(2)

    with c1:
        dfc = df[df[COUNTY_COL] == county] if county != "All" else df
        render_scope_summary(theme, f"County: {county}", dfc[s_col], dfc[m_col], f"{theme}_county")

    with c2:
        if subcounty != "All" and SUBCOUNTY_COL in df.columns:
            dfs = df[df[SUBCOUNTY_COL] == subcounty]
            render_scope_summary(theme, f"Subcounty: {subcounty}", dfs[s_col], dfs[m_col], f"{theme}_sc")
        else:
            st.info("No subcounty selected.")


# ---------- FACILITY TABLES ----------

def facility_maturity_table(df, theme):
    s_col = THEME_SCORE_COLS[theme]
    m_col = THEME_MATURITY_COLS[theme]
    cols = [COUNTY_COL, SUBCOUNTY_COL, FACILITY_COL, s_col, m_col]
    cols = [c for c in cols if c in df.columns]
    tmp = df[cols].dropna(subset=[m_col])

    tmp["Maturity Category"] = tmp[m_col].apply(maturity_label)
    agg = tmp.groupby([c for c in [COUNTY_COL, SUBCOUNTY_COL, FACILITY_COL, "Maturity Category"] if c in tmp.columns], as_index=False)[s_col].mean()
    agg.rename(columns={s_col: "Score (%)"}, inplace=True)
    agg["Maturity"] = agg["Maturity Category"].apply(lambda x: MATURITY_ICONS.get(x))
    agg = agg.sort_values("Score (%)", ascending=False)
    return agg


def style_maturity_table(df):
    def style_row(row):
        col = MATURITY_COLORS.get(row["Maturity Category"])
        return ["background-color: {}".format(col) if c == "Score (%)" else "" for c in row.index]

    return df.style.apply(style_row, axis=1)


# ---------- SUMMARY PAGE ----------

def summary_page(df, county, subcounty):
    st.header("Summary")

    show_theme_summary_banner(df, "Summary", county, subcounty)

    # Pie + counts
    mat = df[OVERALL_MATURITY_COL].dropna().apply(maturity_label)
    count_df = mat.value_counts().reindex(["Bronze", "Silver", "Gold"]).fillna(0).astype(int).reset_index()
    count_df.columns = ["Category", "Facilities"]
    st.subheader("Facilities by maturity")
    st.table(count_df)

    fig = px.pie(count_df, values="Facilities", names="Category", hole=0.3)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Facility list (with scores)")

    fac = facility_maturity_table(df, "Summary")
    for cat in ["Bronze", "Silver", "Gold"]:
        sub = fac[fac["Maturity Category"] == cat]
        st.markdown(f"**{MATURITY_ICONS.get(cat)} – {len(sub)} facilities**")
        if sub.empty:
            st.write("None")
        else:
            st.dataframe(style_maturity_table(sub), use_container_width=True)


# ---------- THEMATIC PAGES ----------

def thematic_page(df, meta, theme, county, subcounty):
    st.header(theme)
    show_theme_summary_banner(df, theme, county, subcounty)

    mapped_theme = {
        "Service Delivery": "Service Delivery",
        "Logistics and Cold Chain": "Logistics & Cold Chain",
        "Data Quality": "Data Quality",
        "Community Linkage": "Community Linkage",
        "HRH": "HRH",
        "Support Supervision": "Support Supervision",
    }.get(theme, theme)

    theme_meta = meta[meta["theme"] == mapped_theme]

    # Charts
    cats = theme_meta[theme_meta["is_categorical"]]
    if not cats.empty:
        st.subheader("Yes/No Questions")
        for _, row in cats.iterrows():
            if row["column"] in df.columns:
                show_categorical_chart(df, row["column"])

    st.markdown("---")

    # Open text
    txts = theme_meta[theme_meta["is_open_ended"]]
    if not txts.empty:
        st.subheader("Open-ended Responses")
        for _, row in txts.iterrows():
            if row["column"] in df.columns:
                show_open_ended_table(df, row["column"])

    # Facility table
    st.markdown("---")
    st.subheader("Facilities (with scores)")
    fac = facility_maturity_table(df, theme)
    for cat in ["Bronze", "Silver", "Gold"]:
        sub = fac[fac["Maturity Category"] == cat]
        st.markdown(f"**{MATURITY_ICONS.get(cat)} – {len(sub)} facilities**")
        if sub.empty:
            st.write("None")
        else:
            st.dataframe(style_maturity_table(sub), use_container_width=True)


# ---------- MAIN ----------

def main():
    st.set_page_config(page_title="Support Supervision Maturity Dashboard", layout="wide")
    st.title("Support Supervision Maturity Model Dashboard")

    df, meta = load_data()

    st.sidebar.header("Filters")
    counties = ["All"] + sorted(df[COUNTY_COL].dropna().unique())
    county = st.sidebar.selectbox("County", counties)

    if SUBCOUNTY_COL in df.columns:
        sub_list = df[df[COUNTY_COL] == county][SUBCOUNTY_COL].dropna().unique() if county != "All" else df[SUBCOUNTY_COL].dropna().unique()
        subcounties = ["All"] + sorted(sub_list)
        subcounty = st.sidebar.selectbox("Subcounty", subcounties)
    else:
        subcounty = "All"

    facilities = df[FACILITY_COL].dropna().unique()
    facilities = ["All"] + sorted(facilities)
    facility = st.sidebar.selectbox("Facility", facilities)

    df_f = filter_data(df, county, subcounty, facility)

    st.sidebar.markdown("---")
    st.sidebar.write(f"Rows: **{len(df_f)}**")

    tabs = st.tabs([
        "Summary",
        "Service Delivery",
        "Logistics and Cold Chain",
        "Data Quality",
        "Community Linkage",
        "HRH",
        "Support Supervision"
    ])

    with tabs[0]: summary_page(df_f, county, subcounty)
    with tabs[1]: thematic_page(df_f, meta, "Service Delivery", county, subcounty)
    with tabs[2]: thematic_page(df_f, meta, "Logistics and Cold Chain", county, subcounty)
    with tabs[3]: thematic_page(df_f, meta, "Data Quality", county, subcounty)
    with tabs[4]: thematic_page(df_f, meta, "Community Linkage", county, subcounty)
    with tabs[5]: thematic_page(df_f, meta, "HRH", county, subcounty)
    with tabs[6]: thematic_page(df_f, meta, "Support Supervision", county, subcounty)


if __name__ == "__main__":
    main()
