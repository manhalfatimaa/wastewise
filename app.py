import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="WasteWise", page_icon="🌱", layout="wide")
st.markdown("""<style>.block-container{padding-top:2rem;}[data-testid='stMetric']{background:#f1f8f2;border-radius:12px;padding:14px;}</style>""", unsafe_allow_html=True)

DEMO = [
    ("Chicken Sandwich", 70, 56, 9, 130),
    ("Biryani", 90, 78, 8, 170),
    ("Samosa", 120, 98, 18, 35),
    ("Pasta", 55, 42, 10, 155),
]

def demo_data():
    rows = []
    for days_ago in range(6, -1, -1):
        day = date.today() - timedelta(days=days_ago)
        for i, (item, made, sold, discarded, cost) in enumerate(DEMO):
            adjustment = ((days_ago * 3 + i * 2) % 9) - 4
            qty_made = made + adjustment
            qty_sold = min(qty_made, sold + adjustment // 2)
            qty_discarded = min(qty_made - qty_sold, discarded)
            rows.append({"Date": day, "Food Item": item, "Prepared": qty_made,
                         "Sold": qty_sold, "Discarded": qty_discarded,
                         "Cost per Portion (PKR)": cost})
    return pd.DataFrame(rows)

if "records" not in st.session_state:
    st.session_state.records = demo_data()

st.title("🌱 WasteWise")
st.caption("Smarter Cafeterias • Less Waste • Better Business Decisions")
st.info("DEMO MODE: Initial records are fictional examples, not observations from a real cafeteria. Changes are kept only in this browser session. Export your data to save it.")

with st.sidebar:
    st.header("Navigation")
    page = st.radio("Go to", ["Overview", "Log Food", "Smart Recommendations", "Savings Simulator", "ESG Report"])
    st.divider()
    if st.button("Reset to sample data"):
        st.session_state.records = demo_data()
        st.rerun()
    uploaded = st.file_uploader("Import previously exported CSV", type="csv")
    if uploaded is not None and st.button("Load CSV"):
        try:
            df = pd.read_csv(uploaded)
            required = ["Date", "Food Item", "Prepared", "Sold", "Discarded", "Cost per Portion (PKR)"]
            if not all(c in df.columns for c in required):
                raise ValueError("CSV does not have the required columns")
            for col in ["Prepared", "Sold", "Discarded", "Cost per Portion (PKR)"]:
                df[col] = pd.to_numeric(df[col], errors="raise")
            df["Date"] = pd.to_datetime(df["Date"], errors="raise").dt.date
            if (df[["Prepared", "Sold", "Discarded", "Cost per Portion (PKR)"]] < 0).any().any():
                raise ValueError("Negative values are not allowed")
            if ((df["Sold"] + df["Discarded"]) > df["Prepared"]).any():
                raise ValueError("Sold + discarded cannot exceed prepared")
            st.session_state.records = df[required]
            st.success("Records loaded")
            st.rerun()
        except Exception as exc:
            st.error(f"Unable to load file: {exc}")

records = st.session_state.records.copy()
records["Unsold"] = records["Prepared"] - records["Sold"]
records["Discard Cost"] = records["Discarded"] * records["Cost per Portion (PKR)"]
records["Unsold Cost"] = records["Unsold"] * records["Cost per Portion (PKR)"]

if page == "Overview":
    st.subheader("Cafeteria Performance Overview")
    a, b, c, d = st.columns(4)
    a.metric("Portions Prepared", f"{int(records['Prepared'].sum()):,}")
    b.metric("Portions Discarded", f"{int(records['Discarded'].sum()):,}")
    c.metric("Discarded Production Cost", f"Rs. {records['Discard Cost'].sum():,.0f}")
    rate = records["Discarded"].sum() / records["Prepared"].sum() * 100 if records["Prepared"].sum() else 0
    d.metric("Discard Rate", f"{rate:.1f}%")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Discarded Portions by Food")
        st.bar_chart(records.groupby("Food Item")["Discarded"].sum())
    with right:
        st.markdown("#### Daily Discarded Production Cost")
        daily = records.groupby("Date")["Discard Cost"].sum()
        st.line_chart(daily)
    st.caption("Discarded production cost = discarded portions × estimated production cost per portion. This is not the same as lost sales revenue.")

elif page == "Log Food":
    st.subheader("Add a Daily Food Record")
    with st.form("food_form", clear_on_submit=True):
        food_date = st.date_input("Date", value=date.today())
        item = st.text_input("Food item", placeholder="e.g., Chicken Sandwich")
        a, b, c = st.columns(3)
        made = a.number_input("Portions prepared", min_value=0, step=1)
        sold = b.number_input("Portions sold", min_value=0, step=1)
        discarded = c.number_input("Portions discarded", min_value=0, step=1)
        cost = st.number_input("Production cost per portion (PKR)", min_value=0.0, step=5.0)
        submitted = st.form_submit_button("Add Record", type="primary")
        if submitted:
            if not item.strip():
                st.error("Please enter a food item")
            elif sold + discarded > made:
                st.error("Sold plus discarded portions cannot exceed prepared portions")
            else:
                new = pd.DataFrame([{"Date": food_date, "Food Item": item.strip(), "Prepared": made,
                    "Sold": sold, "Discarded": discarded, "Cost per Portion (PKR)": cost}])
                st.session_state.records = pd.concat([st.session_state.records, new], ignore_index=True)
                st.success("Record added. Open Overview to see updated results.")
    st.markdown("#### Current Records")
    st.dataframe(records, use_container_width=True, hide_index=True)
    st.download_button("Download records as CSV", st.session_state.records.to_csv(index=False),
                       file_name="wastewise_records.csv", mime="text/csv")

elif page == "Smart Recommendations":
    st.subheader("Preparation Planning")
    st.write("A simple baseline recommendation uses average sales for the most recent recorded days. It is not an AI forecast and cannot account for unexpected events.")
    items = sorted(records["Food Item"].unique())
    selected = st.selectbox("Choose food item", items)
    buffer = st.slider("Safety buffer above average sales (%)", 0, 30, 10)
    item_records = records[records["Food Item"] == selected].sort_values("Date")
    recent = item_records.tail(7)
    average = recent["Sold"].mean()
    suggested = int(round(average * (1 + buffer / 100)))
    x, y, z = st.columns(3)
    x.metric("Average Sales", f"{average:.1f} portions")
    y.metric("Suggested Next Preparation", f"{suggested} portions")
    z.metric("Recent Discarded Portions", f"{int(recent['Discarded'].sum())}")
    st.line_chart(item_records.set_index("Date")[["Prepared", "Sold", "Discarded"]])
    st.warning("Use this as a planning estimate only. Validate against weekdays, exam schedules, stock-outs, and cafeteria manager feedback before acting.")

elif page == "Savings Simulator":
    st.subheader("What If We Reduce Food Waste?")
    reduction = st.slider("Hypothetical reduction in discarded portions (%)", 0, 75, 25)
    current_cost = records["Discard Cost"].sum()
    potential = current_cost * reduction / 100
    a, b, c = st.columns(3)
    a.metric("Current Recorded Discard Cost", f"Rs. {current_cost:,.0f}")
    b.metric("Illustrative Avoidable Cost", f"Rs. {potential:,.0f}")
    c.metric("Remaining Discard Cost", f"Rs. {current_cost - potential:,.0f}")
    st.bar_chart(pd.DataFrame({"PKR": [current_cost, current_cost - potential]}, index=["Current", "Scenario"]))
    st.caption("Scenario only, not a measured saving. Avoided production costs require actual operational changes; savings may be lower after implementation costs and other constraints.")

else:
    st.subheader("Environmental, Social & Governance Snapshot")
    prepared = records["Prepared"].sum()
    discarded = records["Discarded"].sum()
    st.markdown("### 🌿 Environmental")
    st.write(f"Recorded discarded portions: **{discarded:,.0f}** out of **{prepared:,.0f}** prepared.")
    st.write("For defensible carbon estimates, collect food weights and use documented food-specific emissions factors. No unverified CO₂ estimate is shown.")
    st.markdown("### 🤝 Social")
    st.write("Possible goals: train cafeteria staff to record waste consistently, encourage responsible consumption, and explore safe surplus-food handling with management.")
    st.markdown("### 🛡️ Governance")
    st.write("Suggested controls: designated data owner, daily record review, weekly trend checks, documented assumptions, and management approval for operational changes.")
    st.markdown("### 💰 Financial")
    st.write(f"Estimated production cost of recorded discarded food: **Rs. {records['Discard Cost'].sum():,.0f}**.")
    st.caption("All figures depend on input data quality. Sample data must not be presented as verified field research.")

st.divider()
st.caption("WasteWise | Student sustainability innovation prototype | Built with Streamlit")
