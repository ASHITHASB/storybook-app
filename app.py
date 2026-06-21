import streamlit as st
import os
import re
import time
import requests
import urllib.parse
from datetime import datetime

from openai import OpenAI
from supabase import create_client, Client

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ==============================
# CONFIG
# ==============================

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

supabase: Client = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

HF_TOKEN = st.secrets.get("HF_TOKEN", "")
HF_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1"

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
    font-size: 1.15rem;
    line-height: 1.8;
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
# LANGUAGE CONFIG
# ==============================

LANGUAGES = {
    "English": {
        "prompt_lang": "English",
        "font_name": "Helvetica",
        "font_path": None,
    },
    "Hindi (हिंदी)": {
        "prompt_lang": "Hindi",
        "font_name": "NotoDevanagari",
        "font_path": "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    },
    "Tamil (தமிழ்)": {
        "prompt_lang": "Tamil",
        "font_name": "NotoTamil",
        "font_path": "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
    },
    "Malayalam (മലയാളം)": {
        "prompt_lang": "Malayalam",
        "font_name": "NotoMalayalam",
        "font_path": "/usr/share/fonts/truetype/noto/NotoSansMalayalam-Regular.ttf",
    },
}

@st.cache_resource
def register_fonts():
    """Register Noto fonts once at startup, including family mapping."""
    registered = {}
    for lang, cfg in LANGUAGES.items():
        path = cfg["font_path"]
        name = cfg["font_name"]
        if path and os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                # Must register family so ReportLab can resolve bold/italic lookups
                registerFontFamily(name, normal=name, bold=name, italic=name, boldItalic=name)
                registered[lang] = name
            except Exception:
                registered[lang] = "Helvetica"
        else:
            # Font file not found — fall back to Helvetica (PDF won't render script correctly
            # but won't crash; web display is still fine)
            registered[lang] = "Helvetica"
    return registered

font_registry = register_fonts()

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

# Comma-separated tester emails that bypass the one-story limit
TESTER_EMAILS = {
    e.strip().lower()
    for e in st.secrets.get("TESTER_EMAILS", "").split(",")
    if e.strip()
}


def is_tester(email: str) -> bool:
    return email.strip().lower() in TESTER_EMAILS


def is_existing_user(email: str) -> bool:
    result = supabase.table("users").select("email").eq("email", email).execute()
    return len(result.data) > 0


def save_user(email: str, phone: str):
    # Testers bypass DB entirely — no insert needed
    if is_tester(email):
        return
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
        elif not is_tester(email) and is_existing_user(email):
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

col1, col2, col3, col4 = st.columns(4)
with col1:
    name = st.text_input("Child's Name", placeholder="e.g. Layla")
with col2:
    age = st.selectbox("Age", [3, 4, 5, 6, 7, 8])
with col3:
    gender = st.selectbox("Gender", ["Girl", "Boy"])
with col4:
    language = st.selectbox("Story Language", list(LANGUAGES.keys()))

theme = st.selectbox("Story Theme", [
    "Kindness 💖",
    "Courage 🦁",
    "Friendship 🤝",
    "Confidence 🌟",
])

st.markdown("### ✨ Personalize the story")

col5, col6, col7 = st.columns(3)
with col5:
    family = st.multiselect("Family members", ["Mother", "Father", "Brother", "Sister", "Grandma", "Grandpa"])
with col6:
    animals = st.multiselect("Favourite animals", ["Dog", "Cat", "Bird", "Rabbit", "Horse"])
with col7:
    places = st.multiselect("Favourite places", ["Park", "Beach", "School", "Forest", "Home"])

event = st.text_input("Special event (optional)", placeholder="e.g. first day of school, birthday party")

# ==============================
# CHARACTER MEMORY
# ==============================

def generate_character_memory(name, age, gender):
    prompt = f"""Describe a storybook character's appearance in one short sentence (under 20 words).
Name: {name}, Age: {age}, Gender: {gender}
Include: face shape, hair, skin tone, outfit colour. No proper nouns.
Example: round face, curly brown hair, warm skin, yellow dress with white collar"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# ==============================
# STORY ENGINE
# ==============================

def generate_story(name, age, gender, theme, family, animals, places, event, language):
    memory = st.session_state.character_memory
    lang_cfg = LANGUAGES[language]
    prompt_lang = lang_cfg["prompt_lang"]

    character_desc = f"{name}, a {age}-year-old {gender.lower()} child. Appearance: {memory}."
    personalization = []
    if family:
        personalization.append(f"Family members who appear: {', '.join(family)}")
    if animals:
        personalization.append(f"Animals in the story: {', '.join(animals)}")
    if places:
        personalization.append(f"Places visited: {', '.join(places)}")
    if event:
        personalization.append(f"Story revolves around: {event}")
    personalization_text = "\n".join(personalization) if personalization else ""

    prompt = f"""Write a warm children's storybook in {prompt_lang}. Output exactly 8 pages using this format with no extra text, no bold, no markdown:

Page 1
Text: [2-3 simple sentences for a {age}-year-old, written in {prompt_lang}]
Scene: [one sentence visual description of the illustration, written in English]

Page 2
Text: ...
Scene: ...

(repeat through Page 8)

Character: {character_desc}
Theme: {theme}
{personalization_text}

Important rules:
- Text sections must be in {prompt_lang}
- Scene sections must always be in English (used for image generation)
- Use plain text only — no asterisks, no bold, no markdown
- Every page must have both Text: and Scene: on their own lines
- End with a positive, uplifting conclusion"""

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
    # Strip markdown bold/italic
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', story_text)

    strategies = [
        re.compile(
            r'Page\s*\d+[:\.]?\s*\n+\s*Text:\s*(.*?)\s*\n+\s*Scene:\s*(.*?)(?=\n+\s*Page\s*\d+|\Z)',
            re.DOTALL | re.IGNORECASE
        ),
        re.compile(
            r'Text:\s*(.*?)\s*\nScene:\s*(.*?)(?=\nText:|\Z)',
            re.DOTALL | re.IGNORECASE
        ),
        re.compile(
            r'Page\s*\d+[:\.]?\s+(.*?)\s*\nScene:\s*(.*?)(?=\nPage\s*\d+|\Z)',
            re.DOTALL | re.IGNORECASE
        ),
    ]

    for pattern in strategies:
        matches = pattern.findall(text)
        pages = []
        for text_content, scene in matches:
            text_content = text_content.strip()
            scene = scene.strip()
            if text_content and scene and len(scene) >= 10:
                pages.append({"text": text_content, "scene": scene})
        if len(pages) >= 3:
            return pages

    return []

# ==============================
# IMAGE ENGINE
# ==============================

def build_image_prompt(scene, memory, age, gender):
    character = f"{age} year old {gender.lower()} child, {memory}, same face and clothes throughout"
    style = "children's storybook watercolor illustration, soft pastel colours, warm magical lighting, high detail, no text, no watermark"
    return f"{character}, {scene}, {style}"


def generate_image_hf(prompt):
    """Hugging Face Inference API — free tier, retries on model cold-start."""
    if not HF_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    for attempt in range(3):
        try:
            r = requests.post(
                HF_API_URL,
                headers=headers,
                json={"inputs": prompt, "parameters": {"width": 768, "height": 512}},
                timeout=90,
            )
            if r.status_code == 200 and len(r.content) > 5000:
                return r.content
            elif r.status_code == 503:
                # Model is loading — wait and retry
                wait = 20 * (attempt + 1)
                time.sleep(wait)
                continue
        except Exception:
            continue
    return None


def generate_image_pollinations(scene, memory, age, gender):
    """Fallback: Pollinations.ai (no token needed)."""
    prompt = build_image_prompt(scene, memory, age, gender)
    encoded = urllib.parse.quote(prompt)
    seed = abs(hash(scene)) % 99999
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=512&seed={seed}&nologo=true"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and len(r.content) > 5000:
            return r.content
    except Exception:
        pass
    return None


def get_image(scene, memory, age, gender):
    """Try HF first, fall back to Pollinations."""
    prompt = build_image_prompt(scene, memory, age, gender)
    img_bytes = generate_image_hf(prompt)
    if not img_bytes:
        img_bytes = generate_image_pollinations(scene, memory, age, gender)
    return img_bytes

# ==============================
# PDF
# ==============================

def create_pdf(pages, name, theme, language):
    file_path = "/tmp/storybook.pdf"
    doc = SimpleDocTemplate(
        file_path, pagesize=A5,
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.5*inch, bottomMargin=0.5*inch
    )

    lang_cfg = LANGUAGES[language]
    font_name = font_registry.get(language, "Helvetica")

    title_style = ParagraphStyle(
        name="Title", fontName=font_name, fontSize=20,
        alignment=TA_CENTER, spaceAfter=6, leading=28
    )
    subtitle_style = ParagraphStyle(
        name="Subtitle", fontName=font_name, fontSize=12,
        alignment=TA_CENTER, textColor=(0.4, 0.4, 0.4)
    )
    text_style = ParagraphStyle(
        name="Body", fontName=font_name, fontSize=13,
        alignment=TA_CENTER, leading=22, spaceAfter=6
    )

    elements = []

    # Cover
    elements.append(Spacer(1, 1.5*inch))
    elements.append(Paragraph(f"{name}'s Magical Story", title_style))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph(theme, subtitle_style))
    elements.append(PageBreak())

    for page in pages:
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

if st.button("✨ Create My Storybook", disabled=not name.strip()):

    if not name.strip():
        st.warning("Please enter the child's name.")
        st.stop()

    if not st.session_state.character_memory:
        with st.spinner("Creating your character..."):
            st.session_state.character_memory = generate_character_memory(name, age, gender)

    st.session_state.attempt_count += 1
    memory = st.session_state.character_memory

    progress = st.progress(0, text="Writing the story...")
    story_text = generate_story(name, age, gender, theme, family, animals, places, event, language)
    pages = parse_story(story_text)
    progress.progress(20, text="Story written! Generating illustrations...")

    if not pages:
        st.error("Story generation failed — the format was unexpected. Please try again.")
        st.stop()

    structured_pages = []

    source_label = "Hugging Face" if HF_TOKEN else "Pollinations"
    for i, page in enumerate(pages):
        pct = 20 + int((i / len(pages)) * 65)
        progress.progress(pct, text=f"Illustrating page {i+1} of {len(pages)} via {source_label}...")

        img_bytes = get_image(page["scene"], memory, age, gender)
        img_path = f"/tmp/page_{i}.png"
        if img_bytes:
            with open(img_path, "wb") as f:
                f.write(img_bytes)
            page["image_path"] = img_path
        else:
            page["image_path"] = None
        structured_pages.append(page)

    progress.progress(85, text="Building your PDF...")
    pdf_path = create_pdf(structured_pages, name, theme, language)
    progress.progress(100, text="Done!")
    progress.empty()

    # Display
    st.markdown(f"## 📖 {name}'s Story")
    for page in structured_pages:
        with st.container():
            if page.get("image_path") and os.path.exists(page["image_path"]):
                st.image(page["image_path"], use_container_width=True)
            st.markdown(f'<div class="story-card">{page["text"]}</div>', unsafe_allow_html=True)

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
    feedback = st.text_area("Share your thoughts (optional)", height=100)
    if st.button("Submit Feedback"):
        if feedback.strip():
            supabase.table("feedback").insert({
                "email": st.session_state.user_email,
                "feedback": feedback.strip(),
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
            st.success("Thank you! Your feedback means a lot 💖")

    st.balloons()

# Retry
if 0 < st.session_state.attempt_count < MAX_ATTEMPTS:
    remaining = MAX_ATTEMPTS - st.session_state.attempt_count
    st.divider()
    st.caption(f"Not happy with this version? You have {remaining} more attempt(s).")
    if st.button("🔁 Try a different version"):
        st.session_state.character_memory = None
        st.rerun()
