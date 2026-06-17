"""
generate_post.py
-----------------
Generate content based on retrieved post either from scraping or research on internet.
"""

import json
import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from tavily import TavilyClient

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Cached at module level so Streamlit doesn't reconnect on every interaction.
_vectorstore: Chroma | None = None
_llm: ChatGoogleGenerativeAI | None = None


def get_vectorstore() -> Chroma:
    """Return a connection to the persisted ChromaDB collection.

    Returns:
        A Chroma vectorstore instance pointed at config.CHROMA_DIR.
    """
    global _vectorstore
    if _vectorstore is None:
        config.require_keys("GEMINI_API_KEY")
        embeddings = GoogleGenerativeAIEmbeddings(
            model=config.GEMINI_EMBEDDING_MODEL,
            google_api_key=config.GEMINI_API_KEY,
        )
        _vectorstore = Chroma(
            collection_name=config.CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=config.CHROMA_DIR,
        )
    return _vectorstore


def get_llm() -> ChatGoogleGenerativeAI:
    """Return a (lazily-initialized) Gemini chat model client.

    Returns:
        A ChatGoogleGenerativeAI instance configured with a moderate
        temperature — creative enough for engaging hooks, controlled
        enough to stay on-brief.
    """
    global _llm
    if _llm is None:
        config.require_keys("GEMINI_API_KEY")
        _llm = ChatGoogleGenerativeAI(
            model=config.GEMINI_CHAT_MODEL,
            google_api_key=config.GEMINI_API_KEY,
            temperature=0.7,
        )
    return _llm


def retrieve_style_examples(query: str, k: int = config.DEFAULT_RETRIEVAL_K) -> list[str]:
    """Fetch the k most stylistically/topically relevant past posts for a query.

    Args:
        query: The new topic/idea to match against the style corpus.
        k: Number of example posts to retrieve.

    Returns:
        A list of raw post text strings, most relevant first.
    """
    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search(query, k=k)
    return [doc.page_content for doc in results]


def research_topic(topic: str, max_results: int = 5) -> str:
    """Use Tavily to gather a short, current-events summary of a topic.

    Args:
        topic: The subject to research, e.g. "AI agents in marketing".
        max_results: How many search results Tavily should return.

    Returns:
        A newline-joined string of result snippets, ready to drop into a
        generation prompt. Returns an empty string if Tavily finds nothing.
    """
    config.require_keys("TAVILY_API_KEY")
    client = TavilyClient(api_key=config.TAVILY_API_KEY)

    response = client.search(query=topic, max_results=max_results, search_depth="basic")
    snippets = [r.get("content", "").strip() for r in response.get("results", []) if r.get("content")]

    if not snippets:
        logger.warning("Tavily returned no usable results for topic: %s", topic)
        return ""

    return "\n\n".join(f"- {s}" for s in snippets)


def _build_prompt(topic: str, audience: str, goal: str, style_examples: list[str], research: str = "") -> str:
    """Construct the full generation prompt sent to Gemini.

    Centralizing prompt construction here (rather than inlining it in every
    generation function) keeps the instructions consistent across the
    User Input and Auto-Research workflows.

    Args:
        topic: The post's subject.
        audience: Who the post should speak to.
        goal: The business objective (e.g. "lead generation").
        style_examples: Real reference posts retrieved from ChromaDB.
        research: Optional fresh research context (Auto-Research mode only).

    Returns:
        A single prompt string instructing Gemini to return strict JSON.
    """
    examples_block = "\n\n---\n\n".join(style_examples) if style_examples else "(no examples retrieved)"
    research_block = f"\nRECENT RESEARCH ON THIS TOPIC:\n{research}\n" if research else ""

    return f"""You are ghostwriting a LinkedIn post. Study the WRITING STYLE of the
reference posts below very closely — sentence length, line-break rhythm,
hook pattern, use of personal anecdotes, and how each post ends.

REFERENCE POSTS (style to imitate, NOT content to reuse):
{examples_block}
{research_block}
NEW POST BRIEF:
- Topic: {topic}
- Target audience: {audience}
- Goal: {goal}

Write a brand-new LinkedIn post on this topic that reads as if the SAME
author wrote it — same voice, same structural habits, same energy — but
with entirely original content relevant to the new topic and audience.

Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:
{{
  "hook": "the first 1-2 lines designed to stop the scroll",
  "body": "the main content of the post, with \\n for line breaks",
  "cta": "a single closing call-to-action or question",
  "full_post": "hook + body + cta combined exactly as it should be posted",
  "hashtags": ["10", "relevant", "hashtags", "without", "the", "#", "symbol"],
  "image_idea": "a concrete suggested image or graphic concept for this post",
  "carousel_idea": "a short outline for a 4-6 slide carousel version of this post",
  "thumbnail_text": "punchy 3-7 word text overlay for slide 1 / the thumbnail"
}}"""


def _call_llm_for_json(prompt: str) -> dict[str, Any]:
    """Send a prompt to Gemini and parse the response as JSON.

    Args:
        prompt: The full prompt string (must instruct the model to return JSON).

    Returns:
        Parsed JSON as a dict.

    Raises:
        ValueError: If the model's response cannot be parsed as JSON.
    """
    llm = get_llm()
    response = llm.invoke(prompt)
    raw_text = response.content.strip()

    # Defensive cleanup in case the model wraps the JSON in markdown fences
    # despite instructions not to.
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse model output as JSON: %s", raw_text[:500])
        raise ValueError(
            "Gemini did not return valid JSON. Try regenerating, or lower "
            "the temperature in get_llm() for more predictable formatting."
        ) from exc


def generate_post_from_topic(topic: str, audience: str, goal: str) -> dict[str, Any]:
    """Part 2 — User Input Workflow: generate a post from a user-supplied topic.

    Args:
        topic: The post's subject, as typed by the user.
        audience: The intended reader, e.g. "Marketing Agencies".
        goal: The business objective, e.g. "Lead Generation".

    Returns:
        Dict with keys: hook, body, cta, full_post, hashtags, image_idea,
        carousel_idea, thumbnail_text, style_examples_used.
    """
    examples = retrieve_style_examples(query=topic, k=config.DEFAULT_RETRIEVAL_K)
    prompt = _build_prompt(topic, audience, goal, examples)
    result = _call_llm_for_json(prompt)
    result["style_examples_used"] = examples
    return result


def generate_post_from_research(topic: str, audience: str, goal: str) -> dict[str, Any]:
    """Part 3 — Auto-Research Workflow: research a topic, then generate.

    Args:
        topic: The seed topic to research and write about.
        audience: The intended reader.
        goal: The business objective.

    Returns:
        Same shape as generate_post_from_topic(), plus a "research_summary" key.
    """
    research = research_topic(topic)
    examples = retrieve_style_examples(query=topic, k=config.DEFAULT_RETRIEVAL_K)
    prompt = _build_prompt(topic, audience, goal, examples, research=research)
    result = _call_llm_for_json(prompt)
    result["style_examples_used"] = examples
    result["research_summary"] = research
    return result
