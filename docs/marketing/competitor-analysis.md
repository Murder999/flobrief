# Flobrief — Rakip Analizi

**Araştırma Tarihi:** 12 Temmuz 2026  
**Analizi Yapan:** Claude Code (web araştırması + proje kaynak kodu incelemesi)  
**Kapsam:** Planable, Filestage, Ziflow, ClickUp, Monday.com ve Türkiye pazarı

---

## 1. Yönetici Özeti

Flobrief, ajanslar ile marka müşterileri arasındaki **brief yönetimi ve onay sürecini** merkeze alan dikey bir B2B SaaS ürünüdür. Rakipler ya genel proje yönetimi (ClickUp, Monday.com) ya da sosyal medya içerik onayı (Planable) ya da dosya proofing (Filestage, Ziflow) konumlandırması yapar — **brieffing + onay + içerik takvimi + beyaz etiket + Türkçe ödeme** bütünlüğünü tek platformda sunan bir rakip yoktur.

**En büyük fırsat:** Türkiye ve çevre pazarlarda, ajans-marka ilişkisini yönetmek için hâlâ e-posta + Excel + WhatsApp kullanan ajanslar; yerelleştirilmiş ve dikey bir platforma ciddi ödeme niyetindedir.

**En büyük tehdit:** ClickUp ve Monday.com'un ajans-spesifik şablon paketleriyle pazara girmesi ve Planable'ın brief yönetimi modülü eklemesi.

---

## 2. Flobrief Ürün Özeti

Flobrief'in mevcut (v1.0) yetenekleri:

| Modül | Özellikler |
|-------|------------|
| **Brief Yönetimi** | Dinamik şablon motoru, sektörel şablonlar (10 adet), alan değerleri, versiyon geçmişi, durum akışı |
| **Onay Portalı** | Marka müşterisine özel public portal, SHA-256 token güvenliği, yorum/thread sistemi, onay geçmişi |
| **İçerik Takvimi** | Haftalık/aylık görünüm, platform dağılımı, atama takibi, durum geçmişi |
| **Beyaz Etiket** | Ajans logosu/rengi/domain, plan bazlı erişim kontrolü |
| **Raporlama** | KPI raporu, PDF ihracat, paylaşılabilir güvenli bağlantı |
| **Bildirimler** | E-posta (Resend), WhatsApp (mimari hazır), uygulama içi |
| **Abonelik** | iyzico entegrasyonu, plan bazlı yetkilendirme |
| **Multi-tenant** | Ajans + marka alt kiracı, RBAC, platform admin paneli |
| **Varlık Yönetimi** | Dosya yükleme, versiyonlama, brief ve takvim öğelerine bağlantı |
| **RBAC** | agency_owner / agency_admin / agency_member / brand_admin / brand_member |

---

## 3. Rakip Profilleri

---

### 3.1 Planable

**Ne Yapar:** Sosyal medya içerik planlama ve onay platformu.

**Hedef Kitle:** Sosyal medya ajansları, dijital pazarlama ekipleri, çok markalı in-house ekipler.

**Fiyatlandırma (2026):**
| Plan | Fiyat |
|------|-------|
| Free | 50 toplam gönderi limiti |
| Basic | ~$33/workspace/ay |
| Pro | ~$49–59/workspace/ay |
| Analytics eklentisi | +$9/workspace/ay |

*Workspace başına fiyatlandırma — kullanıcı sayısı sınırsız.*

**Temel Özellikler:**
- 9 sosyal ağda planlama (Facebook, Instagram, LinkedIn, X, TikTok, YouTube, Pinterest, Google Business, Bluesky)
- Çok seviyeli onay akışları (zorunlu, isteğe bağlı, sıralı)
- Gerçek zamanlı yorum ve notlar
- Medya düzenleme (görsel ve video)
- Birleşik gelen kutusu (yorum ve DM yönetimi, ek ücretle)
- Çapraz kanal performans analitiği (ek ücretle)

**Güçlü Yönler:**
- Sosyal içerik onayı konumlandırmasında pazar lideri
- Ajans-müşteri işbirliğine odaklı temiz UX
- Workspace modeli ajanslar için esnek
- Sağlam sosyal medya planlama yetenekleri

**Zayıf Yönler:**
- **Brief yönetimi yok:** Yaratıcı brief oluşturma, sektörel şablonlar, brief versiyonlama
- **Beyaz etiket yok:** Marka portalı Flobrief markasıyla çalışır
- **İçerik takvimi kısıtlı:** Sadece sosyal medya gönderileri; çok kanallı kampanya planlaması zayıf
- **Türkçe ödeme yok:** iyzico veya yerel ödeme methodu desteği bulunmuyor
- Küçük ekipler için fiyat yüksek olabiliyor
- Görsel yükleme kalitesi şikayetleri mevcut
- Çok içerik olduğunda platform yavaşlıyor

**Temel Konumlandırma:** *"İşbirliği önce gelen sosyal medya yönetim aracı"*

---

### 3.2 Filestage

**Ne Yapar:** İçerik inceleme ve onay için online proofing platformu.

**Hedef Kitle:** Yaratıcı ajanslar, üretim ekipleri, pazarlama departmanları.

**Fiyatlandırma (2026):**
| Plan | Fiyat |
|------|-------|
| Free | 1 aktif proje, 5 dosya/ay |
| Starter | €199/ay |
| Business | €329/ay |
| Enterprise | Teklif üzerine |

*Sınırsız dosya, versiyon ve hakem (reviewer).*

**Temel Özellikler:**
- Video, görsel, PDF, doküman proofing
- Sıralı ve paralel onay aşamaları
- Otomatik e-posta hatırlatmaları
- Sürüm karşılaştırma
- Yorum ve açıklama araçları
- 20+ entegrasyon (Slack, MS Teams, Monday, ClickUp, Asana, Jira)

**Güçlü Yönler:**
- G2 puanı 4.6/5 (242 değerlendirme)
- "En Kolay Admin", "En Yüksek Kullanıcı Benimsemesi" (G2 enterprise)
- Dosya inceleme konusunda kapsamlı yorum araçları
- Dış bağlantı ile müşteri erişimi (hesap gerektirmiyor)
- Özelleştirilebilir markalı inceleme alanları

**Zayıf Yönler:**
- **Brief yönetimi yok:** Yalnızca dosya/içerik inceleme aşamasını kapsar; brief oluşturma ve şablon motoru yok
- **İçerik takvimi yok**
- **Abonelik yönetimi yok:** Kendi fatura sistemi yok
- **Türkçe ödeme yok**
- Kullanıcılar arayüzün karmaşık ve zaman zaman hatalı olduğunu bildiriyor
- Doğrusal iş akışları; otomasyon ve dinamik yönlendirme sınırlı
- Küçük ekipler için başlangıç fiyatı yüksek (€199/ay)

**Temel Konumlandırma:** *"Yaratıcı içerik inceleme için online proofing"*

---

### 3.3 Ziflow

**Ne Yapar:** Yaratıcı ekipler için kurumsal düzeyde online proofing platformu.

**Hedef Kitle:** Orta ve büyük ölçekli ajanslar, in-house yaratıcı ekipler, kurumsal pazarlama.

**Fiyatlandırma (2026):**
| Plan | Kullanıcı | Fiyat/ay |
|------|-----------|----------|
| Free | 2 kullanıcı | $0 |
| Standard | 15 kullanıcıya kadar | ~$249 |
| Pro | Daha fazla kullanıcı | ~$399 |
| Enterprise | Sınırsız | Teklif üzerine |

**Temel Özellikler:**
- Her dosya türü desteği: video, çok sayfalı PDF, görsel, web URL, ses
- ZiflowAI: AI içerik önerileri, uyumluluk kontrolü
- Özelleştirilebilir onay iş akışları
- Otomatik hatırlatmalar ve son tarihler
- Proje yönetimi entegrasyonları
- Yan yana versiyon karşılaştırma

**Güçlü Yönler:**
- G2 puanı 4.5/5 (938 değerlendirme)
- Geniş dosya türü desteği
- Güçlü iş akışı otomasyonu
- ZiflowAI ile uyumluluk kontrolü özelliği
- Kurumsal ölçekte güvenilirlik

**Zayıf Yönler:**
- **Brief yönetimi yok:** Sadece dosya onayı; brief oluşturma süreci kapsam dışı
- **İçerik takvimi yok**
- **Beyaz etiket sınırlı**
- **Türkçe ödeme yok**
- Dik öğrenme eğrisi; müşteri eğitimi gerekiyor
- Küçük ekipler için çok pahalı ($249+/ay)
- Uzun yükleme süreleri şikayetleri
- Kullanıcı arayüzü karmaşık; müşteri onboarding'i zorlaştırıyor

**Temel Konumlandırma:** *"Kurumsal yaratıcı operasyonlar için online proofing"*

---

### 3.4 ClickUp

**Ne Yapar:** Her şeyi kapsayan genel proje yönetimi platformu.

**Hedef Kitle:** Her sektörden küçükten büyüğe tüm ekipler.

**Fiyatlandırma (2026):**
| Plan | Fiyat/kullanıcı/ay (yıllık) |
|------|----------------------------|
| Free Forever | $0 |
| Unlimited | $7 |
| Business | $12 |
| Enterprise | Teklif |
| ClickUp Brain (AI) | +$9/kullanıcı/ay |

**Temel Özellikler:**
- 15+ görünüm türü (Liste, Kanban, Gantt, Takvim, Tablo, vb.)
- Özelleştirilebilir otomasyon (10.000 çalıştırma/ay, Business'ta)
- Hedefler ve zaman takibi
- Özel alan izinleri
- Doküman (ClickUp Docs)
- ClickUp Brain AI asistan

**Güçlü Yönler:**
- Çok düşük başlangıç fiyatı
- Aşırı esneklik — her sektöre uyum sağlayabilir
- Geniş entegrasyon ekosistemi
- Ajans şablon paketleri mevcut
- Güçlü otomasyon motor

**Zayıf Yönler:**
- **Ajansa özel değil:** Her şeyi yapmaya çalışır; brief yönetimi için kapsamlı özelleştirme gerektirir
- **Onay portalı yok:** Marka müşterisine yönelik hazır public onay arayüzü bulunmuyor
- **Beyaz etiket yok**
- **iyzico yok:** Türk pazar için yerel ödeme desteği yok
- **Abonelik yönetimi yok:** Ajansın kendi müşterilerini faturalandırması desteklenmiyor
- Çok özellik = çok karmaşıklık; onboarding süreci uzun
- Yaratıcı brief için özel şablon motoru yok
- AI eklentisi faturayı belirgin biçimde artırıyor

**Temel Konumlandırma:** *"Hepsi bir arada proje yönetimi"*

---

### 3.5 Monday.com

**Ne Yapar:** İş akışı otomasyonu ve proje yönetimi platformu (artı CRM, Dev, Service ürünleri).

**Hedef Kitle:** Her büyüklükte şirket; pazarlama, operasyon, satış ekipleri.

**Fiyatlandırma (2026):**
| Plan | Fiyat/koltuk/ay (yıllık) |
|------|--------------------------|
| Free | 2 koltuk |
| Basic | ~$9 |
| Standard | ~$12 |
| Pro | ~$19 |
| Enterprise | Teklif |

*Misafir (müşteri) erişimi: 4 misafir = 1 koltuk.*

**Temel Özellikler:**
- Esnek pano ve iş akışları
- Otomasyon kuralları ve entegrasyon eylemleri
- monday Work Management, CRM, Dev, Service ürünleri
- Dashboard raporlama
- Timeline ve Gantt görünümleri
- Çoklu çalışma alanı (workspace)

**Güçlü Yönler:**
- Güçlü otomasyon ve entegrasyon
- Temiz ve sezgisel arayüz
- Geniş pazar payı ve ekosistem
- Ajans kullanımı için müşteri görünümü (guest access)
- Esnek yapı — çok sektöre uyum sağlar

**Zayıf Yönler:**
- **Brief yönetimi yok:** Yaratıcı brief şablonları, alan motoru, versiyon yönetimi yok
- **Onay portalı yok:** Müşteri için public onay arayüzü bulunmuyor
- **Beyaz etiket yok:** Kendi markanızla sunamıyorsunuz
- **iyzico yok:** Türk pazar için yerel ödeme yok
- **Abonelik yönetimi yok**
- Ajans kullanımı için heavy setup gerekiyor
- Misafir erişimi pahalı (4 misafir = 1 koltuk maliyeti)
- Brief/onay iş akışları için özel geliştirme gerekiyor

**Temel Konumlandırma:** *"Daha iyi çalışmanızı sağlayan platform"*

---

### 3.6 Türkiye Pazarı ve Yerel Çözümler

**Mevcut Durum:**

Türkiye'de ajans-marka brief ve onay yönetimi için özel bir SaaS çözümü pratikte yoktur. Ajanslar şu anda şunu kullanır:
- **Brief:** E-posta, Google Docs, Word şablonları
- **Onay:** WhatsApp grupları, e-posta zinciri
- **Takip:** Excel, Google Sheets
- **Raporlama:** Manuel PDF veya Canva tasarımı

**Edvido:** Türkiye'deki en bilinen "ajans" ürünü, aslında bir ajans bulucu marketplace'tir — proje yönetimi veya brief platformu değildir.

**Pazar Boşluğu:**
- Hiçbir yerel araç brief + onay + takvim + beyaz etiket bütünlüğünü Türkçe olarak sunmuyor
- iyzico entegrasyonu ile yerel ödeme: rakiplerin hiçbirinde yok
- Türkçe arayüz + Türk takvim konvansiyonu (Pazartesi başlangıçlı ISO hafta)
- WhatsApp bildirim mimarisine hazır altyapı (Türkiye'de WhatsApp iş iletişiminde dominant)
- KVKK uyumluluğu için yerel veri depolama hassasiyeti

---

## 4. Mesajlaşma Karşılaştırma Matrisi

| Boyut | Flobrief | Planable | Filestage | Ziflow | ClickUp | Monday.com |
|-------|----------|----------|-----------|--------|---------|------------|
| **Birincil tagline** | Brief yönetimi + onay platformu (ajanslar için) | "İşbirliği önce gelen sosyal medya aracı" | "Online proofing platformu" | "Kurumsal yaratıcı proofing" | "Hepsi bir arada PM" | "Daha iyi çalış" |
| **Hedef alıcı** | Türkiye/bölge ajans sahipleri + marka yöneticileri | Sosyal medya ajansları | Yaratıcı proje yöneticileri | Kurumsal kreatif ekipler | Genel PM kullanıcıları | Genel iş ekipleri |
| **Anahtar farklılaştırıcı** | Brief + onay + takvim + beyaz etiket + iyzico | Sosyal medya onay UX | Dosya proofing derinliği | Kurumsal iş akışı otomasyonu | Esneklik ve fiyat | Otomasyon ve entegrasyon |
| **Ton/Ses** | Premium, profesyonel, Türkiye odaklı | Samimi, modern, ajans dostu | Pratik, temiz, ekip odaklı | Kurumsal, güçlü, teknik | Enerjetik, kapsamlı | Kurumsal, güvenilir |
| **Temel değer önerisi** | Brief'ten onaya tek platform; yerel ödeme | Sosyal medya içerik onayı kolaylaştırır | Yaratıcı içerik incelemeyi hızlandırır | Kurumsal düzeyde proofing | Her şeyi bir yerde yönet | İş akışını otomatikleştir |
| **Fiyatlandırma yaklaşımı** | Workspace/tenant bazlı, iyzico ile yerel TL | Workspace bazlı ($33–59/ay) | Proje/team bazlı (€199–329/ay) | Kullanıcı bazlı ($249–399/ay) | Kullanıcı başına ($7–12/ay) | Koltuk başına ($9–19/ay) |

---

## 5. Özellik Karşılaştırması

| Özellik | Flobrief | Planable | Filestage | Ziflow | ClickUp | Monday.com |
|---------|----------|----------|-----------|--------|---------|------------|
| Brief şablon motoru | ✅ (dinamik, sektörel) | ❌ | ❌ | ❌ | ⚠️ (özel yapım) | ⚠️ (özel yapım) |
| Brief versiyon geçmişi | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Brief durum akışı | ✅ (5 aşama) | ❌ | ❌ | ❌ | ⚠️ (özel yapım) | ⚠️ (özel yapım) |
| Public onay portalı | ✅ (markalı) | ⚠️ (sosyal içerik) | ✅ (dosya) | ✅ (dosya) | ❌ | ❌ |
| Dosya proofing/açıklama | ⚠️ (temel) | ⚠️ (medya) | ✅ | ✅ | ❌ | ❌ |
| İçerik takvimi | ✅ | ✅ (sosyal) | ❌ | ❌ | ⚠️ (genel) | ⚠️ (genel) |
| Çok kiracılı mimari | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| Beyaz etiket branding | ✅ (logo, renk, domain) | ❌ | ⚠️ (inceleme alanı) | ⚠️ (sınırlı) | ❌ | ❌ |
| Raporlama + PDF ihracat | ✅ | ✅ (analitik ek) | ❌ | ❌ | ⚠️ | ⚠️ |
| Paylaşılabilir rapor linki | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| RBAC (çok rol) | ✅ (5 rol) | ⚠️ (2 rol) | ⚠️ | ⚠️ | ✅ | ✅ |
| E-posta bildirimleri | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| WhatsApp bildirimleri | ✅ (mimari hazır) | ❌ | ❌ | ❌ | ❌ | ❌ |
| Abonelik/fatura yönetimi | ✅ (iyzico) | ❌ | ❌ | ❌ | ❌ | ❌ |
| Türkçe ödeme (iyzico) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Platform admin paneli | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| İmmutable audit log | ✅ | ❌ | ❌ | ❌ | ⚠️ | ⚠️ |
| API erişimi | ✅ (FastAPI) | ⚠️ (Pro+) | ⚠️ (Enterprise) | ⚠️ (Enterprise) | ✅ | ✅ |
| Sosyal medya yayınlama | ❌ | ✅ (9 platform) | ❌ | ❌ | ❌ | ❌ |
| AI proofing / içerik | ❌ | ⚠️ | ❌ | ✅ (ZiflowAI) | ✅ (ek ücret) | ✅ |
| Varlık (asset) yönetimi | ✅ (versiyonlu) | ⚠️ (medya) | ✅ | ✅ | ⚠️ | ⚠️ |
| Entegrasyon ekosistemi | ❌ (v1) | ✅ | ✅ (20+) | ✅ | ✅ (geniş) | ✅ (geniş) |

*✅ = tam destek, ⚠️ = kısmi/özelleştirme gerektirir, ❌ = yok*

---

## 6. İçerik Boşluğu Analizi

### Flobrief'in Öne Çıkabileceği İçerik Konuları

| Konu | Rakipler | Flobrief Fırsatı |
|------|----------|------------------|
| Ajans brief sürecini nasıl dijitalleştirirsiniz | Neredeyse hiç içerik yok | Rehber, şablon, vaka çalışması |
| Türkiye'de ajans-marka ilişkisi yönetimi | Türkçe içerik yok | Türkçe blog, webinar |
| Onay sürecinde WhatsApp zincirinin maliyeti | Hiç içerik yok | Özgün araştırma + içerik |
| Beyaz etiket portal nasıl kurulur | Çok az içerik | Adım adım rehber |
| Ajans raporlaması: müşteriye ne sunmalı | Çeşitli içerik var | iyzico faturalamayla bütünleşik rehber |
| KPI takibi: brief döngüsü metrikleri | Yok | Özgün blog + PDF |

### Flobrief'in Olmadığı Ama Rakiplerin Ürettiği Konular

| Konu | Kim Üretiyor |
|------|-------------|
| Sosyal medya onay en iyi uygulamaları | Planable |
| Online proofing rehberi (video, PDF) | Filestage, Ziflow |
| Yaratıcı proje yönetimi nasıl yapılır | ClickUp, Monday |
| Kurumsal iş akışı otomasyonu | Monday, Ziflow |

---

## 7. Fırsatlar

### 7.1 Konumlandırma Boşlukları

1. **"Brief-to-approval" dikey platform:** Hiçbir rakip tüm brief yaşam döngüsünü (oluşturma → atama → versiyon → onay → takvim → raporlama) tek platformda sunmuyor. Flobrief bu boşluğu dolduruyor.

2. **Türkiye ve MENA pazarı için yerelleştirilmiş çözüm:**
   - iyzico ile yerel TL ödeme
   - Türkçe arayüz ve Türkçe şablonlar
   - Pazartesi başlangıçlı ISO hafta takvimi
   - KVKK uyumlu altyapı
   - WhatsApp bildirimi (Türkiye'de B2B iletişimde dominant)

3. **Ajans beyaz etiketi:** Rakipler arasında Filestage ve Ziflow çok sınırlı branding sunar. Flobrief'in tam markalı public portal + özel domain özelliği, ajanslara müşteri karşısında premium görünüm sağlar.

4. **Platform-as-a-platform:** Platform admin paneli ile çok ajansı yöneten SaaS operatörlerine satılabilir (agency-of-agencies veya franchising modeli).

### 7.2 Underserved Segmentler

- **Orta ölçekli Türk dijital ajanslar (5–50 kişi):** Mevcut araçlar ya çok pahalı (Ziflow, Filestage) ya da çok generic (ClickUp, Monday)
- **In-house marka ekipleri:** Birden fazla ajansla çalışan marka tarafı; brief başlatma ve onay takibini tek yerden yapmak istiyor
- **MENA ve Balkan pazarları:** İngilizce araçlara yabancı, Stripe kartı olmayan şirketler

---

## 8. Tehditler

### 8.1 Doğrudan Tehditler

| Tehdit | Kaynak | Olasılık | Etki |
|--------|--------|-----------|------|
| Planable brief yönetimi ekler | Planable | Orta | Yüksek |
| ClickUp "Ajans Modu" paketi çıkarır | ClickUp | Orta | Orta |
| Yeni Türk rakip çıkar (daha ucuz) | Yerli startup | Düşük | Yüksek |
| Monday.com Türkiye odaklı satış kampanyası | Monday | Düşük | Orta |

### 8.2 Yapısal Tehditler

- **AI destekli otomatik brief oluşturma:** Rakipler AI ile brief içeriğini otomatik üretirse; Flobrief'in şablon motoru basit kalabilir
- **Mega platform konsolidasyonu:** Adobe (Workfront) veya Salesforce bu segmenti satın alabilir
- **Entegrasyon eksikliği:** v1'de Slack, Asana, Jira entegrasyonu yok; kurumsal müşteriler vazgeçebilir

---

## 9. Flobrief'te Eksik Kalan Kritik Özellikler (v1 Sonrası Yol Haritası)

Aşağıdaki özellikler rekabet avantajı için önceliklendirilmeli:

### Yüksek Öncelik

| Özellik | Gerekçe | Hangi Rakip Baskı Yaratıyor |
|---------|----------|----------------------------|
| **Gelişmiş dosya proofing** (video timestamp, PDF açıklama, markup) | Brief'e eklenen tasarımları aynı platformda onaylamak | Filestage, Ziflow |
| **Slack / Microsoft Teams entegrasyonu** | Bildirim kanalı; enterprise müşteri beklentisi | Filestage (20+ entegrasyon) |
| **AI brief asistanı** (brief alanlarını otomatik doldur) | Ajans verimliliği; rekabetçi farklılaşma | ZiflowAI, ClickUp Brain |
| **Gerçek zamanlı WebSocket bildirimleri** | Post-launch roadmap'te zaten var; kullanıcı beklentisi | Planable, Filestage |
| **Mobil uygulama veya PWA** | Marka onay sürecinde mobil kullanım yaygın | Planable (mobil uyumlu) |

### Orta Öncelik

| Özellik | Gerekçe |
|---------|---------|
| **Zapier / Make entegrasyonu** | Diğer araçlarla birleştirilebilirlik |
| **Toplu brief ihracat (CSV/Excel)** | Kurumsal müşteri talebi |
| **E-posta şablon editörü (görsel)** | Marka bildirimi özelleştirmesi |
| **Çok dilli portal** (EN + TR) | MENA genişlemesi |
| **S3/R2 depolama** | Production ölçeği için (post-launch roadmap'te var) |
| **Sentry + OpenTelemetry** | Canlı hata takibi ve observability |

### Uzun Vadeli

| Özellik | Gerekçe |
|---------|---------|
| **Sosyal medya yayın entegrasyonu** | Takvim öğelerini doğrudan yayınlama |
| **Gelir paylaşım modeli** (ajans alt hesapları) | Ajans-müşteri faturalandırma |
| **Stripe entegrasyonu** | Uluslararası genişleme |
| **Playwright E2E test** | QA güvencesi (post-launch roadmap'te var) |

---

## 10. Önerilen Eylemler

### Hızlı Kazanımlar (Bu Hafta / Bu Ay)

1. **"Flobrief vs Planable" ve "Flobrief vs Filestage" karşılaştırma sayfaları oluşturun** — SEO'da "brief approval software Turkey" için öne geçin
2. **Türkçe blog içeriği başlatın:** "E-postayla brief yönetiminin ajansınıza maliyeti ne?" — organic trafik için
3. **Demo seed scriptini satış demosu olarak hazırlayın** — potansiyel müşterilere interaktif demo linki gönderin
4. **WhatsApp Business kaydına başlayın** — Meta onay süreci uzun; erkenden başlanmalı

### Stratejik Hamleler (3–6 Ay)

5. **Slack entegrasyonu ekleyin** — enterprise ajansların vazgeçmeme nedeni Slack bildirimleri
6. **AI brief asistanı:** Brief alanlarını sektör şablonuna göre öneren basit bir LLM çağrısı yüksek algısal değer yaratır
7. **Filestage benzeri dosya markup:** Brief'e eklenen tasarım dosyalarına yorum düşme özelliği Ziflow/Filestage'e gerek bırakmaz
8. **"Türkiye'nin Ajans SaaS Raporu" araştırması yayınlayın** — marka bilinirliği + PR + organik link için özgün veri

---

## 11. Konumlandırma Haritası

```
                    KURUMSAL / BÜYÜK ÖLÇEK
                            │
            Ziflow ●        │
                            │
    Filestage ●             │
                            │
DOSYA / DOSYA               │                    BRIEF / İŞ AKIŞI
PROOFING ───────────────────┼──────────────── ODAKLI
                            │
              Monday.com ●  │   ● Flobrief
                            │     (hedef konum)
        ClickUp ●           │
                            │
              Planable ●    │
                            │
                    KÜÇÜK / KİŞİSEL
```

Flobrief'in hedef konum: **Brief-iş akışı odaklı + orta ölçek ajans** — Ziflow ve Filestage'in fiyat olarak ulaşamadığı, ClickUp ve Monday'in özellik derinliğinden yoksun olduğu bölge.

---

## Kaynaklar

- [Planable Fiyatlandırma](https://planable.io/pricing/)
- [Filestage Fiyatlandırma](https://filestage.io/pricing/)
- [Ziflow Fiyatlandırma](https://www.ziflow.com/pricing)
- [ClickUp Fiyatlandırma](https://clickup.com/pricing)
- [Monday.com Planları](https://support.monday.com/hc/en-us/articles/4405633151634-Plans-and-pricing-for-monday-com)
- [G2 Filestage vs Ziflow](https://www.g2.com/compare/filestage-vs-ziflow)
- [Filestage vs Ziflow Karşılaştırması](https://filestage.io/filestage-vs-ziflow/)
- [Top Ziflow Alternatifleri 2026](https://filestage.io/blog/ziflow-alternatives/)
- [En İyi Müşteri Onay Uygulamaları 2026](https://quantumbyte.ai/articles/best-client-approval-software-2026)
- [Ajans Yönetim Yazılımı Pazar Raporu](https://dataintelo.com/report/agency-management-software-market)
