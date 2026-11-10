import streamlit as st
import pandas as pd
from datetime import date, timedelta
import io

st.set_page_config(
    page_title="WasteWise | Campus Food Waste Dashboard",
    page_icon="♻️",
    layout="wide"
)

APP_DATA_VERSION = 3

# ----------------------------
# Sample data (illustrative)
# ----------------------------
DEMO_ITEMS = [
    {"item": "Chicken Sandwich", "prepared": 70, "sold": 56, "discarded": 9, "cost": 130, "price": 200},
    {"item": "Biryani", "prepared": 90, "sold": 78, "discarded": 8, "cost": 170, "price": 250},
    {"item": "Samosa", "prepared": 120, "sold": 98, "discarded": 18, "cost": 35, "price": 60},
    {"item": "Pasta", "prepared": 55, "sold": 42, "discarded": 10, "cost": 155, "price": 220},
]

def make_demo_data():
    rows = []
    today = date.today()
    for days_ago in range(6, -1, -1):
        for i, item in enumerate(DEMO_ITEMS):
            adjustment = ((days_ago * 3 + i * 2) % 9) - 4
            prepared = max(0, item["prepared"] + adjustment)
            sold = max(0, min(prepared, item["sold"] + adjustment // 2))
            discarded = max(0, min(prepared - sold, item["discarded"]))
            rows.append({
                "Date": today - timedelta(days=days_ago),
                "Food Item": item["item"],
                "Prepared": prepared,
                "Sold": sold,
                "Discarded": discarded,
                "Cost per Portion (PKR)": item["cost"],
                "Selling Price (PKR)": item["price"],
            })
    return pd.DataFrame(rows)

REQUIRED_COLUMNS = [
    "Date", "Food Item", "Prepared", "Sold", "Discarded",
    "Cost per Portion (PKR)", "Selling Price (PKR)"
]

def clean_records(df):
    df = df.copy()
    # Older CSV files may not have a selling-price column.
    if "Selling Price (PKR)" not in df.columns:
        df["Selling Price (PKR)"] = pd.NA
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            if col == "Date":
                df[col] = date.today()
            elif col == "Food Item":
                df[col] = "Unknown item"
            else:
                df[col] = pd.NA
    df = df[REQUIRED_COLUMNS]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    for col in ["Prepared", "Sold", "Discarded", "Cost per Portion (PKR)", "Selling Price (PKR)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Food Item"] = df["Food Item"].fillna("Unknown item").astype(str)
    df = df.dropna(subset=["Date", "Prepared", "Sold", "Discarded", "Cost per Portion (PKR)"])
    return df.reset_index(drop=True)

def add_calculations(df):
    out = df.copy()
    numeric_cols = ["Prepared", "Sold", "Discarded", "Cost per Portion (PKR)", "Selling Price (PKR)"]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["Unsold"] = (out["Prepared"] - out["Sold"]).clip(lower=0)
    out["Discard Cost (PKR)"] = out["Discarded"] * out["Cost per Portion (PKR)"]
    out["Unsold Cost (PKR)"] = out["Unsold"] * out["Cost per Portion (PKR)"]
    out["Sales Revenue (PKR)"] = out["Sold"] * out["Selling Price (PKR)"]
    out["Production Cost of Sold Portions (PKR)"] = out["Sold"] * out["Cost per Portion (PKR)"]
    out["Gross Contribution (PKR)"] = (
        out["Sales Revenue (PKR)"] - out["Production Cost of Sold Portions (PKR)"]
    )
    return out

# ----------------------------
# Session data and reset logic
# ----------------------------
# Version 3 deliberately replaces the old in-session demo dataset once.
if st.session_state.get("data_version") != APP_DATA_VERSION:
    st.session_state.records = make_demo_data()
    st.session_state.data_version = APP_DATA_VERSION
elif "records" not in st.session_state:
    st.session_state.records = make_demo_data()

st.title("♻️ WasteWise")
st.caption("A smart food-waste and business decision dashboard for campus cafeterias.")
st.info(
    "Demo mode: the preloaded figures and prices are illustrative sample data, "
    "not verified records or prices from the campus cafeteria."
)

# Sidebar controls
st.sidebar.title("WasteWise Controls")
page = st.sidebar.radio(
    "Navigate",
    ["Overview", "Log Food", "Smart Recommendations", "Savings Simulator", "ESG Report"]
)

st.sidebar.divider()
st.sidebar.subheader("Data management")

if st.sidebar.button("Replace all records with latest demo data", use_container_width=True):
    st.session_state.records = make_demo_data()
    st.session_state.data_version = APP_DATA_VERSION
    st.rerun()

if st.sidebar.button("Clear all records", use_container_width=True):
    st.session_state.records = pd.DataFrame(columns=REQUIRED_COLUMNS)
    st.session_state.data_version = APP_DATA_VERSION
    st.rerun()

uploaded_file = st.sidebar.file_uploader("Import records from CSV", type=["csv"])
if uploaded_file is not None:
    if st.sidebar.button("Replace records with uploaded CSV", use_container_width=True):
        try:
            imported = pd.read_csv(uploaded_file)
            st.session_state.records = clean_records(imported)
            st.session_state.data_version = APP_DATA_VERSION
            st.sidebar.success(f"Imported {len(st.session_state.records)} rows.")
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"Could not import this CSV: {exc}")

st.sidebar.caption("Export your records before clearing or replacing them.")

records = clean_records(st.session_state.records)
st.session_state.records = records
calculated = add_calculations(records)

# ----------------------------
# Shared metrics
# ----------------------------
def money(value):
    if pd.isna(value):
        return "—"
    return f"PKR {value:,.0f}"

def show_empty_message():
    st.warning("There are no records yet. Add food records on the Log Food page or import a CSV.")

if page == "Overview":
    st.header("Overview")
    if records.empty:
        show_empty_message()
    else:
        total_prepared = records["Prepared"].sum()
        total_sold = records["Sold"].sum()
        total_discarded = records["Discarded"].sum()
        discard_rate = (total_discarded / total_prepared * 100) if total_prepared else 0
        priced = calculated.dropna(subset=["Selling Price (PKR)"])
        revenue = priced["Sales Revenue (PKR)"].sum()
        contribution = priced["Gross Contribution (PKR)"].sum()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Portions prepared", f"{total_prepared:,.0f}")
        c2.metric("Portions sold", f"{total_sold:,.0f}")
        c3.metric("Portions discarded", f"{total_discarded:,.0f}")
        c4.metric("Discard rate", f"{discard_rate:.1f}%")

        c5, c6, c7 = st.columns(3)
        c5.metric("Discarded food cost", money(calculated["Discard Cost (PKR)"].sum()))
        c6.metric("Sales revenue*", money(revenue))
        c7.metric("Gross contribution*", money(contribution))
        st.caption("*Revenue and gross contribution include only records with a selling price. Gross contribution is not net profit; overheads and other expenses are not deducted.")

        st.subheader("Daily food-waste trend")
        daily = records.groupby("Date", as_index=False)[["Prepared", "Sold", "Discarded"]].sum()
        daily = daily.sort_values("Date").set_index("Date")
        st.line_chart(daily[["Prepared", "Sold", "Discarded"]])

        st.subheader("Records")
        st.dataframe(calculated, use_container_width=True, hide_index=True)

        csv_bytes = records.to_csv(index=False).encode("utf-8")
        st.download_button("Download records as CSV", csv_bytes, "wastewise_records.csv", "text/csv")

elif page == "Log Food":
    st.header("Log Food")
    st.write("Enter one food item's daily figures. Use actual cafeteria observations when available.")
    with st.form("food_entry_form", clear_on_submit=True):
        selected_date = st.date_input("Date", value=date.today())
        item_name = st.text_input("Food item", placeholder="e.g. Chicken sandwich")
        col1, col2, col3 = st.columns(3)
        prepared = col1.number_input("Portions prepared", min_value=0, step=1)
        sold = col2.number_input("Portions sold", min_value=0, step=1)
        discarded = col3.number_input("Portions discarded", min_value=0, step=1)
        col4, col5 = st.columns(2)
        cost = col4.number_input("Cost per portion (PKR)", min_value=0.0, step=5.0)
        has_price = st.checkbox("I know the selling price")
        price = col5.number_input("Selling price per portion (PKR)", min_value=0.0, step=5.0, disabled=not has_price)
        submitted = st.form_submit_button("Save food record", type="primary")

        if submitted:
            if not item_name.strip():
                st.error("Please enter a food item name.")
            elif sold + discarded > prepared:
                st.error("Sold portions plus discarded portions cannot exceed portions prepared.")
            else:
                new_row = {
                    "Date": selected_date,
                    "Food Item": item_name.strip(),
                    "Prepared": int(prepared),
                    "Sold": int(sold),
                    "Discarded": int(discarded),
                    "Cost per Portion (PKR)": float(cost),
                    "Selling Price (PKR)": float(price) if has_price else pd.NA,
                }
                st.session_state.records = pd.concat(
                    [records, pd.DataFrame([new_row])], ignore_index=True
                )
                st.success("Record saved.")
                st.rerun()

    if not records.empty:
        st.subheader("Current records")
        st.dataframe(records, use_container_width=True, hide_index=True)
        csv_bytes = records.to_csv(index=False).encode("utf-8")
        st.download_button("Download current records", csv_bytes, "wastewise_records.csv", "text/csv")

elif page == "Smart Recommendations":
    st.header("Smart Recommendations")
    st.caption("These are simple data-based planning suggestions, not AI predictions.")
    if records.empty:
        show_empty_message()
    else:
        item_summary = records.groupby("Food Item").agg(
            Average_Sold=("Sold", "mean"),
            Average_Prepared=("Prepared", "mean"),
            Total_Discarded=("Discarded", "sum")
        ).reset_index()
        buffer_pct = st.slider("Safety buffer above average sales (%)", 0, 30, 10)
        item_summary["Suggested Preparation"] = (
            item_summary["Average_Sold"] * (1 + buffer_pct / 100)
        ).apply(lambda x: int(round(x)))
        item_summary["Potential Check"] = item_summary.apply(
            lambda r: "Review preparation level" if r["Total_Discarded"] > 0 else "Continue monitoring",
            axis=1
        )
        st.dataframe(item_summary, use_container_width=True, hide_index=True)
        st.write("Use these estimates as a starting point. Consider weekdays, events, weather and stock availability before changing production.")

elif page == "Savings Simulator":
    st.header("Savings Simulator")
    st.write("Explore a hypothetical reduction in discarded portions. This is a scenario, not a measured result.")
    if records.empty:
        show_empty_message()
    else:
        current_discard = int(records["Discarded"].sum())
        average_cost = (
            (records["Discarded"] * records["Cost per Portion (PKR)"]).sum() / current_discard
            if current_discard else 0
        )
        reduction = st.slider("Assumed reduction in food discarded (%)", 0, 100, 25)
        avoided = current_discard * reduction / 100
        estimated_saving = avoided * average_cost
        a, b, c = st.columns(3)
        a.metric("Current discarded portions", f"{current_discard:,.0f}")
        b.metric("Potentially avoided portions", f"{avoided:,.1f}")
        c.metric("Illustrative production-cost saving", money(estimated_saving))
        st.caption("Estimate uses the average production cost of discarded portions. It is not a guaranteed cash saving.")

elif page == "ESG Report":
    st.header("ESG Report")
    st.write("A simple environmental, social and governance snapshot.")
    if records.empty:
        show_empty_message()
    else:
        total_prepared = records["Prepared"].sum()
        total_discarded = records["Discarded"].sum()
        rate = total_discarded / total_prepared * 100 if total_prepared else 0
        st.metric("Food discard rate", f"{rate:.1f}%")
        st.metric("Discarded portions recorded", f"{total_discarded:,.0f}")
        st.subheader("ESG interpretation")
        st.markdown("""
        **Environmental:** Track discarded portions and their production cost. Weighing food waste would make the environmental measurement stronger.

        **Social:** Consider safe donation of suitable surplus food, staff awareness and clear food-handling procedures.

        **Governance:** Maintain dated records, consistent measurement methods and transparent reporting. Clearly distinguish observed data from estimates.
        """)
        st.subheader("Recommended evidence to collect")
        st.markdown("""
        - Daily prepared, sold and discarded quantities
        - Actual ingredient or production cost per portion
        - Selling price, if the cafeteria is willing to share it
        - Waste weight in kilograms, if scales are available
        - Date, measurement method and person recording the data
        """)
        st.warning("Do not report carbon-emission reductions unless you have a defensible waste-weight figure and a reliable conversion factor.")