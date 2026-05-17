import streamlit as st
from dotenv import load_dotenv
from agent import TravelAgent, build_itinerary, markdown_to_pdf
from ui.components import render_tool_results_in_chat
from ui.voice import render_voice_input

load_dotenv()

st.set_page_config(
    layout="wide",
    page_title="AI Travel Planner",
    page_icon="✈️",
)

st.markdown("""
<style>
/* ── Mobile responsiveness ── */
@media (max-width: 768px) {
    /* Stack columns vertically on mobile */
    [data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }
    /* Full-width containers */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }
    /* Larger tap targets for buttons */
    .stButton > button {
        width: 100% !important;
        padding: 0.6rem 1rem !important;
        font-size: 1rem !important;
    }
    .stDownloadButton > button {
        width: 100% !important;
    }
    /* Readable font sizes */
    .stMarkdown p, .stMarkdown li {
        font-size: 0.95rem !important;
    }
    /* Chat input full width */
    [data-testid="stChatInput"] {
        font-size: 1rem !important;
    }
    /* Metric cards smaller */
    [data-testid="metric-container"] {
        padding: 0.4rem !important;
    }
    /* Hide wide layout padding on mobile */
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
}

/* ── General polish ── */
[data-testid="stChatMessage"] {
    border-radius: 12px;
    padding: 0.5rem;
}
.stButton > button {
    border-radius: 8px;
}
[data-testid="stMetric"] {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []          # OpenAI-format history
if "display_items" not in st.session_state:
    st.session_state.display_items = []    # Rich render history
if "itinerary_md" not in st.session_state:
    st.session_state.itinerary_md = None
if "itinerary_pdf" not in st.session_state:
    st.session_state.itinerary_pdf = None
if "agent_running" not in st.session_state:
    st.session_state.agent_running = False

agent = TravelAgent()

# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.title("✈ AI Travel Planner")
    st.caption("Powered by GPT-4o")
    st.divider()

    voice_text = render_voice_input()

    st.divider()

    has_history = len(st.session_state.messages) > 0

    if st.button("📋 Build Full Itinerary", type="primary", disabled=not has_history):
        with st.spinner("Building your itinerary..."):
            md = build_itinerary(st.session_state.messages)
            st.session_state.itinerary_md = md
            st.session_state.itinerary_pdf = markdown_to_pdf(md)
        st.success("Itinerary ready!")

    if st.session_state.itinerary_pdf:
        st.download_button(
            label="⬇ Download Itinerary (PDF)",
            data=st.session_state.itinerary_pdf,
            file_name="travel_itinerary.pdf",
            mime="application/pdf",
        )

    st.divider()

    if st.button("🗑 New Trip", type="secondary", disabled=not has_history):
        st.session_state.messages = []
        st.session_state.display_items = []
        st.session_state.itinerary_md = None
        st.session_state.itinerary_pdf = None
        st.session_state.pop("_last_audio_hash", None)
        st.rerun()

    st.divider()
    st.markdown(
        "**Tools available:**\n"
        "- ✈ Flights\n"
        "- 🏨 Hotels\n"
        "- 🍽 Restaurants\n"
        "- 🗺 Attractions & things to do\n"
        "- 🌤 Weather & packing\n"
        "- 📍 Distances\n"
        "- 🚇 Local transport\n"
        "- 🚗 Intercity travel (drive/bus/train)"
    )

# ── Main Chat Area ─────────────────────────────────────────────
st.title("Plan Your Trip")

if not st.session_state.display_items:
    st.markdown(
        "> 👋 Try: *\"Plan me a 5-day trip to Tokyo from NYC in July, budget $3000\"*"
    )

# Replay history from display_items
for item in st.session_state.display_items:
    if item["type"] == "user":
        with st.chat_message("user"):
            st.markdown(item["content"])
    elif item["type"] == "assistant":
        with st.chat_message("assistant"):
            if item.get("content"):
                st.markdown(item["content"])
            for tool_name, result in item.get("tool_results", {}).items():
                render_tool_results_in_chat(tool_name, result)

# ── Handle Input ───────────────────────────────────────────────
text_input = st.chat_input("Ask me to plan your trip...")
user_input = (voice_text or text_input or "").strip()

if user_input and not st.session_state.agent_running:
    st.session_state.agent_running = True

    # Show user bubble immediately
    with st.chat_message("user"):
        st.markdown(user_input)

    # Append to OpenAI history
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Containers for live streaming
    with st.chat_message("assistant"):
        text_placeholder = st.empty()
        tool_status_widgets: dict[str, st.delta_generator.DeltaGenerator] = {}
        pending_results: dict[str, dict] = {}

        accumulated_text = ""

        def on_text_chunk(chunk: str):
            global accumulated_text
            accumulated_text += chunk
            text_placeholder.markdown(accumulated_text + "▌")

        def on_tool_call(tool_name: str, args: dict):
            label_map = {
                "search_flights": "✈ Searching flights...",
                "search_hotels": "🏨 Searching hotels...",
                "search_restaurants": "🍽 Searching restaurants...",
                "get_weather": "🌤 Getting weather...",
                "get_distance": "📍 Calculating distance...",
                "get_local_transport": "🚇 Finding local transport...",
                "search_intercity_travel": "🚗 Finding intercity travel options...",
                "search_attractions": "🗺 Finding attractions...",
            }
            label = label_map.get(tool_name, f"⚙ Running {tool_name}...")
            tool_status_widgets[tool_name] = st.status(label, expanded=False)

        def on_tool_result(tool_name: str, result: dict):
            pending_results[tool_name] = result
            widget = tool_status_widgets.get(tool_name)
            if widget:
                done_map = {
                    "search_flights": "✈ Flights found",
                    "search_hotels": "🏨 Hotels found",
                    "search_restaurants": "🍽 Restaurants found",
                    "get_weather": "🌤 Weather loaded",
                    "get_distance": "📍 Distance calculated",
                    "get_local_transport": "🚇 Transport options ready",
                    "search_intercity_travel": "🚗 Travel options ready",
                    "search_attractions": "🗺 Attractions found",
                }
                widget.update(label=done_map.get(tool_name, f"✓ {tool_name}"), state="complete")

        # Run agent loop
        updated_messages = agent.run(
            st.session_state.messages,
            on_text_chunk=on_text_chunk,
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
        )

        # Finalise streaming text
        if accumulated_text:
            text_placeholder.markdown(accumulated_text)

        # Render rich cards below the text
        for tool_name, result in pending_results.items():
            render_tool_results_in_chat(tool_name, result)

    # Persist updated history (agent loop returns full history excluding system)
    st.session_state.messages = updated_messages

    # Find the last assistant message text for display_items
    last_assistant_text = ""
    for msg in reversed(updated_messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            last_assistant_text = msg["content"]
            break

    st.session_state.display_items.append({"type": "user", "content": user_input})
    st.session_state.display_items.append({
        "type": "assistant",
        "content": last_assistant_text,
        "tool_results": dict(pending_results),
    })

    st.session_state.agent_running = False
    st.rerun()
