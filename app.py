import streamlit as st
import pandas as pd
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ---------- PAGE CONFIG (must be first Streamlit command) ----------
st.set_page_config(page_title="Auto BI Analytics Tool", layout="wide")

# ---------- CUSTOM FONT ----------
st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"]  {
    font-family: 'Inter', sans-serif;
}

h1, h2, h3 {
    letter-spacing: -0.04em;
}

p, div, span, label {
    letter-spacing: -0.02em;
}

</style>
""", unsafe_allow_html=True)

# ---------- TITLE ----------
st.title("📊 Auto BI — Automated Data Analysis Tool")
st.caption("Automatic exploratory data analysis and visualization dashboard")

# ---------- COLOR PALETTE ----------
chart_colors = [
    "#4CAF50",
    "#FF9800",
    "#9C27B0",
    "#2196F3",
    "#F44336",
    "#009688",
]

# ---------- SIDEBAR ----------
with st.sidebar:

    st.header("📂 Dataset")

    file = st.file_uploader(
        "Upload CSV Dataset",
        type=["csv"],
        key="dataset_uploader"
    )

    st.markdown("---")

    st.header("🧹 Data Cleaning")

    remove_duplicates = st.checkbox("Remove duplicate rows")
    drop_missing = st.checkbox("Drop rows with missing values")

# ---------- REPORT FUNCTION ----------
def generate_report(df):

    buffer = BytesIO()
    styles = getSampleStyleSheet()

    elements = []

    elements.append(Paragraph("Auto BI Data Analysis Report", styles['Title']))
    elements.append(Spacer(1,20))

    elements.append(Paragraph(f"Rows: {df.shape[0]}", styles['Normal']))
    elements.append(Paragraph(f"Columns: {df.shape[1]}", styles['Normal']))

    elements.append(Spacer(1,20))

    summary = df.describe().to_string()

    elements.append(Paragraph("Statistical Summary", styles['Heading2']))
    elements.append(Spacer(1,10))

    elements.append(Paragraph(summary.replace("\n","<br/>"), styles['Normal']))

    doc = SimpleDocTemplate(buffer)
    doc.build(elements)

    buffer.seek(0)

    return buffer

# ---------- MAIN APP ----------
if file is not None:

    df = pd.read_csv(file)

    if remove_duplicates:
        df = df.drop_duplicates()

    if drop_missing:
        df = df.dropna()

    numeric_cols = df.select_dtypes(include=['int64','float64']).columns
    cat_cols = df.select_dtypes(include=['object']).columns

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Dashboard",
        "📈 Visualizations",
        "🔍 Auto EDA",
        "📄 Report"
    ])

# ---------- DASHBOARD ----------
    with tab1:

        st.subheader("Dataset Overview")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Rows", df.shape[0])
        c2.metric("Columns", df.shape[1])
        c3.metric("Missing Values", df.isnull().sum().sum())
        c4.metric("Duplicate Rows", df.duplicated().sum())

        st.subheader("Dataset Preview")

        st.dataframe(df)

        st.subheader("Statistical Summary")

        st.write(df.describe())

        st.download_button(
            "Download Cleaned Dataset",
            df.to_csv(index=False),
            "cleaned_dataset.csv"
        )

# ---------- VISUALIZATIONS ----------
    with tab2:

        st.subheader("Interactive Charts")

        if len(numeric_cols) > 0:

            column = st.selectbox("Select Numeric Column", numeric_cols)

            fig = px.histogram(
                df,
                x=column,
                color_discrete_sequence=[chart_colors[0]],
                title=f"Distribution of {column}"
            )

            st.plotly_chart(fig, use_container_width=True)

            fig2 = px.box(
                df,
                y=column,
                color_discrete_sequence=[chart_colors[1]],
                title=f"Box Plot of {column}"
            )

            st.plotly_chart(fig2, use_container_width=True)

        if len(numeric_cols) >= 2:

            st.subheader("Scatter Plot")

            x = st.selectbox("X Axis", numeric_cols, key="scatter_x")
            y = st.selectbox("Y Axis", numeric_cols, key="scatter_y")

            fig3 = px.scatter(
                df,
                x=x,
                y=y,
                color_discrete_sequence=[chart_colors[2]],
                title=f"{x} vs {y}"
            )

            st.plotly_chart(fig3, use_container_width=True)

        if len(cat_cols) > 0:

            st.subheader("Categorical Distribution")

            cat = st.selectbox("Categorical Column", cat_cols)

            count_df = df[cat].value_counts().reset_index()
            count_df.columns = [cat, "count"]

            fig4 = px.bar(
                count_df,
                x=cat,
                y="count",
                color=cat,
                color_discrete_sequence=px.colors.qualitative.Set3,
                title=f"{cat} Distribution"
            )

            st.plotly_chart(fig4, use_container_width=True)

        if len(numeric_cols) >= 2:

            st.subheader("Correlation Heatmap")

            corr = df[numeric_cols].corr()

            fig, ax = plt.subplots()

            sns.heatmap(
                corr,
                annot=True,
                cmap="coolwarm",
                ax=ax
            )

            st.pyplot(fig)

# ---------- AUTO EDA ----------
    with tab3:

        st.subheader("Column Types")

        st.write(df.dtypes)

        st.subheader("Missing Values")

        missing = df.isnull().sum()
        st.write(missing)

        missing_rows = df[df.isnull().any(axis=1)]

        st.write("Rows with missing values:", len(missing_rows))

        if not missing_rows.empty:
            st.dataframe(missing_rows)

        st.subheader("Duplicate Rows")

        duplicates = df[df.duplicated()]

        st.write("Duplicate rows:", len(duplicates))

        if not duplicates.empty:
            st.dataframe(duplicates)

        st.subheader("Outlier Detection")

        for col in numeric_cols:

            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)

            iqr = q3 - q1

            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            outliers = df[(df[col] < lower) | (df[col] > upper)]

            st.write(f"{col}: {len(outliers)} outliers")

        st.subheader("Strong Correlations")

        if len(numeric_cols) >= 2:

            corr = df[numeric_cols].corr()

            pairs = corr.unstack().sort_values(ascending=False)

            pairs = pairs[pairs < 1]

            st.write(pairs.head(5))

# ---------- REPORT ----------
    with tab4:

        st.subheader("Download Analysis Report")

        report = generate_report(df)

        st.download_button(
            "Download PDF Report",
            report,
            "autobi_report.pdf",
            "application/pdf"
        )

else:

    st.info("Upload a dataset from the sidebar to begin analysis.")