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
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False

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
google_client = google_genai.Client(api_key=GOOGLE_API_KEY) if (GOOGLE_GENAI_AVAILABLE and GOOGLE_API_KEY) else None

DASHSCOPE_API_KEY = st.secrets.get("DASHSCOPE_API_KEY", "")

SARVAM_API_KEY = st.secrets.get("SARVAM_API_KEY", "")
try:
    from sarvamai import SarvamAI
    sarvam_client = SarvamAI(api_subscription_key=SARVAM_API_KEY) if SARVAM_API_KEY else None
except Exception:
    sarvam_client = None

MAX_ATTEMPTS = 3

# ==============================
# STORY TEMPLATES
# ==============================

TEMPLATES = {
    "First Day of School 🏫": {
        "tagline": "Nervous about something new? You're braver than you think.",
        "theme": "Courage 🦁",
        "pages": [
            {
                "text": "The night before school, {name} carefully packed every crayon and pencil into {his_her} new bag. {He_She} pressed the bag close and breathed in that lovely new-school smell. But deep inside, butterflies danced a nervous little dance.",
                "scene": "a child sitting on a bedroom floor at night, moonlight through the window, carefully packing a colourful backpack with pencils and crayons, expression of excited nervousness, cosy bedroom with toys and books, warm lamplight",
            },
            {
                "text": "Morning came in bright and golden. {name} put on {his_her} favourite outfit and ate a big bowl of porridge. 'You are ready,' said Mum, giving {him_her} the warmest hug.",
                "scene": "a sunny kitchen at breakfast time, a child eating porridge at a round table, parent standing nearby smiling warmly, golden morning light streaming through window, cheerful colourful home interior",
            },
            {
                "text": "The school gates were tall and the playground was full of voices {name} did not recognise yet. So many children — all strangers. {He_She} held {his_her} bag straps tight and walked in.",
                "scene": "a busy school playground, a child stepping bravely through iron gates, sea of cheerful unfamiliar children playing in the background, bright sunny day, colourful school building",
            },
            {
                "text": "{name} sat at a desk near the window and watched the other children quietly. {He_She} missed home and the cosy smell of breakfast. The classroom felt very, very big.",
                "scene": "a child sitting alone at a classroom desk by a sunny window, looking a little wistful, bright and colourful classroom with alphabet posters and potted plants, warm morning light",
            },
            {
                "text": "Then a smiling face appeared beside {name} — a classmate with paint on {his_her} fingers and a box of shared crayons. 'Want to draw with me?' {he_she} asked. {name}'s heart lit up.",
                "scene": "two children sitting side by side at a classroom table, one child offering a box of crayons to the other with a shy smile, colourful drawings spread on the table, warm classroom light",
            },
            {
                "text": "Story time was magical, and recess was even better. {name} ran and laughed and discovered that school was full of the most wonderful surprises. {He_She} was not nervous anymore.",
                "scene": "children playing joyfully at recess on a bright playground, the main child character running and laughing with new friends, bright blue sky, colourful play equipment",
            },
            {
                "text": "When the bell rang, {name} ran through the gate with a heart full to bursting. 'Guess what, Mum!' {he_she} cried, the words tumbling out all at once. 'School is brilliant!'",
                "scene": "a child running joyfully out of school gates towards a waiting parent with arms wide open, warm afternoon golden light, other happy children and parents in background",
            },
            {
                "text": "That evening, {name} laid out {his_her} bag for tomorrow — carefully, happily — before {he_she} had even had dinner. Because tomorrow, {he_she} could not wait to go back.",
                "scene": "a child's cosy bedroom in the evening, the child placing a backpack neatly by the door and smiling to themselves, warm lamp light, peaceful and happy atmosphere",
            },
        ],
    },
    "Dinosaur Adventure 🦕": {
        "tagline": "What if dinosaurs were friendly and waiting to be found?",
        "theme": "Curiosity 🔍",
        "pages": [
            {
                "text": "{name} was digging in the garden after breakfast when the spade hit something hard and strange. It was an egg — smooth as a river stone, and glowing the faintest gold. {He_She} carried it inside very carefully, eyes wide with wonder.",
                "scene": "a child crouching in a sunlit garden, carefully lifting a small golden glowing egg from the soil, wide excited eyes, colourful flowers around, dappled morning sunlight through garden trees",
            },
            {
                "text": "That night, the egg began to crack. Tiny golden sparks flew out, and then — crack, crack, CRACK — a small head appeared. The tiniest dinosaur {name} had ever seen blinked up at {him_her} with enormous curious eyes.",
                "scene": "a child's cosy bedroom at night, a glowing egg cracking open on a soft rug, a tiny cute cartoon dinosaur emerging and looking up at the child with big bright eyes, soft golden night light",
            },
            {
                "text": "{name} named the dinosaur Pip, and Pip went absolutely everywhere. The neighbours were very surprised to see them both at the post box. The postman dropped all his letters.",
                "scene": "a child and a tiny bright-coloured cartoon dinosaur walking cheerfully down a neighbourhood street together, surprised neighbours looking out from doorways, sunny day, colourful houses",
            },
            {
                "text": "Then Pip squeezed into the garden shed and got very, very stuck. {He_She} wriggled and huffed and made the most mournful sound. {name} thought hard. This called for a brilliant plan.",
                "scene": "a small cute cartoon dinosaur stuck halfway through a garden shed doorway looking worried, a child kneeling outside with hand on chin thinking hard, sunny garden setting",
            },
            {
                "text": "A bucket, a rope, and one very long scarf later — WHOOSH! — out popped Pip like a cork from a bottle. They landed in a heap on the grass, laughing so hard {name}'s sides ached.",
                "scene": "a child and a small cartoon dinosaur tumbling onto the grass together in a laughing heap, a rope and bright scarf visible, joyful sunny garden afternoon, expressions of pure delight",
            },
            {
                "text": "They shared {name}'s packed lunch under the apple tree — Pip ate all the cucumber, which surprised everyone. The sun was warm and the day was utterly perfect.",
                "scene": "a child and a small dinosaur sharing a picnic under a large apple tree, the dinosaur eating cucumber delightedly, warm golden afternoon light, peaceful garden setting",
            },
            {
                "text": "But at sunset, Pip's golden glow grew brighter. {He_She} nuzzled {name}'s cheek and pointed toward the forest. {name} hugged Pip for a long, long time before letting go.",
                "scene": "a child hugging a small glowing cartoon dinosaur at the edge of a forest at sunset, warm golden and orange sky, silhouettes of trees, tender farewell scene",
            },
            {
                "text": "The next morning, {name} found a single tiny footprint in the dewy grass — golden and gleaming like a star. {He_She} smiled. It had all been wonderfully, beautifully real.",
                "scene": "a tiny golden glowing dinosaur footprint sparkling in dewy morning grass, a child's feet visible at the edge of the frame, soft early morning light, dewdrops catching the sun",
            },
        ],
    },
    "Backyard Adventures 🐕": {
        "tagline": "Imagination turns any backyard into a whole world.",
        "theme": "Friendship 🤝",
        "pages": [
            {
                "text": "It was a sunny Saturday with absolutely nothing to do — which, {name} had discovered, was the very best kind of day. {He_She} and {his_her} dog, Biscuit, went to sit in the backyard and think.",
                "scene": "a child and a fluffy golden dog sitting side by side on the grass in a sunny backyard, both looking thoughtful and content, garden fence and flowers in background, bright afternoon light",
            },
            {
                "text": "'This is not just a backyard,' {name} announced to Biscuit very seriously. 'This is the Great Jungle of Zanzibar, and I am the bravest explorer who ever lived.' Biscuit wagged his tail in complete agreement.",
                "scene": "a child standing heroically in a backyard wearing an improvised explorer's hat, pointing dramatically into the distance, the fluffy dog sitting at attention beside them, leafy garden",
            },
            {
                "text": "The garden hose lay coiled across the grass — clearly a vast and rushing river. Biscuit barked at it. {name} narrowed {his_her} eyes. They would have to find a way across.",
                "scene": "a child and a dog staring down very seriously at a garden hose as if it were a wide river, both with determined expressions, bright sunny backyard setting",
            },
            {
                "text": "{name} dragged out two planks from the shed and wobbled carefully across the 'river', arms stretched wide for balance. Biscuit bounded over in one magnificent leap and stood waiting proudly on the other side.",
                "scene": "a child carefully tiptoeing along two wooden planks over a garden hose, arms outstretched for balance, the fluffy dog watching proudly from the far side, sunny backyard",
            },
            {
                "text": "Digging near the roses, {name}'s fingers found something cold and shiny in the soil — a smooth, beautiful stone that caught the light like treasure. 'We found it!' {he_she} gasped. 'The treasure of Zanzibar!'",
                "scene": "a child holding a smooth shiny stone up triumphantly in the sunlight, the dog jumping up excitedly beside them, a garden with roses in the background, golden afternoon light",
            },
            {
                "text": "Mum came out with juice and biscuits and heard all about Zanzibar. Before anyone knew it, she was wearing a colander hat and had become the expedition's chief map-maker. Biscuit was very pleased with this.",
                "scene": "a parent wearing a funny colander on their head, sitting in the garden drawing a treasure map, a child and a fluffy dog watching with delight, warm afternoon garden setting",
            },
            {
                "text": "The sun began to lower itself behind the fence, painting everything gold and soft. The Great Jungle of Zanzibar grew quiet. The expedition was over for today — but what an expedition it had been.",
                "scene": "a child and a dog sitting together on the grass at golden hour watching the sunset, the parent nearby, long warm shadows across the backyard, peaceful beautiful end-of-day light",
            },
            {
                "text": "That night, {name} lay in bed carefully drawing a map of the Great Jungle on a piece of paper. {He_She} would need it for tomorrow. There was still so much of Zanzibar left to explore.",
                "scene": "a child lying in bed by warm lamplight, drawing a treasure map on paper with focused happy expression, cosy bedroom at night, the fluffy dog asleep on the floor below",
            },
        ],
    },
    "Bear & Me 🐻": {
        "tagline": "Big friends make the world feel smaller.",
        "theme": "Friendship 🤝",
        "pages": [
            {
                "text": "{name} lived at the edge of a cosy town where the garden ended and the forest began. Every morning, after breakfast, {he_she} would pull on {his_her} boots and go exploring. {He_She} never knew what {he_she} might find.",
                "scene": "a child in bright yellow boots stepping through a garden gate onto a sunlit forest path, morning light filtering through tall trees, a cosy cottage visible behind, sense of adventure and possibility",
            },
            {
                "text": "That morning, through the silver birch trees, {name} spotted something large and brown and very still. A bear — a big, gentle bear — sat beneath a tree reading a small book with enormous concentration.",
                "scene": "a large friendly cartoon bear sitting against a birch tree in a sunlit forest, reading a tiny book with great seriousness, a child peering shyly through the trees watching with wide curious eyes",
            },
            {
                "text": "The bear's name was Barnaby, and his kitchen was the warmest, stickiest, most wonderful place {name} had ever been. Together they baked honey cakes and made a truly glorious mess.",
                "scene": "a child and a large friendly bear baking together in a cosy woodland kitchen, both covered in flour and honey and laughing, warm golden light, kitchen shelves lined with honey jars",
            },
            {
                "text": "Later, Barnaby led {name} to a sparkling stream and placed a small fishing rod in {his_her} hands. 'Patience,' said Barnaby, 'is the most important thing.' {name} tried very, very hard to be patient.",
                "scene": "a child and a large friendly bear sitting side by side on the bank of a sparkling woodland stream, both holding fishing rods, peaceful dappled light through trees, reflections in the water",
            },
            {
                "text": "{name} decided to help carry Barnaby's enormous honey pot all the way back to the cottage. {He_She} took one handle and Barnaby took the other — but the ground was lumpy, and down they both went with a wonderful THUMP.",
                "scene": "a child and a large bear tumbling over together in a forest clearing, a large honey pot tipped on its side, honey splashed on both of them, laughing expressions, warm sunny forest",
            },
            {
                "text": "Barnaby laughed until his big round tummy shook like a hill in an earthquake. {name} laughed until {he_she} had to sit down. Then together they picked up every drop and solved the problem perfectly.",
                "scene": "a child and a bear sitting in sunshine laughing together, both covered in honey, the honey pot safely righted between them, warm forest clearing, completely happy expressions",
            },
            {
                "text": "As the afternoon light turned golden, Barnaby made a soft, deep nest of autumn leaves in a sunny spot and tucked {name} in very gently. The leaves smelled of cinnamon. {He_She} closed {his_her} eyes.",
                "scene": "a large gentle bear carefully tucking a sleepy child into a cosy pile of golden autumn leaves in a sunlit forest clearing, tender and warm scene, afternoon golden light",
            },
            {
                "text": "{name} woke up in {his_her} own bed, with {his_her} boots still on and a small honey-gold feather on the pillow. {He_She} smiled a very slow, very certain smile. It had been absolutely real.",
                "scene": "a child waking up in their cosy bedroom still wearing yellow boots, holding a golden feather up in a beam of morning sunlight, smiling with quiet certainty and joy",
            },
        ],
    },
    "Mermaid Adventure 🧜": {
        "tagline": "Dive into an underwater kingdom full of colour and wonder.",
        "theme": "Curiosity 🔍",
        "pages": [
            {
                "text": "{name} found the shell at the very end of a very long beach, just as the sun was melting into the sea. It was pink and spiralled and glowed like the inside of a dream. {He_She} pressed it gently to {his_her} ear.",
                "scene": "a child on a golden beach at sunset, holding a beautiful glowing pink spiral shell to their ear, the sea reflecting the golden sunset, warm orange and pink sky",
            },
            {
                "text": "The sea reached up and took {name}'s hand, and suddenly — without any fuss at all — {he_she} was underwater. Everything was blue and shimmering and full of a gentle music {he_she} could completely feel.",
                "scene": "a child floating gently underwater in glowing blue water, eyes wide with peaceful wonder, colourful fish and soft rays of light all around, magical shimmering underwater world",
            },
            {
                "text": "A mermaid appeared out of the light — graceful and laughing, with hair like swaying green seaweed and a tail like a thousand jewels. 'I've been waiting for you,' she said warmly. 'Come — I'll show you everything.'",
                "scene": "a beautiful friendly mermaid with a jewelled tail reaching out her hand to a child underwater, smiling warmly, glowing blue water background, tropical fish swimming past",
            },
            {
                "text": "They swam past castles built of coral, through curtains of light and colour, past dolphins who spun in circles just to say hello. {name} had never moved like this before — free and fast and light as thought.",
                "scene": "a child and a mermaid swimming joyfully together through a vibrant coral reef, playful dolphins spinning nearby, shafts of golden underwater sunlight, castle-like coral formations in every colour",
            },
            {
                "text": "Then they heard a small, sad sound. A baby seahorse floated alone, turning in slow circles, its tiny face crumpled with worry. 'It's lost,' said the mermaid quietly. {name} felt {his_her} heart squeeze tight.",
                "scene": "a tiny sad baby seahorse floating alone in glowing blue water, looking lost and worried, a child and a friendly mermaid nearby looking at it with gentle concern",
            },
            {
                "text": "{name} followed a trail of glowing bubbles — up, around, through a rock arch and into a meadow of swaying sea-grass. And there was the seahorse's family, waiting and waving with delight.",
                "scene": "a child and mermaid watching joyfully as a tiny seahorse swims towards its happy waiting family in a beautiful sea-grass meadow, golden bubble trail visible, warm underwater light",
            },
            {
                "text": "The fish threw a party — there was no other word for it. They sang in bubbles, danced in spirals, and brought {name} a crown woven from the most luminous shells in the sea. {He_She} put it on and felt magnificent.",
                "scene": "a child wearing a beautiful shell crown surrounded by singing and dancing fish in a magical glowing underwater party, bubbles and light everywhere, joyful and festive underwater scene",
            },
            {
                "text": "{name} woke on the beach just as the first light touched the sea. The shell was warm in {his_her} hand, still faintly glowing. {He_She} held it up to the dawn and whispered thank you. The waves whispered gently back.",
                "scene": "a child sitting alone on a peaceful beach at dawn, holding a softly glowing shell up against the first pale light of morning, the calm sea in front of them, magical and serene",
            },
        ],
    },
    "Diwali Night 🪔": {
        "tagline": "The brightest night of the year — full of light, family, and love.",
        "theme": "Family & Joy 🏮",
        "pages": [
            {
                "text": "{name} had been counting the days to Diwali for a very long time indeed. Today was finally the day, and the whole house smelled of marigolds, ghee, and the very best kind of excitement.",
                "scene": "a child standing in a beautifully decorated Indian home at dusk, marigold garlands hanging, clay diyas unlit on the windowsill, warm golden light, expression of pure excitement, vibrant and colourful traditional home",
            },
            {
                "text": "Together with Mum, {name} rolled the wicks and filled each tiny diya with golden oil. {He_She} counted them carefully — there were twenty-seven. Every single one needed to shine.",
                "scene": "a child and parent sitting on the floor together, carefully filling small clay diyas with oil and placing cotton wicks, warm afternoon light, brass plates and flowers nearby, cosy Indian home",
            },
            {
                "text": "When the first diya was lit, something magical happened. The whole room seemed to breathe in — and then glow. {name} watched the tiny flame dance and felt something warm bloom in {his_her} chest.",
                "scene": "a child lighting the first clay diya with a long matchstick in a darkening room, the flame catching and casting warm golden light on the child's face, other diyas waiting nearby, magical glow",
            },
            {
                "text": "Nani arrived with a big box of mithai — barfi and ladoo and jalebi piled high. She pressed a ladoo straight into {name}'s mouth before {he_she} could even say hello. {He_She} didn't mind at all.",
                "scene": "an elderly grandmother arriving at the door carrying a large box of Indian sweets, a child reaching in with delighted expression, bright lights and decorations, warm family gathering",
            },
            {
                "text": "Outside, the lane had turned into something like a dream. Every doorstep glowed with diyas, every balcony with fairy lights. {name} held Nani's hand and walked very slowly, wanting to remember every single moment.",
                "scene": "a child walking hand in hand with an elderly grandmother along a lane lined with glowing diyas and fairy lights on Diwali night, neighbours at their doors, warm magical festive atmosphere",
            },
            {
                "text": "Then — BOOM! — the first firecracker burst into a shower of silver stars above the rooftops. {name} gasped and then burst out laughing. The sky was celebrating too.",
                "scene": "a child looking up at a burst of silver and gold fireworks above rooftops on Diwali night, expression of wonder and delight, warm glowing street below, family nearby",
            },
            {
                "text": "Back home, they sat on the rooftop together — Mum, Dad, Nani, and {name} — and watched the whole city sparkle. {name} felt so full of love {he_she} thought {he_she} might burst, just like a firecracker.",
                "scene": "a family sitting together on a rooftop at night watching Diwali fireworks, the city lit up below, warm and cosy together, the child leaning against a grandparent, sky full of colour",
            },
            {
                "text": "That night, {name} lay in bed with the smell of smoke and marigolds still in the air, and the warmth of the whole day still glowing inside {him_her}. Some nights, {he_she} thought, are made of pure gold.",
                "scene": "a child lying contentedly in bed at night, eyes just closing, the soft glow of a diya visible at the window, peaceful and happy, the room still warm with the magic of Diwali",
            },
        ],
    },
    "Nani's Kitchen 🍚": {
        "tagline": "The most magical place in the world smells like cardamom and love.",
        "theme": "Love & Belonging 💛",
        "pages": [
            {
                "text": "Every summer, {name} got to spend a whole week at Nani's house — and every summer, it felt like arriving somewhere {he_she} had always belonged. The moment the door opened, the whole house smelled like cardamom and love.",
                "scene": "a child arriving at a grandmother's traditional Indian home, the door opening to reveal warm light and an elderly woman with open arms, the child stepping inside joyfully, summer sunlight outside",
            },
            {
                "text": "Nani's kitchen was the heart of the house. It had brass vessels stacked to the ceiling, bundles of dried herbs, and a big wooden spoon that Nani said had been stirring things for fifty years. {name} believed her completely.",
                "scene": "a warm and colourful Indian grandmother's kitchen with brass vessels on shelves, dried herbs hanging, a large wooden spoon on the counter, cosy and full of character, warm golden light",
            },
            {
                "text": "'Today,' said Nani, tying an apron around {name}'s middle, 'you learn to make kheer.' {He_She} handed {name} the wooden spoon and pointed at the pot. 'You stir. Slowly. With love. That is the secret ingredient.'",
                "scene": "an elderly grandmother tying a small apron around a child in a kitchen, handing them a large wooden spoon, pointing at a pot on the stove, warm and affectionate expression, Indian kitchen setting",
            },
            {
                "text": "{name} stirred and stirred while Nani added milk, then rice, then three cardamom pods that she crushed between her fingers like magic. The kitchen filled with the most beautiful smell {name} had ever known.",
                "scene": "a child stirring a large pot on a stove while an elderly grandmother adds ingredients, cardamom pods and small bowls of sugar and saffron nearby, steam rising, cosy Indian kitchen, both smiling",
            },
            {
                "text": "But {name} stirred a little too enthusiastically, and a great wave of kheer leapt out of the pot and onto Nani's apron. There was a terrible moment of silence. Then Nani laughed — a huge, wonderful, rolling laugh.",
                "scene": "a child looking mortified as kheer (rice pudding) has splashed onto an elderly grandmother's apron, the grandmother laughing warmly with her head thrown back, the pot on the stove behind them",
            },
            {
                "text": "They ate the kheer on the rooftop as the sun went down, just the two of them, in bowls with silver spoons. It was, {name} decided, the most delicious thing {he_she} had ever tasted. Even with the spilling.",
                "scene": "a child and an elderly grandmother sitting together on a rooftop at sunset, eating from small silver bowls, warm golden light, comfortable and happy together, the city soft in the background",
            },
            {
                "text": "That evening, Nani taught {name} one more thing — how to make chai. There was ginger and milk and two spoons of sugar and Nani saying 'a little more, a little more' until it was exactly right.",
                "scene": "an elderly grandmother and a child standing at a stove making chai together, the grandmother guiding the child's hand, steam rising from the pot, warm kitchen light, jars of spices visible",
            },
            {
                "text": "When {name} went home at the end of the week, Nani pressed the old wooden spoon into {his_her} hands. 'So you remember,' she said. {name} held it all the way home. {He_She} did not need reminding.",
                "scene": "a child holding a large old wooden spoon and looking up at an elderly grandmother in a doorway, both with soft happy expressions, the grandmother's hand on the child's cheek, warm evening light",
            },
        ],
    },
    "Unicorn Magic 🦄": {
        "tagline": "Some friendships are truly magical.",
        "theme": "Kindness 💖",
        "pages": [
            {
                "text": "{name} had made exactly one hundred and two wishes on the big bright star outside {his_her} window. But {he_she} had never really, truly expected any of them to come true.",
                "scene": "a child kneeling at a bedroom window at night, gazing up at one very bright star in a dark starry sky, an expression of hopeful longing, moonlight across the bedroom, cosy and peaceful",
            },
            {
                "text": "Then, softly, {his_her} window filled with silver light. {name} held very still. Standing in the garden — patient and glowing and more beautiful than anything {he_she} had ever imagined — was a unicorn with a mane like moonlight.",
                "scene": "a magnificent white unicorn with a silver glowing mane standing in a moonlit garden below a child's window, looking up gently and calmly, magical silver light all around",
            },
            {
                "text": "They flew together through a sky full of clouds shaped like whales and elephants and one very round walrus. {name} laughed with the wind in {his_her} hair and felt completely, perfectly safe.",
                "scene": "a child riding a glowing white unicorn through a beautiful night sky, passing cloud shapes of a whale, an elephant, and a walrus, stars everywhere, the child laughing with pure joy",
            },
            {
                "text": "The unicorn landed in a meadow where flowers glowed like tiny lanterns and the butterflies sang quiet little songs just to themselves. {name} walked through it all and everything felt like the best kind of dream.",
                "scene": "a child and a white unicorn in a magical glowing night meadow, tiny lantern-like flowers all around, butterflies with softly glowing wings, moonlit and enchanted atmosphere",
            },
            {
                "text": "But then {name} saw her — a tiny fairy sitting on a mushroom, wings folded flat and dull, crying the smallest of tears. 'My wings,' she whispered. 'They've lost all their sparkle. I cannot fly anymore.'",
                "scene": "a tiny fairy sitting sadly on a large mushroom cap, her wings dull and flat, a child crouching gently at eye level looking at her with deep sympathy, moonlit magical meadow",
            },
            {
                "text": "{name} sat beside her and said the kindest, truest things {he_she} could think of. And when {he_she} reached out and held the fairy's tiny hand, something marvellous happened — the wings shimmered, glittered, and blazed back to life.",
                "scene": "a child gently holding a tiny fairy's hand, the fairy's wings suddenly blazing back to brilliant sparkle and colour, magical golden light spreading outward, joyful expression on the fairy's face",
            },
            {
                "text": "The unicorn carried {name} home through a sky that was slowly turning pink with dawn. {name} felt full — full of something {he_she} did not have quite the right word for, but that felt a great deal like joy.",
                "scene": "a child riding a white unicorn homeward through a sky turning beautiful pink and gold at dawn, peaceful and content expression, their home visible softly in the distance below",
            },
            {
                "text": "{name} climbed into bed and pulled the blanket up — and there on the pillow, glowing softly like a promise kept, was a single small flower from the meadow. {He_She} closed {his_her} eyes and smiled.",
                "scene": "a child's pillow in soft early morning light with a small glowing magical flower resting on it, the child tucked under a cosy blanket just visible at the edge, peaceful and magical",
            },
        ],
    },
}

# ==============================
# LANGUAGE CONFIG
# ==============================

LANGUAGES = {
    "English": {
        "prompt_lang": "English", "font_name": "Helvetica", "font_path": None,
        "use_sarvam": False,
        "persona": None,
        "template_only": False,
    },
    "Hindi (हिंदी)": {
        "prompt_lang": "Hindi", "font_name": "NotoDevanagari",
        "font_path": "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        # GPT-4o handles Hindi reasonably — persona prompt improves naturalness significantly
        "use_sarvam": False,
        "persona": (
            "Aap ek pyaari si Dadi hain jo apni choti naati/naatey ko sone se pehle pyaar se kahani suna rahi hain. "
            "Aap simple, rozmarra ki Hindi mein likhti hain — bilkul aise jaise ghar pe bol-chaal hoti hai. "
            "Koi literary ya kitabi Hindi nahi. Chote chote vaakya. Dil ko chhune waali zubaan."
        ),
        "template_only": True,
    },
    "Tamil (தமிழ்)": {
        "prompt_lang": "Tamil", "font_name": "NotoTamil",
        "font_path": "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
        # Sarvam AI gives significantly better Tamil quality than GPT-4o
        "use_sarvam": True,
        "persona": (
            "Neenga oru anbu paatti, thoonguvatharku mun ungal peran/petti'kku kadhai solkireenga. "
            "Saralaana, anbaana, veetu Tamil payanpaduttunga — literary Tamil alla. "
            "Kuruiya vaakiyangal. Illam pesa palavaam pola."
        ),
        "template_only": True,
    },
    "Malayalam (മലയാളം)": {
        "prompt_lang": "Malayalam", "font_name": "NotoMalayalam",
        "font_path": "/usr/share/fonts/truetype/noto/NotoSansMalayalam-Regular.ttf",
        # Sarvam AI gives significantly better Malayalam quality than GPT-4o
        "use_sarvam": True,
        "persona": (
            "Ningal oru snehamulla Ammachi aanu, uyakkathinu mun ningalude paerakuttikku kadha parayan. "
            "Lalikamaya, veettile samsaara bhasha upayogikkanam — formal Malayalam alla. "
            "Kuriya vaakyankal. Snaehavumaaya swaravum."
        ),
        "template_only": True,
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
    tc1, tc2, tc3, tc4, tc5 = st.columns(5)
    with tc1:
        t_name = st.text_input("Child's name", key="t_name", placeholder="e.g. Layla")
    with tc2:
        t_age = st.selectbox("Age", [3, 4, 5, 6, 7, 8], key="t_age")
    with tc3:
        t_gender = st.selectbox("Gender", ["Girl", "Boy"], key="t_gender")
    with tc4:
        t_lang = st.selectbox("Language", list(LANGUAGES.keys()), key="t_lang")
    with tc5:
        if LANGUAGES[t_lang].get("template_only"):
            st.markdown("")  # spacer
            st.caption("🇮🇳 Vernacular stories are template-only for now")

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

    st.markdown("### Visual style")
    t_style = st.radio(
        "Visual style",
        list(VISUAL_STYLES.keys()),
        horizontal=True,
        key="t_style",
        label_visibility="collapsed",
        captions=["Disney/Pixar 3D art", "Bold ink, flat colour"],
    )

    if st.session_state.attempt_count < MAX_ATTEMPTS:
        if st.button("✦ Preview My Story", key="btn_template", disabled=not t_name.strip()):
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
                "fav_colour": t_colour, "visual_style": t_style,
            }
            st.rerun()
    else:
        st.success("🎉 You've used all your story attempts!")

# ============================================================
# TAB 2 — CUSTOM MODE
# ============================================================

with tab_custom:
    st.markdown("### About the child")
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        c_name = st.text_input("Child's name", key="c_name", placeholder="e.g. Arjun")
    with cc2:
        c_age = st.selectbox("Age", [3, 4, 5, 6, 7, 8], key="c_age")
    with cc3:
        c_gender = st.selectbox("Gender", ["Girl", "Boy"], key="c_gender")
    c_lang = "English"  # Vernacular for custom stories coming soon
    st.caption("🌐 Custom stories are in English. Hindi / Tamil / Malayalam coming soon for custom mode.")

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

    st.markdown("### Visual style")
    c_style = st.radio(
        "Visual style",
        list(VISUAL_STYLES.keys()),
        horizontal=True,
        key="c_style",
        label_visibility="collapsed",
        captions=["Disney/Pixar 3D art", "Bold ink, flat colour"],
    )

    if st.session_state.attempt_count < MAX_ATTEMPTS:
        if st.button("✦ Preview My Story", key="btn_custom", disabled=not c_name.strip()):
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
                "freewrite": c_freewrite, "visual_style": c_style,
            }
            st.rerun()
    else:
        st.success("🎉 You've used all your story attempts!")

# ============================================================
# STORY GENERATION — 3-phase: preview → confirm → finalise
# ============================================================

if "_mode" not in st.session_state:
    st.stop()

mode   = st.session_state["_mode"]
p      = st.session_state["_params"]
memory = st.session_state.character_memory
prompt_lang = LANGUAGES[p["language"]]["prompt_lang"]

# ==============================
# BUILD STORY PROMPT (custom mode only — templates use pre-baked pages)
# ==============================

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
# HELPERS
# ==============================

def parse_story(raw):
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', raw)
    for pattern in [
        re.compile(r'Page\s*\d+[:\.]?\s*\n+\s*Text:\s*(.*?)\s*\n+\s*Scene:\s*(.*?)(?=\n+\s*Page\s*\d+|\Z)', re.DOTALL | re.IGNORECASE),
        re.compile(r'Text:\s*(.*?)\s*\nScene:\s*(.*?)(?=\nText:|\Z)', re.DOTALL | re.IGNORECASE),
    ]:
        matches = pattern.findall(text)
        pages = [{"text": t.strip(), "scene": s.strip()} for t, s in matches if t.strip() and s.strip() and len(s.strip()) >= 10]
        if len(pages) >= 3:
            return pages
    return []


def _age_complexity_guide(age):
    """Return age-appropriate sentence complexity guidance."""
    if age <= 4:
        return (
            "Write VERY short, simple sentences — maximum 8 words each. "
            "Use only the most basic everyday vocabulary a toddler knows. "
            "Repeat key words warmly. Think: board book simplicity."
        )
    elif age <= 6:
        return (
            "Write short, simple sentences — maximum 12 words each. "
            "Use warm, everyday vocabulary. Simple cause-and-effect. "
            "Think: early reader picture book."
        )
    else:
        return (
            "Write warm, engaging sentences. Up to 20 words. "
            "Can include gentle humour and richer description. "
            "Think: classic children's illustrated chapter book."
        )


def _generate_vernacular_page(scene, name, gender, age, lang_key, page_number):
    """
    Generate one story page natively in the target language from a scene description.
    Uses Sarvam AI for Tamil/Malayalam, GPT-4o for Hindi.
    This produces natural, age-appropriate vernacular — not a translation.
    """
    lang_cfg = LANGUAGES[lang_key]
    prompt_lang = lang_cfg["prompt_lang"]
    persona = lang_cfg.get("persona", "")
    age_guide = _age_complexity_guide(age)
    pronoun_hint = "girl / she / her" if gender == "Girl" else "boy / he / him"

    prompt = f"""You are a beloved children's storybook author. {persona}

Write 2–3 warm, lyrical sentences in {prompt_lang} for page {page_number} of a children's storybook.

Story context:
- Main character: {name} (a {age}-year-old {pronoun_hint})
- Scene to illustrate: {scene}

Writing rules:
- {age_guide}
- Write ONLY in {prompt_lang} — no English words except the name '{name}'
- Keep the name '{name}' exactly as written
- Warm, loving, bedtime-story tone
- No bold, no asterisks, no punctuation other than . , ! ?
- Return ONLY the story text. Nothing else."""

    # Route to Sarvam for Tamil/Malayalam (better script quality)
    if lang_cfg.get("use_sarvam") and sarvam_client:
        try:
            r = sarvam_client.chat.completions.create(
                model="sarvam-m",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.75,
                max_tokens=200,
            )
            text = r.choices[0].message.content.strip()
            if text:
                return text
        except Exception:
            pass  # Fall through to GPT-4o

    # GPT-4o for Hindi (and Sarvam fallback)
    for model in ["gpt-4o", "gpt-4o-mini"]:
        try:
            r = openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.75,
                max_tokens=200,
            )
            text = r.choices[0].message.content.strip()
            if text:
                return text
        except Exception as e:
            if "PermissionDenied" in type(e).__name__ or "permission" in str(e).lower():
                continue
            break
    return None


def build_template_pages(p, prompt_lang):
    """
    Template mode:
    - English: substitute {name}/{pronoun} placeholders in pre-baked pages (instant, no API call)
    - Vernacular: generate each page natively from scene description (not translated)
    """
    t = TEMPLATES[p["template_name"]]
    if p["gender"] == "Girl":
        pronouns = {"He_She": "She", "he_she": "she", "His_Her": "Her", "his_her": "her", "Him_Her": "Her", "him_her": "her"}
    else:
        pronouns = {"He_She": "He", "he_she": "he", "His_Her": "His", "his_her": "his", "Him_Her": "Him", "him_her": "him"}

    pages = []
    for pg in t["pages"]:
        text = pg["text"].replace("{name}", p["name"])
        for key, val in pronouns.items():
            text = text.replace("{" + key + "}", val)
        pages.append({"text": text, "scene": pg["scene"]})

    if prompt_lang == "English":
        return pages

    # Vernacular: generate each page natively from scene description
    lang_key = p["language"]
    for i, pg in enumerate(pages):
        native = _generate_vernacular_page(
            pg["scene"], p["name"], p["gender"], p["age"],
            lang_key, page_number=i + 1,
        )
        if native:
            pg["text"] = native
        # If generation fails for a page, keep the English text as fallback

    return pages


def gen_story_text():
    prompt = build_custom_prompt(p, memory)
    for model in ["gpt-4o", "gpt-4o-mini"]:
        try:
            resp = openai_client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}], temperature=0.85,
            )
            return resp.choices[0].message.content
        except Exception as e:
            if "PermissionDenied" in type(e).__name__ or "permission" in str(e).lower():
                continue
            raise
    return None


def save_image(img_bytes, index):
    path = f"/tmp/page_{index}.png"
    with open(path, "wb") as f:
        f.write(img_bytes)
    return path


# ==============================
# IMAGE GENERATION
# ==============================

fav_colour = p.get("fav_colour", "")

# ==============================
# CHARACTER REFERENCE (phase 1a — before page generation)
# ==============================

def generate_character_reference(memory, age, gender, fav_colour, visual_style="🎨 Illustrated Storybook"):
    """
    Generate one canonical character-sheet image, then use GPT-4o vision
    to extract an ultra-precise description. All page images use this
    anchored description for visual consistency.
    """
    style_cfg = VISUAL_STYLES.get(visual_style, VISUAL_STYLES["🎨 Illustrated Storybook"])
    colour_note = f"wearing a {fav_colour} coloured outfit," if fav_colour else ""
    colour_emphasis = f" IMPORTANT: the child's outfit must be {fav_colour} coloured." if fav_colour else ""
    ref_prompt = (
        f"Children's book character reference sheet: a {age} year old {gender.lower()} child, "
        f"{memory}, {colour_note} "
        f"front-facing, neutral friendly smile, full body view, plain white background, "
        f"{style_cfg['ref_style']}, no text.{colour_emphasis}"
    )

    # Generate reference image — Nano Banana Pro's thinking process is ideal here
    ref_bytes = (
        _dalle3(ref_prompt)
        or _nano_banana_pro(ref_prompt)
        or _qwen(ref_prompt)
        or _nano_banana2(ref_prompt)
    )
    if not ref_bytes:
        return memory   # fallback: use original description

    # Save reference image
    ref_path = "/tmp/character_ref.png"
    with open(ref_path, "wb") as f:
        f.write(ref_bytes)

    # Ask GPT-4o vision for a precise appearance description
    try:
        b64 = base64.b64encode(ref_bytes).decode()
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": (
                    "Describe this illustrated child character's appearance with maximum precision for an artist to reproduce exactly. "
                    "Include: exact hair colour, style and length; skin tone; eye colour; outfit (colour, style, every detail); "
                    "any accessories. Under 40 words. No names."
                )},
            ],
        }]
        for model in ["gpt-4o", "gpt-4o-mini"]:
            try:
                r = openai_client.chat.completions.create(model=model, messages=messages, max_tokens=100)
                desc = r.choices[0].message.content.strip()
                # Always enforce the requested outfit colour — image generators don't always obey
                if fav_colour and fav_colour.lower() not in desc.lower():
                    desc = re.sub(
                        r'\b(red|blue|yellow|pink|purple|orange|white|black|brown|grey|gray|teal|navy|maroon|beige|gold|silver|green|cyan|violet)\b(\s+\w+)?\s+(outfit|shirt|dress|top|jacket|clothes|jumper|t-shirt)',
                        f'{fav_colour} outfit',
                        desc, flags=re.IGNORECASE,
                    )
                    if fav_colour.lower() not in desc.lower():
                        desc += f", wearing {fav_colour} outfit"
                return desc
            except Exception as e:
                if "PermissionDenied" in type(e).__name__ or "permission" in str(e).lower():
                    continue
                break
    except Exception:
        pass

    # Fallback: original description + colour guarantee
    base = memory
    if fav_colour and fav_colour.lower() not in base.lower():
        base += f", wearing {fav_colour} outfit"
    return base


# ==============================
# VISUAL STYLES
# ==============================

VISUAL_STYLES = {
    "🎨 Illustrated Storybook": {
        "label": "Illustrated Storybook",
        "image_style": (
            "vibrant children's book illustration, 3D cartoon style, "
            "bright saturated colors, Disney and Pixar inspired art, "
            "clean professional illustration, expressive cute characters, "
            "rich detailed colorful background, warm cheerful lighting, "
            "high quality digital art, playful and charming"
        ),
        "ref_style": "vibrant 3D cartoon style, Disney/Pixar inspired, high detail",
        "negative": (
            "deformed hands, extra fingers, missing fingers, bad anatomy, "
            "deformed feet, ugly hands, fused fingers, mutated hands, "
            "photorealistic, dark, scary, text, watermark, blurry, deformed, ugly, low quality, sketch, grayscale"
        ),
        "pdf_panel_border": False,
    },
    "📰 Comic Strip": {
        "label": "Comic Strip",
        "image_style": (
            "children's comic book panel illustration, bold clean ink outlines, "
            "flat vibrant colours, Tintin and Asterix and Beano inspired, "
            "expressive cartoon faces, dynamic composition, bright cheerful comic art, "
            "clear panel framing, no speech bubbles, no text in image"
        ),
        "ref_style": "children's comic book style, bold ink outlines, flat bright colours, Tintin/Asterix inspired",
        "negative": (
            "photorealistic, 3D render, blurry, deformed, ugly, dark, scary, "
            "text, watermark, speech bubbles, low quality, extra fingers, bad anatomy"
        ),
        "pdf_panel_border": True,
    },
}

# ==============================
# IMAGE PROMPT BUILDER
# ==============================

def build_image_prompt(scene, anchored_memory, age, gender, fav_colour, visual_style="🎨 Illustrated Storybook"):
    style_cfg = VISUAL_STYLES.get(visual_style, VISUAL_STYLES["🎨 Illustrated Storybook"])
    colour_instruction = (
        f"wearing a {fav_colour} outfit — outfit colour is {fav_colour}, this is mandatory,"
        if fav_colour else ""
    )
    character = (
        f"a {age} year old {gender.lower()} child, {anchored_memory}, {colour_instruction} "
        f"exact same character design on every page"
    )
    framing = "medium shot or wide shot, full scene visible, no extreme close-ups of hands or feet"
    return f"{character}, {scene}, {framing}, {style_cfg['image_style']}", style_cfg["negative"]


# ==============================
# IMAGE GENERATORS
# ==============================

def _dalle3(prompt_text):
    """DALL-E 3 — best anatomy, ~$0.04/image."""
    try:
        resp = openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt_text[:4000],   # DALL-E 3 prompt limit
            size="1792x1024",
            quality="standard",
            n=1,
        )
        url = resp.data[0].url
        r = requests.get(url, timeout=60)
        if r.status_code == 200 and len(r.content) > 5000:
            return r.content
    except Exception:
        pass
    return None


def _qwen(prompt_text):
    """Alibaba Qwen Wanx image generation via DashScope."""
    if not DASHSCOPE_API_KEY:
        return None
    try:
        import dashscope
        from dashscope import ImageSynthesis
        dashscope.api_key = DASHSCOPE_API_KEY
        rsp = ImageSynthesis.call(
            model="wanx2.1-t2i-turbo",
            prompt=prompt_text[:800],
            n=1,
            size="1280*720",
        )
        if rsp.status_code == 200 and rsp.output.results:
            url = rsp.output.results[0].url
            r = requests.get(url, timeout=60)
            if r.status_code == 200 and len(r.content) > 5000:
                return r.content
    except Exception:
        pass
    return None


def _nano_banana_pro(prompt_text):
    """Nano Banana Pro (gemini-3-pro-image-preview) — thinking model, best quality for reference sheets."""
    if not google_client:
        return None
    try:
        interaction = google_client.interactions.create(
            model="gemini-3-pro-image-preview",
            input=prompt_text[:4000],
        )
        if interaction.output_image and interaction.output_image.data:
            return base64.b64decode(interaction.output_image.data)
    except Exception:
        pass
    return None


def _nano_banana2(prompt_text):
    """Nano Banana 2 (gemini-3.1-flash-image-preview) — fast, high quality for page illustrations."""
    if not google_client:
        return None
    try:
        interaction = google_client.interactions.create(
            model="gemini-3.1-flash-image-preview",
            input=prompt_text[:4000],
        )
        if interaction.output_image and interaction.output_image.data:
            return base64.b64decode(interaction.output_image.data)
    except Exception:
        pass
    return None


def _nano_banana_fast(prompt_text):
    """Nano Banana (gemini-2.5-flash-image) — speed fallback, low latency."""
    if not google_client:
        return None
    try:
        interaction = google_client.interactions.create(
            model="gemini-2.5-flash-image",
            input=prompt_text[:4000],
        )
        if interaction.output_image and interaction.output_image.data:
            return base64.b64decode(interaction.output_image.data)
    except Exception:
        pass
    return None


def _hf(prompt_text, negative):
    if not HF_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt_text, "parameters": {
        "negative_prompt": negative, "width": 768, "height": 512,
        "num_inference_steps": 30, "guidance_scale": 7.5,
    }}
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


def get_image(scene, anchored_memory, age, gender, fav_colour, visual_style="🎨 Illustrated Storybook"):
    """Fallback chain: DALL-E 3 → Qwen → Nano Banana 2 → Nano Banana Fast → SDXL → Pollinations."""
    prompt_text, negative = build_image_prompt(scene, anchored_memory, age, gender, fav_colour, visual_style)

    img = (
        _dalle3(prompt_text)
        or _qwen(prompt_text)
        or _nano_banana2(prompt_text)
        or _nano_banana_fast(prompt_text)
        or _hf(prompt_text, negative)
    )
    if img:
        return img

    # Pollinations with retries
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
    return None


name         = p["name"]
age          = p["age"]
gender       = p["gender"]
language     = p["language"]
visual_style = p.get("visual_style", "🎨 Illustrated Storybook")
theme_display = TEMPLATES[p["template_name"]]["theme"] if mode == "template" else p.get("theme", "")

PREVIEW_PAGES = 2   # number of pages illustrated in preview

# ==============================
# PDF BUILDER
# ==============================

def create_pdf(pages, name, theme, language, visual_style="🎨 Illustrated Storybook"):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors as rl_colors

    file_path = "/tmp/storybook.pdf"
    is_comic = VISUAL_STYLES.get(visual_style, {}).get("pdf_panel_border", False)

    doc = SimpleDocTemplate(file_path, pagesize=A5,
                            leftMargin=0.55*inch, rightMargin=0.55*inch,
                            topMargin=0.55*inch, bottomMargin=0.55*inch)
    font_name = font_registry.get(language, "Helvetica")

    if is_comic:
        title_style    = ParagraphStyle("Title",    fontName=font_name, fontSize=22, alignment=TA_CENTER, spaceAfter=8,  leading=30, textColor=(0.05, 0.05, 0.05))
        subtitle_style = ParagraphStyle("Subtitle", fontName=font_name, fontSize=12, alignment=TA_CENTER, textColor=(0.2, 0.2, 0.2), leading=18)
        body_style     = ParagraphStyle("Body",     fontName=font_name, fontSize=12, alignment=TA_CENTER, leading=20, spaceAfter=6, textColor=(0.1, 0.1, 0.1))
    else:
        title_style    = ParagraphStyle("Title",    fontName=font_name, fontSize=22, alignment=TA_CENTER, spaceAfter=8,  leading=30)
        subtitle_style = ParagraphStyle("Subtitle", fontName=font_name, fontSize=12, alignment=TA_CENTER, textColor=(0.55, 0.35, 0.15), leading=18)
        body_style     = ParagraphStyle("Body",     fontName=font_name, fontSize=13, alignment=TA_CENTER, leading=22, spaceAfter=6)

    elements = [
        Spacer(1, 1.4*inch),
        Paragraph(f"{name}'s Magical Story", title_style),
        Spacer(1, 0.2*inch),
        Paragraph(theme, subtitle_style),
        PageBreak(),
    ]

    for page in pages:
        if page.get("image_path") and os.path.exists(page["image_path"]):
            img_elem = Image(page["image_path"], width=4.3*inch, height=3.2*inch)
            if is_comic:
                # Wrap in a black-bordered panel frame
                panel = Table([[img_elem]], colWidths=[4.3*inch])
                panel.setStyle(TableStyle([
                    ('BOX',        (0, 0), (-1, -1), 2.5, rl_colors.black),
                    ('BACKGROUND', (0, 0), (-1, -1), rl_colors.white),
                    ('TOPPADDING',    (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                    ('LEFTPADDING',   (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
                ]))
                elements.append(panel)
            else:
                elements.append(img_elem)
            elements.append(Spacer(1, 0.15*inch))
        elements.append(Paragraph(page["text"], body_style))
        elements.append(PageBreak())

    doc.build(elements)
    return file_path


# ==============================
# PHASE 1 — GENERATE PREVIEW
# ==============================

if not st.session_state.get("_preview_done"):
    prog = st.progress(0, text="Weaving the story...")

    if mode == "template":
        # Pre-baked: no GPT story call needed (instant for English, one translation call for vernacular)
        pages = build_template_pages(p, prompt_lang)
        if not pages:
            st.error("Could not load story template. Please try again.")
            del st.session_state["_mode"]
            st.stop()
    else:
        story_text = gen_story_text()
        if not story_text:
            st.error("Could not generate story. Check your OpenAI API key.")
            st.stop()
        pages = parse_story(story_text)
        if not pages:
            st.error("Story format was unexpected. Please try again.")
            del st.session_state["_mode"]
            st.stop()

    # Generate character reference image for visual consistency
    prog.progress(15, text="Creating character reference for consistency...")
    anchored_memory = generate_character_reference(memory, age, gender, fav_colour, visual_style)
    st.session_state["_anchored_memory"] = anchored_memory

    prog.progress(25, text=f"Story written! Illustrating first {PREVIEW_PAGES} pages for preview...")

    for i in range(min(PREVIEW_PAGES, len(pages))):
        prog.progress(25 + int((i + 1) / PREVIEW_PAGES * 70), text=f"Illustrating preview page {i+1}...")
        img = get_image(pages[i]["scene"], anchored_memory, age, gender, fav_colour, visual_style)
        pages[i]["image_path"] = save_image(img, i) if img else None

    prog.progress(100, text="Preview ready!")
    prog.empty()

    st.session_state["_preview_done"] = True
    st.session_state["_preview_pages"] = pages
    st.rerun()


# ==============================
# PHASE 2 — SHOW PREVIEW + CONFIRM
# ==============================

if st.session_state.get("_preview_done") and not st.session_state.get("_finalize"):
    pages = st.session_state["_preview_pages"]

    st.markdown('<div class="ornament">✦ ❧ ✦</div>', unsafe_allow_html=True)
    st.markdown(f"## 👀 Preview — {name}'s Story")
    st.caption("First 2 pages are fully illustrated. Read all 8 pages below to check the story direction.")

    for i, page in enumerate(pages):
        if i < PREVIEW_PAGES and page.get("image_path") and os.path.exists(page["image_path"]):
            st.image(page["image_path"], use_container_width=True)
        elif i >= PREVIEW_PAGES:
            st.markdown(
                f'<div style="background:#f3ece0;border:1px dashed #c9a96e;border-radius:6px;'
                f'padding:10px;text-align:center;color:#a08060;font-style:italic;margin-bottom:6px;">'
                f'🖼️ Illustration will be generated when you finalise</div>',
                unsafe_allow_html=True,
            )
        st.markdown(f'<div class="story-card">{page["text"]}</div>', unsafe_allow_html=True)

    st.markdown('<div class="ornament">✦ ❧ ✦</div>', unsafe_allow_html=True)
    st.markdown("### What would you like to do?")

    btn1, btn2 = st.columns(2)
    with btn1:
        if st.button("✦ Looks great! Create Full Storybook"):
            st.session_state["_finalize"] = True
            st.rerun()
    with btn2:
        remaining = MAX_ATTEMPTS - st.session_state.attempt_count
        if remaining > 0:
            if st.button(f"🔁 Try a different version ({remaining} left)"):
                # Keep _mode and _params, just reset preview so we regenerate
                del st.session_state["_preview_done"]
                del st.session_state["_preview_pages"]
                st.session_state.attempt_count += 1
                st.rerun()
        else:
            st.caption("No more preview attempts — please finalise this version.")

    st.stop()


# ==============================
# PHASE 3 — FINALISE (remaining images + PDF)
# ==============================

pages = st.session_state["_preview_pages"]
anchored_memory = st.session_state.get("_anchored_memory", memory)

prog = st.progress(0, text="Generating remaining illustrations...")
remaining_indices = [i for i in range(len(pages)) if i >= PREVIEW_PAGES or not pages[i].get("image_path")]

for step, i in enumerate(remaining_indices):
    pct = int((step + 1) / max(len(remaining_indices), 1) * 85)
    prog.progress(pct, text=f"Illustrating page {i+1} of {len(pages)}...")
    img = get_image(pages[i]["scene"], anchored_memory, age, gender, fav_colour, visual_style)
    pages[i]["image_path"] = save_image(img, i) if img else None

prog.progress(90, text="Binding your storybook...")
pdf_path = create_pdf(pages, name, theme_display, language, visual_style)
prog.progress(100, text="Your storybook is ready!")
prog.empty()

# ==============================
# FINAL DISPLAY
# ==============================

st.markdown('<div class="ornament">✦ ❧ ✦</div>', unsafe_allow_html=True)
st.markdown(f"## 📖 {name}'s Storybook")

for page in pages:
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
