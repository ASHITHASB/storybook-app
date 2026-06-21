import streamlit as st
import os
import re
import requests
import urllib.parse
from datetime import datetime

from openai import OpenAI
from supabase import create_client, Client

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import inch

# ==============================
# CONFIG
# ==============================

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

supabase: Client = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.set_page_config(page_title="Magical Storybook", page_icon="✨", layout="wide")

st.markdown("""
<style>
.block-container {
    max-width: 860px !important;
    padding-left: 5%;
    padding-right: 5%;
}
.story-card {
    background: linear-gradient(135deg, #fff1ff, #e6f7ff);
    padding: 24px;
    border-radius: 20px;
    margin-bottom: 20px;
    text-align: center;
    font-size: 1.1rem;
    line-height: 1.7;
}
.stButton>button {
    width: 100%;
    border-radius: 25px;
    font-size: 1rem;
    padding: 0.6rem;
}
h1 { text-align: center; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>✨ My Magical Storybook ✨</h1>", unsafe_allow_html=True)

MAX_ATTEMPTS = 3

# ==============================
# SESSION STATE
# ==============================

for key, default in {
    "user_registered": False,
    "story_generated": False,
    "attempt_count": 0,
    "character_memory": None,
    "user_email": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ==============================
# USER STORAGE (Supabase)
# ==============================

def is_existing_user(email: str) -> bool:
    result = supabase.table("users").select("email").eq("email", email).execute()
    return len(result.data) > 0


def save_user(email: str, phone: str):
    supabase.table("users").insert({
        "email": email,
        "phone": phone,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

# ==============================
# SIGNUP
# ==============================

if not st.session_state.user_registered:
    st.markdown("## 🔐 Sign up to get started")

    col1, col2 = st.columns(2)
    with col1:
        email = st.text_input("📧 Email")
    with col2:
        phone = st.text_input("📱 Mobile Number")

    if st.button("Continue →"):
        if not email or not phone:
            st.warning("Please fill in both fields.")
        elif is_existing_user(email):
            st.error("This email has already created a story. Each email gets one storybook during beta.")
        else:
            save_user(email, phone)
            st.session_state.user_registered = True
            st.session_state.user_email = email
            st.success("Welcome! Let's create your story ✨")
            st.rerun()

    st.stop()

# ==============================
# STORY INPUTS
# ==============================

st.markdown("### 👶 Tell us about the child")

col1, col2, col3 = st.columns(3)
with col1:
    name = st.text_input("Child's Name", placeholder="e.g. Layla")
with col2:
    age = st.selectbox("Age", [3, 4, 5, 6, 7, 8])
with col3:
    gender = st.selectbox("Gender", ["Girl", "Boy"])

theme = st.selectbox("Story Theme", [
    "Kindness 💖",
    "Courage 🦁",
    "Friendship 🤝",
    "Confidence 🌟",
])

st.markdown("### ✨ Personalize the story")

col4, col5, col6 = st.columns(3)
with col4:
    family = st.multiselect("Family members", ["Mother", "Father", "Brother", "Sister", "Grandma", "Grandpa"])
with col5:
    animals = st.multiselect("Favourite animals", ["Dog", "Cat", "Bird", "Rabbit", "Horse"])
with col6:
    places = st.multiselect("Favourite places", ["Park", "Beach", "School", "Forest", "Home"])

event = st.text_input("Special event (optional)", placeholder="e.g. first day of school, birthday party")

# ==============================
# CHARACTER MEMORY
# ==============================

def generate_character_memory(name, age, gender):
    prompt = f"""
Describe the appearance of a storybook character in 1 short sentence.

Name: {name}, Age: {age}, Gender: {gender}

Include: face shape, hair colour and style, skin tone, outfit colour.
Keep it under 20 words. No proper nouns. Example:
round face, curly brown hair, warm skin, yellow dress with white collar
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# ==============================
# STORY ENGINE
# ==============================

def generate_story(name, age, gender, theme, family, animals, places, event):
    memory = st.session_state.character_memory

    character_desc = f"{name}, a {age}-year-old {gender.lower()} child. Appearance: {memory}."
    personalization = []
    if family:
        personalization.append(f"Family members who appear: {', '.join(family)}")
    if animals:
        personalization.append(f"Animals in the story: {', '.join(animals)}")
    if places:
        personalization.append(f"Places visited: {', '.join(places)}")
    if event:
        personalization.append(f"The story revolves around: {event}")
    personalization_text = "\n".join(personalization) if personalization else "No extra personalization."

    prompt = f"""
Write a warm, age-appropriate children's storybook with exactly 8 pages.

Main character: {character_desc}

Theme: {theme}

{personalization_text}

Format each page EXACTLY like this (no deviations):

Page 1
Text: [2-3 sentences of story text, simple and engaging for a {age}-year-old]
Scene: [vivid visual description of this page's illustration, 1 sentence, no character names]

Page 2
Text: ...
Scene: ...

...continue through Page 8.

Rules:
- Keep the same character appearance throughout
- Each page text should be simple, warm, and age-appropriate
- Scene descriptions should be visually rich for illustration
- End with a positive, uplifting conclusion
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )
    return response.choices[0].message.content

# ==============================
# PARSE STORY
# ==============================

def parse_story(story_text):
    """Robust regex-based parser for the Page N / Text: / Scene: format."""
    pattern = re.compile(
        r"Page\s+\d+\s*\n+Text:\s*(.*?)\s*\nScene:\s*(.*?)(?=\nPage\s+\d+|\Z)",
        re.DOTALL | re.IGNORECASE
    )
    matches = pattern.findall(story_text)
    pages = []
    for text, scene in matches:
        text = text.strip()
        scene = scene.strip()
        if text and scene and len(scene) >= 15:
            pages.append({"text": text, "scene": scene})
    return pages

# ==============================
# IMAGE ENGINE (Pollinations.ai — free)
# ==============================

def build_image_url(scene, memory, age, gender):
    character = f"{age} year old {gender.lower()} child, {memory}, same face and clothes throughout"
    style = "children's storybook watercolor illustration, soft pastel colours, warm magical lighting, high detail, no text, no watermark"
    full_prompt = f"{character}, {scene}, {style}"
    encoded = urllib.parse.quote(full_prompt)
    # seed based on scene for consistency
    seed = abs(hash(scene)) % 99999
    return f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=576&seed={seed}&nologo=true"


def download_image(url, path):
    """Download image with timeout and size check."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        if len(r.content) < 5000:  # suspiciously small = likely error image
            return False
        with open(path, "wb") as f:
            f.write(r.content)
        return True
    except Exception:
        return False

# ==============================
# PDF
# ==============================

def create_pdf(pages, name, theme):
    file_path = "/tmp/storybook.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A5,
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        name="Title", fontSize=20, alignment=TA_CENTER,
        spaceAfter=6, leading=26, fontName="Helvetica-Bold"
    )
    subtitle_style = ParagraphStyle(
        name="Subtitle", fontSize=12, alignment=TA_CENTER,
        textColor=(0.4, 0.4, 0.4), fontName="Helvetica"
    )
    text_style = ParagraphStyle(
        name="Body", fontSize=13, alignment=TA_CENTER,
        leading=20, spaceAfter=6, fontName="Helvetica"
    )

    elements = []

    # Cover page
    elements.append(Spacer(1, 1.5*inch))
    elements.append(Paragraph(f"{name}'s Magical Story", title_style))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph(theme, subtitle_style))
    elements.append(PageBreak())

    for i, page in enumerate(pages):
        if page.get("image_path") and os.path.exists(page["image_path"]):
            elements.append(Image(page["image_path"], width=4.3*inch, height=3.2*inch))
            elements.append(Spacer(1, 0.15*inch))

        elements.append(Paragraph(page["text"], text_style))
        elements.append(PageBreak())

    doc.build(elements)
    return file_path

# ==============================
# MAIN GENERATE FLOW
# ==============================

if st.session_state.attempt_count >= MAX_ATTEMPTS:
    st.success("🎉 You've used all your story versions! Your final storybook is ready above.")
    st.stop()

generate_disabled = not name or not name.strip()

if st.button("✨ Create My Storybook", disabled=generate_disabled):

    if not name.strip():
        st.warning("Please enter the child's name.")
        st.stop()

    # Generate character memory once (persists across retries)
    if not st.session_state.character_memory:
        with st.spinner("Creating your character..."):
            st.session_state.character_memory = generate_character_memory(name, age, gender)

    st.session_state.attempt_count += 1
    memory = st.session_state.character_memory

    # Generate story
    progress = st.progress(0, text="Writing the story...")
    story_text = generate_story(name, age, gender, theme, family, animals, places, event)
    pages = parse_story(story_text)
    progress.progress(20, text="Story written! Generating illustrations...")

    if not pages:
        st.error("Story generation failed — the format was unexpected. Please try again.")
        st.stop()

    structured_pages = []

    for i, page in enumerate(pages):
        pct = 20 + int((i / len(pages)) * 65)
        progress.progress(pct, text=f"Illustrating page {i+1} of {len(pages)}...")

        img_url = build_image_url(page["scene"], memory, age, gender)
        img_path = f"/tmp/page_{i}.png"

        success = download_image(img_url, img_path)
        page["image_path"] = img_path if success else None
        structured_pages.append(page)

    progress.progress(85, text="Building your PDF...")
    pdf_path = create_pdf(structured_pages, name, theme)
    progress.progress(100, text="Done!")
    progress.empty()

    # Display story
    st.markdown(f"## 📖 {name}'s Story")
    for i, page in enumerate(structured_pages):
        with st.container():
            if page.get("image_path") and os.path.exists(page["image_path"]):
                st.image(page["image_path"], use_container_width=True)
            st.markdown(f'<div class="story-card">{page["text"]}</div>', unsafe_allow_html=True)

    # Download
    st.divider()
    with open(pdf_path, "rb") as f:
        st.download_button(
            "📥 Download Your Storybook (PDF)",
            f,
            file_name=f"{name.strip()}_storybook.pdf",
            mime="application/pdf",
        )

    # Feedback
    st.divider()
    st.markdown("### 💬 How did we do?")
    feedback = st.text_area("Share your thoughts (optional) — your feedback helps us improve!", height=100)
    if st.button("Submit Feedback"):
        if feedback.strip():
            supabase.table("feedback").insert({
                "email": st.session_state.user_email,
                "feedback": feedback.strip(),
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
            st.success("Thank you! Your feedback means a lot 💖")

    st.balloons()
    st.session_state.story_generated = True

# Retry button
if 0 < st.session_state.attempt_count < MAX_ATTEMPTS:
    remaining = MAX_ATTEMPTS - st.session_state.attempt_count
    st.divider()
    st.caption(f"Not happy with this version? You have {remaining} more attempt(s).")
    if st.button("🔁 Try a different version"):
        st.session_state.character_memory = None
        st.rerun()
