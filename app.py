import os

import pandas as pd
import streamlit as st

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(APP_DIR, "team_vibecoder.csv")

st.set_page_config(
    page_title="India Runs AI — Team Vibecoder",
    page_icon="🧭",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_rankings(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"candidate_id": str})
    df["rank"] = df["rank"].astype(int)
    df["score"] = df["score"].astype(float)
    df["reasoning"] = df["reasoning"].astype(str)
    return df.sort_values("rank").reset_index(drop=True)


with st.sidebar:
    st.header("System Stats")
    st.metric("Execution Time", "< 5s")
    st.metric("Peak RAM", "~0.4 GB")
    st.metric("Architecture", "Offline FAISS Two-Pass")
    st.divider()
    st.caption(
        "CPU-only · zero network during ranking · no LLMs · "
        "grounded zero-hallucination reasoning."
    )

st.title("India Runs AI: Intelligent Candidate Discovery (Team Vibecoder)")
st.caption(
    "Top 100 ranked candidates with grounded, AST-derived reasoning for every match."
)

if not os.path.exists(CSV_PATH):
    st.error(
        f"Could not find `team_vibecoder.csv` at {CSV_PATH}. "
        "Run the ranker to generate it, then refresh."
    )
    st.stop()

df = load_rankings(CSV_PATH)

c1, c2, c3 = st.columns(3)
c1.metric("Candidates Ranked", f"{len(df):,}")
c2.metric("Top Score", f"{df['score'].max():.3f}")
c3.metric("Cutoff Score (#100)", f"{df['score'].min():.3f}")

query = st.text_input(
    "Filter by candidate ID or reasoning keyword",
    placeholder="e.g. CAND_0068351, RAG, LangChain, Qdrant…",
)

view = df
if query:
    mask = df["candidate_id"].str.contains(query, case=False, na=False) | df[
        "reasoning"
    ].str.contains(query, case=False, na=False)
    view = df[mask]
    st.caption(f"Showing {len(view)} of {len(df)} candidates matching “{query}”.")

st.dataframe(
    view,
    width="stretch",
    hide_index=True,
    height=620,
    column_config={
        "candidate_id": st.column_config.TextColumn("Candidate ID", width="medium"),
        "rank": st.column_config.NumberColumn("Rank", format="%d", width="small"),
        "score": st.column_config.ProgressColumn(
            "Score",
            help="Normalized relevance score in [0, 1] (rank 1 = 1.000).",
            format="%.4f",
            min_value=0.0,
            max_value=1.0,
            width="small",
        ),
        "reasoning": st.column_config.TextColumn(
            "Reasoning (grounded)",
            help="Zero-hallucination reasoning derived directly from candidate data.",
            width="large",
        ),
    },
)

with st.expander("Read full reasoning per candidate"):
    for _, row in view.iterrows():
        st.markdown(
            f"**#{row['rank']} · {row['candidate_id']}** "
            f"· score {row['score']:.4f}"
        )
        st.write(row["reasoning"])
        st.divider()
