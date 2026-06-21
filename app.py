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
HF_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"

st.set_page_config(page_title="My Magical Storybook", page_icon="📖", layout="wide")

# ==============================
# STORYBOOK ILLUSTRATED STYLE
# ==============================

st.html("""
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
[data-testid="stAppViewContainer"] { background-color: #faf6ef; }
[data-testid="stHeader"] { background-color: #faf6ef; }
.block-container { max-width: 820px !important; padding: 2rem 3rem; }
h1 { font-family: 'Playfair Display', Georgia, serif !important; font-size: 2.6rem !important; color: #5c3317 !important; text-align: center; letter-spacing: 1px; margin-bottom: 0.2rem !important; }
h2, h3 { font-family: 'Playfair Display', Georgia, serif !important; color: #5c3317 !important; }
.ornament { text-align: center; color: #c9a96e; font-size: 1.4rem; margin: 0.5rem 0 1.2rem 0; letter-spacing: 8px; }
.story-card { background: #fdf8f0; border: 1px solid #d4b896; border-radius: 6px; padding: 28px 36px; margin-bottom: 28px; font-family: 'Crimson Text', Georgia, serif; font-size: 1.25rem; line-height: 2; text-align: center; color: #3d2b1f; box-shadow: 0 2px 12px rgba(139,90,43,0.08); }
.stButton>button { width: 100%; border-radius: 30px; font-family: 'Playfair Display', Georgia, serif; font-size: 1.05rem; padding: 0.65rem 1.5rem; background: linear-gradient(135deg, #8b5e3c, #c9883f); color: white !important; border: none; letter-spacing: 0.5px; box-shadow: 0 2px 8px rgba(139,90,43,0.3); }
.stButton>button:hover { background: linear-gradient(135deg, #7a5234, #b87a38); }
[data-testid="stDownloadButton"] button { background: linear-gradient(135deg, #3d6b4f, #5a9e72) !important; }
img { border-radius: 8px; }
</style>
""")

st.markdown("<h1>📖 My Magical Storybook</h1>", unsafe_allow_html=True)
st.markdown('<div class="ornament">✦ ❧ ✦</div>', unsafe_allow_html=True)

MAX_ATTEMPTS = 3

# ==============================
# LANGUAGE CONFIG
# ==============================

LANGUAGES = {
    "English": {"prompt_lang": "English", "font_name": "Helvetica", "font_path": None},
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
    registered = {}
    for lang, cfg in LANGUAGES.items():
        path, name = cfg["font_path"], cfg["font_name"]
        if path and os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                registerFontFamily(name, normal=name, bold=name, italic=name, boldItalic=name)
                registered[lang] = name
            except Exception:
                registered[lang] = "Helvetica"
        else:
            registered[lang] = "Helvetica"
    return registered

font_registry = register_fonts()

# ==============================
# SESSION STATE
# ==============================

for key, default in {
    "user_registered": False,
    "attempt_count": 0,
    "character_memory": None,
    "user_email": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ==============================
# USER STORAGE
# ==============================

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
    st.markdown("### 🔐 Sign up to begin")

    col1, col2 = st.columns(2)
    with col1:
        email = st.text_input("Email address")
    with col2:
        phone = st.text_input("Mobile number")

    if st.button("Continue →"):
        if not email or not phone:
            st.warning("Please fill in both fields.")
        elif not is_tester(email) and is_existing_user(email):
            st.error("This email has already created a story. Each email gets one storybook during beta.")
        else:
            save_user(email, phone)
            st.session_state.user_registered = True
            st.session_state.user_email = email
            st.rerun()

    st.stop()

# ==============================
# STORY INPUTS
# ==============================

st.markdown("### About the child")

col1, col2, col3, col4 = st.columns(4)
with col1:
    name = st.text_input("Child's name", placeholder="e.g. Layla")
with col2:
    age = st.selectbox("Age", [3, 4, 5, 6, 7, 8])
with col3:
    gender = st.selectbox("Gender", ["Girl", "Boy"])
with col4:
    language = st.selectbox("Language", list(LANGUAGES.keys()))

theme = st.selectbox("Story theme", [
    "Kindness 💖",
    "Courage 🦁",
    "Friendship 🤝",
    "Confidence 🌟",
    "Curiosity 🔍",
    "Honesty 🌿",
])

st.markdown("### Personalise the story")

col5, col6, col7 = st.columns(3)
with col5:
    family = st.multiselect("Family members", ["Mother", "Father", "Brother", "Sister", "Grandma", "Grandpa"])
with col6:
    animals = st.multiselect("Favourite animals", ["Dog", "Cat", "Bird", "Rabbit", "Horse", "Elephant"])
with col7:
    places = st.multiselect("Favourite places", ["Park", "Beach", "School", "Forest", "Home", "Library"])

event = st.text_input("Special event (optional)", placeholder="e.g. first day of school, birthday party")

# Advanced options
with st.expander("✦ Advanced customisation (optional)"):
    col8, col9 = st.columns(2)
    with col8:
        interests = st.text_input("Child's interests / hobbies", placeholder="e.g. painting, football, dancing")
        fav_colour = st.text_input("Favourite colour", placeholder="e.g. purple, sunshine yellow")
    with col9:
        best_friend = st.text_input("Best friend's name", placeholder="e.g. Mia, Arjun")
        moral = st.text_input("Specific lesson or moral", placeholder="e.g. it's okay to ask for help")

# ==============================
# CHARACTER MEMORY
# ==============================

def generate_character_memory(name, age, gender, fav_colour):
    colour_hint = f"Their favourite colour is {fav_colour}, reflected in their outfit." if fav_colour else ""
    prompt = f"""Describe a children's storybook character's appearance in one vivid sentence (under 25 words).
Name: {name}, Age: {age}, Gender: {gender}. {colour_hint}
Include: hair style and colour, skin tone, outfit with specific colour. No proper nouns. Be warm and specific.
Example: long wavy black hair, golden-brown skin, bright purple dress with white stars and little red boots"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# ==============================
# STORY ENGINE
# ==============================

def generate_story(name, age, gender, theme, family, animals, places, event,
                   language, interests, fav_colour, best_friend, moral):

    memory = st.session_state.character_memory
    prompt_lang = LANGUAGES[language]["prompt_lang"]

    # Build rich personalization block
    details = []
    if family:
        details.append(f"Family members who appear: {', '.join(family)}")
    if animals:
        details.append(f"Animals featured: {', '.join(animals)}")
    if places:
        details.append(f"Places visited: {', '.join(places)}")
    if event:
        details.append(f"Central event: {event}")
    if interests:
        details.append(f"Child's passions and hobbies: {interests}")
    if best_friend:
        details.append(f"Best friend who appears: {best_friend}")
    if fav_colour:
        details.append(f"Favourite colour (woven into scenes): {fav_colour}")
    if moral:
        details.append(f"Specific lesson the story teaches: {moral}")

    personalization = "\n".join(f"- {d}" for d in details) if details else "- Keep it warm and universal"

    prompt = f"""You are an award-winning children's picture book author writing in {prompt_lang}.

Write a beautifully crafted, emotionally resonant storybook with exactly 8 pages. Each page should feel like a moment from a treasured illustrated book — vivid, lyrical, and perfectly pitched for a {age}-year-old.

Main character: {name}, a {age}-year-old {gender.lower()}. Appearance: {memory}.

Theme: {theme}

Story details:
{personalization}

Output each page in EXACTLY this format (plain text only — no bold, no asterisks, no markdown):

Page 1
Text: [2–3 warm, simple sentences in {prompt_lang}. Rich in imagery. Age-appropriate for {age}.]
Scene: [One sentence describing this page's illustration in English. Be specific: setting, mood, colours, what character is doing. This is used for image generation.]

Page 2
Text: ...
Scene: ...

(continue through Page 8)

Rules:
- Text must be in {prompt_lang}
- Scene must always be in English
- Build emotional arc: wonder → challenge → growth → joyful resolution
- Use sensory language and gentle humour
- The ending should leave the child feeling warm, capable, and loved
- Plain text only. No markdown formatting whatsoever."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
    )
    return response.choices[0].message.content

# ==============================
# PARSE STORY
# ==============================

def parse_story(story_text):
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
    ]
    for pattern in strategies:
        matches = pattern.findall(text)
        pages = [
            {"text": t.strip(), "scene": s.strip()}
            for t, s in matches
            if t.strip() and s.strip() and len(s.strip()) >= 10
        ]
        if len(pages) >= 3:
            return pages
    return []

# ==============================
# IMAGE ENGINE
# ==============================

def build_image_prompt(scene, memory, age, gender, fav_colour):
    colour_note = f"wearing {fav_colour} coloured clothes," if fav_colour else ""
    character = f"a {age} year old {gender.lower()} child, {memory}, {colour_note} same consistent appearance"
    style = (
        "children's picture book illustration, detailed watercolor and ink, "
        "warm golden lighting, rich background detail, storybook art, "
        "reminiscent of classic illustrated children's books, "
        "soft pastel palette, expressive and charming"
    )
    negative = "photorealistic, 3D render, CGI, dark, scary, text, watermark, blurry, ugly, deformed"
    return f"{character}, {scene}, {style}", negative


def generate_image_hf(prompt, negative):
    if not HF_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "negative_prompt": negative,
            "width": 768,
            "height": 512,
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
        },
    }
    for attempt in range(3):
        try:
            r = requests.post(HF_API_URL, headers=headers, json=payload, timeout=120)
            if r.status_code == 200 and len(r.content) > 5000:
                return r.content
            elif r.status_code == 503:
                time.sleep(20 * (attempt + 1))
        except Exception:
            continue
    return None


def generate_image_pollinations(scene, memory, age, gender, fav_colour):
    prompt, _ = build_image_prompt(scene, memory, age, gender, fav_colour)
    encoded = urllib.parse.quote(prompt)
    seed = abs(hash(scene)) % 99999
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=512&seed={seed}&nologo=true"
    try:
        r = requests.get(url, timeout=35)
        if r.status_code == 200 and len(r.content) > 5000:
            return r.content
    except Exception:
        pass
    return None


def get_image(scene, memory, age, gender, fav_colour):
    prompt, negative = build_image_prompt(scene, memory, age, gender, fav_colour)
    img = generate_image_hf(prompt, negative)
    if not img:
        img = generate_image_pollinations(scene, memory, age, gender, fav_colour)
    return img

# ==============================
# PDF
# ==============================

def create_pdf(pages, name, theme, language):
    file_path = "/tmp/storybook.pdf"
    doc = SimpleDocTemplate(
        file_path, pagesize=A5,
        leftMargin=0.55*inch, rightMargin=0.55*inch,
        topMargin=0.55*inch, bottomMargin=0.55*inch
    )
    font_name = font_registry.get(language, "Helvetica")

    title_style = ParagraphStyle(
        "Title", fontName=font_name, fontSize=22,
        alignment=TA_CENTER, spaceAfter=8, leading=30,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", fontName=font_name, fontSize=12,
        alignment=TA_CENTER, textColor=(0.55, 0.35, 0.15), leading=18,
    )
    body_style = ParagraphStyle(
        "Body", fontName=font_name, fontSize=13,
        alignment=TA_CENTER, leading=22, spaceAfter=6,
    )

    elements = [
        Spacer(1, 1.4*inch),
        Paragraph(f"{name}'s Magical Story", title_style),
        Spacer(1, 0.2*inch),
        Paragraph(theme, subtitle_style),
        PageBreak(),
    ]

    for page in pages:
        if page.get("image_path") and os.path.exists(page["image_path"]):
            elements.append(Image(page["image_path"], width=4.3*inch, height=3.2*inch))
            elements.append(Spacer(1, 0.15*inch))
        elements.append(Paragraph(page["text"], body_style))
        elements.append(PageBreak())

    doc.build(elements)
    return file_path

# ==============================
# MAIN FLOW
# ==============================

if st.session_state.attempt_count >= MAX_ATTEMPTS:
    st.success("🎉 You've used all your story versions! Your final storybook is ready above.")
    st.stop()

if st.button("✦ Create My Storybook", disabled=not name.strip()):

    if not name.strip():
        st.warning("Please enter the child's name.")
        st.stop()

    if not st.session_state.character_memory:
        with st.spinner("Bringing your character to life..."):
            st.session_state.character_memory = generate_character_memory(name, age, gender, fav_colour)

    st.session_state.attempt_count += 1
    memory = st.session_state.character_memory

    progress = st.progress(0, text="Weaving the story...")
    story_text = generate_story(
        name, age, gender, theme, family, animals, places, event,
        language, interests, fav_colour, best_friend, moral
    )
    pages = parse_story(story_text)
    progress.progress(20, text="Story written! Creating illustrations...")

    if not pages:
        st.error("Story generation returned an unexpected format. Please try again.")
        st.stop()

    structured_pages = []
    for i, page in enumerate(pages):
        pct = 20 + int((i / len(pages)) * 65)
        progress.progress(pct, text=f"Illustrating page {i+1} of {len(pages)}...")

        img_bytes = get_image(page["scene"], memory, age, gender, fav_colour)
        img_path = f"/tmp/page_{i}.png"
        if img_bytes:
            with open(img_path, "wb") as f:
                f.write(img_bytes)
            page["image_path"] = img_path
        else:
            page["image_path"] = None
        structured_pages.append(page)

    progress.progress(88, text="Binding your storybook...")
    pdf_path = create_pdf(structured_pages, name, theme, language)
    progress.progress(100, text="Your storybook is ready!")
    progress.empty()

    # Display
    st.markdown('<div class="ornament">✦ ❧ ✦</div>', unsafe_allow_html=True)
    st.markdown(f"## {name}'s Story")

    for page in structured_pages:
        if page.get("image_path") and os.path.exists(page["image_path"]):
            st.image(page["image_path"], use_container_width=True)
        st.markdown(f'<div class="story-card">{page["text"]}</div>', unsafe_allow_html=True)

    st.markdown('<div class="ornament">✦ ❧ ✦</div>', unsafe_allow_html=True)

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
    feedback = st.text_area("Your thoughts help us improve the experience for every child:", height=100)
    if st.button("Send Feedback"):
        if feedback.strip():
            supabase.table("feedback").insert({
                "email": st.session_state.user_email,
                "feedback": feedback.strip(),
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
            st.success("Thank you so much! 💖")

    st.balloons()

# Retry
if 0 < st.session_state.attempt_count < MAX_ATTEMPTS:
    remaining = MAX_ATTEMPTS - st.session_state.attempt_count
    st.divider()
    st.caption(f"Not quite right? You have {remaining} more attempt(s) to regenerate.")
    if st.button("🔁 Try a different version"):
        st.session_state.character_memory = None
        st.rerun()
