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

# Güvenilir Cloudflare CDN Font Bağlantıları
FONT_BOLD_URL = "https://cdnjs.cloudflare.com/ajax/libs/roboto-fontface/0.10.0/fonts/roboto/Roboto-Bold.ttf"
FONT_REG_URL = "https://cdnjs.cloudflare.com/ajax/libs/roboto-fontface/0.10.0/fonts/roboto/Roboto-Regular.ttf"

# Çift Aşamalı Güvenli Font Yükleyici
@st.cache_data
def load_fonts():
    fonts = {}
    urls = {"bold": FONT_BOLD_URL, "regular": FONT_REG_URL}
    
    for key, url in urls.items():
        # 1. Aşama: İnternetten Fontu Çekmeyi Dene
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200 and len(response.content) > 10000:
                fonts[key] = response.content
                continue
        except:
            pass
        
        # 2. Aşama: Başarısız Olursa Linux Sunucusundaki Kurulu Fontları Ara (Garantili Çözüm)
        local_paths = {
            "bold": [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
            ],
            "regular": [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            ]
        }
        for path in local_paths[key]:
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        fonts[key] = f.read()
                        break
                except:
                    pass
    return fonts

st.title("📰 Nöbetçi Gazete Post Robotu")
st.write("Web sitesi linkini girerek Instagram için 4:5 oranında tweet tasarımlı görsel ve metin özeti oluşturabilirsiniz.")

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

# Piksel Tabanlı Hassas Metin Sarma Fonksiyonu
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
                
                # --- AKILLI GÖVDE (BODY) METNİ BULUCU ---
                best_container = None
                max_chars = 0
                
                # Sık kullanılan haber ana içerik sınıfları
                selectors = [
                    'div.article-text', 'div.content-text', 'div.article-content',
                    'div[itemprop="articleBody"]', 'div.entry-content', 'article'
                ]
                for sel in selectors:
                    el = soup.select_one(sel)
                    if el:
                        p_text_len = sum(len(p.get_text().strip()) for p in el.find_all('p'))
                        if p_text_len > 300:
                            best_container = el
                            break
                
                # Bulunamazsa Metin Yoğunluğu Analiz Algoritması
                if not best_container:
                    for el in soup.find_all(['div', 'main', 'article']):
                        class_str = " ".join(el.get('class', [])).lower()
                        id_str = el.get('id', '').lower()
                        # Menü, footer, reklam vb. alanları ele
                        if any(x in class_str or x in id_str for x in ['header', 'footer', 'menu', 'sidebar', 'nav', 'comment', 'ad-', 'widget']):
                            continue
                        
                        p_tags = el.find_all('p', recursive=False)
                        char_count = sum(len(p.get_text().strip()) for p in p_tags if len(p.get_text().strip()) > 40)
                        if char_count > max_chars:
                            max_chars = char_count
                            best_container = el

                # Paragrafları ayıklama
                if best_container:
                    paragraphs = [p.get_text().strip() for p in best_container.find_all('p') if len(p.get_text().strip()) > 45]
                else:
                    paragraphs = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text().strip()) > 50]
                
                # Alakasız/çerez metinlerin süzülmesi
                clean_paragraphs = []
                boilerplate_keywords = [
                    "çerez", "cookie", "politikası", "abone", "tıklayın", "tıklayınız", 
                    "paylaş", "beğen", "yazar", "editör", "yayınlanma", "güncelleme", 
                    "tarafından", "hakkında", "tüm hakları", "yorumlar", "giriş yap", 
                    "üye ol", "e-posta", "telefon", "reklam", "takip et", "galerisi"
                ]
                
                for p in paragraphs:
                    if any(key in p.lower() for key in boilerplate_keywords):
                        continue
                    clean_paragraphs.append(p)
                
                # En temiz ilk 3 gerçek paragraftan özgün özet metni oluşturma
                real_paragraphs = clean_paragraphs[:3]
                full_text = " ".join(real_paragraphs)
                sentences = re.split(r'(?<=[.!?])\s+', full_text)
                summary = " ".join(sentences[:4]) # İlk 4 temiz ve alakalı cümle
                
                if not summary.strip():
                    summary = "Haber gövde içeriği tespit edilemedi. Lütfen linki kontrol edin."
                
                # Hashtags
                hashtags = generate_hashtags(summary + " " + title)
                img_url = find_image_url(soup, url_input)
                
                # Görsel Motoru (Pillow)
                canvas_width, canvas_height = 1080, 1350
                post_img = Image.new("RGB", (canvas_width, canvas_height), "#121212")

                if img_url:
                    try:
                        img_data = requests.get(img_url, headers=headers, timeout=10).content
                        web_img = Image.open(io.BytesIO(img_data)).convert("RGB")
                        web_w, web_h = web_img.size
                        ratio = max(canvas_width / web_w, canvas_height / web_h)
                        new_size = (int(web_w * ratio), int(web_h * ratio))
                        resized_img = web_img.resize(new_size, Image.Resampling.LANCZOS)
                        x_offset = (resized_img.size[0] - canvas_width) // 2
                        y_offset = (resized_img.size[1] - canvas_height) // 2
                        post_img = resized_img.crop((x_offset, y_offset, x_offset + canvas_width, y_offset + canvas_height))
                        post_img = post_img.filter(ImageFilter.GaussianBlur(4))
                    except:
                        pass

                dim_overlay = Image.new("RGBA", post_img.size, (0, 0, 0, 80))
                post_img = Image.alpha_composite(post_img.convert("RGBA"), dim_overlay).convert("RGB")

                # Fontları Çift Aşamalı Güvenli Fonksiyonla Yükleme
                loaded_fonts = load_fonts()
                bold_bytes = loaded_fonts.get("bold")
                reg_bytes = loaded_fonts.get("regular")

                # Mobil Okunabilirlik İçin Ölçeklendirilmiş Büyük Font Boyutları
                char_len = len(title)
                if char_len > 110:
                    font_size_val = 40
                elif char_len > 60:
                    font_size_val = 48
                else:
                    font_size_val = 56

                if bold_bytes and reg_bytes:
                    font_title = ImageFont.truetype(io.BytesIO(bold_bytes), font_size_val)
                    font_name = ImageFont.truetype(io.BytesIO(bold_bytes), 32)
                    font_handle = ImageFont.truetype(io.BytesIO(reg_bytes), 26)
                    font_stats = ImageFont.truetype(io.BytesIO(reg_bytes), 24)
                else:
                    font_title = font_name = font_handle = font_stats = ImageFont.load_default()

                # Hassas piksel sarma ölçüm yüzeyi
                dummy_img = Image.new("RGB", (1, 1))
                dummy_draw = ImageDraw.Draw(dummy_img)

                # Genişletilmiş kart yapısı (Yatayda 960px). Kullanılabilir alan = 870px.
                wrapped_text = wrap_text_by_pixels(title, font_title, 870, dummy_draw)
                
                try:
                    bbox = dummy_draw.textbbox((0, 0), wrapped_text, font=font_title, spacing=18)
                    text_h = bbox[3] - bbox[1]
                except Exception:
                    num_lines = len(wrapped_text.split('\n'))
                    text_h = num_lines * (font_size_val + 18)

                # Kart En Boy Ölçüleri (Diklemesine de Metinle Tam Uyumlu)
                card_w = 960
                card_h = 160 + text_h + 120
                if card_h > 1080: card_h = 1080
                elif card_h < 400: card_h = 400

                card_x = (canvas_width - card_w) // 2
                card_y = (canvas_height - card_h) // 2

                # Okunabilirliği Artırmak İçin Kart Opaklığı %98'e (250/255) çıkarıldı
                card_layer = Image.new("RGBA", post_img.size, (0, 0, 0, 0))
                card_draw = ImageDraw.Draw(card_layer)
                card_draw.rounded_rectangle([(card_x, card_y), (card_x + card_w, card_y + card_h)], radius=30, fill=(255, 255, 255, 250))
                post_img = Image.alpha_composite(post_img.convert("RGBA"), card_layer).convert("RGB")

                draw = ImageDraw.Draw(post_img)
                avatar_x, avatar_y = card_x + 45, card_y + 45
                avatar_diameter = 74
                avatar_img = None

                # Favicon
                try:
                    fav_response = requests.get(FAVICON_URL, headers=headers, timeout=5)
                    if fav_response.status_code == 200 and len(fav_response.content) > 100:
                        fav_img = Image.open(io.BytesIO(fav_response.content)).convert("RGBA")
                        fav_img = fav_img.resize((avatar_diameter, avatar_diameter), Image.Resampling.LANCZOS)
                        mask = Image.new("L", (avatar_diameter, avatar_diameter), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.ellipse((0, 0, avatar_diameter, avatar_diameter), fill=255)
                        avatar_img = Image.new("RGBA", (avatar_diameter, avatar_diameter), (0, 0, 0, 0))
                        avatar_img.paste(fav_img, (0, 0), mask=mask)
                except:
                    pass

                if avatar_img:
                    post_img.paste(avatar_img, (avatar_x, avatar_y), mask=avatar_img.split()[3])
                else:
                    draw.ellipse([(avatar_x, avatar_y), (avatar_x + avatar_diameter, avatar_y + avatar_diameter)], fill="#FF9800")

                # Metin Rengi tam siyah (#050505) ve Satır Aralığı 18px (Hassas Okunabilirlik)
                draw.text((avatar_x + 95, avatar_y + 8), "Nöbetçi Gazete", font=font_name, fill="#0F1419")
                draw.text((avatar_x + 95, avatar_y + 43), "@nobetcigazete", font=font_handle, fill="#536471")
                draw.text((avatar_x, card_y + 160), wrapped_text, font=font_title, fill="#050505", spacing=18)
                draw.text((avatar_x, card_y + card_h - 60), "💬 247      🔁 1.1K      ❤️ 4.8K      ✉️", font=font_stats, fill="#536471")

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
