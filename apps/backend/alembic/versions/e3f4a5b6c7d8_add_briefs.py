"""add briefs and industry template seeds

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-07-08
"""

from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# System template data (seeded once in upgrade)
# ---------------------------------------------------------------------------

_SYSTEM_TEMPLATES = [
    {
        "name": "Kozmetik Kampanya Brief'i",
        "description": "Kozmetik ve güzellik markalarına yönelik kapsamlı kampanya brief'i.",
        "industry": "branding",
        "sections": [
            {
                "title": "Kampanya Genel Bilgileri",
                "description": "Kampanyanın amacını ve hedeflerini tanımlayın.",
                "fields": [
                    {"field_key": "kampanya_adi", "label": "Kampanya Adı", "field_type": "text", "is_required": True, "placeholder": "örn. Yaz Koleksiyonu Lansmanı"},
                    {"field_key": "kampanya_suresi", "label": "Kampanya Süresi (Başlangıç–Bitiş)", "field_type": "text", "is_required": True, "placeholder": "örn. 1 Ağustos – 31 Ağustos 2025"},
                    {"field_key": "kampanya_butcesi", "label": "Kampanya Bütçesi (TL)", "field_type": "number", "placeholder": "örn. 25000"},
                    {"field_key": "kampanya_hedefi", "label": "Kampanya Hedefi", "field_type": "campaign_goal", "is_required": True},
                ],
            },
            {
                "title": "Ürün & Marka Bilgileri",
                "description": "Tanıtılacak ürün ve marka detayları.",
                "fields": [
                    {"field_key": "urun_adi", "label": "Ürün Adı / Koleksiyonu", "field_type": "text", "is_required": True, "placeholder": "örn. Nemlendirici Krem SPF 50"},
                    {"field_key": "urun_ozellikleri", "label": "Ürün Özellikleri & Faydaları", "field_type": "textarea", "is_required": True, "placeholder": "Ürünün temel özelliklerini ve tüketiciye sağladığı faydaları açıklayın"},
                    {"field_key": "marka_renkleri", "label": "Marka Rengi", "field_type": "color"},
                    {"field_key": "referans_gorseller", "label": "Referans Görseller / Moodboard", "field_type": "reference_images"},
                ],
            },
            {
                "title": "Hedef Kitle & Platform",
                "description": "Kime, nerede ve nasıl ulaşmak istiyorsunuz?",
                "fields": [
                    {"field_key": "hedef_kitle", "label": "Hedef Kitle", "field_type": "target_audience", "is_required": True},
                    {"field_key": "yayinlanacak_platformlar", "label": "Yayınlanacak Platformlar", "field_type": "platform_selector", "is_required": True},
                    {"field_key": "icerik_tonu", "label": "İçerik Tonu", "field_type": "select", "is_required": True, "options": {"choices": ["Lüks & Premium", "Samimi & Doğal", "Eğlenceli & Genç", "Bilimsel & Güvenilir"]}},
                    {"field_key": "yasaklanan_ifadeler", "label": "Kaçınılacak İfadeler / Konular", "field_type": "textarea", "placeholder": "Marka tarafından yasak olan ifadeler, iddialar veya konular"},
                ],
            },
        ],
    },
    {
        "name": "Sağlık & Klinik Brief'i",
        "description": "Sağlık, klinik ve medikal hizmetlere yönelik iletişim brief'i.",
        "industry": "content",
        "sections": [
            {
                "title": "Klinik / Kurum Bilgileri",
                "description": None,
                "fields": [
                    {"field_key": "klinik_adi", "label": "Klinik / Kurum Adı", "field_type": "text", "is_required": True},
                    {"field_key": "uzmanlik_alanlari", "label": "Uzmanlık Alanları", "field_type": "multi_select", "is_required": True, "options": {"choices": ["Estetik Cerrahi", "Diş Hekimliği", "Dermatoloji", "Ortopedi", "Göz Hastalıkları", "Genel Tıp", "Kadın Doğum", "Psikiyatri"]}},
                    {"field_key": "hedef_hasta_grubu", "label": "Hedef Hasta Grubu", "field_type": "target_audience", "is_required": True},
                ],
            },
            {
                "title": "Kampanya Detayları",
                "description": None,
                "fields": [
                    {"field_key": "kampanya_konusu", "label": "Kampanya Konusu", "field_type": "text", "is_required": True, "placeholder": "örn. Yazlık Cilt Bakımı Paketi"},
                    {"field_key": "ana_mesaj", "label": "Ana Mesaj", "field_type": "textarea", "is_required": True, "placeholder": "Hasta / müşteriye iletilmek istenen temel mesaj"},
                    {"field_key": "cta_metni", "label": "CTA (Harekete Geçirici İfade)", "field_type": "text", "placeholder": "örn. Ücretsiz Konsültasyon Al"},
                    {"field_key": "gorsel_ton", "label": "Görsel Ton", "field_type": "select", "is_required": True, "options": {"choices": ["Tıbbi / Resmi", "Sıcak / Samimi", "Modern / Minimal", "Umut Vaat Eden / Motivasyonel"]}},
                ],
            },
            {
                "title": "Platform & Bütçe",
                "description": None,
                "fields": [
                    {"field_key": "platform", "label": "Yayın Platformu", "field_type": "platform_selector", "is_required": True},
                    {"field_key": "butce", "label": "Bütçe (TL)", "field_type": "number"},
                    {"field_key": "yayinlanma_tarihi", "label": "Yayınlanma Tarihi", "field_type": "date"},
                    {"field_key": "yasal_uyarilar", "label": "Zorunlu Yasal / Etik Uyarılar", "field_type": "textarea", "placeholder": "Sektöre özgü zorunlu uyarı metinleri"},
                ],
            },
        ],
    },
    {
        "name": "E-Ticaret Kampanya Brief'i",
        "description": "Online mağaza ve e-ticaret kampanyaları için kapsamlı brief şablonu.",
        "industry": "digital_ad",
        "sections": [
            {
                "title": "Kampanya Bilgileri",
                "description": None,
                "fields": [
                    {"field_key": "kampanya_basligi", "label": "Kampanya Başlığı", "field_type": "text", "is_required": True, "placeholder": "örn. 11.11 İndirim Festivali"},
                    {"field_key": "kampanya_hedefi", "label": "Kampanya Hedefi", "field_type": "campaign_goal", "is_required": True},
                    {"field_key": "indirim_orani", "label": "İndirim Oranı / Teklif", "field_type": "text", "placeholder": "örn. %30 İndirim, Ücretsiz Kargo"},
                    {"field_key": "kampanya_tarihleri", "label": "Kampanya Tarihleri", "field_type": "text", "is_required": True, "placeholder": "Başlangıç ve bitiş tarihleri"},
                ],
            },
            {
                "title": "Ürün & Teklifler",
                "description": None,
                "fields": [
                    {"field_key": "one_cikan_urunler", "label": "Öne Çıkan Ürünler / Kategoriler", "field_type": "textarea", "is_required": True, "placeholder": "Kampanyada vurgulanacak ürünler ve kategoriler"},
                    {"field_key": "landing_page_url", "label": "Landing Page URL", "field_type": "url", "placeholder": "https://"},
                    {"field_key": "promosyon_kodu", "label": "Promosyon Kodu (varsa)", "field_type": "text"},
                ],
            },
            {
                "title": "Hedefleme & Dağıtım",
                "description": None,
                "fields": [
                    {"field_key": "hedef_kitle", "label": "Hedef Kitle", "field_type": "target_audience", "is_required": True},
                    {"field_key": "platform", "label": "Reklam Platformları", "field_type": "platform_selector", "is_required": True},
                    {"field_key": "sezon_veya_event", "label": "Sezon / Özel Gün", "field_type": "text", "placeholder": "örn. Babalar Günü, Okul Sezonu"},
                    {"field_key": "butce", "label": "Medya Bütçesi (TL)", "field_type": "number", "is_required": True},
                ],
            },
        ],
    },
    {
        "name": "Sosyal Medya Post Brief'i",
        "description": "Tekli sosyal medya içerik paylaşımları için hızlı ve etkili brief.",
        "industry": "social_media",
        "sections": [
            {
                "title": "Post Temel Bilgileri",
                "description": None,
                "fields": [
                    {"field_key": "baslik", "label": "Post Başlığı / Konusu", "field_type": "text", "is_required": True},
                    {"field_key": "ana_mesaj", "label": "Ana Mesaj / Caption", "field_type": "textarea", "is_required": True, "placeholder": "Post'ta iletilmek istenen mesaj veya yazı"},
                    {"field_key": "yayinlanma_tarihi", "label": "Yayınlanma Tarihi & Saati", "field_type": "date", "is_required": True},
                    {"field_key": "platform", "label": "Platform", "field_type": "platform_selector", "is_required": True},
                ],
            },
            {
                "title": "Görsel Yönlendirme",
                "description": None,
                "fields": [
                    {"field_key": "gorsel_tipi", "label": "Görsel Format", "field_type": "select", "is_required": True, "options": {"choices": ["Tek Fotoğraf", "Carousel", "Video", "Reels", "Story", "İnfografik"]}},
                    {"field_key": "renk_paleti", "label": "Renk Paleti", "field_type": "color"},
                    {"field_key": "referans_gorseller", "label": "Referans Görseller", "field_type": "reference_images"},
                ],
            },
            {
                "title": "Detaylar",
                "description": None,
                "fields": [
                    {"field_key": "hashtag_onerileri", "label": "Hashtag Önerileri", "field_type": "textarea", "placeholder": "#flobrief #sosyalmedya"},
                    {"field_key": "cta", "label": "CTA (Harekete Geçirici İfade)", "field_type": "text", "placeholder": "örn. Hemen Satın Al, Detayları Gör"},
                    {"field_key": "hedef_kitle", "label": "Hedef Kitle", "field_type": "target_audience"},
                ],
            },
        ],
    },
    {
        "name": "Reels & Video Brief'i",
        "description": "Kısa video ve Reels içerik üretimleri için kapsamlı brief şablonu.",
        "industry": "content",
        "sections": [
            {
                "title": "Video Genel Bilgileri",
                "description": None,
                "fields": [
                    {"field_key": "video_basligi", "label": "Video Başlığı", "field_type": "text", "is_required": True},
                    {"field_key": "platform", "label": "Platform", "field_type": "platform_selector", "is_required": True},
                    {"field_key": "video_suresi", "label": "Video Süresi", "field_type": "select", "is_required": True, "options": {"choices": ["15 saniye", "30 saniye", "60 saniye", "90 saniye", "3 dakika+"]}},
                    {"field_key": "yayinlanma_tarihi", "label": "Yayınlanma Tarihi", "field_type": "date"},
                ],
            },
            {
                "title": "İçerik & Senaryo",
                "description": None,
                "fields": [
                    {"field_key": "senaryo_konsept", "label": "Senaryo / Konsept", "field_type": "rich_text", "is_required": True, "placeholder": "Video'nun hikayesi, sahneler ve akış"},
                    {"field_key": "muzik_tercihi", "label": "Müzik Tercihi", "field_type": "text", "placeholder": "Belirli bir şarkı veya stil tercihi"},
                    {"field_key": "referans_videolar", "label": "Referans Video URL'leri", "field_type": "url", "placeholder": "https://"},
                ],
            },
            {
                "title": "Görsel Yön & Ton",
                "description": None,
                "fields": [
                    {"field_key": "video_tonu", "label": "Video Tonu", "field_type": "select", "is_required": True, "options": {"choices": ["Eğlenceli / Viral", "Bilgilendirici / Eğitici", "Duygusal / Motivasyonel", "Marka Tanıtımı", "Ürün Odaklı"]}},
                    {"field_key": "renk_paleti", "label": "Renk Paleti", "field_type": "color"},
                    {"field_key": "moodboard", "label": "Moodboard", "field_type": "moodboard"},
                ],
            },
        ],
    },
    {
        "name": "Web Sitesi Brief'i",
        "description": "Kurumsal web sitesi, landing page veya e-ticaret sitesi projeleri için brief.",
        "industry": "web",
        "sections": [
            {
                "title": "Proje Genel Bilgileri",
                "description": None,
                "fields": [
                    {"field_key": "site_adi", "label": "Site / Proje Adı", "field_type": "text", "is_required": True},
                    {"field_key": "site_amaci", "label": "Sitenin Amacı & Hedefleri", "field_type": "textarea", "is_required": True, "placeholder": "Sitenin ne için kullanılacağı ve beklenen dönüşümler"},
                    {"field_key": "hedef_kitle", "label": "Hedef Kitle", "field_type": "target_audience", "is_required": True},
                ],
            },
            {
                "title": "Tasarım Gereksinimleri",
                "description": None,
                "fields": [
                    {"field_key": "renk_paleti", "label": "Renk Paleti", "field_type": "color"},
                    {"field_key": "font_tercihi", "label": "Font / Yazı Tipi Tercihi", "field_type": "text", "placeholder": "örn. Inter, Helvetica, ya da marka fontu"},
                    {"field_key": "referans_siteler", "label": "Referans Siteler URL", "field_type": "url", "placeholder": "Beğendiğiniz sitelerin adresleri"},
                    {"field_key": "moodboard", "label": "Moodboard", "field_type": "moodboard"},
                ],
            },
            {
                "title": "Teknik Gereksinimler",
                "description": None,
                "fields": [
                    {"field_key": "cms_tercihi", "label": "CMS / Teknoloji Tercihi", "field_type": "select", "is_required": True, "options": {"choices": ["WordPress", "Webflow", "Next.js", "Özel Geliştirme", "Diğer"]}},
                    {"field_key": "sayfa_sayisi", "label": "Tahmini Sayfa Sayısı", "field_type": "number"},
                    {"field_key": "dil_destegi", "label": "Dil Desteği", "field_type": "multi_select", "options": {"choices": ["Türkçe", "İngilizce", "Almanca", "Arapça", "Rusça"]}},
                    {"field_key": "seo_gereksinimleri", "label": "SEO Gereksinimleri", "field_type": "textarea", "placeholder": "Hedef anahtar kelimeler, teknik SEO beklentileri"},
                ],
            },
        ],
    },
    {
        "name": "Kurumsal Kimlik Brief'i",
        "description": "Marka kimliği, logo ve kurumsal tasarım projeleri için brief şablonu.",
        "industry": "branding",
        "sections": [
            {
                "title": "Şirket & Marka Bilgileri",
                "description": None,
                "fields": [
                    {"field_key": "sirket_adi", "label": "Şirket / Marka Adı", "field_type": "text", "is_required": True},
                    {"field_key": "sektor", "label": "Sektör", "field_type": "text", "is_required": True},
                    {"field_key": "kurulusun_hikayesi", "label": "Kuruluşun Hikayesi & Vizyonu", "field_type": "textarea", "is_required": True},
                ],
            },
            {
                "title": "Hedef Kitle & Değerler",
                "description": None,
                "fields": [
                    {"field_key": "marka_degerleri", "label": "Marka Değerleri (3–5 kelime)", "field_type": "textarea", "is_required": True, "placeholder": "örn. Güvenilir, Modern, Yenilikçi"},
                    {"field_key": "hedef_kitle", "label": "Hedef Kitle", "field_type": "target_audience", "is_required": True},
                    {"field_key": "rakipler", "label": "Rakipler & Farklılaşma", "field_type": "textarea", "placeholder": "Ana rakipler ve markanın farkını yazın"},
                ],
            },
            {
                "title": "Tasarım Tercihleri",
                "description": None,
                "fields": [
                    {"field_key": "renk_tercihleri", "label": "Renk Tercihleri", "field_type": "color"},
                    {"field_key": "logo_tarzi", "label": "Logo Tarzı", "field_type": "select", "is_required": True, "options": {"choices": ["Modern / Minimal", "Klasik / Kurumsal", "Yaratıcı / Bold", "El Yazısı / Organik"]}},
                    {"field_key": "referans_markalar", "label": "Referans Markalar / Moodboard", "field_type": "reference_images"},
                ],
            },
            {
                "title": "Teslimat Kapsamı",
                "description": None,
                "fields": [
                    {"field_key": "teslimat_kapsamı", "label": "Teslimat Kapsamı", "field_type": "multi_select", "is_required": True, "options": {"choices": ["Logo (tüm varyantlar)", "Kartvizit", "Antetli Kağıt", "Sosyal Medya Profil Görselleri", "Sunum Şablonu", "E-posta İmzası"]}},
                    {"field_key": "deadline", "label": "Teslim Tarihi", "field_type": "date"},
                ],
            },
        ],
    },
    {
        "name": "Influencer Kampanya Brief'i",
        "description": "Influencer iş birliği ve içerik üretimi kampanyaları için detaylı brief.",
        "industry": "influencer",
        "sections": [
            {
                "title": "Kampanya Bilgileri",
                "description": None,
                "fields": [
                    {"field_key": "marka_adi", "label": "Marka Adı", "field_type": "text", "is_required": True},
                    {"field_key": "kampanya_konusu", "label": "Kampanya Konusu & Ürün", "field_type": "textarea", "is_required": True},
                    {"field_key": "kampanya_hashtag", "label": "Kampanya Hashtag", "field_type": "text", "placeholder": "#kampanya #marka"},
                ],
            },
            {
                "title": "Influencer Gereksinimleri",
                "description": None,
                "fields": [
                    {"field_key": "influencer_kategorisi", "label": "Influencer Kategorisi", "field_type": "multi_select", "is_required": True, "options": {"choices": ["Yaşam Tarzı", "Güzellik / Kozmetik", "Fitness & Sağlık", "Yemek & Mutfak", "Teknoloji", "Moda", "Seyahat", "Anne & Çocuk"]}},
                    {"field_key": "min_takipci", "label": "Min. Takipçi Sayısı", "field_type": "number", "placeholder": "örn. 50000"},
                    {"field_key": "platform", "label": "Kampanya Platformu", "field_type": "platform_selector", "is_required": True},
                ],
            },
            {
                "title": "İçerik Gereksinimleri",
                "description": None,
                "fields": [
                    {"field_key": "icerik_formati", "label": "İçerik Formatı", "field_type": "select", "is_required": True, "options": {"choices": ["Feed Post", "Reels / Video", "Story", "YouTube Video", "TikTok", "Blog Yazısı"]}},
                    {"field_key": "mesaj_noktalari", "label": "Vurgulanacak Mesaj Noktaları", "field_type": "textarea", "is_required": True, "placeholder": "Influencer'ın mutlaka bahsetmesi gereken özellikler ve mesajlar"},
                    {"field_key": "yasaklanan_ifadeler", "label": "Yasaklanan İfadeler / Rakipler", "field_type": "textarea"},
                ],
            },
            {
                "title": "Bütçe & Zamanlama",
                "description": None,
                "fields": [
                    {"field_key": "influencer_sayisi", "label": "Hedef Influencer Sayısı", "field_type": "number"},
                    {"field_key": "butce", "label": "Toplam Bütçe (TL)", "field_type": "number"},
                    {"field_key": "yayinlanma_tarihi", "label": "İçerik Yayın Tarihi", "field_type": "date", "is_required": True},
                ],
            },
        ],
    },
    {
        "name": "Restoran & Gıda Brief'i",
        "description": "Restoran, kafe ve gıda markaları için içerik & pazarlama brief'i.",
        "industry": "content",
        "sections": [
            {
                "title": "Mekan & Marka Bilgileri",
                "description": None,
                "fields": [
                    {"field_key": "restoran_adi", "label": "Restoran / Marka Adı", "field_type": "text", "is_required": True},
                    {"field_key": "mutfak_turu", "label": "Mutfak Türü", "field_type": "text", "placeholder": "örn. Türk, İtalyan, Vegan, Fast Food"},
                    {"field_key": "hedef_musteri", "label": "Hedef Müşteri Profili", "field_type": "target_audience", "is_required": True},
                ],
            },
            {
                "title": "Kampanya & İçerik",
                "description": None,
                "fields": [
                    {"field_key": "kampanya_konusu", "label": "Kampanya Konusu", "field_type": "textarea", "is_required": True, "placeholder": "örn. Yeni Menü Lansmanı, Özel Gün Kampanyası"},
                    {"field_key": "one_cikan_urunler", "label": "Öne Çıkan Ürünler / Yemekler", "field_type": "textarea", "placeholder": "Vurgulanacak menü öğeleri"},
                    {"field_key": "kampanya_suresi", "label": "Kampanya Süresi", "field_type": "text", "placeholder": "Başlangıç – Bitiş tarihleri"},
                ],
            },
            {
                "title": "Görsel Yönlendirme",
                "description": None,
                "fields": [
                    {"field_key": "fotograf_tarzi", "label": "Fotoğraf / Çekim Tarzı", "field_type": "select", "is_required": True, "options": {"choices": ["Yemek Fotoğrafçılığı (flat lay)", "Ambians / Atmosfer", "Şef & Mutfak", "Müşteri Deneyimi", "Kombinasyon"]}},
                    {"field_key": "renk_paleti", "label": "Renk Paleti", "field_type": "color"},
                    {"field_key": "referans_gorseller", "label": "Referans Görseller", "field_type": "reference_images"},
                ],
            },
            {
                "title": "Platform & Ton",
                "description": None,
                "fields": [
                    {"field_key": "platform", "label": "Yayın Platformu", "field_type": "platform_selector", "is_required": True},
                    {"field_key": "icerik_tonu", "label": "İçerik Tonu", "field_type": "select", "is_required": True, "options": {"choices": ["Lüks / Fine Dining", "Samimi / Ev Yemeği", "Genç & Eğlenceli", "Profesyonel / Kurumsal"]}},
                    {"field_key": "butce", "label": "Bütçe (TL)", "field_type": "number"},
                ],
            },
        ],
    },
    {
        "name": "Gayrimenkul Brief'i",
        "description": "Konut, ofis ve ticari gayrimenkul projeleri için pazarlama brief'i.",
        "industry": "digital_ad",
        "sections": [
            {
                "title": "Proje Bilgileri",
                "description": None,
                "fields": [
                    {"field_key": "proje_adi", "label": "Proje Adı", "field_type": "text", "is_required": True},
                    {"field_key": "proje_turu", "label": "Proje Türü", "field_type": "select", "is_required": True, "options": {"choices": ["Konut Projesi", "Ofis / İş Merkezi", "Alışveriş Merkezi", "Arsa / Tarla", "Villa / Müstakil"]}},
                    {"field_key": "konum", "label": "Konum", "field_type": "text", "is_required": True, "placeholder": "İl, İlçe, Mahalle"},
                    {"field_key": "teslim_tarihi", "label": "Teslim Tarihi / Yatırım Süreci", "field_type": "text"},
                ],
            },
            {
                "title": "Hedef Kitle & Değer Önerisi",
                "description": None,
                "fields": [
                    {"field_key": "hedef_kitle", "label": "Hedef Kitle", "field_type": "target_audience", "is_required": True},
                    {"field_key": "fiyat_araligi", "label": "Satış / Kira Fiyat Aralığı", "field_type": "text", "placeholder": "örn. 3.000.000 – 7.500.000 TL"},
                    {"field_key": "kampanya_hedefi", "label": "Kampanya Hedefi", "field_type": "campaign_goal", "is_required": True},
                ],
            },
            {
                "title": "Görsel & İçerik",
                "description": None,
                "fields": [
                    {"field_key": "gorsel_tarzi", "label": "Görsel Tarzı", "field_type": "select", "is_required": True, "options": {"choices": ["Lüks / Premium", "Modern / Minimal", "Aile Odaklı / Sıcak", "Yatırım / Kariyer"]}},
                    {"field_key": "moodboard", "label": "Moodboard", "field_type": "moodboard"},
                    {"field_key": "referans_gorseller", "label": "Proje Görselleri / Referanslar", "field_type": "reference_images"},
                ],
            },
            {
                "title": "Medya & Bütçe",
                "description": None,
                "fields": [
                    {"field_key": "platform", "label": "Reklam Platformları", "field_type": "platform_selector", "is_required": True},
                    {"field_key": "butce", "label": "Medya Bütçesi (TL)", "field_type": "number", "is_required": True},
                    {"field_key": "kampanya_baslangic", "label": "Kampanya Başlangıç Tarihi", "field_type": "date"},
                ],
            },
        ],
    },
]


def _seed_system_templates(conn: object) -> None:
    existing_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM brief_templates WHERE is_system_template = TRUE")
    ).scalar_one()
    if existing_count > 0:
        return

    for tmpl in _SYSTEM_TEMPLATES:
        row = conn.execute(
            sa.text("""
                INSERT INTO brief_templates
                    (id, agency_id, name, description, industry, is_system_template, is_active, created_by_id, created_at, updated_at)
                VALUES
                    (gen_random_uuid(), NULL, :name, :description, :industry, true, true, NULL, now(), now())
                RETURNING id
            """),
            {"name": tmpl["name"], "description": tmpl["description"], "industry": tmpl["industry"]},
        )
        template_id = row.scalar_one()

        for s_idx, section in enumerate(tmpl["sections"]):
            srow = conn.execute(
                sa.text("""
                    INSERT INTO brief_template_sections
                        (id, template_id, title, description, sort_order, created_at, updated_at)
                    VALUES
                        (gen_random_uuid(), :template_id, :title, :description, :sort_order, now(), now())
                    RETURNING id
                """),
                {
                    "template_id": template_id,
                    "title": section["title"],
                    "description": section.get("description"),
                    "sort_order": s_idx,
                },
            )
            section_id = srow.scalar_one()

            for f_idx, field in enumerate(section["fields"]):
                conn.execute(
                    sa.text("""
                        INSERT INTO brief_template_fields
                            (id, section_id, field_key, label, help_text, field_type, is_required,
                             options, validation_rules, placeholder, sort_order, created_at, updated_at)
                        VALUES
                            (gen_random_uuid(), :section_id, :field_key, :label, :help_text, :field_type,
                             :is_required, :options, NULL, :placeholder, :sort_order, now(), now())
                    """),
                    {
                        "section_id": section_id,
                        "field_key": field["field_key"],
                        "label": field["label"],
                        "help_text": field.get("help_text"),
                        "field_type": field["field_type"],
                        "is_required": field.get("is_required", False),
                        "options": json.dumps(field["options"]) if field.get("options") else None,
                        "placeholder": field.get("placeholder"),
                        "sort_order": f_idx,
                    },
                )


def upgrade() -> None:
    # Allow NULL created_by_id for system templates
    op.alter_column(
        "brief_templates",
        "created_by_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    op.create_table(
        "briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brief_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("deadline", sa.String(10), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_brief_agency_id", "briefs", ["agency_id"])
    op.create_index("ix_brief_brand_id", "briefs", ["brand_id"])
    op.create_index("ix_brief_status", "briefs", ["status"])
    op.create_index("ix_brief_template_id", "briefs", ["template_id"])

    op.create_table(
        "brief_field_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("briefs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_field_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brief_template_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bfv_brief_id", "brief_field_values", ["brief_id"])
    op.create_unique_constraint("uq_brief_field_value", "brief_field_values", ["brief_id", "template_field_id"])

    op.create_table(
        "brief_assignees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("briefs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_label", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_brief_assignee_brief_id", "brief_assignees", ["brief_id"])
    op.create_unique_constraint("uq_brief_assignee", "brief_assignees", ["brief_id", "user_id"])

    # Seed system templates
    conn = op.get_bind()
    _seed_system_templates(conn)


def downgrade() -> None:
    op.drop_table("brief_assignees")
    op.drop_table("brief_field_values")
    op.drop_table("briefs")
    op.alter_column(
        "brief_templates",
        "created_by_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
