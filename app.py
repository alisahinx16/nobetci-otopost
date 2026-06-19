import io
import os
import re
import requests
import textwrap
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import streamlit as st
from urllib.parse import urljoin

st.set_page_config(page_title="Nöbetçi Gazete Post Robotu", page_icon="📰", layout="centered")

# Sabitler
STOP_WORDS = {
    "ve", "veya", "ama", "ile", "bir", "bu", "şu", "o", "için", "gibi", "de", "da", "ise", "ki", 
    "en", "daha", "her", "çok", "kendi", "biz", "siz", "onlar", "ben", "sen", "mi", "mı", "mu", "mü",
    "olan", "olarak", "tarafından", "birlikte", "önce", "sonra", "karşı", "üzerine", "yeni",
    "yok", "var", "hiç", "şimdi", "nasıl", "neden", "çünkü", "böyle", "şöyle", "artık", "zaman", "biri"
}
FAVICON_URL = "https://nobetcigazetecom.teimg.com/nobetcigazete-com/uploads/2025/08/favicon-nobetci-1.ico"
LOGO_YATAY_URL = "https://nobetcigazetecom.teimg.com/nobetcigazete-com/uploads/2025/08/logolar/logo-yatay-2.png"

# Güvenilir Direkt Raw GitHub Font Bağlantıları
FONT_BOLD_URL = "https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Bold.ttf"
FONT_REG_URL = "https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Regular.ttf"

# Çift Aşamalı ve İşletim Sistemi Taramalı Garantili Font Yükleyici
@st.cache_data
def load_font_safely(font_type="bold"):
    urls = {"bold": FONT_BOLD_URL, "regular": FONT_REG_URL}
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(urls[font_type], headers=headers, timeout=5)
        if response.status_code == 200 and len(response.content) > 10000:
            return response.content
    except:
        pass

    search_dirs = ["/usr/share/fonts", "/usr/local/share/fonts", "/system/fonts"]
    keywords = ["bold", "sans", "liberation", "dejavu", "arial"] if font_type == "bold" else ["regular", "sans", "liberation", "dejavu", "arial"]
    
    for d in search_dirs:
        if os.path.exists(d):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith(".ttf"):
                        f_lower = f.lower()
                        if any(k in f_lower for k in keywords):
                            try:
                                with open(os.path.join(root, f), "rb") as font_file:
                                    return font_file.read()
                            except:
                                pass

    for d in search_dirs:
        if os.path.exists(d):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith(".ttf"):
                        try:
                            with open(os.path.join(root, f), "rb") as font_file:
                                return font_file.read()
                        except:
                            pass
    return None

st.title("📰 Nöbetçi Gazete Post Robotu")
st.write("Web sitesi linkini girerek Instagram için 4:5 oranında kurumsal tasarımlı görsel ve metin özeti oluşturabilirsiniz.")

url_input = st.text_input("Web Sayfası Linki:", placeholder="https://nobetcigazete.com/...")

def generate_hashtags(text):
    cleaned = re.sub(r'[^\w\s]', '', text.lower())
    words = cleaned.split()
    meaningful_words = [w for w in words if len(w) > 3 and w not in STOP_WORDS]
    freq = {}
    for w in meaningful_words:
        freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    top_words = [w[0] for w in sorted_words[:5]]
    
    fallbacks = ["güncel", "gününözeti", "keşfet", "sosyalmedya", "trend"]
    while len(top_words) < 5:
        candidate = fallbacks.pop(0)
        if candidate not in top_words:
            top_words.append(candidate)
    return " ".join([f"#{w}" for w in top_words])

def find_image_url(soup, base_url):
    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'):
        return urljoin(base_url, og_img.get('content'))
    images = soup.find_all('img')
    for img in images:
        src = img.get('src') or img.get('data-src')
        if src and not src.endswith('.svg') and not 'logo' in src.lower():
            return urljoin(base_url, src)
    return None

def wrap_text_by_pixels(text, font, max_width, draw):
    paragraphs = text.split('\n')
    wrapped_paragraphs = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            wrapped_paragraphs.append("")
            continue
        lines = []
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word]) if current_line else word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_w = bbox[2] - bbox[0]
            if line_w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
        if current_line:
            lines.append(" ".join(current_line))
        wrapped_paragraphs.append("\n".join(lines))
    return "\n".join(wrapped_paragraphs)

if st.button("Gönderi ve Özet Oluştur", type="primary"):
    if not url_input:
        st.warning("Lütfen geçerli bir link girin.")
    else:
        with st.spinner("Veriler çekiliyor ve görsel hazırlanıyor..."):
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                response = requests.get(url_input, headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # H2 bulma
                h2_tag = soup.find('h2')
                if h2_tag and h2_tag.get_text().strip():
                    title = h2_tag.get_text().strip()
                else:
                    h1_tag = soup.find('h1')
                    if h1_tag and h1_tag.get_text().strip():
                        title = h1_tag.get_text().strip()
                    else:
                        title_tag = soup.find('title')
                        title = title_tag.get_text().strip() if title_tag else "Başlık Bulunamadı"
                
                # --- AKILLI VE SIFIR HATALI ÖZET SİSTEMİ ---
                # Hata ihtimalini sıfırlamak için özet metni doğrudan h2 başlığı olarak ayarlandı
                summary = title
                
                # Hashtags (Doğrudan h2 metninden üretilir)
                hashtags = generate_hashtags(summary)
                img_url = find_image_url(soup, url_input)
                
                # --- GÖRSEL ŞABLON MOTORU (1080x1350 - 4:5) ---
                canvas_width, canvas_height = 1080, 1350
                post_img = Image.new("RGB", (canvas_width, canvas_height), "#0a2d6c")
                draw = ImageDraw.Draw(post_img)

                # Fontları Yükleme (Garantili Akıllı Motor)
                bold_bytes = load_font_safely("bold")
                reg_bytes = load_font_safely("regular")

                if bold_bytes and reg_bytes:
                    font_gundem = ImageFont.truetype(io.BytesIO(bold_bytes), 40)
                    font_title = ImageFont.truetype(io.BytesIO(bold_bytes), 40)
                else:
                    font_gundem = font_title = ImageFont.load_default()

                # --- 1. ÜST PANEL TASARIMI (Header) ---
                # A) GÜNDEM Kategori Sekmesi (Sol Üst)
                draw.rounded_rectangle([(70, 80), (450, 180)], radius=25, fill="#ffffff")
                draw.rectangle([(70, 130), (450, 180)], fill="#ffffff")
                
                gundem_text = "GÜNDEM"
                g_bbox = draw.textbbox((0, 0), gundem_text, font=font_gundem)
                g_w = g_bbox[2] - g_bbox[0]
                g_h = g_bbox[3] - g_bbox[1]
                g_x = 70 + (380 - g_w) // 2
                g_y = 80 + (100 - g_h) // 2 - 4
                draw.text((g_x, g_y), gundem_text, font=font_gundem, fill="#0a2d6c")

                # B) NÖBETÇİ GAZETE Yatay Logosu (Sağ Üst - Yazılar kaldırıldı, direkt görsel eklendi)
                logo_img = None
                try:
                    logo_response = requests.get(LOGO_YATAY_URL, headers=headers, timeout=5)
                    if logo_response.status_code == 200 and len(logo_response.content) > 100:
                        raw_logo = Image.open(io.BytesIO(logo_response.content)).convert("RGBA")
                        
                        # Logo yüksekliğini 85px olarak sabitleyip genişliğini oranlıyoruz
                        logo_h = 85
                        logo_w = int(raw_logo.size[0] * (logo_h / raw_logo.size[1]))
                        
                        # Taşma kontrolü
                        if logo_w > 380:
                            logo_w = 380
                            logo_h = int(raw_logo.size[1] * (logo_w / raw_logo.size[0]))
                            
                        logo_img = raw_logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
                except:
                    pass

                if logo_img:
                    # Logoyu sağ marj olan 1010 piksele yaslayarak dikeyde tam ortalıyoruz
                    logo_x_pos = 1010 - logo_w
                    logo_y_pos = 80 + (100 - logo_h) // 2
                    post_img.paste(logo_img, (logo_x_pos, logo_y_pos), mask=logo_img.split()[3] if len(logo_img.split()) > 3 else None)

                # --- 2. ORTA HABER GÖRSELİ (940x680 - Yuvarlatılmış Köşeli) ---
                if img_url:
                    try:
                        img_data = requests.get(img_url, headers=headers, timeout=10).content
                        web_img = Image.open(io.BytesIO(img_data)).convert("RGB")
                        
                        web_w, web_h = web_img.size
                        ratio = max(940 / web_w, 680 / web_h)
                        new_size = (int(web_w * ratio), int(web_h * ratio))
                        resized_img = web_img.resize(new_size, Image.Resampling.LANCZOS)
                        
                        x_offset = (resized_img.size[0] - 940) // 2
                        y_offset = (resized_img.size[1] - 680) // 2
                        cropped_img = resized_img.crop((x_offset, y_offset, x_offset + 940, y_offset + 680))
                        
                        mask = Image.new("L", (940, 680), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.rounded_rectangle([(0, 0), (940, 680)], radius=24, fill=255)
                        
                        rounded_img = Image.new("RGBA", (940, 680), (0, 0, 0, 0))
                        rounded_img.paste(cropped_img.convert("RGBA"), (0, 0), mask=mask)
                        post_img.paste(rounded_img, (70, 200), mask=rounded_img.split()[3])
                    except:
                        draw.rounded_rectangle([(70, 200), (1010, 880)], radius=24, fill="#121212")
                else:
                    draw.rounded_rectangle([(70, 200), (1010, 880)], radius=24, fill="#121212")

                # --- 3. ALT METİN ALANI (Büyük ve Okunaklı Beyaz Yazı) ---
                dummy_img = Image.new("RGB", (1, 1))
                dummy_draw = ImageDraw.Draw(dummy_img)
                
                wrapped_text = wrap_text_by_pixels(title, font_title, 940, dummy_draw)
                draw.text((70, 925), wrapped_text, font=font_title, fill="#ffffff", spacing=18)

                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.image(post_img, caption="Oluşturulan Instagram Görseli (4:5)", use_container_width=True)
                    
                    # İndirme Butonu
                    img_byte_arr = io.BytesIO()
                    post_img.save(img_byte_arr, format='PNG')
                    img_byte_arr = img_byte_arr.getvalue()
                    st.download_button(label="Görseli Telefona İndir", data=img_byte_arr, file_name="nobetci_instagram.png", mime="image/png")
                
                with col2:
                    st.subheader("Hazır Açıklama Metni")
                    text_area_content = f"{summary}\n\n{hashtags}"
                    st.text_area("Kopyalamak için tıklayın:", value=text_area_content, height=350)
                    
            except Exception as e:
                st.error(f"Bir hata meydana geldi: {e}")
