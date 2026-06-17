"""
app.py
------
The user-facing Streamlit application for demonstration.

"""

import streamlit as st

import config
import ingest
import generate_post as gp

st.set_page_config(page_title="LinkedIn Style Agent", layout="wide")


def render_result(result: dict) -> None:
    """Render a generated post result dict into the Streamlit UI.

    Args:
        result: Output of generate_post_from_topic() or generate_post_from_research().
    """
    st.subheader("Generated Post")
    st.text_area("Full post (copy-paste ready)", value=result.get("full_post", ""), height=260)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Hook**")
        st.info(result.get("hook", ""))
        st.markdown("**Call to action**")
        st.info(result.get("cta", ""))
    with col2:
        st.markdown("**Body**")
        st.info(result.get("body", ""))

    st.markdown("**Hashtags**")
    hashtags = result.get("hashtags", [])
    st.code(" ".join(f"#{tag}" for tag in hashtags))

    st.subheader("Bonus: Visual Suggestions")
    vcol1, vcol2, vcol3 = st.columns(3)
    with vcol1:
        st.markdown("**Image idea**")
        st.write(result.get("image_idea", ""))
    with vcol2:
        st.markdown("**Carousel idea**")
        st.write(result.get("carousel_idea", ""))
    with vcol3:
        st.markdown("**Thumbnail text**")
        st.write(result.get("thumbnail_text", ""))

    if result.get("research_summary"):
        with st.expander("Research used for this post"):
            st.write(result["research_summary"])

    with st.expander("Style reference posts retrieved from ChromaDB"):
        for i, example in enumerate(result.get("style_examples_used", []), start=1):
            st.markdown(f"**Example {i}**")
            st.text(example)


def sidebar() -> None:
    """Render the sidebar: status checks and the knowledge-base rebuild button."""
    st.sidebar.title("Setup Status")

    gemini_ok = bool(config.GEMINI_API_KEY)
    tavily_ok = bool(config.TAVILY_API_KEY)

    st.sidebar.write("Gemini API key:", "PRESENT" if gemini_ok else "missing — add to .env")
    st.sidebar.write("Tavily API key (research mode only):", "PRESENT" if tavily_ok else "missing — add to .env")

    st.sidebar.divider()
    st.sidebar.subheader("Knowledge Base")
    st.sidebar.caption(
        "Builds/rebuilds the ChromaDB style collection from "
        "data/raw_posts.json (or data/sample_posts.json if that's missing)."
    )
    if st.sidebar.button("Rebuild knowledge base"):
        with st.spinner("Embedding posts into ChromaDB..."):
            try:
                ingest.main()
                st.sidebar.success("Knowledge base rebuilt.")
            except Exception as exc:  # noqa: BLE001 - surface any failure to the user
                st.sidebar.error(f"Ingestion failed: {exc}")


def main() -> None:
    """Application entry point."""
    st.title("LinkedIn Content Creation Agent")
    st.caption("Generates posts in a trained writing style using RAG over real reference posts (Gemini + ChromaDB).")

    sidebar()

    tab1, tab2 = st.tabs(["User Input Workflow", "Research & Generate"])

    with tab1:
        st.write("Provide a topic, audience, and goal — the agent retrieves the closest-matching "
                  "style examples and writes a new post around your brief.")
        topic = st.text_input("Topic", placeholder="e.g. AI Agents", key="topic_1")
        audience = st.text_input("Audience", placeholder="e.g. Marketing Agencies", key="audience_1")
        goal = st.text_input("Goal", placeholder="e.g. Lead Generation", key="goal_1")

        if st.button("Generate Post", type="primary", key="gen_1"):
            if not topic:
                st.warning("Please enter a topic.")
            else:
                with st.spinner("Retrieving style examples and generating..."):
                    try:
                        result = gp.generate_post_from_topic(topic, audience or "general audience", goal or "engagement")
                        render_result(result)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Generation failed: {exc}")

    with tab2:
        st.write("Give just a topic — the agent searches the web for current context via Tavily, "
                  "then writes the post using that research plus the trained style.")
        topic2 = st.text_input("Topic to research", placeholder="e.g. AI Agents in 2026", key="topic_2")
        audience2 = st.text_input("Audience", placeholder="e.g. Marketing Agencies", key="audience_2")
        goal2 = st.text_input("Goal", placeholder="e.g. Lead Generation", key="goal_2")

        if st.button("Research & Generate", type="primary", key="gen_2"):
            if not topic2:
                st.warning("Please enter a topic.")
            else:
                with st.spinner("Researching via Tavily, then generating..."):
                    try:
                        result = gp.generate_post_from_research(topic2, audience2 or "general audience", goal2 or "engagement")
                        render_result(result)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Generation failed: {exc}")


if __name__ == "__main__":
    main()
