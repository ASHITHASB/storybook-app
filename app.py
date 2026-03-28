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