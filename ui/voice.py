import os
import io
import streamlit as st
from openai import OpenAI


def render_voice_input() -> str | None:
    """
    Renders a mic button using Streamlit's built-in audio_input widget.
    Returns Whisper-transcribed text, or None if no audio was recorded.
    """
    st.markdown("**🎙 Voice Input**")

    audio = st.audio_input("Record your request", key="voice_recorder")

    if audio is None:
        return None

    # Deduplicate — only transcribe when a new recording comes in
    audio_bytes = audio.read()
    if not audio_bytes:
        return None

    import hashlib
    audio_hash = hashlib.md5(audio_bytes).hexdigest()
    if st.session_state.get("_last_audio_hash") == audio_hash:
        return None
    st.session_state["_last_audio_hash"] = audio_hash

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    buf = io.BytesIO(audio_bytes)
    buf.name = "audio.wav"

    with st.spinner("Transcribing..."):
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
        )

    text = transcript.text.strip()
    if text:
        st.success(f'Heard: "{text}"')
    return text or None
