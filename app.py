import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import seaborn as sns
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests
import re
import tempfile
import time  # For the cookie race-condition fix
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from streamlit_cookies_manager import EncryptedCookieManager

# ---------- CONFIG ----------
st.set_page_config(page_title="Luminant BI Analytics Tool", layout="wide")

API_KEY = "AIzaSyA_Rcb6UVBQSqqH_9jBSXeEkbZUn3jnT3k"

# ---------- COOKIE SETUP ("Remember Me") ----------
cookies = EncryptedCookieManager(
    prefix="luminantbi_",
    password="super-secret-bca-project-password" 
)
if not cookies.ready():
    st.stop()

if "user" not in st.session_state:
    st.session_state.user = None

# Auto-Login Logic
if st.session_state.user is None and cookies.get("saved_email"):
    st.session_state.user = {
        "email": cookies["saved_email"], 
        "username": cookies["saved_email"].split('@')[0]
    }

# ---------- STYLE ----------
st.markdown("""
<style>
.metric-card {
    background: white;
    color: black;
    padding: 15px;
    border-radius: 12px;
    text-align: center;
    font-weight: 600;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.eda-section {
    background: #f8f9fa;
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 15px;
}

/* Insight cards */
.insight-card {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding: 16px 20px;
    border-radius: 12px;
    margin-bottom: 12px;
    border: 1px solid;
    transition: transform 0.15s ease;
}
.insight-card:hover { transform: translateX(4px); }
.insight-card.strong {
    background: #f0fdf4;
    border-color: #86efac;
}
.insight-card.moderate {
    background: #fffbeb;
    border-color: #fcd34d;
}
.insight-card.none {
    background: #fff5f5;
    border-color: #feb2b2;
}
.insight-badge {
    flex-shrink: 0;
    width: 38px;
    height: 38px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
}
.insight-badge.strong  { background: #dcfce7; }
.insight-badge.moderate { background: #fef9c3; }
.insight-badge.none    { background: #fee2e2; }
.insight-body { flex: 1; }
.insight-label {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 3px;
}
.insight-label.strong  { color: #16a34a; }
.insight-label.moderate { color: #d97706; }
.insight-label.none    { color: #dc2626; }
.insight-text {
    font-size: 0.95rem;
    font-weight: 600;
    color: #1a202c;
}
.insight-subtext {
    font-size: 0.8rem;
    color: #718096;
    margin-top: 2px;
}
.insight-score {
    flex-shrink: 0;
    font-size: 1.4rem;
    font-weight: 700;
    align-self: center;
}
.insight-score.strong  { color: #16a34a; }
.insight-score.moderate { color: #d97706; }
.insight-score.none    { color: #dc2626; }
.insight-summary {
    display: flex;
    gap: 12px;
    margin: 16px 0 28px 0;
    flex-wrap: wrap;
}
.insight-summary-pill {
    padding: 8px 18px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}
.insight-summary-pill.strong  { background: #dcfce7; color: #16a34a; }
.insight-summary-pill.moderate { background: #fef9c3; color: #d97706; }
.insight-summary-pill.none    { background: #fee2e2; color: #dc2626; }
</style>
""", unsafe_allow_html=True)

# ---------- COLORS ----------
chart_colors = ["#4CAF50","#FF9800","#9C27B0","#2196F3","#F44336","#009688"]

# ---------- HELPERS ----------
def strip_emoji(text):
    return re.sub(r'[^\x00-\x7F]+', '', text).strip()

def close_fig(fig):
    plt.close(fig)

# ---------- AUTH ----------
def sign_up(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
    return requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}).json()

def sign_in(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
    return requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}).json()

# ---------- INSIGHTS (NLG) ----------
def generate_insights(df):
    num = df.select_dtypes(include=[np.number]).columns
    insights = []

    if len(num) >= 2:
        corr = df[num].corr()
        for i in range(len(num)):
            for j in range(i + 1, len(num)):
                val = corr.iloc[i, j]
                if pd.isna(val):
                    continue
                
                direction = "Positive" if val > 0 else "Negative"
                if abs(val) > 0.7:
                    insights.append(f"Strong: '{num[i]}' & '{num[j]}' have a Strong {direction} Trend. They move closely together. ({val:.2f})")
                elif abs(val) > 0.4:
                    insights.append(f"Moderate: '{num[i]}' & '{num[j]}' have a Moderate {direction} Trend. Visible relationship exists. ({val:.2f})")

    # Categorical Insights
    cat = df.select_dtypes(include=['object', 'category']).columns
    for c in cat:
        vc = df[c].value_counts()
        if not vc.empty:
            top_val = vc.idxmax()
            top_pct = (vc.max() / len(df)) * 100
            if top_pct > 40:
                insights.append(f"Category: In '{c}', '{top_val}' dominates the dataset, making up {top_pct:.1f}% of the records.")

    if not insights:
        insights.append("No strong relationships found")

    corr_matrix = df[num].corr() if len(num) >= 2 else None
    return insights, corr_matrix

# ---------- AUTO EDA (HIGHLIGHTED) ----------
def run_auto_eda(df):
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist() 
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

    # --- 1. Dataset Overview ---
    st.subheader("📋 Dataset Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rows", df.shape[0])
    col2.metric("Columns", df.shape[1])
    col3.metric("Numeric Columns", len(num_cols))
    col4.metric("Categorical Columns", len(cat_cols))

    with st.expander("🔍 Column Data Types", expanded=False):
        dtype_df = pd.DataFrame({
            "Column": df.columns,
            "Data Type": df.dtypes.astype(str).values,
            "Non-Null Count": df.notnull().sum().values,
            "Null %": (df.isnull().sum().values / len(df) * 100).round(2)
        })
        st.dataframe(dtype_df.style.map(lambda x: 'background-color: #ffcccc' if x > 0 else '', subset=['Null %']), use_container_width=True)

    st.markdown("---")

    # --- 2. Missing Value Analysis ---
    st.subheader("🕳️ Missing Value Analysis")
    missing = df.isnull().sum()
    missing = missing[missing > 0]

    if missing.empty:
        st.success("✅ No missing values found in the dataset!")
    else:
        miss_df = pd.DataFrame({
            "Column": missing.index,
            "Missing Count": missing.values,
            "Missing %": (missing.values / len(df) * 100).round(2)
        })
        st.dataframe(miss_df.style.background_gradient(cmap='Reds', subset=['Missing %']), use_container_width=True)

        fig = px.bar(
            miss_df, x="Column", y="Missing %",
            title="Missing Values by Column (%)",
            color="Missing %",
            color_continuous_scale="Reds"
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # --- 3. Statistical Summary ---
    st.subheader("📊 Statistical Summary")
    if num_cols:
        stats_df = df[num_cols].describe().T.round(2)
        st.dataframe(stats_df.style.background_gradient(cmap='Blues'), use_container_width=True)
    else:
        st.info("No numeric columns to summarize.")

    st.markdown("---")

    # --- 4. Numeric Column Distributions ---
    if num_cols:
        st.subheader("📈 Numeric Column Distributions")
        st.caption("Histogram + Box plot for each numeric column")

        cols_per_row = 2
        for i in range(0, len(num_cols), cols_per_row):
            row_cols = st.columns(cols_per_row)
            for j, col_name in enumerate(num_cols[i:i + cols_per_row]):
                with row_cols[j]:
                    st.markdown(f"**{col_name}**")
                    fig = px.histogram(
                        df, x=col_name,
                        marginal="box",
                        color_discrete_sequence=[chart_colors[j % len(chart_colors)]],
                        title=col_name
                    )
                    fig.update_layout(height=300, margin=dict(t=30, b=10))
                    st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

    # --- 5. Outlier Detection ---
    if num_cols:
        st.subheader("🚨 Outlier Detection (IQR Method)")
        outlier_summary = []
        for col_name in num_cols:
            Q1 = df[col_name].quantile(0.25)
            Q3 = df[col_name].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            outliers = df[(df[col_name] < lower) | (df[col_name] > upper)]
            outlier_summary.append({
                "Column": col_name,
                "Outlier Count": len(outliers),
                "Outlier %": round(len(outliers) / len(df) * 100, 2),
                "Lower Bound": round(lower, 2),
                "Upper Bound": round(upper, 2)
            })

        outlier_df = pd.DataFrame(outlier_summary)
        st.dataframe(outlier_df.style.background_gradient(cmap='Oranges', subset=['Outlier %']), use_container_width=True)

        with st.expander("📦 View Box Plots for Outliers"):
            for col_name in num_cols:
                fig = px.box(df, y=col_name, title=f"Box Plot — {col_name}",
                             color_discrete_sequence=[chart_colors[2]])
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

    # --- 6. Categorical Column Analysis ---
    if cat_cols:
        st.subheader("🗂️ Categorical Column Analysis")
        for col_name in cat_cols:
            unique_count = df[col_name].nunique()
            top_val = df[col_name].value_counts().idxmax()
            st.markdown(f"**{col_name}** — {unique_count} unique values | Most common: `{top_val}`")

            val_counts = df[col_name].value_counts().reset_index()
            val_counts.columns = [col_name, "count"]
            val_counts = val_counts.head(15)

            fig = px.bar(
                val_counts, x=col_name, y="count",
                color="count",
                color_continuous_scale="Blues",
                title=f"Value Counts — {col_name} (Top 15)"
            )
            fig.update_layout(height=300, margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

    # --- 7. Correlation Heatmap ---
    if len(num_cols) >= 2:
        st.subheader("🔥 Correlation Heatmap")
        corr = df[num_cols].corr()

        fig, ax = plt.subplots(figsize=(max(6, len(num_cols)), max(4, len(num_cols) - 1)))
        sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm",
                    ax=ax, linewidths=0.5, square=True)
        ax.set_title("Feature Correlation Matrix")
        st.pyplot(fig)
        close_fig(fig)

        st.markdown("**Top Correlated Pairs:**")
        mask = np.triu(np.ones(corr.shape), k=1).astype(bool)
        corr_pairs = corr.where(mask).stack().reset_index()
        corr_pairs.columns = ["Feature 1", "Feature 2", "Correlation"]
        corr_pairs["Abs Correlation"] = corr_pairs["Correlation"].abs()
        corr_pairs = corr_pairs.sort_values("Abs Correlation", ascending=False).head(10)
        
        st.dataframe(corr_pairs[["Feature 1", "Feature 2", "Correlation"]].round(3).style.background_gradient(cmap='Greens', subset=['Correlation']),
                     use_container_width=True)

# ---------- REPORT ----------
def generate_report(df, insights):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Luminant BI - Automated Data Analysis Report", styles['Title']))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("1. Dataset Overview", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    table_data = [
        ["Metric", "Value"],
        ["Total Rows", str(df.shape[0])],
        ["Total Columns", str(df.shape[1])],
        ["Numeric Columns", str(len(num_cols))],
        ["Categorical Columns", str(len(cat_cols))],
        ["Missing Cells", str(df.isnull().sum().sum())],
        ["Duplicate Rows", str(df.duplicated().sum())]
    ]
    
    t = Table(table_data, colWidths=[200, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2196F3")), 
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8f9fa")), 
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#dddddd")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("2. Automated Insights & Correlations", styles['Heading2']))
    elements.append(Spacer(1, 10))

    for insight in insights:
        clean = strip_emoji(insight)  
        if clean:
            elements.append(Paragraph(f"• {clean}", styles['Normal']))
            elements.append(Spacer(1, 5))

    elements.append(Spacer(1, 15))

    elements.append(Paragraph("3. Data Visualizations", styles['Heading2']))
    elements.append(Spacer(1, 10))

    num = df.select_dtypes(include=[np.number]).columns  

    def save_fig(fig):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        fig.savefig(tmp.name, bbox_inches="tight", dpi=150) 
        close_fig(fig)  
        return tmp.name

    if len(num) > 0:
        elements.append(Paragraph(f"Distribution of {num[0]}", styles['Heading3']))
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.histplot(df[num[0]], kde=True, ax=ax, color="#4CAF50") 
        ax.set_title(f"Distribution of {num[0]}")
        path = save_fig(fig)
        elements.append(Image(path, width=350, height=230))
        elements.append(Spacer(1, 15))

    if len(num) >= 2:
        elements.append(Paragraph(f"Relationship: {num[0]} vs {num[1]}", styles['Heading3']))
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.scatterplot(x=df[num[0]], y=df[num[1]], alpha=0.6, ax=ax, color="#2196F3")
        ax.set_title(f"{num[0]} vs {num[1]}")
        path = save_fig(fig)
        elements.append(Image(path, width=350, height=230))
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("Feature Correlation Matrix", styles['Heading3']))
        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(df[num].corr(), annot=True, cmap="coolwarm", fmt=".2f", ax=ax)
        path = save_fig(fig)
        elements.append(Image(path, width=350, height=300))

    doc = SimpleDocTemplate(buffer)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ---------- LOGIN/SIGNUP UI ----------
if st.session_state.user is None:
    # Wrap login UI in a container so we can clear it immediately upon success
    login_container = st.empty()
    
    with login_container.container():
        st.title("🔐 Luminant BI")
        mode = st.radio("", ["Login", "Sign Up"], horizontal=True)
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        remember_me = st.checkbox("Remember me on this device", value=True)

        if st.button("Proceed"):
            res = sign_in(email, password) if mode == "Login" else sign_up(email, password)
            if "email" in res:
                # 1. Set session state
                st.session_state.user = {"email": email, "username": username or email.split('@')[0]}
                
                # 2. Save cookie to remember user
                if remember_me:
                    cookies["saved_email"] = email
                    cookies.save()
                
                # 3. Clear UI immediately. Do NOT rerun, let the script finish naturally.
                login_container.empty()
            else:
                st.error("Authentication Failed. Please check your credentials.")

# CRITICAL: Stop execution if user is still not logged in
if st.session_state.user is None:
    st.stop()

# ---------- MAIN APP ----------
st.title("📊 Luminant BI Dashboard")

with st.sidebar:
    st.success(f"Logged in as {st.session_state.user['username']}")

    if st.button("Logout"):
        st.session_state.user = None
        if "saved_email" in cookies:
            del cookies["saved_email"]
            cookies.save()
        # Sleep to give browser time to delete the cookie before refreshing
        time.sleep(0.5)
        st.rerun()

    file = st.file_uploader("Upload CSV", type=["csv"])

    st.markdown("### 🧹 Cleaning")
    remove_duplicates = st.checkbox("Remove duplicates")
    drop_missing = st.checkbox("Drop missing rows")
    fill_method = st.selectbox("Fill missing values", ["None", "Mean", "Median", "Mode"])

    if drop_missing and fill_method != "None":
        st.warning("⚠️ 'Drop missing rows' and 'Fill missing values' are both on. Drop runs first, leaving nothing to fill.")

if file:
    df = pd.read_csv(file)

    if remove_duplicates:
        df = df.drop_duplicates()

    if drop_missing:
        df = df.dropna()

    if fill_method != "None" and not drop_missing:
        for col in df.select_dtypes(include=[np.number]).columns:
            if fill_method == "Mean":
                df[col] = df[col].fillna(df[col].mean())
            elif fill_method == "Median":
                df[col] = df[col].fillna(df[col].median())
            elif fill_method == "Mode":
                mode_vals = df[col].mode()
                if not mode_vals.empty: 
                    df[col] = df[col].fillna(mode_vals[0])

    insights, corr = generate_insights(df)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Dashboard", "Visualizations", "Auto EDA", "Insights", "Report"])

    with tab1:
        st.markdown("## 📊 Dashboard")
        st.caption("A quick overview of your dataset — key stats and the full data table.")

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='metric-card'>Rows<br>{df.shape[0]}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='metric-card'>Columns<br>{df.shape[1]}</div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='metric-card'>Missing<br>{df.isnull().sum().sum()}</div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='metric-card'>Duplicates<br>{df.duplicated().sum()}</div>", unsafe_allow_html=True)

        st.markdown("---")

        st.dataframe(df)
        st.download_button("Download Cleaned CSV", df.to_csv(index=False), "cleaned.csv")

    with tab2:
        st.markdown("## 📈 Visualizations")
        st.caption("Interactively explore your data — select columns to generate histograms, box plots, scatter plots, bar charts, and a correlation heatmap.")
        num = df.select_dtypes(include=[np.number]).columns 
        cat = df.select_dtypes(include=['object', 'category']).columns

        if len(num) > 0:
            col = st.selectbox("Column", num, key="viz_col")
            st.plotly_chart(px.histogram(df, x=col, color_discrete_sequence=[chart_colors[0]]))
            st.plotly_chart(px.box(df, y=col, color_discrete_sequence=[chart_colors[1]]))

        if len(num) >= 2:
            x = st.selectbox("X axis", num, key="scatter_x")
            y = st.selectbox("Y axis", num, key="scatter_y")

            if len(cat) > 0:
                color = st.selectbox("Color by", [None] + list(cat), key="scatter_color")
                if color:
                    fig = px.scatter(df, x=x, y=y, color=color)
                else:
                    fig = px.scatter(df, x=x, y=y, color_discrete_sequence=[chart_colors[2]])
            else:
                fig = px.scatter(df, x=x, y=y, color_discrete_sequence=[chart_colors[2]])

            st.plotly_chart(fig)

        if len(cat) > 0:
            c = st.selectbox("Category", key="cat_col", options=cat)
            count_df = df[c].value_counts().reset_index()
            count_df.columns = [c, "count"]
            st.plotly_chart(px.bar(count_df, x=c, y="count"))

        if len(num) >= 2:
            fig, ax = plt.subplots()
            sns.heatmap(df[num].corr(), annot=True, cmap="coolwarm", ax=ax)
            st.pyplot(fig)
            close_fig(fig)

    with tab3:
        st.markdown("## 🔬 Automatic Exploratory Data Analysis")
        st.caption("Full EDA report generated automatically from your dataset.")
        run_auto_eda(df)

    with tab4:
        st.markdown("## 💡 Insights")
        st.caption("Automatically detected relationships between numeric columns based on correlation strength.")

        n_strong   = sum(1 for i in insights if i.startswith("Strong"))
        n_moderate = sum(1 for i in insights if i.startswith("Moderate"))
        n_cat      = sum(1 for i in insights if i.startswith("Category"))
        n_none     = 1 if insights == ["No strong relationships found"] else 0

        pills_html = '<div class="insight-summary">'
        if n_strong:
            pills_html += f'<div class="insight-summary-pill strong">✅ {n_strong} Strong</div>'
        if n_moderate:
            pills_html += f'<div class="insight-summary-pill moderate">🟡 {n_moderate} Moderate</div>'
        if n_cat:
            pills_html += f'<div class="insight-summary-pill strong">📊 {n_cat} Dominant Categories</div>'
        if n_none:
            pills_html += f'<div class="insight-summary-pill none"> 🔴 No strong patterns</div>'
        pills_html += '</div>'
        st.markdown(pills_html, unsafe_allow_html=True)

        for insight in insights:
            if insight.startswith("Strong"):
                parts   = insight.replace("Strong: ", "").rsplit("(", 1)
                pair_desc = parts[0].strip()
                score   = parts[1].replace(")", "").strip() if len(parts) > 1 else ""
                
                card_html = f"""
                <div class="insight-card strong">
                    <div class="insight-badge strong">🟢</div>
                    <div class="insight-body">
                        <div class="insight-label strong">Strong Correlation</div>
                        <div class="insight-text">{pair_desc}</div>
                    </div>
                    <div class="insight-score strong">{score}</div>
                </div>"""

            elif insight.startswith("Moderate"):
                parts   = insight.replace("Moderate: ", "").rsplit("(", 1)
                pair_desc = parts[0].strip()
                score   = parts[1].replace(")", "").strip() if len(parts) > 1 else ""
                
                card_html = f"""
                <div class="insight-card moderate">
                    <div class="insight-badge moderate">🟡</div>
                    <div class="insight-body">
                        <div class="insight-label moderate">Moderate Correlation</div>
                        <div class="insight-text">{pair_desc}</div>
                    </div>
                    <div class="insight-score moderate">{score}</div>
                </div>"""

            elif insight.startswith("Category"):
                desc = insight.replace("Category: ", "").strip()
                card_html = f"""
                <div class="insight-card strong">
                    <div class="insight-badge strong">📊</div>
                    <div class="insight-body">
                        <div class="insight-label strong">Dominant Category</div>
                        <div class="insight-text">{desc}</div>
                    </div>
                </div>"""

            else:
                card_html = """
                <div class="insight-card none">
                    <div class="insight-badge none">🔴</div>
                    <div class="insight-body">
                        <div class="insight-label none">All Clear</div>
                        <div class="insight-text">No significant patterns found</div>
                    </div>
                </div>"""

            st.markdown(card_html, unsafe_allow_html=True)

    with tab5:
        st.markdown("## 📄 Report")
        st.caption("Download a PDF report of your dataset including key insights and charts.")
        report = generate_report(df, insights)
        st.download_button("Download PDF", report, "report.pdf")

else:
    st.info("Upload dataset to start")
