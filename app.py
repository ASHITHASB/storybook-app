import streamlit as st
import os
import re
import time
import base64
import requests
import urllib.parse
from datetime import datetime

from openai import OpenAI
from supabase import create_client, Client

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

try:
    from google import genai as google_genai
    IMAGEN_AVAILABLE = True
except ImportError:
    IMAGEN_AVAILABLE = False

# ==============================
# CONFIG
# ==============================

openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

supabase: Client = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

HF_TOKEN = st.secrets.get("HF_TOKEN", "")
HF_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"

GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
google_client = google_genai.Client(api_key=GOOGLE_API_KEY) if (IMAGEN_AVAILABLE and GOOGLE_API_KEY) else None

MAX_ATTEMPTS = 3

# ==============================
# STORY TEMPLATES
# ==============================

TEMPLATES = {
    "First Day of School 🏫": {
        "tagline": "Nervous about something new? You're braver than you think.",
        "theme": "Courage 🦁",
        "plot": (
            "Page 1: The night before school, {name} packs their bag excitedly but feels butterflies in their tummy.\n"
            "Page 2: Morning arrives — {name} gets dressed in their favourite outfit and eats breakfast.\n"
            "Page 3: {name} arrives at school and sees many new faces and feels a little overwhelmed.\n"
            "Page 4: {name} sits alone at their desk, missing home and feeling shy.\n"
            "Page 5: A kind classmate smiles and shares their crayons — they start drawing together.\n"
            "Page 6: {name} discovers they love story time and playing at recess.\n"
            "Page 7: At the end of the day, {name} runs home bursting with things to share.\n"
            "Page 8: That night, {name} lays out their bag for tomorrow — they can't wait to go back."
        ),
    },
    "Dinosaur Adventure 🦕": {
        "tagline": "What if dinosaurs were friendly and waiting to be found?",
        "theme": "Curiosity 🔍",
        "plot": (
            "Page 1: {name} discovers a mysterious glowing egg in the garden.\n"
            "Page 2: The egg hatches into a tiny, friendly dinosaur with big curious eyes.\n"
            "Page 3: {name} and the dinosaur explore the neighbourhood together, causing little surprises.\n"
            "Page 4: The dinosaur gets stuck in a tight spot and {name} must be brave and clever.\n"
            "Page 5: {name} finds a creative way to free the dinosaur — together they cheer.\n"
            "Page 6: They share a meal and watch the sunset, the best of friends.\n"
            "Page 7: The dinosaur must return to the forest — they hug goodbye sadly but warmly.\n"
            "Page 8: {name} finds a tiny dino footprint the next morning — proof the adventure was real."
        ),
    },
    "Backyard Adventures 🐕": {
        "tagline": "Imagination turns any backyard into a whole world. (Bluey-inspired)",
        "theme": "Friendship 🤝",
        "plot": (
            "Page 1: {name} and their dog are in the backyard on a sunny afternoon with nothing planned.\n"
            "Page 2: {name} decides the yard is actually a jungle — they are the brave explorer.\n"
            "Page 3: A challenge appears: a wide 'river' to cross (the garden hose, really).\n"
            "Page 4: {name} builds a bridge from planks and wobbles across with the dog cheering.\n"
            "Page 5: They discover a 'treasure' buried in the soil — a shiny stone.\n"
            "Page 6: Mum or Dad joins the game for the grand finale adventure.\n"
            "Page 7: The game ends as the sun goes down but the magic of the day stays.\n"
            "Page 8: {name} falls asleep that night already dreaming of tomorrow's adventure."
        ),
    },
    "Bear & Me 🐻": {
        "tagline": "Big friends make the world feel smaller. (Masha-inspired)",
        "theme": "Friendship 🤝",
        "plot": (
            "Page 1: {name} lives near a cosy forest and loves to explore after breakfast.\n"
            "Page 2: Deep in the trees, {name} meets a big, gentle bear with kind eyes.\n"
            "Page 3: They bake honey cakes together in the bear's kitchen and make a wonderful mess.\n"
            "Page 4: The bear teaches {name} how to fish in the sparkling stream.\n"
            "Page 5: {name} tries to help the bear carry something heavy and causes a funny tumble.\n"
            "Page 6: They laugh together and solve the problem as a team.\n"
            "Page 7: Bear tucks {name} into a cosy pile of autumn leaves for a nap in the sun.\n"
            "Page 8: {name} wakes up at home in their own bed, smiling — was it all a dream?"
        ),
    },
    "Mermaid Adventure 🧜": {
        "tagline": "Dive into an underwater kingdom full of colour and wonder.",
        "theme": "Curiosity 🔍",
        "plot": (
            "Page 1: {name} finds a glowing pink shell on the beach at sunset.\n"
            "Page 2: Touching the shell, {name} is magically transformed and sinks gently underwater.\n"
            "Page 3: A friendly mermaid appears and offers to show {name} the ocean kingdom.\n"
            "Page 4: They swim past coral castles, playful dolphins and fish of every colour.\n"
            "Page 5: A tiny seahorse is lost and crying — {name} decides to help find its home.\n"
            "Page 6: {name} follows a trail of glowing bubbles and reunites the seahorse with its family.\n"
            "Page 7: The ocean throws a sparkling party in {name}'s honour with singing fish.\n"
            "Page 8: {name} wakes up on the beach at dawn, the glowing shell safe in their hand."
        ),
    },
    "Unicorn Magic 🦄": {
        "tagline": "Some friendships are truly magical.",
        "theme": "Kindness 💖",
        "plot": (
            "Page 1: {name} makes a wish on the brightest star before bedtime.\n"
            "Page 2: A soft glow at the window — a unicorn is waiting, mane like moonlight.\n"
            "Page 3: They fly through a sky full of clouds shaped like elephants and whales.\n"
            "Page 4: They land in a meadow where flowers glow and butterflies sing tiny songs.\n"
            "Page 5: A small fairy sits crying — her wings have lost their sparkle.\n"
            "Page 6: {name} offers a kind word and a gentle hug — the wings flutter and shine again.\n"
            "Page 7: The unicorn carries {name} home as the sky turns pink with dawn.\n"
            "Page 8: {name} wakes to find a single glowing flower on the pillow — it was all real."
        ),
    },
}

# ==============================
# LANGUAGE CONFIG
# ==============================

LANGUAGES = {
    "English": {"prompt_lang": "English", "font_name": "Helvetica", "font_path": None},
    "Hindi (हिंदी)": {
        "prompt_lang": "Hindi", "font_name": "NotoDevanagari",
        "font_path": "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    },
    "Tamil (தமிழ்)": {
        "prompt_lang": "Tamil", "font_name": "NotoTamil",
        "font_path": "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
    },
    "Malayalam (മലയാളം)": {
        "prompt_lang": "Malayalam", "font_name": "NotoMalayalam",
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
# PHOTO → APPEARANCE EXTRACTION
# ==============================

def extract_appearance_from_photo(photo_bytes: bytes, age: int, gender: str) -> str:
    """Use GPT-4o vision to extract the child's appearance from a photo."""
    b64 = base64.b64encode(photo_bytes).decode()
    # Detect image type from magic bytes
    mime = "image/jpeg"
    if photo_bytes[:4] == b'\x89PNG':
        mime = "image/png"
    elif photo_bytes[:4] == b'RIFF':
        mime = "image/webp"

    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            {"type": "text", "text": (
                f"This is a photo of a {age}-year-old {gender.lower()} child. "
                "Describe their appearance for a children's storybook illustrator in ONE sentence under 25 words. "
                "Include: hair colour and style, skin tone, eye colour if visible, and outfit colour. "
                "Be warm and specific. No names. "
                "Example: long curly black hair, warm golden-brown skin, bright brown eyes, red t-shirt with denim shorts"
            )},
        ],
    }]
    for model in ["gpt-4o", "gpt-4o-mini"]:
        try:
            response = openai_client.chat.completions.create(
                model=model, messages=messages, max_tokens=80,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "PermissionDenied" in type(e).__name__ or "permission" in str(e).lower():
                continue
            raise
    raise RuntimeError("No available vision model. Check your OpenAI API key permissions.")

# ==============================
# PAGE CONFIG & STYLE
# ==============================

st.set_page_config(page_title="My Magical Storybook", page_icon="📖", layout="wide")

st.html("""
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
[data-testid="stAppViewContainer"] { background-color: #faf6ef; }
[data-testid="stHeader"] { background-color: #faf6ef; }
.block-container { max-width: 860px !important; padding: 2rem 3rem; }
h1 { font-family: 'Playfair Display', Georgia, serif !important; font-size: 2.6rem !important; color: #5c3317 !important; text-align: center; letter-spacing: 1px; margin-bottom: 0.2rem !important; }
h2, h3 { font-family: 'Playfair Display', Georgia, serif !important; color: #5c3317 !important; }
.ornament { text-align: center; color: #c9a96e; font-size: 1.4rem; margin: 0.5rem 0 1.2rem 0; letter-spacing: 8px; }
.template-card { background: #fdf8f0; border: 1.5px solid #d4b896; border-radius: 10px; padding: 18px 20px; margin-bottom: 14px; cursor: pointer; transition: border-color 0.2s; }
.template-card:hover { border-color: #8b5e3c; }
.story-card { background: #fdf8f0; border: 1px solid #d4b896; border-radius: 6px; padding: 28px 36px; margin-bottom: 28px; font-family: 'Crimson Text', Georgia, serif; font-size: 1.25rem; line-height: 2; text-align: center; color: #3d2b1f; box-shadow: 0 2px 12px rgba(139,90,43,0.08); }
.stButton>button { width: 100%; border-radius: 30px; font-family: 'Playfair Display', Georgia, serif; font-size: 1.05rem; padding: 0.65rem 1.5rem; background: linear-gradient(135deg, #8b5e3c, #c9883f); color: white !important; border: none; letter-spacing: 0.5px; box-shadow: 0 2px 8px rgba(139,90,43,0.3); }
.stButton>button:hover { background: linear-gradient(135deg, #7a5234, #b87a38); }
[data-testid="stDownloadButton"] button { background: linear-gradient(135deg, #3d6b4f, #5a9e72) !important; }
img { border-radius: 8px; }
</style>
""")

st.markdown("<h1>📖 My Magical Storybook</h1>", unsafe_allow_html=True)
st.markdown('<div class="ornament">✦ ❧ ✦</div>', unsafe_allow_html=True)

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

def is_tester(email):
    return email.strip().lower() in TESTER_EMAILS

def is_existing_user(email):
    return len(supabase.table("users").select("email").eq("email", email).execute().data) > 0

def save_user(email, phone):
    if is_tester(email):
        return
    supabase.table("users").insert({
        "email": email, "phone": phone,
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
# MODE TABS
# ==============================

tab_template, tab_custom = st.tabs(["📚 Template Stories", "✍️ Custom Story"])

# ============================================================
# TAB 1 — TEMPLATE MODE
# ============================================================

with tab_template:
    st.markdown("### Choose your story")

    template_name = st.selectbox(
        "Story template",
        list(TEMPLATES.keys()),
        format_func=lambda x: x,
        label_visibility="collapsed",
    )
    t = TEMPLATES[template_name]
    st.info(f"**{template_name}** — {t['tagline']}")

    st.markdown("### About the child")
    tc1, tc2, tc3, tc4 = st.columns(4)
    with tc1:
        t_name = st.text_input("Child's name", key="t_name", placeholder="e.g. Layla")
    with tc2:
        t_age = st.selectbox("Age", [3, 4, 5, 6, 7, 8], key="t_age")
    with tc3:
        t_gender = st.selectbox("Gender", ["Girl", "Boy"], key="t_gender")
    with tc4:
        t_lang = st.selectbox("Language", list(LANGUAGES.keys()), key="t_lang")

    st.markdown("### Child's appearance")
    t_photo = st.file_uploader(
        "📷 Upload a photo of your child (optional — we'll match the character to them)",
        type=["jpg", "jpeg", "png", "webp"], key="t_photo",
    )
    if not t_photo:
        ta1, ta2, ta3 = st.columns(3)
        with ta1:
            t_hair = st.text_input("Hair", key="t_hair", placeholder="e.g. long curly black hair")
        with ta2:
            t_colour = st.text_input("Favourite colour (outfit)", key="t_colour", placeholder="e.g. purple")
        with ta3:
            t_skin = st.text_input("Skin tone", key="t_skin", placeholder="e.g. warm golden skin")
    else:
        t_hair = t_skin = ""
        t_colour = st.text_input("Favourite colour (outfit)", key="t_colour", placeholder="e.g. purple")
        st.caption("✅ Photo uploaded — we'll extract the appearance automatically.")

    if st.session_state.attempt_count < MAX_ATTEMPTS:
        if st.button("✦ Create Storybook", key="btn_template", disabled=not t_name.strip()):
            if not t_name.strip():
                st.warning("Please enter the child's name.")
                st.stop()

            with st.spinner("Bringing your character to life..."):
                if t_photo:
                    st.session_state.character_memory = extract_appearance_from_photo(
                        t_photo.read(), t_age, t_gender
                    )
                else:
                    parts = [p for p in [t_hair, t_skin, f"{t_colour} outfit" if t_colour else ""] if p]
                    if parts:
                        st.session_state.character_memory = ", ".join(parts)
                    else:
                        r = openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content":
                                f"Describe a storybook child in one sentence (under 20 words). "
                                f"Age: {t_age}, Gender: {t_gender}. Include hair, skin, outfit. No proper nouns."}]
                        )
                        st.session_state.character_memory = r.choices[0].message.content.strip()

            st.session_state.attempt_count += 1
            st.session_state["_mode"] = "template"
            st.session_state["_params"] = {
                "name": t_name, "age": t_age, "gender": t_gender,
                "language": t_lang, "template_name": template_name,
                "fav_colour": t_colour,
            }
            st.rerun()
    else:
        st.success("🎉 You've used all your story attempts!")

# ============================================================
# TAB 2 — CUSTOM MODE
# ============================================================

with tab_custom:
    st.markdown("### About the child")
    cc1, cc2, cc3, cc4 = st.columns(4)
    with cc1:
        c_name = st.text_input("Child's name", key="c_name", placeholder="e.g. Arjun")
    with cc2:
        c_age = st.selectbox("Age", [3, 4, 5, 6, 7, 8], key="c_age")
    with cc3:
        c_gender = st.selectbox("Gender", ["Girl", "Boy"], key="c_gender")
    with cc4:
        c_lang = st.selectbox("Language", list(LANGUAGES.keys()), key="c_lang")

    c_theme = st.selectbox("Story theme", [
        "Kindness 💖", "Courage 🦁", "Friendship 🤝",
        "Confidence 🌟", "Curiosity 🔍", "Honesty 🌿",
    ], key="c_theme")

    st.markdown("### Personalise")
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        c_family = st.multiselect("Family members", ["Mother", "Father", "Brother", "Sister", "Grandma", "Grandpa"])
    with cp2:
        c_animals = st.multiselect("Animals", ["Dog", "Cat", "Bird", "Rabbit", "Horse", "Elephant"])
    with cp3:
        c_places = st.multiselect("Places", ["Park", "Beach", "School", "Forest", "Home", "Library"])

    c_event = st.text_input("Special event (optional)", placeholder="e.g. first day of school", key="c_event")

    st.markdown("### Child's appearance")
    c_photo = st.file_uploader(
        "📷 Upload a photo of your child (optional — we'll match the character to them)",
        type=["jpg", "jpeg", "png", "webp"], key="c_photo",
    )
    if c_photo:
        st.caption("✅ Photo uploaded — we'll extract the appearance automatically.")

    with st.expander("✦ Advanced customisation (optional)"):
        ca1, ca2 = st.columns(2)
        with ca1:
            c_interests = st.text_input("Interests / hobbies", placeholder="e.g. painting, football")
            c_colour = st.text_input("Favourite colour (outfit)", placeholder="e.g. purple")
        with ca2:
            c_friend = st.text_input("Best friend's name", placeholder="e.g. Mia")
            c_moral = st.text_input("Specific lesson or moral", placeholder="e.g. it's okay to ask for help")

    # Plot customisation
    st.markdown("### ✍️ Customise the storyline")
    plot_mode = st.radio(
        "How would you like to shape the story?",
        ["🗝️ Guided plot points", "📝 Free-write the plot"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if plot_mode == "🗝️ Guided plot points":
        gp1, gp2 = st.columns(2)
        with gp1:
            c_opening = st.text_area("Opening scene", placeholder="Where does the story begin? What is the child doing?", height=90)
            c_challenge = st.text_area("Problem or challenge", placeholder="What difficulty or adventure does the child face?", height=90)
        with gp2:
            c_turning = st.text_area("Turning point", placeholder="How does the child face it? What changes?", height=90)
            c_resolution = st.text_area("Resolution", placeholder="How does it end? What does the child learn?", height=90)
        c_freewrite = None
    else:
        c_freewrite = st.text_area(
            "Write your story plot",
            placeholder="Describe the full story in your own words. The AI will turn it into a beautiful illustrated book.",
            height=180,
        )
        c_opening = c_challenge = c_turning = c_resolution = None

    if st.session_state.attempt_count < MAX_ATTEMPTS:
        if st.button("✦ Create My Storybook", key="btn_custom", disabled=not c_name.strip()):
            if not c_name.strip():
                st.warning("Please enter the child's name.")
                st.stop()

            with st.spinner("Bringing your character to life..."):
                if c_photo:
                    st.session_state.character_memory = extract_appearance_from_photo(
                        c_photo.read(), c_age, c_gender
                    )
                else:
                    colour_hint = f"Favourite colour is {c_colour}, reflected in outfit." if c_colour else ""
                    r = openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content":
                            f"Describe a storybook child's appearance in one vivid sentence (under 25 words). "
                            f"Age: {c_age}, Gender: {c_gender}. {colour_hint} "
                            f"Include hair, skin tone, outfit colour. No proper nouns."}]
                    )
                    st.session_state.character_memory = r.choices[0].message.content.strip()

            st.session_state.attempt_count += 1
            st.session_state["_mode"] = "custom"
            st.session_state["_params"] = {
                "name": c_name, "age": c_age, "gender": c_gender,
                "language": c_lang, "theme": c_theme,
                "family": c_family, "animals": c_animals,
                "places": c_places, "event": c_event,
                "interests": c_interests, "fav_colour": c_colour,
                "best_friend": c_friend, "moral": c_moral,
                "plot_mode": plot_mode,
                "opening": c_opening, "challenge": c_challenge,
                "turning": c_turning, "resolution": c_resolution,
                "freewrite": c_freewrite,
            }
            st.rerun()
    else:
        st.success("🎉 You've used all your story attempts!")

# ============================================================
# STORY GENERATION (runs after button press + rerun)
# ============================================================

if "_mode" not in st.session_state:
    st.stop()

mode = st.session_state["_mode"]
p = st.session_state["_params"]
memory = st.session_state.character_memory
prompt_lang = LANGUAGES[p["language"]]["prompt_lang"]

# ==============================
# BUILD STORY PROMPT
# ==============================

def build_template_prompt(p, memory):
    t = TEMPLATES[p["template_name"]]
    plot_with_name = t["plot"].replace("{name}", p["name"])
    return f"""You are an award-winning children's picture book author writing in {prompt_lang}.

Write a beautifully crafted, emotionally resonant storybook. Use the plot guide below as the exact page-by-page structure, but write it with vivid, lyrical language perfectly pitched for a {p['age']}-year-old.

Main character: {p['name']}, a {p['age']}-year-old {p['gender'].lower()}. Appearance: {memory}.

Theme: {t['theme']}

Plot guide (follow this structure exactly):
{plot_with_name}

Output each page in EXACTLY this format (plain text only — no bold, no asterisks, no markdown):

Page 1
Text: [2–3 warm, lyrical sentences in {prompt_lang}]
Scene: [one sentence describing the illustration in English — specific setting, mood, colours, action]

Page 2
Text: ...
Scene: ...

(continue through Page 8)

Rules:
- Text must be in {prompt_lang}
- Scene must always be in English
- Follow the plot guide closely but write with warmth and imagination
- End with a joyful, uplifting moment
- Plain text only. No markdown whatsoever."""


def build_custom_prompt(p, memory):
    details = []
    if p.get("family"):       details.append(f"Family members: {', '.join(p['family'])}")
    if p.get("animals"):      details.append(f"Animals: {', '.join(p['animals'])}")
    if p.get("places"):       details.append(f"Places: {', '.join(p['places'])}")
    if p.get("event"):        details.append(f"Special event: {p['event']}")
    if p.get("interests"):    details.append(f"Interests: {p['interests']}")
    if p.get("best_friend"):  details.append(f"Best friend: {p['best_friend']}")
    if p.get("fav_colour"):   details.append(f"Favourite colour: {p['fav_colour']}")
    if p.get("moral"):        details.append(f"Lesson to teach: {p['moral']}")
    personalization = "\n".join(f"- {d}" for d in details) if details else "- Keep it warm and universal"

    if p.get("freewrite"):
        plot_section = f"Parent's story plot (use this as the basis for the story):\n{p['freewrite']}"
    else:
        parts = []
        if p.get("opening"):    parts.append(f"Opening: {p['opening']}")
        if p.get("challenge"):  parts.append(f"Challenge: {p['challenge']}")
        if p.get("turning"):    parts.append(f"Turning point: {p['turning']}")
        if p.get("resolution"): parts.append(f"Resolution: {p['resolution']}")
        plot_section = ("Parent's story plot points:\n" + "\n".join(parts)) if parts else ""

    return f"""You are an award-winning children's picture book author writing in {prompt_lang}.

Write a beautifully crafted, emotionally resonant storybook with exactly 8 pages. Each page should feel like a moment from a treasured illustrated book — vivid, lyrical, and perfectly pitched for a {p['age']}-year-old.

Main character: {p['name']}, a {p['age']}-year-old {p['gender'].lower()}. Appearance: {memory}.

Theme: {p['theme']}

{plot_section}

Story details:
{personalization}

Output each page in EXACTLY this format (plain text only — no bold, no asterisks, no markdown):

Page 1
Text: [2–3 warm, lyrical sentences in {prompt_lang}]
Scene: [one sentence describing the illustration in English — specific setting, mood, colours, action]

Page 2
Text: ...
Scene: ...

(continue through Page 8)

Rules:
- Text must be in {prompt_lang}. Scene must always be in English.
- Build emotional arc: wonder → challenge → growth → joyful resolution
- Use sensory language, warmth and gentle humour
- Plain text only. No markdown whatsoever."""


# ==============================
# GENERATE STORY
# ==============================

prompt = build_template_prompt(p, memory) if mode == "template" else build_custom_prompt(p, memory)

progress = st.progress(0, text="Weaving the story...")

story_text = None
for model in ["gpt-4o", "gpt-4o-mini"]:
    try:
        resp = openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85,
        )
        story_text = resp.choices[0].message.content
        break
    except Exception as e:
        if "PermissionDenied" in type(e).__name__ or "permission" in str(e).lower():
            continue
        raise

if not story_text:
    st.error("Could not generate story. Check your OpenAI API key.")
    st.stop()

# ==============================
# PARSE
# ==============================

def parse_story(story_text):
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', story_text)
    for pattern in [
        re.compile(r'Page\s*\d+[:\.]?\s*\n+\s*Text:\s*(.*?)\s*\n+\s*Scene:\s*(.*?)(?=\n+\s*Page\s*\d+|\Z)', re.DOTALL | re.IGNORECASE),
        re.compile(r'Text:\s*(.*?)\s*\nScene:\s*(.*?)(?=\nText:|\Z)', re.DOTALL | re.IGNORECASE),
    ]:
        matches = pattern.findall(text)
        pages = [{"text": t.strip(), "scene": s.strip()} for t, s in matches if t.strip() and s.strip() and len(s.strip()) >= 10]
        if len(pages) >= 3:
            return pages
    return []

pages = parse_story(story_text)
progress.progress(20, text="Story written! Generating illustrations...")

if not pages:
    st.error("Story format was unexpected. Please try again.")
    del st.session_state["_mode"]
    st.stop()

# ==============================
# IMAGE GENERATION
# ==============================

fav_colour = p.get("fav_colour", "")

def build_image_prompt(scene, memory, age, gender, fav_colour):
    colour_note = f"wearing {fav_colour} coloured clothes," if fav_colour else ""
    character = f"a {age} year old {gender.lower()} child, {memory}, {colour_note} consistent appearance throughout"
    style = (
        "vibrant children's book illustration, 3D cartoon style, "
        "bright saturated colors, Disney and Pixar inspired art, "
        "clean professional illustration, expressive cute characters, "
        "rich detailed colorful background, warm cheerful lighting, "
        "high quality digital art, playful and charming"
    )
    negative = "photorealistic, dark, scary, text, watermark, blurry, deformed, ugly, low quality, sketch, grayscale"
    return f"{character}, {scene}, {style}", negative


def generate_image_gemini_flash(prompt_text):
    """Gemini 2.0 Flash image generation (experimental)."""
    if not google_client:
        return None
    try:
        from google.genai import types as gtypes
        response = google_client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=prompt_text,
            config=gtypes.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data is not None:
                return part.inline_data.data
    except Exception:
        pass
    return None


def generate_image_imagen3(prompt_text):
    """Imagen 3 — Google's dedicated image generation model."""
    if not google_client:
        return None
    try:
        from google.genai import types as gtypes
        response = google_client.models.generate_images(
            model="imagen-3.0-generate-001",
            prompt=prompt_text,
            config=gtypes.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="3:2",
                safety_filter_level="block_some",
                person_generation="allow_all",
            ),
        )
        if response.generated_images:
            return response.generated_images[0].image.image_bytes
    except Exception:
        pass
    return None


def generate_image_hf(prompt_text, negative):
    if not HF_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt_text,
        "parameters": {"negative_prompt": negative, "width": 768, "height": 512,
                       "num_inference_steps": 30, "guidance_scale": 7.5},
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
    prompt_text, _ = build_image_prompt(scene, memory, age, gender, fav_colour)
    encoded = urllib.parse.quote(prompt_text)
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
    """Try all image generators in order. Retry Pollinations up to 3x to guarantee an image."""
    prompt_text, negative = build_image_prompt(scene, memory, age, gender, fav_colour)

    img = (
        generate_image_gemini_flash(prompt_text)
        or generate_image_imagen3(prompt_text)
        or generate_image_hf(prompt_text, negative)
    )
    if img:
        return img

    # Pollinations with retries — vary seed each attempt for a fresh result
    for attempt in range(3):
        encoded = urllib.parse.quote(prompt_text)
        seed = (abs(hash(scene)) + attempt * 7919) % 99999
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=512&seed={seed}&nologo=true"
        try:
            r = requests.get(url, timeout=45)
            if r.status_code == 200 and len(r.content) > 5000:
                return r.content
        except Exception:
            time.sleep(3)

    return None  # should rarely reach here


structured_pages = []
name = p["name"]
age = p["age"]
gender = p["gender"]
language = p["language"]

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

# ==============================
# PDF
# ==============================

def create_pdf(pages, name, theme, language):
    file_path = "/tmp/storybook.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A5,
                            leftMargin=0.55*inch, rightMargin=0.55*inch,
                            topMargin=0.55*inch, bottomMargin=0.55*inch)
    font_name = font_registry.get(language, "Helvetica")
    title_style = ParagraphStyle("Title", fontName=font_name, fontSize=22, alignment=TA_CENTER, spaceAfter=8, leading=30)
    subtitle_style = ParagraphStyle("Subtitle", fontName=font_name, fontSize=12, alignment=TA_CENTER, textColor=(0.55, 0.35, 0.15), leading=18)
    body_style = ParagraphStyle("Body", fontName=font_name, fontSize=13, alignment=TA_CENTER, leading=22, spaceAfter=6)

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

progress.progress(88, text="Binding your storybook...")
theme_display = TEMPLATES[p["template_name"]]["theme"] if mode == "template" else p.get("theme", "")
pdf_path = create_pdf(structured_pages, name, theme_display, language)
progress.progress(100, text="Your storybook is ready!")
progress.empty()

# ==============================
# DISPLAY
# ==============================

st.markdown('<div class="ornament">✦ ❧ ✦</div>', unsafe_allow_html=True)
st.markdown(f"## {name}'s Story")

for page in structured_pages:
    if page.get("image_path") and os.path.exists(page["image_path"]):
        st.image(page["image_path"], use_container_width=True)
    st.markdown(f'<div class="story-card">{page["text"]}</div>', unsafe_allow_html=True)

st.markdown('<div class="ornament">✦ ❧ ✦</div>', unsafe_allow_html=True)

with open(pdf_path, "rb") as f:
    st.download_button(
        "📥 Download Your Storybook (PDF)", f,
        file_name=f"{name.strip()}_storybook.pdf", mime="application/pdf",
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
if st.session_state.attempt_count < MAX_ATTEMPTS:
    remaining = MAX_ATTEMPTS - st.session_state.attempt_count
    st.divider()
    st.caption(f"Not quite right? You have {remaining} more attempt(s) to regenerate.")
    if st.button("🔁 Try a different version"):
        st.session_state.character_memory = None
        del st.session_state["_mode"]
        st.rerun()
