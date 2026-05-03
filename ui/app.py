from __future__ import annotations

import json
import os

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="IndiaIR", layout="wide")
st.title("IndiaIR")


def api_get(path: str, params: dict | None = None):
    with httpx.Client(timeout=30) as client:
        response = client.get(f"{API_BASE_URL}{path}", params=params)
        response.raise_for_status()
        return response.json()


def api_post(path: str, payload: dict):
    with httpx.Client(timeout=120) as client:
        response = client.post(f"{API_BASE_URL}{path}", json=payload)
        response.raise_for_status()
        return response


@st.cache_data(ttl=60)
def load_companies() -> list[dict]:
    try:
        return api_get("/api/v1/companies")
    except Exception:
        return []


companies = load_companies()
company_by_name = {company["name"]: company for company in companies}
sectors = sorted({company.get("sector") for company in companies if company.get("sector")})

with st.sidebar:
    st.header("Filters")
    selected_sectors = st.multiselect("Sector", sectors)
    visible_companies = [c for c in companies if not selected_sectors or c.get("sector") in selected_sectors]
    selected_names = st.multiselect("Company", [c["name"] for c in visible_companies])
    selected_ids = [company_by_name[name]["id"] for name in selected_names]
    document_types = st.multiselect("Document type", ["concall_transcript", "investor_presentation", "results_press_release", "management_change"])
    speaker_roles = st.multiselect("Speaker role", ["management", "analyst", "moderator", "unknown", "press_release"])
    if st.button("Run mock ingestion"):
        api_post("/api/v1/pipeline/mock-ingest", {})
        st.cache_data.clear()
        st.rerun()

page = st.sidebar.radio("View", ["Search", "Q&A", "Company", "Financials", "Management Changes", "Coverage Dashboard"])

if page == "Search":
    query = st.text_input("Search filings", value="CDMO capacity")
    mode = st.segmented_control("Mode", ["keyword", "semantic"], default="keyword")
    if st.button("Search") and query:
        payload = {"query": query, "companies": selected_ids or None, "document_types": document_types or None, "speaker_roles": speaker_roles or None, "page": 1, "page_size": 20}
        data = api_post(f"/api/v1/search/{mode}", payload).json()
        st.caption(f"{data['total']} results in {data['took_ms']} ms")
        for result in data["results"]:
            st.subheader(f"{result['company_name']} {result.get('quarter') or ''}")
            st.markdown(result["snippet"], unsafe_allow_html=True)
            st.caption(f"{result['document_type']} | {result.get('speaker_name') or result.get('speaker_role') or 'source'} | document {result['document_id']}")

elif page == "Q&A":
    question = st.text_area("Question", value="What has Laurus Labs management said about CDMO capacity utilization?")
    if st.button("Ask") and question:
        payload = {"question": question, "company_ids": selected_ids or None}
        placeholder = st.empty()
        answer = ""
        citations = []
        financials = []
        with httpx.stream("POST", f"{API_BASE_URL}/api/v1/qa/ask", json=payload, timeout=120) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                if event["type"] == "token":
                    answer += event["content"]
                    placeholder.markdown(answer, unsafe_allow_html=True)
                elif event["type"] == "citations":
                    citations = event["citations"]
                elif event["type"] == "financials":
                    financials = event["data"]
        if citations:
            st.subheader("Citations")
            st.dataframe(pd.DataFrame(citations), use_container_width=True)
        if financials:
            st.subheader("Financial context")
            st.dataframe(pd.DataFrame(financials), use_container_width=True)

elif page == "Company":
    name = st.selectbox("Company", [company["name"] for company in companies] or [""])
    if name:
        company = company_by_name[name]
        detail = api_get(f"/api/v1/companies/{company['id']}")
        st.metric("Indexed documents", detail.get("document_count") or 0)
        events = api_get(f"/api/v1/companies/{company['id']}/events")
        st.subheader("Timeline")
        st.dataframe(pd.DataFrame(events), use_container_width=True)
        st.subheader("Transcript Viewer")
        st.info("Use Search to open source document IDs and speaker-attributed passages.")

elif page == "Financials":
    frames = []
    for company in companies:
        if selected_ids and company["id"] not in selected_ids:
            continue
        rows = api_get(f"/api/v1/companies/{company['id']}/financials")
        for row in rows:
            row["company_name"] = company["name"]
        frames.extend(rows)
    if frames:
        df = pd.DataFrame(frames)
        metric = st.selectbox("Metric", ["revenue", "ebitda", "pat", "ebitda_margin"])
        fig = px.line(df, x="period", y=metric, color="company_name", markers=True)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No financial rows yet. Run mock ingestion or process results press releases.")

elif page == "Management Changes":
    params = {"page": 1, "page_size": 100}
    if selected_ids and len(selected_ids) == 1:
        params["company_id"] = selected_ids[0]
    data = api_get("/api/v1/management-changes", params=params)
    st.dataframe(pd.DataFrame(data["results"]), use_container_width=True)

else:
    health = api_get("/api/v1/health")
    st.json(health)
    st.subheader("Coverage")
    st.dataframe(pd.DataFrame(companies), use_container_width=True)
