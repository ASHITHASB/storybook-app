import streamlit as st
import os
import csv
import requests
import urllib.parse
from datetime import datetime

from openai import OpenAI

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch

# ==============================
# CONFIG
# ==============================

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="Magical Storybook", layout="wide")

st.title("✨ Magical Storybook")

# ==============================
# SESSION STATE
# ==============================

if "user_registered" not in st.session_state:
    st.session_state.user_registered = False

if "story_generated" not in st.session_state:
    st.session_state.story_generated = False

if "attempt_count" not in st.session_state:
    st.session_state.attempt_count = 0

if "character_memory" not in st.session_state:
    st.session_state.character_memory = None

MAX_ATTEMPTS = 3

# ==============================
# USER STORAGE
# ==============================

def is_existing_user(email):
    if not os.path.exists("users.csv"):
        return False
    with open("users.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["email"] == email:
                return True
    return False


def save_user(email, phone):
    file_exists = os.path.isfile("users.csv")
    with open("users.csv", "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["email", "phone", "timestamp"])
        writer.writerow([email, phone, datetime.now()])

# ==============================
# SIGNUP
# ==============================

if not st.session_state.user_registered:

    st.subheader("🔐 Sign up")

    email = st.text_input("Email")
    phone = st.text_input("Phone")

    if st.button("Continue"):

        if not email or not phone:
            st.warning("Fill all fields")

        elif is_existing_user(email):
            st.error("You already created a story")

        else:
            save_user(email, phone)
            st.session_state.user_registered = True
            st.success("Welcome!")

    st.stop()

# ==============================
# INPUTS
# ==============================

col1, col2, col3 = st.columns(3)

with col1:
    name = st.text_input("Child Name")

with col2:
    age = st.selectbox("Age", [3,4,5,6,7,8])

with col3:
    gender = st.selectbox("Gender", ["Boy", "Girl"])

theme = st.selectbox("Theme", ["Kindness", "Courage", "Friendship"])

st.subheader("✨ Personalize the story")

family = st.multiselect("Family", ["Mother", "Father", "Brother", "Sister"])
animals = st.multiselect("Animals", ["Dog", "Cat", "Bird"])
places = st.multiselect("Places", ["Park", "School", "Home"])
event = st.text_input("Event (optional)")

# ==============================
# CHARACTER MEMORY
# ==============================

def generate_character_memory(name, age, gender):

    prompt = f"""
    Create a visual description of a child.

    Name: {name}
    Age: {age}
    Gender: {gender}

    Include:
    face, hair, clothing

    Keep it short.

    Example:
    round face, curly hair, red shirt, blue shorts
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()

# ==============================
# STORY ENGINE
# ==============================

def build_character(name, age, gender):

    memory = st.session_state.character_memory

    return f"""
    {name}, a {age}-year-old {gender.lower()} child.

    Appearance:
    {memory}

    SAME character across all pages.
    """

def build_personalization(family, animals, places, event):

    return f"""
    Family: {", ".join(family) if family else "None"}
    Animals: {", ".join(animals) if animals else "None"}
    Places: {", ".join(places) if places else "None"}
    Event: {event if event else "None"}
    """

def generate_story(name, age, gender, theme, family, animals, places, event):

    character = build_character(name, age, gender)
    personalization = build_personalization(family, animals, places, event)

    prompt = f"""
    Create a high-quality children's story.

    Character:
    {character}

    Theme:
    {theme}

    Personalization:
    {personalization}

    Requirements:
    - 8 pages exactly
    - Each page MUST include:
        Text:
        Scene:
    - Scene must be visually rich
    - Maintain same character
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

# ==============================
# PARSE
# ==============================

def parse_story(story_text):
    pages = story_text.split("Page")
    structured = []

    for p in pages:
        if "Text:" in p and "Scene:" in p:
            try:
                text = p.split("Text:")[1].split("Scene:")[0].strip()
                scene = p.split("Scene:")[1].strip()

                if len(scene) < 20:
                    continue

                structured.append({"text": text, "scene": scene})

            except:
                continue

    return structured

# ==============================
# IMAGE ENGINE
# ==============================

def generate_image(scene, name, age, gender):

    memory = st.session_state.character_memory

    character = f"""
    {age} year old {gender.lower()} child named {name},
    {memory},
    same character, same clothes, same face
    """

    style = """
    children's storybook illustration,
    watercolor, pastel colors,
    magical lighting, high detail
    """

    negative = "no text, no watermark, no modern objects"

    prompt = f"{character}, {scene}, {style}, {negative}"

    encoded = urllib.parse.quote(prompt)

    return f"https://image.pollinations.ai/prompt/{encoded}"

# ==============================
# PDF
# ==============================

def create_pdf(pages, name):

    file_path = "storybook.pdf"

    doc = SimpleDocTemplate(file_path, pagesize=A5)
    styles = getSampleStyleSheet()

    text_style = ParagraphStyle(name='Text', alignment=TA_CENTER)

    elements = []

    elements.append(Paragraph(f"{name}'s Story", styles["Title"]))
    elements.append(PageBreak())

    for page in pages:

        if page.get("image_path"):
            elements.append(Image(page["image_path"], width=4*inch, height=3*inch))

        elements.append(Paragraph(page["text"], text_style))
        elements.append(PageBreak())

    doc.build(elements)

    return file_path

# ==============================
# GENERATE FLOW
# ==============================

if st.button("✨ Create Story"):

    if st.session_state.attempt_count >= MAX_ATTEMPTS:
        st.error("Max attempts reached")
        st.stop()

    st.session_state.attempt_count += 1

    if not st.session_state.character_memory:
        st.session_state.character_memory = generate_character_memory(name, age, gender)

    story = generate_story(name, age, gender, theme, family, animals, places, event)
    pages = parse_story(story)

    structured_pages = []

    for i, page in enumerate(pages):

        st.markdown(f"### Page {i+1}")

        if i < 5:
            img_url = generate_image(page["scene"], name, age, gender)
            st.image(img_url)

            try:
                img_data = requests.get(img_url).content
                path = f"temp_{i}.png"

                with open(path, "wb") as f:
                    f.write(img_data)

                page["image_path"] = path
            except:
                page["image_path"] = None

        st.markdown(page["text"])

        structured_pages.append(page)

    pdf = create_pdf(structured_pages, name)

    with open(pdf, "rb") as f:
        st.download_button("📥 Download Storybook", f, "storybook.pdf")

# Retry
if st.session_state.attempt_count < MAX_ATTEMPTS:
    if st.button("🔁 Try another version"):
        st.session_state.character_memory = None
        st.rerun()
else:
    st.success("Final story locked 🎉")
=======
import streamlit as st
import os
import csv
import requests
from datetime import datetime

from openai import OpenAI

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch
from reportlab.lib import colors

# 🔐 API KEY (Streamlit Cloud)
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="Magical Storybook", page_icon="✨", layout="wide")

# 🌈 UI
st.markdown("""
<style>
.block-container {
    max-width: 100% !important;
    padding-left: 5%;
    padding-right: 5%;
}
.story-card {
    background: linear-gradient(135deg, #fff1ff, #e6f7ff);
    padding: 20px;
    border-radius: 20px;
    margin-bottom: 20px;
}
.stButton>button {
    width: 100%;
    border-radius: 25px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center;'>✨ My Magical Storybook ✨</h1>", unsafe_allow_html=True)

# Session
if "user_registered" not in st.session_state:
    st.session_state.user_registered = False
if "story_generated" not in st.session_state:
    st.session_state.story_generated = False

# Save user
def save_user(email, phone):
    file_exists = os.path.isfile("users.csv")
    with open("users.csv", "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["email", "phone", "timestamp"])
        writer.writerow([email, phone, datetime.now()])

# Signup
if not st.session_state.user_registered:
    st.markdown("## 🔐 Sign up to continue")
    email = st.text_input("📧 Email")
    phone = st.text_input("📱 Mobile Number")

    if st.button("Continue"):
        if not email or not phone:
            st.warning("Please fill all fields")
        else:
            save_user(email, phone)
            st.session_state.user_registered = True
            st.success("Welcome! ✨")

    st.stop()

# Inputs
col1, col2 = st.columns(2)
with col1:
    name = st.text_input("Child's Name")
with col2:
    age = st.selectbox("Age", [3,4,5,6,7,8])

theme = st.selectbox(
    "Theme",
    ["Kindness 💖", "Courage 🦁", "Friendship 🤝", "Confidence 🌟"]
)

# Story
def generate_story(name, age, theme):
    prompt = f"""
    Create a magical children's story.

    Child: {name}, Age: {age}, Theme: {theme}

    8-12 pages with Text + Scene.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Image
def generate_image(scene, name, age):
    prompt = f"""
    Children's storybook illustration of a {age}-year-old child named {name}.
    Scene: {scene}
    watercolor, fairy tale style
    """
    result = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024"
    )
    return result.data[0].url

# PDF
def create_pdf(pages, name, theme):
    file_path = "storybook.pdf"

    doc = SimpleDocTemplate(file_path, pagesize=A5)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(name='Title', fontSize=22, alignment=TA_CENTER)
    text_style = ParagraphStyle(name='Text', fontSize=14, alignment=TA_CENTER)

    elements = []

    elements.append(Spacer(1, 2 * inch))
    elements.append(Paragraph(f"{name}'s Magical Story", title_style))
    elements.append(PageBreak())

    for page in pages:
        if page.get("image_path"):
            elements.append(Image(page["image_path"], width=4.5*inch, height=4*inch))
            elements.append(Spacer(1, 10))

        elements.append(Paragraph(page["text"], text_style))
        elements.append(PageBreak())

    doc.build(elements)
    return file_path

# Generate
if st.button("✨ Create Story"):

    if st.session_state.story_generated:
        st.warning("Only one story allowed")
    else:

        story_text = generate_story(name, age, theme)
        st.session_state.story_generated = True

        pages = story_text.split("Page")
        structured_pages = []

        for i, p in enumerate(pages):
            if "Text:" in p and "Scene:" in p:
                text = p.split("Text:")[1].split("Scene:")[0].strip()
                scene = p.split("Scene:")[1].strip()

                page_data = {"text": text, "scene": scene}

                if i < 5:
                    try:
                        img_url = generate_image(scene, name, age)
                        st.image(img_url)

                        img_path = f"temp_{i}.png"
                        img_data = requests.get(img_url).content
                        with open(img_path, "wb") as f:
                            f.write(img_data)

                        page_data["image_path"] = img_path
                    except:
                        page_data["image_path"] = None

                structured_pages.append(page_data)

        st.markdown("## 📖 Your Storybook")

        for page in structured_pages:
            st.markdown(page["text"])

        pdf = create_pdf(structured_pages, name, theme)

        with open(pdf, "rb") as f:
            st.download_button("📥 Download Storybook", f, "storybook.pdf")

        st.balloons()
