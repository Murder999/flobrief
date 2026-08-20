export type LandingSlug =
  | "ajans-programi"
  | "musteri-onay-sistemi"
  | "revizyon-takip"
  | "musteri-portali"
  | "online-brief";

export interface LandingFeature {
  title: string;
  description: string;
  icon: "brief" | "message" | "check" | "history" | "portal" | "file" | "palette" | "users";
}

export interface LandingPageConfig {
  slug: LandingSlug;
  badge: string;
  h1: string;
  description: string;
  title: string;
  metaDescription: string;
  visual: "agency" | "approval" | "revision" | "portal" | "brief";
  hero: "split" | "centered";
  tone: "indigo" | "emerald" | "amber" | "violet" | "blue";
  problem: { eyebrow: string; title: string; description: string; points: string[] };
  solution: { eyebrow: string; title: string; description: string };
  workflow: { title: string; description: string; steps: string[] };
  features: LandingFeature[];
  scenario: { title: string; description: string; agency: string; customer: string };
  proof: string[];
  related: LandingSlug[];
  sectionOrder: Array<"problem" | "workflow" | "features" | "scenario">;
}

export const SEO_LANDING_PAGES: Record<LandingSlug, LandingPageConfig> = {
  "ajans-programi": {
    slug: "ajans-programi",
    badge: "Ajans operasyonu, tek akışta",
    h1: "Ajans Programı — Brief, Müşteri, Revizyon ve Onay Yönetimi",
    description: "Müşteri brieflerinden ekip işlerine, revizyonlardan son onaya kadar ajans operasyonunuzu tek platformda yönetin.",
    title: "Ajans Programı: Brief, Revizyon ve Onay Yönetimi | PostPiloter",
    metaDescription: "Ajans brieflerini, müşteri işlerini, revizyonları ve onayları tek akışta yönetin. PostPiloter ile ajans operasyonunu düzenleyin.",
    visual: "agency",
    hero: "split",
    tone: "indigo",
    problem: {
      eyebrow: "Dağınık operasyon",
      title: "Müşteri iletişimi farklı kanallara dağıldığında işin resmi kaybolur",
      description: "WhatsApp mesajları, e-posta zincirleri ve ayrı dosyalar; briefin ne olduğunu, son revizyonu ve onay durumunu ekip için belirsiz hale getirir.",
      points: ["Farklı yerlerden gelen briefler", "Mesajlarda kaybolan revizyonlar", "Görünmeyen onay ve teslim durumu"],
    },
    solution: {
      eyebrow: "PostPiloter yaklaşımı",
      title: "Genel amaçlı CRM değil, ajans–müşteri kreatif operasyonu",
      description: "Her işi müşterisi, briefi, yorumları, revizyonları, teslimleri ve onay durumuyla birlikte takip edin. Ajans ekibi ve müşteri aynı sürecin güncel halini görsün.",
    },
    workflow: {
      title: "Müşteriden teslime görünür bir iş akışı",
      description: "Her adım bir öncekinin bağlamını korur; ekip yeniden bilgi toplamak yerine işin kendisine odaklanır.",
      steps: ["Müşteri", "Brief", "İş", "Revizyon", "Onay", "Teslim"],
    },
    features: [
      { title: "Standart brief akışı", description: "Müşteri taleplerini aynı yapıda toplayın ve ekip için net bir başlangıç noktası oluşturun.", icon: "brief" },
      { title: "İşe bağlı iletişim", description: "Yorumları ve değişiklik taleplerini ilgili brief ve teslim üzerinde tutun.", icon: "message" },
      { title: "Onay durumu", description: "İnceleme, revizyon ve onay aşamalarını aynı iş kaydında görün.", icon: "check" },
      { title: "Müşteri çalışma alanı", description: "Müşterinin kendi brieflerini, işleri, dosyaları ve onay bekleyen içerikleri izlemesini sağlayın.", icon: "portal" },
    ],
    scenario: {
      title: "Kampanya talebi geldiğinde herkes aynı bağlamda ilerler",
      description: "Müşteri briefi kendi alanından iletir. Ajans işi üretime alır, teslimi paylaşır ve geri bildirimi doğrudan iş üzerinde toplar.",
      agency: "Ajans, sorumluluğu ve işin güncel durumunu tek ekrandan takip eder.",
      customer: "Müşteri, hangi çalışmanın incelendiğini ve son kararın ne olduğunu görür.",
    },
    proof: ["Dinamik brief formları", "Yorum ve revizyon akışı", "Müşteri portalı"],
    related: ["musteri-onay-sistemi", "revizyon-takip", "musteri-portali", "online-brief"],
    sectionOrder: ["problem", "workflow", "features", "scenario"],
  },
  "musteri-onay-sistemi": {
    slug: "musteri-onay-sistemi",
    badge: "Net geri bildirim, görünür karar",
    h1: "Müşteri Onay Sistemi — Tasarım ve İçerik Onaylarını Tek Yerde Yönetin",
    description: "İşi paylaşın, müşteri incelesin, yorumunu bıraksın; revizyon ve onay kararı aynı çalışma alanında ilerlesin.",
    title: "Müşteri Onay Sistemi: Tasarım ve İçerik Onayı | PostPiloter",
    metaDescription: "Tasarım ve içerik onaylarını tek yerde yönetin. Müşteri yorumlarını işe bağlayın, revizyonu izleyin ve onaylanan versiyonu görün.",
    visual: "approval",
    hero: "centered",
    tone: "emerald",
    problem: {
      eyebrow: "Karar nerede kaldı?",
      title: "Onay mesaj zincirinde kaldığında hangi çalışmanın kabul edildiği belirsizleşir",
      description: "Dosya ayrı yerde, yorum başka kanalda, son karar ise bir e-postanın içinde kaldığında ekip tekrar tekrar teyit ister.",
      points: ["Onayın ilgili işe bağlanmaması", "Eski ve yeni teslimin karışması", "Revizyon talebinin görünür olmaması"],
    },
    solution: {
      eyebrow: "Tek karar noktası",
      title: "Teslim, yorum, revizyon ve onay aynı bağlamda",
      description: "Müşteri sunulan çalışmayı inceler, yorum bırakır, revizyon ister veya onaylar. Durum iş kaydına yansır ve ekip hangi teslim üzerinde karar verildiğini görür.",
    },
    workflow: {
      title: "İncelemeden son karara beş net adım",
      description: "Geri bildirimi işin dışına taşımadan onay sürecini tamamlayın.",
      steps: ["İşi paylaş", "Müşteri incelesin", "Yorum bıraksın", "Revizyon yapılsın", "Onay alınsın"],
    },
    features: [
      { title: "Teslime bağlı yorumlar", description: "Geri bildirimi ilgili çalışma ve teslim bağlamında tutun.", icon: "message" },
      { title: "Açık durumlar", description: "İncelemede, revizyon istendi ve onaylandı gibi durumları ayırt edin.", icon: "check" },
      { title: "Versiyon görünürlüğü", description: "Teslim sürümünü ve onay durumunu aynı çalışma alanında görün.", icon: "history" },
      { title: "Müşteri erişimi", description: "Müşterinin kendi portalından inceleme ve karar sürecine katılmasını sağlayın.", icon: "portal" },
    ],
    scenario: {
      title: "Sosyal medya tasarımı onaya çıktığında",
      description: "Ajans teslimi incelemeye sunar. Müşteri görseli değerlendirir, gerekli değişikliği yorum olarak iletir ve güncel teslimi onaylar.",
      agency: "Ajans hangi yorumun açık olduğunu ve hangi teslimin onaylandığını takip eder.",
      customer: "Müşteri kararını dosya aramadan, ilgili işin içinden verir.",
    },
    proof: ["Teslim durumları", "Yorum ve revizyon noktaları", "Onay kaydı"],
    related: ["revizyon-takip", "musteri-portali", "ajans-programi"],
    sectionOrder: ["workflow", "problem", "features", "scenario"],
  },
  "revizyon-takip": {
    slug: "revizyon-takip",
    badge: "Geri bildirim kaybolmasın",
    h1: "Revizyon Takip Sistemi — Müşteri Geri Bildirimlerini Kaybetmeyin",
    description: "WhatsApp, e-posta ve farklı mesaj zincirlerine dağılan revizyonları ilgili iş, teslim ve yorum bağlamında takip edin.",
    title: "Revizyon Takip Sistemi: Müşteri Geri Bildirimleri | PostPiloter",
    metaDescription: "Müşteri revizyonlarını ilgili işe bağlayın. Yorumları, değişiklik taleplerini, teslim sürümlerini ve son onaya kadar ilerlemeyi izleyin.",
    visual: "revision",
    hero: "split",
    tone: "amber",
    problem: {
      eyebrow: "En yaygın darboğaz",
      title: "Revizyonların WhatsApp, e-posta ve mesaj zincirlerinde kaybolması",
      description: "Dağınık geri bildirim ekipte aynı soruyu tekrar doğurur: Hangi değişiklik yapıldı, hangisi açık ve müşteri son olarak neyi onayladı?",
      points: ["Birbiriyle çelişen yorumlar", "Kapanmayan değişiklik talepleri", "Teslim geçmişinin karışması"],
    },
    solution: {
      eyebrow: "İşe bağlı revizyon yönetimi",
      title: "Her değişiklik talebini ait olduğu çalışmada tutun",
      description: "Yorumları ve görsel üzerindeki revizyon noktalarını teslimle ilişkilendirin. Sürümler ve açık geri bildirimler görünür kalsın; süreç son onaya kadar izlenebilsin.",
    },
    workflow: {
      title: "Revizyon döngüsünü kapatan akış",
      description: "Talebin kaynağını, güncel teslimi ve sonucu aynı bağlamda koruyun.",
      steps: ["Teslimi paylaş", "Geri bildirimi topla", "Revizyonu uygula", "Yeni sürümü sun", "Son onayı al"],
    },
    features: [
      { title: "Revizyon noktaları", description: "Görsel teslim üzerinde değişiklik istenen alanı işaretleyin ve açıklamayı bağlayın.", icon: "message" },
      { title: "Teslim sürümleri", description: "Güncel teslimi ve önceki sürümleri aynı iş alanında ayırt edin.", icon: "history" },
      { title: "Açık geri bildirimler", description: "Açık revizyon noktalarını görün ve yanıtlarla birlikte takip edin.", icon: "check" },
      { title: "Merkezi dosyalar", description: "Teslim dosyalarını ilgili brief ve iş bağlamında saklayın.", icon: "file" },
    ],
    scenario: {
      title: "Bir kampanya görseli birkaç tur revizyon aldığında",
      description: "Müşteri değişiklik noktalarını teslim üzerinde iletir. Ajans yeni sürümü ekler ve açık talepleri gözden geçirerek son onaya ilerler.",
      agency: "Ekip hangi talebin hangi sürümde ele alındığını görür.",
      customer: "Müşteri eski mesajları aramadan güncel teslim üzerinden ilerler.",
    },
    proof: ["Görsel revizyon noktaları", "Teslim versiyon şeridi", "Açık yorum takibi"],
    related: ["musteri-onay-sistemi", "ajans-programi", "musteri-portali"],
    sectionOrder: ["problem", "features", "workflow", "scenario"],
  },
  "musteri-portali": {
    slug: "musteri-portali",
    badge: "Müşterinize profesyonel bir çalışma alanı",
    h1: "Ajanslar İçin Müşteri Portalı",
    description: "Müşteriler brieflerini, işleri, yorumları, revizyonları, onayları ve kendileriyle paylaşılan dosyaları tek alandan takip etsin.",
    title: "Ajanslar İçin Müşteri Portalı | PostPiloter",
    metaDescription: "Ajans müşterilerinize brief, iş, yorum, revizyon, onay ve dosyaları tek alanda sunun. Markanıza uyarlanabilen profesyonel portal deneyimi.",
    visual: "portal",
    hero: "split",
    tone: "violet",
    problem: {
      eyebrow: "Müşteri deneyimi",
      title: "Profesyonel iş üretmek kadar süreci profesyonel sunmak da önemli",
      description: "Müşteri güncel işi, bekleyen onayı veya paylaşılan dosyayı bulmak için ajans ekibine tekrar yazmak zorunda kalmamalı.",
      points: ["Sürecin müşteriye görünmemesi", "Dosyaların farklı kanallarda kalması", "Brief ve onayların kopuk ilerlemesi"],
    },
    solution: {
      eyebrow: "Müşteriye ait alan",
      title: "Her müşteri kendi markasının güncel iş akışını görür",
      description: "Portal; briefleri, işleri, içerik takvimini, yorumları, revizyonları, onayları ve müşteriyle paylaşılmış dosyaları tek deneyimde bir araya getirir.",
    },
    workflow: {
      title: "Ajansın yönettiği, müşterinin kolayca takip ettiği deneyim",
      description: "Müşteri yalnızca kendi çalışma alanındaki bilgileri ve kendisiyle paylaşılan süreçleri görür.",
      steps: ["Müşteri giriş yapar", "Briefini iletir", "İşi takip eder", "Teslimi inceler", "Yorum veya onay verir"],
    },
    features: [
      { title: "Müşteri dashboardu", description: "Güncel briefleri, yaklaşan işleri ve aksiyon bekleyen başlıkları aynı alanda gösterin.", icon: "portal" },
      { title: "Brief ve dosyalar", description: "Müşterinin brief oluşturmasını ve ilgili dosyaları iş bağlamında paylaşmasını sağlayın.", icon: "file" },
      { title: "Yorum, revizyon, onay", description: "Geri bildirim ve karar akışını müşterinin kendi çalışma alanına taşıyın.", icon: "check" },
      { title: "White-label görünüm", description: "Portal deneyimini ajans adı, logo ve renk ayarlarıyla markanıza uyarlayın.", icon: "palette" },
    ],
    scenario: {
      title: "Yeni bir müşteri ajansla çalışmaya başladığında",
      description: "Müşteri portalından brief oluşturur, ajansın paylaştığı işi izler ve teslim üzerinde geri bildirim verir. Süreç tek bir profesyonel arayüzde ilerler.",
      agency: "Ajans müşteri iletişimini iş kayıtlarıyla birlikte yönetir.",
      customer: "Müşteri kendi markasına ait işleri ve dosyaları tek alanda bulur.",
    },
    proof: ["Marka bazlı müşteri alanı", "Logo ve renk ayarları", "Müşteriye açık dosyalar"],
    related: ["online-brief", "musteri-onay-sistemi", "revizyon-takip", "ajans-programi"],
    sectionOrder: ["features", "problem", "scenario", "workflow"],
  },
  "online-brief": {
    slug: "online-brief",
    badge: "Eksiksiz talepler, ortak başlangıç noktası",
    h1: "Online Brief Oluşturma — Ajanslar İçin Dijital Brief Formu",
    description: "Briefi standartlaştırın, müşteriden dijital olarak toplayın, işe dönüştürün ve süreç boyunca aynı kayıt üzerinden takip edin.",
    title: "Online Brief Oluşturma: Dijital Brief Formu | PostPiloter",
    metaDescription: "Ajanslar için online brief formu ile müşteri taleplerini standartlaştırın. Briefi dijital toplayın, işe dönüştürün ve süreç boyunca takip edin.",
    visual: "brief",
    hero: "centered",
    tone: "blue",
    problem: {
      eyebrow: "Eksik bilgi döngüsü",
      title: "WhatsApp’tan gelen talepler ekip için eksiksiz bir brief değildir",
      description: "Farklı formatlarda gelen müşteri bilgileri kritik soruları açıkta bırakır; ekip aynı detayları tekrar tekrar sormak zorunda kalır.",
      points: ["Eksik hedef ve kapsam", "Farklı formatlarda talepler", "Ekibin farklı bilgilerle ilerlemesi"],
    },
    solution: {
      eyebrow: "Standart dijital brief",
      title: "Her talebi doğru sorularla, tek yapıda toplayın",
      description: "PostPiloter’ın brief şablonları ve dinamik alanlarıyla müşteriden gereken bilgileri düzenli biçimde alın. Brief kaydı işin geri kalanına bağlansın.",
    },
    workflow: {
      title: "Briefi standartlaştır, müşteriden topla, işe dönüştür",
      description: "Bu sayfa ücretsiz bağımsız bir brief üreticisi değil; PostPiloter içindeki gerçek brief yönetimi akışını anlatır.",
      steps: ["Şablonu belirle", "Soruları düzenle", "Müşteriden topla", "İşe dönüştür", "Süreçte takip et"],
    },
    features: [
      { title: "Dinamik alanlar", description: "Metin, seçim, tarih, bağlantı ve diğer desteklenen alanlarla ihtiyaca uygun brief yapısı kurun.", icon: "brief" },
      { title: "Bölümlü form", description: "Soruları anlaşılır bölümlerde sunun ve gerekli alanları açıkça belirtin.", icon: "check" },
      { title: "Dosya ekleri", description: "Müşterinin destekleyici dosyaları brief kaydına eklemesini sağlayın.", icon: "file" },
      { title: "Ortak iş kaydı", description: "Toplanan briefi yorum, üretim, teslim ve onay sürecinin başlangıç noktası yapın.", icon: "users" },
    ],
    scenario: {
      title: "Yeni kampanya talebi geldiğinde eksik bilgiyle başlamayın",
      description: "Müşteri hedef, kapsam, tarih ve gerekli dosyaları aynı brief içinde paylaşır. Ajans ekibi aynı bilgi setini görerek işi değerlendirir.",
      agency: "Ajans, iş başlamadan önce talebin kapsamını tek yerde inceler.",
      customer: "Müşteri, dağınık mesajlar yerine yönlendirilmiş bir form üzerinden talebini iletir.",
    },
    proof: ["Brief şablonları", "Dinamik form alanları", "Brief dosya ekleri"],
    related: ["ajans-programi", "musteri-portali", "musteri-onay-sistemi"],
    sectionOrder: ["workflow", "features", "problem", "scenario"],
  },
};
