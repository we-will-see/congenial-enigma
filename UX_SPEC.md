# UX Specification
## IndiaIR — Wireframes, States, Accessibility
### Version 1.0 | April 2026

---

> **For AI coding agents:** Implement the Streamlit UI exactly as specified here. Every empty state, error state, and loading state must be implemented. Do not add pages or components not listed here. Use `st.set_page_config(layout="wide")` on all pages.

---

## 1. Global Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  SIDEBAR                    MAIN CONTENT                        │
│  ──────────                 ────────────                        │
│  📊 IndiaIR                 [page content]                      │
│                                                                 │
│  Navigation                                                     │
│  • 🔍 Search                                                    │
│  • 💬 Q&A                                                       │
│  • 🏢 Companies                                                 │
│  • 📈 Financials                                                │
│  • 👤 Management Changes                                        │
│  • ⚙️  Coverage                                                 │
│                                                                 │
│  ──────────                                                     │
│  Status                                                         │
│  DB: ✅  ES: ✅                                                 │
│  Last ingested: 2h ago                                          │
└─────────────────────────────────────────────────────────────────┘
```

Sidebar status panel calls `GET /api/v1/health` on page load. Shows ✅ / ❌ per component.

---

## 2. Page: Search

**URL path / sidebar label:** 🔍 Search

```
┌─────────────────────────────────────────────────────┐
│  Search filings                                     │
│                                                     │
│  [          Search across all filings...          ] │
│                                                     │
│  Filters (collapsible, default collapsed)           │
│  ┌─────────────────────────────────────────────┐   │
│  │ Companies: [All ▼]  (multi-select)          │   │
│  │ Quarters:  [1QFY21 ▼] to [4QFY26 ▼]        │   │
│  │ Type:      [All ▼]  (transcript/pres/PR)    │   │
│  │ Speaker:   [All ▼]  (management/analyst)    │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  [Search]                                           │
│                                                     │
│  ────────────────────────────────────────────────  │
│  RESULTS (42 results in 0.8s)                       │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ Laurus Labs · 3QFY25 · Management           │   │
│  │ Concall Transcript · Jan 23, 2025           │   │
│  │ "...we expect **capacity utilization** to   │   │
│  │  improve to 85% by Q1FY26 as the new CDMO  │   │
│  │  block comes online..."                     │   │
│  │ [View in context →]                         │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  [Previous] Page 1 of 3 [Next]                      │
└─────────────────────────────────────────────────────┘
```

**States:**

*Loading:* `st.spinner("Searching...")` shown while request in flight.

*Empty:*
```
No results found for "xyzzy".
Try: broader terms, fewer filters, or check the Coverage page to confirm this company is indexed.
```

*Error (ES down):*
```
st.error("Search is temporarily unavailable. Please try again in a moment.")
```

*No query entered:* Show placeholder text only, no results panel. Do not auto-search.

**Snippet formatting:** Matched terms wrapped in `**bold**` (rendered by Streamlit markdown). Max 300 characters per snippet, truncated with `…`.

---

## 3. Page: Q&A

**URL path / sidebar label:** 💬 Q&A

```
┌─────────────────────────────────────────────────────┐
│  Ask a question                                     │
│                                                     │
│  Scope (optional)                                   │
│  Companies: [All ▼]   Quarters: [All ▼]            │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ What has Laurus Labs said about CDMO       │   │
│  │ capacity over the last 6 quarters?         │   │
│  └─────────────────────────────────────────────┘   │
│  [Ask]                                              │
│                                                     │
│  ─────────────────────────────────────────────     │
│                          SOURCES         FINANCIALS│
│  ANSWER              │ [Laurus 3QFY25] │ Revenue   │
│                       │ [Laurus 2QFY25] │ EBITDA%  │
│  Based on management │ [Laurus 1QFY25] │ chart     │
│  commentary across   │ ...             │           │
│  6 quarters...       │                 │           │
│  [Laurus, 3QFY25,    │                 │           │
│   Management]        │                 │           │
│                                                     │
│  Follow-up: [                                     ] │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Layout:** Three-column (`st.columns([3, 1, 1])`). Answer streams into left column. Sources panel (middle) shows citation cards. Financial panel (right) shows chart if relevant.

**States:**

*Streaming:* Answer text streams token by token using `st.write_stream`. Do not show spinner — streaming itself provides feedback.

*No relevant context found:*
```
I could not find relevant information for this question in the available filings.
Try: rephrasing, scoping to a specific company, or checking that the relevant quarter is indexed.
```
This message must appear inline in the answer area, not as `st.error`.

*API unavailable:*
```
st.error("Unable to generate answer. The AI service is temporarily unavailable. Please try again.")
```
Do not show partial responses on error.

*Session context:* Last question/answer pair shown above input as context. Maximum 2 turns shown. `st.session_state` used for session management.

**Citation cards (sources panel):**
```
┌────────────────────────┐
│ Laurus Labs            │
│ 3QFY25 · Management   │
│ Concall Transcript     │
│ "...capacity utiliza..." │
│ [View full passage →]  │
└────────────────────────┘
```

---

## 4. Page: Company

**URL path / sidebar label:** 🏢 Companies (then select company)

```
┌─────────────────────────────────────────────────────┐
│  [← Back to companies]                              │
│  Laurus Labs (BSE: 540222)                          │
│  CDMO / API · Indexed: 47 events                   │
│                                                     │
│  ┌── Revenue & EBITDA Margin ────────────────────┐  │
│  │  [Plotly chart — 20 quarters, dual axis]      │  │
│  │  Bar: Revenue (Cr)  Line: EBITDA margin (%)   │  │
│  │  ⚠️ = restatement flag (hover for detail)     │  │
│  └────────────────────────────────────────────────┘ │
│                                                     │
│  ┌── Management ─────────────────────────────────┐  │
│  │  V.V. Ravi Kumar · CFO · Since Apr 2019       │  │
│  │  Dr. Satyanarayana Chava · MD & CEO · Since.. │  │
│  │  [View full history →]                         │  │
│  └────────────────────────────────────────────────┘ │
│                                                     │
│  ┌── Event Timeline ─────────────────────────────┐  │
│  │  4QFY26  Apr 2026  [Transcript] [Pres] [PR]   │  │
│  │  3QFY26  Jan 2026  [Transcript] [PR]           │  │
│  │  2QFY26  Oct 2025  [Transcript] [Pres] [PR]   │  │
│  │  ...                                           │  │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

**States:**

*Loading financials chart:* `st.spinner("Loading financial data...")`

*No financials data:*
```
Financial data not yet extracted for this company.
Check the Coverage page for extraction status.
```

*Restatement flag tooltip:* `⚠️ Revenue restated from ₹1,480 Cr to ₹1,547 Cr (Apr 2025)`

*No events in timeline:* `No events indexed for this company yet.`

---

## 5. Page: Financials Comparison

**URL path / sidebar label:** 📈 Financials

```
┌─────────────────────────────────────────────────────┐
│  Financial Comparison                               │
│                                                     │
│  Companies: [Laurus Labs ×] [Divi's ×] [+ Add]    │
│  Metric: (•) Revenue  ( ) EBITDA  ( ) EBITDA%     │
│          ( ) PAT      ( ) EPS                      │
│  Period:  [1QFY23 ▼] to [4QFY26 ▼]               │
│                                                     │
│  [Compare]                                          │
│                                                     │
│  ┌── Chart ────────────────────────────────────┐   │
│  │  [Plotly line chart — one line per company] │   │
│  │  Restatement markers: ⚠️ on data points     │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌── Data Table ────────────────────────────────┐  │
│  │  Period   Laurus   Divi's   Syngene          │  │
│  │  3QFY25   1,547    2,103    876              │  │
│  │  2QFY25   1,423    1,987    844  ⚠️          │  │
│  └──────────────────────────────────────────────┘  │
│  [Download CSV]                                     │
└─────────────────────────────────────────────────────┘
```

**States:**

*No companies selected:* `Select at least one company to compare.`

*One company only:* Show single-company chart (still useful).

*Missing data for a period:* Show gap in line chart. In table, show `—` for missing values.

*All data missing:* `No financial data available for the selected companies and period.`

---

## 6. Page: Management Changes

**URL path / sidebar label:** 👤 Management Changes

```
┌─────────────────────────────────────────────────────┐
│  Management Changes                                 │
│                                                     │
│  Company: [All ▼]  Role: [KMP ▼]  Type: [All ▼]   │
│  From: [Apr 2024 ▼]  To: [Apr 2026 ▼]             │
│                                                     │
│  23 changes across 12 companies                    │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ Apr 15 2026  Laurus Labs                     │  │
│  │ V.V. Ravi Kumar · CFO · APPOINTMENT          │  │
│  │ Effective: Apr 15 2026                       │  │
│  │ [View filing] [Next concall →]               │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ Mar 01 2026  Syngene International           │  │
│  │ Jonathan Hunt · MD & CEO · RESIGNATION       │  │
│  │ Effective: Mar 31 2026 · Reason: Personal    │  │
│  │ [View filing] [Next concall →]               │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Change type colour coding:**
- APPOINTMENT: `st.success` green border
- RESIGNATION / CESSATION: `st.error` red border
- RETIREMENT: neutral grey border
- RE_APPOINTMENT / ADDITIONAL_CHARGE: `st.info` blue border

**Expanded row (on click):**
```
▼ Mar 01 2026  Syngene International
  Jonathan Hunt · MD & CEO · RESIGNATION
  Effective: Mar 31 2026 · Reason: Personal reasons

  Raw filing text:
  "This is to inform that Jonathan Hunt has tendered his resignation
   as Managing Director & CEO effective March 31, 2026, citing personal reasons..."

  Next concall: 4QFY26 Results Call (Apr 28, 2026) [View transcript →]
```

**States:**

*No results for filters:*
```
No management changes found for the selected filters.
Try broadening the date range or removing company/role filters.
```

---

## 7. Page: Coverage Dashboard

**URL path / sidebar label:** ⚙️ Coverage

For internal use. Shows extraction status across all 30 companies.

```
┌─────────────────────────────────────────────────────┐
│  Coverage Dashboard                                 │
│  Last pipeline run: Apr 30 2026, 09:03 IST  ✅     │
│                                                     │
│  ┌── Overall Stats ───────────────────────────────┐ │
│  │  Documents: 2,847 total                        │ │
│  │  Extracted: 2,701 (94.9%)  ✅                  │ │
│  │  Failed: 62 (2.2%)         ⚠️                  │ │
│  │  Pending: 84 (3.0%)        🔄                  │ │
│  └────────────────────────────────────────────────┘ │
│                                                     │
│  ┌── Per-Company Table ──────────────────────────┐  │
│  │ Company       Events  Extracted  Failed  Fin  │  │
│  │ Laurus Labs   89      87         0       20✅ │  │
│  │ Divi's        76      73         1       20✅ │  │
│  │ Cohance       34      28         3       12⚠️ │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  [Re-run failed documents]  [Export status CSV]     │
└─────────────────────────────────────────────────────┘
```

**Fin column:** Count of quarters with financial data. ✅ if complete for expected periods; ⚠️ if gaps.

---

## 8. Transcript Viewer (Modal / Inline)

Opens when user clicks "View in context →" from Search results or citation cards.

```
┌─────────────────────────────────────────────────────┐
│  Laurus Labs — Concall Transcript                   │
│  3QFY25 · January 23, 2025                         │
│  [← Back to results]  [Open original PDF ↗]       │
│                                                     │
│  ...                                                │
│  ─────────────────────────────────────────          │
│  V.V. Ravi Kumar (CFO)                              │
│  "Thank you. On margins, we expect **capacity       │
│  utilization** to improve to 85% by Q1FY26 as the  │
│  new CDMO block comes online. The capex for this    │
│  block is largely complete."                        │
│  ─────────────────────────────────────────  ◀ JUMP │
│                                                     │
│  Neha Manpuria (JPMorgan)                           │
│  "Thank you. My follow-up question is on..."        │
│  ...                                                │
└─────────────────────────────────────────────────────┘
```

The `◀ JUMP` marker appears next to the passage that was searched/cited — page auto-scrolls to it on load. Implemented via `st.markdown` with an HTML anchor `id`.

---

## 9. Responsive Behaviour

Streamlit with `layout="wide"` is the baseline. No custom responsive CSS required for MVP.

**Minimum supported viewport:** 1280px wide (standard laptop). Below this, Streamlit's default responsive behaviour applies.

**Tables:** Use `st.dataframe` with `use_container_width=True`. Long tables paginate via Streamlit's built-in dataframe pagination.

**Charts:** All Plotly charts use `use_container_width=True`.

---

## 10. Loading and Empty State Summary

Every component that fetches data must have all three states implemented:

| Component | Loading | Empty | Error |
|---|---|---|---|
| Search results | `st.spinner` | "No results found..." | `st.error` |
| Q&A answer | Streaming (no spinner) | Inline "not found" message | `st.error` |
| Company financials chart | `st.spinner` | "Financial data not yet extracted..." | `st.error` |
| Management changes list | `st.spinner` | "No changes found for filters..." | `st.error` |
| Coverage table | `st.spinner` | Should never be empty if pipeline ran | `st.error` |
| Sidebar health status | `st.spinner` (small) | N/A | Shows ❌ |

**Never show:** blank white space, `None`, uncaught Python exceptions in the UI. All exceptions caught and displayed via `st.error`.

---

*Last Updated: April 2026 | Version 1.0*
