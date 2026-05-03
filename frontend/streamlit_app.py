import json
import os

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="IndiaIR", layout="wide")


def api_get(path: str, params: dict | None = None):
    response = httpx.get(f"{API_BASE_URL}{path}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict):
    response = httpx.post(f"{API_BASE_URL}{path}", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=60)
def companies():
    return api_get("/api/v1/companies")


company_rows = companies()
company_options = {row["name"]: row["id"] for row in company_rows}

st.sidebar.title("IndiaIR")
page = st.sidebar.radio("View", ["Search", "Q&A", "Company", "Financials", "Management Changes", "Coverage Dashboard", "Transcript"])


def selected_company_ids(label: str = "Companies") -> list[int]:
    selected = st.sidebar.multiselect(label, list(company_options.keys()))
    return [company_options[name] for name in selected]


if page == "Search":
    st.title("Search")
    mode = st.segmented_control("Mode", ["keyword", "semantic"], default="keyword")
    query = st.text_input("Query")
    cols = st.columns(3)
    with cols[0]:
        doc_types = st.multiselect("Document types", ["concall_transcript", "investor_presentation", "results_press_release"])
    with cols[1]:
        roles = st.multiselect("Speaker roles", ["management", "analyst", "unknown", "press_release"])
    with cols[2]:
        page_size = st.number_input("Results", min_value=5, max_value=100, value=20, step=5)
    company_ids = selected_company_ids()
    if st.button("Run search", type="primary", disabled=len(query) < 2):
        payload = {"query": query, "companies": company_ids or None, "document_types": doc_types or None, "speaker_roles": roles or None, "page_size": page_size}
        data = api_post(f"/api/v1/search/{mode}", payload)
        st.caption(f"{data['total']} results in {data['took_ms']} ms")
        for result in data["results"]:
            st.subheader(f"{result['company_name']} - {result.get('quarter') or 'n/a'}")
            st.markdown(result["snippet"], unsafe_allow_html=True)
            st.caption(f"{result['document_type']} | {result.get('speaker_role') or 'n/a'} | document {result['document_id']}")

elif page == "Q&A":
    st.title("Q&A")
    question = st.text_area("Question", height=120)
    company_ids = selected_company_ids()
    if st.button("Ask", type="primary", disabled=not question.strip()):
        payload = {"question": question, "company_ids": company_ids or None}
        with httpx.stream("POST", f"{API_BASE_URL}/api/v1/qa/ask", json=payload, timeout=120) as response:
            response.raise_for_status()
            answer_box = st.empty()
            answer = ""
            citations = []
            financials = []
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line.removeprefix("data: "))
                if event["type"] == "token":
                    answer += event["content"]
                    answer_box.write(answer)
                elif event["type"] == "citations":
                    citations = event["citations"]
                elif event["type"] == "financials":
                    financials = event["data"]
                elif event["type"] == "error":
                    st.error(event["content"])
        if citations:
            st.subheader("Sources")
            st.dataframe(pd.DataFrame(citations), use_container_width=True)
        if financials:
            st.subheader("Financial context")
            st.dataframe(pd.DataFrame(financials), use_container_width=True)

elif page == "Company":
    st.title("Company")
    name = st.selectbox("Company", list(company_options.keys()))
    company_id = company_options[name]
    detail = api_get(f"/api/v1/companies/{company_id}")
    events = api_get(f"/api/v1/companies/{company_id}/events")
    financials = api_get(f"/api/v1/companies/{company_id}/financials")
    st.json(detail["coverage"])
    st.subheader("Timeline")
    st.dataframe(pd.DataFrame(events), use_container_width=True)
    if financials:
        df = pd.DataFrame(financials)
        st.subheader("Financials")
        metric = st.selectbox("Metric", ["revenue", "ebitda", "pat", "ebitda_margin"])
        st.plotly_chart(px.line(df, x="period", y=metric, markers=True, title=f"{name} {metric}"), use_container_width=True)

elif page == "Financials":
    st.title("Financials")
    metric = st.selectbox("Metric", ["revenue", "ebitda", "pat", "ebitda_margin"])
    selected_ids = selected_company_ids()
    rows = []
    for company in company_rows:
        if selected_ids and company["id"] not in selected_ids:
            continue
        for row in api_get(f"/api/v1/companies/{company['id']}/financials"):
            row["company_name"] = company["name"]
            rows.append(row)
    if rows:
        df = pd.DataFrame(rows)
        st.plotly_chart(px.line(df, x="period", y=metric, color="company_name", markers=True), use_container_width=True)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No financial rows available yet.")

elif page == "Management Changes":
    st.title("Management Changes")
    company_id = st.selectbox("Company filter", ["All", *company_options.keys()])
    role_category = st.selectbox("Role category", ["", "kmp", "board_executive", "board_non_executive", "board_independent"])
    change_type = st.selectbox("Change type", ["", "appointment", "resignation", "retirement", "cessation", "re_appointment", "additional_charge"])
    params = {"page_size": 100}
    if company_id != "All":
        params["company_id"] = company_options[company_id]
    if role_category:
        params["role_category"] = role_category
    if change_type:
        params["change_type"] = change_type
    data = api_get("/api/v1/management-changes", params=params)
    st.dataframe(pd.DataFrame(data["results"]), use_container_width=True)

elif page == "Coverage Dashboard":
    st.title("Coverage Dashboard")
    rows = api_get("/api/v1/coverage")
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        st.plotly_chart(px.bar(df, x="company_name", y="documents", color="extraction_status", facet_col="document_type"), use_container_width=True)

elif page == "Transcript":
    st.title("Transcript")
    document_id = st.number_input("Document ID", min_value=1, step=1)
    if st.button("Load transcript"):
        turns = api_get(f"/api/v1/documents/{int(document_id)}/transcript")
        for turn in turns:
            st.markdown(f"**{turn.get('speaker_name') or turn.get('speaker_raw') or 'Unknown'}** · `{turn['speaker_role']}`")
            st.write(turn["text"])
