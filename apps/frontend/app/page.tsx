"use client";

import {
  motion,
  AnimatePresence,
  useReducedMotion,
  useMotionValue,
  useTransform,
  useSpring,
  useInView,
} from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  FileText, Calendar, BarChart3, Users, Layers, Zap,
  CheckCircle, ArrowRight, ChevronRight, Star,
  Shield, Clock, TrendingUp, Sparkles, Bell,
  Building2, MessageSquare, Mail,
} from "lucide-react";
import { LoginModal } from "@/components/auth/LoginModal";

/* ── Motion presets ──────────────────────────────────────────────────────── */

const ES = [0.16, 1, 0.3, 1] as const;
const vUp = { hidden: { opacity: 0, y: 18 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: ES } } };
const vStagger = { hidden: {}, visible: { transition: { staggerChildren: 0.09, delayChildren: 0.06 } } };
const VP = { once: true, margin: "-80px" } as const;

/* ── Data ────────────────────────────────────────────────────────────────── */

const stats = [
  { value: "12×",  label: "daha hızlı brief süreci",   icon: Clock      },
  { value: "%94",  label: "e-posta trafiğinde azalma", icon: TrendingUp },
  { value: "3×",   label: "daha hızlı revize döngüsü", icon: Zap        },
  { value: "1 dk", label: "yeni marka onboarding",     icon: Star       },
] as const;

const logos = [
  "Nike TR", "L'Oréal", "Zara Home", "Vodafone", "Ülker", "Garanti",
  "Nike TR", "L'Oréal", "Zara Home", "Vodafone", "Ülker", "Garanti",
];

const mockBriefs = [
  { name: "Q3 Sosyal Medya Kampanyası", brand: "Nike TR",     status: "Onay Bekliyor", statusClass: "status-warning", dot: "bg-warning" },
  { name: "Yılbaşı E-posta Şablonları", brand: "Zara Home",  status: "Onaylandı",     statusClass: "status-success", dot: "bg-success" },
  { name: "Influencer Brief Pack",       brand: "L'Oréal TR", status: "Revize İstendi",statusClass: "status-danger",  dot: "bg-danger"  },
  { name: "Brand Awareness Kampanyası",  brand: "Vodafone TR",status: "Üretimde",       statusClass: "status-purple",  dot: "bg-purple"  },
];

const LIFECYCLE_STAGES = [
  { id: "draft",         label: "Taslak",       cls: "status-neutral", desc: "Brief oluşturuldu, detaylar tamamlanmayı bekliyor."    },
  { id: "submitted",     label: "Gönderildi",   cls: "status-accent",  desc: "Marka yöneticisine inceleme için iletildi."            },
  { id: "in_review",     label: "İncelemede",   cls: "status-info",    desc: "Marka ekibi brief içeriğini gözden geçiriyor."         },
  { id: "accepted",      label: "Kabul Edildi", cls: "status-purple",  desc: "Brief yapısı onaylandı, üretime geçmeye hazır."        },
  { id: "in_production", label: "Üretimde",     cls: "status-purple",  desc: "Ajans ekibi içerik üretimini aktif olarak yürütüyor."  },
  { id: "revision",      label: "Revizyon",     cls: "status-danger",  desc: "Marka geri bildirim gönderdi, revizyon gerekiyor."     },
  { id: "approved",      label: "Onaylandı",    cls: "status-success", desc: "Marka nihai onayı verdi, içerik hazır."                },
  { id: "published",     label: "Yayınlandı",   cls: "status-success", desc: "İçerik başarıyla yayına alındı. Süreç tamamlandı."     },
] as const;

/* ── Mini UI: Brief form reveal ──────────────────────────────────────────── */

const BRIEF_FIELDS = [
  { label: "Brief Adı",    value: "Q3 Sosyal Medya Kampanyası" },
  { label: "Marka",        value: "Nike TR"                    },
  { label: "Platform",     value: "Instagram · TikTok"         },
  { label: "Hedef Kitle",  value: "18-34, sport & lifestyle"   },
] as const;

function BriefMiniUI({ reduced }: { reduced: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!inView) return;
    if (reduced) { setStep(BRIEF_FIELDS.length); return; }
    const timers = BRIEF_FIELDS.map((_, i) =>
      setTimeout(() => setStep(i + 1), 400 + i * 400)
    );
    return () => timers.forEach(clearTimeout);
  }, [inView, reduced]);

  return (
    <div ref={ref} className="space-y-2">
      {BRIEF_FIELDS.map((f, i) => (
        <motion.div
          key={f.label}
          initial={{ opacity: 0, y: 8 }}
          animate={step > i ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
          transition={{ duration: 0.3, ease: ES }}
          className="rounded-lg border border-border bg-background px-3 py-2"
        >
          <div className="text-[9px] text-text-muted mb-0.5 uppercase tracking-wider">{f.label}</div>
          <div className="text-xs font-medium text-text">{f.value}</div>
        </motion.div>
      ))}
      <AnimatePresence>
        {step >= BRIEF_FIELDS.length && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.28, ease: ES }}
            className="w-full rounded-lg py-2 text-center text-xs font-semibold text-white cursor-default"
            style={{ background: "var(--gradient-accent)" }}
          >
            Brief Gönder →
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Mini UI: Approval cycle ─────────────────────────────────────────────── */

interface ApprovalPhase {
  label: string;
  cls: string;
  comment: string | null;
  commentCls: string;
}

const APPROVAL_PHASES: ApprovalPhase[] = [
  { label: "V1 Gönderildi", cls: "status-accent",  comment: null,                                                            commentCls: ""                                            },
  { label: "Revizyon",       cls: "status-danger",  comment: "Logo boyutu küçültülmeli, metin daha belirgin olabilir.",       commentCls: "border-danger-border bg-danger-subtle text-danger-text"   },
  { label: "V2 Yüklendi",    cls: "status-info",    comment: null,                                                            commentCls: ""                                            },
  { label: "Onaylandı ✓",   cls: "status-success", comment: "Mükemmel, yayına girebilir!",                                   commentCls: "border-success-border bg-success-subtle text-success-text" },
];

const PHASE_DOT = ["bg-accent", "bg-danger", "bg-info", "bg-success"];

function ApprovalMiniUI({ reduced }: { reduced: boolean }) {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => setPhase(p => (p + 1) % APPROVAL_PHASES.length), 2400);
    return () => clearInterval(id);
  }, [reduced]);

  const p = APPROVAL_PHASES[phase];

  return (
    <div className="space-y-3">
      {/* Phase dots row */}
      <div className="flex items-center gap-1.5">
        {APPROVAL_PHASES.map((ap, i) => (
          <div key={ap.label} className="flex items-center gap-1.5">
            <div
              className={`w-6 h-6 rounded-full text-[9px] font-bold flex items-center justify-center transition-all duration-300 ${
                i === phase
                  ? `${PHASE_DOT[i]} text-white scale-110`
                  : i < phase
                    ? "bg-success-subtle text-success-text"
                    : "bg-surface-2 text-text-muted"
              }`}
            >
              {i < phase ? "✓" : i + 1}
            </div>
            {i < APPROVAL_PHASES.length - 1 && (
              <div
                className={`h-px w-5 flex-shrink-0 transition-colors duration-500 ${
                  i < phase ? "bg-success/50" : "bg-border"
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Status badge */}
      <AnimatePresence mode="wait">
        <motion.span
          key={`status-${phase}`}
          className={`inline-flex text-[10px] font-medium px-2.5 py-1 rounded-full ${p.cls}`}
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.85 }}
          transition={{ duration: 0.18 }}
        >
          {p.label}
        </motion.span>
      </AnimatePresence>

      {/* Comment */}
      <AnimatePresence>
        {p.comment && (
          <motion.div
            key={`comment-${phase}`}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className={`rounded-lg border px-3 py-2 text-[10px] leading-relaxed ${p.commentCls}`}>
              {p.comment}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Mini UI: Calendar cards ─────────────────────────────────────────────── */

const CAL_DAYS = ["Pt", "Sa", "Ça", "Pe", "Cu"];
const CAL_ITEMS = [
  { col: 0, row: 0, label: "Nike Brief",  cls: "status-accent"  },
  { col: 2, row: 0, label: "Zara Story",  cls: "status-info"    },
  { col: 4, row: 0, label: "Vodafone",    cls: "status-warning" },
  { col: 1, row: 1, label: "L'Oréal",    cls: "status-purple"  },
  { col: 3, row: 1, label: "Nike TR V2",  cls: "status-success" },
] as const;

function CalendarMiniUI({ reduced }: { reduced: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!inView) return;
    if (reduced) { setCount(CAL_ITEMS.length); return; }
    const timers = CAL_ITEMS.map((_, i) =>
      setTimeout(() => setCount(i + 1), 350 + i * 320)
    );
    return () => timers.forEach(clearTimeout);
  }, [inView, reduced]);

  return (
    <div ref={ref}>
      <div className="grid grid-cols-5 gap-1 mb-1">
        {CAL_DAYS.map(d => (
          <div key={d} className="text-center text-[9px] text-text-muted font-medium py-0.5">{d}</div>
        ))}
      </div>
      {[0, 1].map(row => (
        <div key={row} className="grid grid-cols-5 gap-1 mb-1">
          {CAL_DAYS.map((_, col) => {
            const item = CAL_ITEMS.find(c => c.col === col && c.row === row);
            const idx = item ? CAL_ITEMS.indexOf(item) : -1;
            const show = item !== undefined && idx < count;
            return (
              <div key={col} className="h-9 rounded-lg border border-border bg-background relative overflow-hidden">
                {show && item && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.7 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.28, ease: ES }}
                    className={`absolute inset-0.5 rounded flex items-center justify-center ${item.cls}`}
                  >
                    <span className="text-[7px] font-semibold leading-tight text-center px-0.5">{item.label}</span>
                  </motion.div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

/* ── Mini UI: Reporting bars ─────────────────────────────────────────────── */

const METRICS = [
  { label: "Brief tamamlanma",    pct: 87, cls: "bg-accent"   },
  { label: "Zamanında teslim",    pct: 94, cls: "bg-success"  },
  { label: "İlk onay oranı",      pct: 71, cls: "bg-info"     },
  { label: "Müşteri memnuniyeti", pct: 96, cls: "bg-purple"   },
] as const;

function ReportingMiniUI({ reduced }: { reduced: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });

  return (
    <div ref={ref} className="space-y-2.5">
      {METRICS.map((m, i) => (
        <div key={m.label}>
          <div className="flex justify-between text-[10px] mb-1">
            <span className="text-text-muted">{m.label}</span>
            <span className="font-semibold text-text">{m.pct}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
            <motion.div
              className={`h-full rounded-full ${m.cls}`}
              initial={{ width: 0 }}
              animate={inView ? { width: `${m.pct}%` } : { width: 0 }}
              transition={{ duration: reduced ? 0 : 0.9, ease: ES, delay: reduced ? 0 : i * 0.1 }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Mini UI: Notification stack ─────────────────────────────────────────── */

const NOTIFS = [
  { Icon: CheckCircle, text: "Zara Home brief onayladı",  time: "Az önce", iconCls: "text-success", bgCls: "bg-success-subtle" },
  { Icon: Bell,        text: "Nike TR revizyon istedi",   time: "2 dk",    iconCls: "text-warning", bgCls: "bg-warning-subtle" },
  { Icon: FileText,    text: "Yeni brief: Vodafone Q4",   time: "15 dk",   iconCls: "text-accent",  bgCls: "bg-accent-subtle"  },
  { Icon: Users,       text: "L'Oréal TR ekibe katıldı", time: "1 sa",    iconCls: "text-info",    bgCls: "bg-info-subtle"    },
] as const;

function NotifMiniUI({ reduced }: { reduced: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });

  return (
    <div ref={ref} className="space-y-1.5">
      {NOTIFS.map((n, i) => (
        <motion.div
          key={n.text}
          initial={{ opacity: 0, x: 14 }}
          animate={inView ? { opacity: 1, x: 0 } : { opacity: 0, x: 14 }}
          transition={{ duration: reduced ? 0 : 0.35, delay: reduced ? 0 : i * 0.12, ease: ES }}
          className="flex items-center gap-2.5 rounded-lg border border-border bg-background p-2"
        >
          <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${n.bgCls}`}>
            <n.Icon className={`w-3 h-3 ${n.iconCls}`} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[10px] font-medium text-text truncate">{n.text}</div>
          </div>
          <div className="text-[9px] text-text-muted flex-shrink-0">{n.time}</div>
        </motion.div>
      ))}
    </div>
  );
}

/* ── Mini UI: Team workload ──────────────────────────────────────────────── */

const TEAM_MEMBERS = [
  { name: "Ahmet Y.",  role: "Kreatif",  count: 5, max: 8, cls: "bg-accent"  },
  { name: "Selin K.",  role: "Strateji", count: 3, max: 8, cls: "bg-info"    },
  { name: "Murat D.",  role: "Tasarım",  count: 6, max: 8, cls: "bg-purple"  },
  { name: "Zeynep A.", role: "Yönetim",  count: 2, max: 8, cls: "bg-success" },
] as const;

function TeamsMiniUI({ reduced }: { reduced: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });

  return (
    <div ref={ref} className="space-y-2.5">
      {TEAM_MEMBERS.map((m, i) => (
        <motion.div
          key={m.name}
          initial={{ opacity: 0, y: 8 }}
          animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
          transition={{ duration: reduced ? 0 : 0.35, delay: reduced ? 0 : i * 0.1, ease: ES }}
          className="flex items-center gap-2.5"
        >
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0"
            style={{ background: "var(--color-accent)" }}
          >
            {m.name[0]}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex justify-between text-[10px] mb-0.5">
              <span className="font-medium text-text">{m.name}</span>
              <span className="text-text-muted">{m.count} brief</span>
            </div>
            <div className="h-1 rounded-full bg-surface-2 overflow-hidden">
              <motion.div
                className={`h-full rounded-full ${m.cls}`}
                initial={{ width: 0 }}
                animate={inView ? { width: `${(m.count / m.max) * 100}%` } : { width: 0 }}
                transition={{ duration: reduced ? 0 : 0.7, ease: ES, delay: reduced ? 0 : 0.3 + i * 0.1 }}
              />
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  );
}

/* ── Brief Card Body (stage-specific content) ────────────────────────────── */

function BriefCardBody({ idx }: { idx: number }) {
  if (idx === 0) return (
    <div className="space-y-4">
      <div>
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-text-muted">Brief tamamlanma</span>
          <span className="font-semibold text-warning">65%</span>
        </div>
        <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
          <div className="h-full w-[65%] rounded-full bg-warning" />
        </div>
      </div>
      <div>
        <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2">Tamamlanmayı bekleyen alanlar</div>
        <div className="space-y-1.5">
          {["Platform seçimi", "Hedef kitle demografisi", "Bütçe aralığı"].map(f => (
            <div key={f} className="flex items-center gap-2 text-xs">
              <div className="w-3.5 h-3.5 rounded border border-danger-border bg-danger-subtle flex-shrink-0" />
              <span className="text-text-secondary">{f}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="flex items-center justify-between pt-3 border-t border-border">
        <div className="flex -space-x-2">
          {([["AY", "var(--color-accent)"], ["SK", "var(--color-info)"]] as const).map(([init, bg], n) => (
            <div key={n} className="w-7 h-7 rounded-full border-2 border-surface flex items-center justify-center text-[9px] font-bold text-white" style={{ background: bg }}>{init}</div>
          ))}
          <div className="w-7 h-7 rounded-full border-2 border-surface bg-surface-2 flex items-center justify-center text-[9px] text-text-muted">+3</div>
        </div>
        <span className="text-[10px] status-neutral px-2.5 py-1 rounded-full">Düzenleniyor</span>
      </div>
    </div>
  );

  if (idx === 1) return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-background p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-7 h-7 rounded-full flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0" style={{ background: "var(--color-accent)" }}>AY</div>
          <div>
            <div className="text-xs font-semibold text-text">Ahmet Y. → Nike TR Ekibi</div>
            <div className="text-[10px] text-text-muted">3 dk önce</div>
          </div>
        </div>
        <p className="text-xs text-text-secondary">&quot;Q3 kampanyası için brief hazır, incelemenizi bekliyoruz.&quot;</p>
      </div>
      <div className="space-y-2.5">
        {[["Alıcı", "Nike TR Marka Ekibi"], ["Öncelik", "Yüksek"], ["Beklenen yanıt", "24 saat"]].map(([label, value]) => (
          <div key={label} className="flex justify-between text-xs">
            <span className="text-text-muted">{label}</span>
            <span className="font-medium text-text">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );

  if (idx === 2) return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 p-3 rounded-xl border border-border bg-background">
        <div className="w-8 h-8 rounded-full flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0" style={{ background: "var(--color-info)" }}>MA</div>
        <div>
          <div className="text-xs font-semibold text-text">Murat A. inceliyor</div>
          <div className="text-[10px] text-text-muted">Nike TR · Marka Direktörü</div>
        </div>
      </div>
      <div className="rounded-xl border border-info-border bg-info-subtle p-3.5">
        <div className="text-[9px] text-text-muted uppercase tracking-wider mb-1.5">Son Yorum</div>
        <p className="text-xs text-info-text">&quot;Platform seçimini netleştirir misiniz? TikTok önemli.&quot;</p>
      </div>
      <div className="flex items-center gap-2 pt-1">
        <Bell className="w-3.5 h-3.5 text-warning" />
        <span className="text-xs text-warning-text font-medium">Yanıt bekleniyor</span>
      </div>
    </div>
  );

  if (idx === 3) return (
    <div className="space-y-4">
      <div className="rounded-xl border border-success-border bg-success-subtle p-4">
        <div className="flex items-center gap-3 mb-2.5">
          <div className="w-8 h-8 rounded-full bg-success flex items-center justify-center flex-shrink-0">
            <CheckCircle className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-sm font-bold text-text">Brief Kabul Edildi</div>
            <div className="text-[10px] text-text-muted">Murat A. · 5 dk önce</div>
          </div>
        </div>
        <p className="text-xs text-success-text">&quot;Brief yapısı onaylandı, üretime geçebilirsiniz.&quot;</p>
      </div>
      <div className="space-y-2.5">
        {[["Kanal", "Instagram + TikTok"], ["Teslim", "15 Tem 2026"], ["Ekip", "Kreatif + Tasarım"]].map(([label, value]) => (
          <div key={label} className="flex justify-between text-xs">
            <span className="text-text-muted">{label}</span>
            <span className="font-medium text-text">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );

  if (idx === 4) return (
    <div className="space-y-4">
      <div>
        <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2.5">Atanan Ekip</div>
        <div className="flex flex-wrap gap-2">
          {([["SK", "var(--color-info)", "Selin K. · Strateji"], ["MD", "var(--color-purple)", "Murat D. · Tasarım"]] as const).map(([init, bg, name]) => (
            <div key={name} className="flex items-center gap-2 rounded-lg border border-border bg-background px-2.5 py-1.5">
              <div className="w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold text-white flex-shrink-0" style={{ background: bg }}>{init}</div>
              <span className="text-[10px] font-medium text-text">{name}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="flex items-center justify-between rounded-xl border border-border bg-background p-3">
        <div className="flex items-center gap-2">
          <FileText className="w-3.5 h-3.5 text-text-muted" />
          <div>
            <div className="text-xs font-semibold text-text">V1 Taslak</div>
            <div className="text-[10px] text-text-muted">8 dk önce yüklendi</div>
          </div>
        </div>
        <span className="text-[10px] status-info px-2 py-0.5 rounded-full">İnceleniyor</span>
      </div>
      <div className="flex items-center gap-2 text-xs">
        <Clock className="w-3.5 h-3.5 text-text-muted" />
        <span className="text-text-muted">Teslim tarihi:</span>
        <span className="font-semibold text-text">15 Tem 2026</span>
      </div>
    </div>
  );

  if (idx === 5) return (
    <div className="space-y-4">
      <div className="rounded-xl border border-danger-border bg-danger-subtle p-4">
        <div className="text-[9px] text-text-muted uppercase tracking-wider mb-2">Marka Yorumu</div>
        <p className="text-xs text-danger-text mb-3">&quot;Logo boyutu küçültülmeli, metin kontrası artırılmalı. Renk paleti markamızla uyumsuz.&quot;</p>
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold text-white flex-shrink-0" style={{ background: "var(--color-accent)" }}>MA</div>
          <span className="text-[10px] text-text-muted">Murat A. · 12 dk önce</span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1.5">
          <FileText className="w-3 h-3 text-text-muted" />
          <span className="text-[10px] text-text-muted line-through">V1</span>
        </div>
        <ArrowRight className="w-3.5 h-3.5 text-text-muted" />
        <div className="flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent-subtle px-2.5 py-1.5">
          <FileText className="w-3 h-3 text-accent" />
          <span className="text-[10px] text-accent font-semibold">V2 hazırlanıyor</span>
        </div>
      </div>
    </div>
  );

  if (idx === 6) return (
    <div className="space-y-4">
      <div className="rounded-xl border border-success-border bg-success-subtle p-4">
        <div className="flex items-center gap-3 mb-2.5">
          <div className="w-9 h-9 rounded-full bg-success flex items-center justify-center flex-shrink-0">
            <CheckCircle className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="text-base font-bold text-text">Brief Onaylandı ✓</div>
            <div className="text-[10px] text-text-muted">Murat A. · Az önce</div>
          </div>
        </div>
        <p className="text-xs text-success-text">&quot;Mükemmel! V2 tam istediğimiz gibi, yayına geçebilir.&quot;</p>
      </div>
      <div className="space-y-2.5">
        {[["Son Versiyon", "V2 Final"], ["Onay Tarihi", "Bugün"], ["Yayın Planı", "15 Tem 2026"]].map(([label, value]) => (
          <div key={label} className="flex justify-between text-xs">
            <span className="text-text-muted">{label}</span>
            <span className="font-medium text-text">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );

  // idx === 7: Yayınlandı
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-success-border bg-success-subtle p-4">
        <div className="flex items-center gap-2 mb-3">
          <Zap className="w-4 h-4 text-success" />
          <span className="text-sm font-bold text-text">Yayına Alındı!</span>
        </div>
        <div className="flex gap-2 mb-3">
          {["Instagram", "TikTok"].map(ch => (
            <span key={ch} className="text-[10px] font-medium px-2.5 py-1 rounded-full status-success">{ch}</span>
          ))}
        </div>
        <p className="text-xs text-success-text">Süreç başarıyla tamamlandı. İçerik takviminde görüntülenebilir.</p>
      </div>
      <div className="space-y-2.5">
        {[["Yayın Tarihi", "15 Tem 2026"], ["Format", "8 post, 3 story, 2 reel"], ["Hedef", "18-34, sport & lifestyle"]].map(([label, value]) => (
          <div key={label} className="flex justify-between text-xs">
            <span className="text-text-muted">{label}</span>
            <span className="font-medium text-text">{value}</span>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 text-xs text-accent pt-1">
        <Calendar className="w-3.5 h-3.5" />
        <span className="font-medium">Takvimde görüntüle →</span>
      </div>
    </div>
  );
}

/* ── Mini event cards per stage ───────────────────────────────────────────── */

const STAGE_TOP_EVENTS = [
  { icon: FileText,    text: "5 alan tamamlandı",       sub: "3 alan eksik",            iconCls: "text-warning", bgCls: "bg-warning-subtle" },
  { icon: Bell,        text: "Brief gönderildi",         sub: "Nike TR bildirim aldı",   iconCls: "text-accent",  bgCls: "bg-accent-subtle"  },
  { icon: MessageSquare, text: "Yorum bekleniyor",       sub: "Yanıt süresi: 24 sa",    iconCls: "text-info",    bgCls: "bg-info-subtle"    },
  { icon: CheckCircle, text: "Brief kabul edildi ✓",     sub: "Murat A. onayladı",      iconCls: "text-success", bgCls: "bg-success-subtle" },
  { icon: Users,       text: "Ekip atandı",              sub: "Selin K. + Murat D.",    iconCls: "text-purple",  bgCls: "bg-purple-subtle"  },
  { icon: Bell,        text: "Revizyon istendi",         sub: "1 yorum bekliyor",       iconCls: "text-danger",  bgCls: "bg-danger-subtle"  },
  { icon: CheckCircle, text: "Onaylandı ✓",             sub: "V2 son versiyon",         iconCls: "text-success", bgCls: "bg-success-subtle" },
  { icon: Zap,         text: "Yayına alındı",            sub: "IG + TikTok aktif",      iconCls: "text-success", bgCls: "bg-success-subtle" },
] as const;

const STAGE_BOTTOM_EVENTS = [
  { label: "Ekip",    value: "AY, SK, MD +3"         },
  { label: "Yanıt",  value: "24 saat"               },
  { label: "Aktivite", value: "5 dk önce"            },
  { label: "Deadline", value: "15 Tem 2026"          },
  { label: "Versiyon", value: "V1 yüklendi"          },
  { label: "Revize",  value: "V1 → V2"               },
  { label: "Yayın",   value: "15 Tem 2026"           },
  { label: "Durum",   value: "Tamamlandı"            },
] as const;

/* ── Brief Lifecycle Scene ───────────────────────────────────────────────── */

function BriefLifecycleScene() {
  const [activeIdx, setActiveIdx] = useState(0);
  const [autoRunning, setAutoRunning] = useState(true);
  const shouldReduceMotion = useReducedMotion() ?? false;
  const stage = LIFECYCLE_STAGES[activeIdx];
  const sectionRef = useRef<HTMLElement>(null);
  const inView = useInView(sectionRef, { once: true, margin: "-10%" });

  useEffect(() => {
    if (!inView || !autoRunning || shouldReduceMotion) return;
    const id = setInterval(() => setActiveIdx(prev => (prev + 1) % LIFECYCLE_STAGES.length), 2600);
    return () => clearInterval(id);
  }, [inView, autoRunning, shouldReduceMotion]);

  const handleStep = (i: number) => {
    setActiveIdx(i);
    setAutoRunning(false);
  };

  const topEv = STAGE_TOP_EVENTS[activeIdx];
  const botEv = STAGE_BOTTOM_EVENTS[activeIdx];

  return (
    <section id="workflow" ref={sectionRef} className="relative min-h-[88vh] flex flex-col justify-center py-20 bg-surface overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 hero-grid opacity-20" />
      <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-accent/20 to-transparent" />
      <div className="absolute bottom-0 inset-x-0 h-px bg-border" />
      <div className="pointer-events-none absolute top-1/3 right-0 w-[500px] h-[500px] blur-[120px] rounded-full" style={{ background: "radial-gradient(circle, rgba(99,102,241,0.05) 0%, transparent 70%)" }} />
      <div className="pointer-events-none absolute bottom-1/4 -left-24 w-[400px] h-[400px] blur-[100px] rounded-full" style={{ background: "radial-gradient(circle, rgba(67,56,202,0.04) 0%, transparent 70%)" }} />

      <div className="relative mx-auto max-w-7xl px-6 w-full">

        {/* Section label */}
        <motion.div
          className="mb-12"
          initial="hidden"
          whileInView="visible"
          viewport={VP}
          variants={vStagger}
        >
          <motion.p variants={vUp} className="text-label-sm text-accent mb-3">İş Akışı</motion.p>
          <motion.h2 variants={vUp} className="text-heading-xl text-text mb-4 max-w-2xl">
            Brief&apos;ten yayına, tüm süreç tek akışta.
          </motion.h2>
          <motion.p variants={vUp} className="text-text-secondary text-base leading-relaxed max-w-2xl">
            Brief oluşturma, ekip atama, üretim, revizyon, onay ve yayın süreçlerini tek merkezden yönetin.
            Her aşama görünür, her karar kayıt altında.
          </motion.p>
        </motion.div>

        <div className="grid lg:grid-cols-12 gap-10 lg:gap-14 items-start">

          {/* ── Left column ──────────────────────────────────────────────── */}
          <div className="lg:col-span-4 lg:sticky lg:top-24">

            {/* Benefits */}
            <motion.div
              className="space-y-5 mb-8"
              initial="hidden"
              whileInView="visible"
              viewport={VP}
              variants={vStagger}
            >
              {[
                { title: "Her aşama görünür",         desc: "Taslaktan yayına kadar süreci ekibinizle şeffaf biçimde yönetin."      },
                { title: "Her karar kayıt altında",    desc: "Revizyon notları, onay tarihleri ve versiyon geçmişi daima erişilebilir." },
                { title: "Her sorumlu net",            desc: "Görev atamaları, deadline'lar ve iş yükü tek bakışta anlaşılır."        },
              ].map(b => (
                <motion.div key={b.title} variants={vUp} className="flex gap-3.5">
                  <div className="w-5 h-5 rounded-full bg-accent-subtle border border-accent/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-accent" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-text mb-0.5">{b.title}</div>
                    <div className="text-xs text-text-muted leading-relaxed">{b.desc}</div>
                  </div>
                </motion.div>
              ))}
            </motion.div>

            {/* Active stage info card */}
            <motion.div
              className="rounded-2xl border border-border bg-surface shadow-card overflow-hidden mb-6"
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={VP}
              transition={{ duration: 0.5, delay: 0.3, ease: ES }}
            >
              <div className="px-5 py-3.5 border-b border-border bg-surface-2">
                <span className="text-[10px] text-text-muted uppercase tracking-wider">Aktif Aşama</span>
              </div>
              <div className="p-5">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeIdx + "-info"}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className={`inline-flex text-xs font-semibold px-2.5 py-1 rounded-full mb-3 ${stage.cls}`}>
                      {activeIdx + 1}. {stage.label}
                    </div>
                    <p className="text-xs text-text-secondary leading-relaxed">{stage.desc}</p>
                  </motion.div>
                </AnimatePresence>
                <div className="mt-4 pt-4 border-t border-border">
                  <div className="flex justify-between text-[10px] text-text-muted mb-1.5">
                    <span>Süreç</span>
                    <span>{activeIdx + 1}/{LIFECYCLE_STAGES.length} adım · {Math.round(((activeIdx + 1) / LIFECYCLE_STAGES.length) * 100)}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-gradient-accent"
                      animate={{ width: `${((activeIdx + 1) / LIFECYCLE_STAGES.length) * 100}%` }}
                      transition={{ duration: 0.55, ease: ES }}
                    />
                  </div>
                </div>
              </div>
            </motion.div>

            {/* CTAs */}
            <motion.div
              className="flex flex-col gap-3"
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={VP}
              transition={{ duration: 0.4, delay: 0.4, ease: ES }}
            >
              <Link
                href="/auth/register"
                className="flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-bold text-white transition-all hover:scale-[1.02] active:scale-[0.98]"
                style={{ background: "var(--gradient-accent)", boxShadow: "0 2px 16px rgba(99,102,241,0.28)" }}
              >
                Ücretsiz başlayın
                <ArrowRight className="w-4 h-4" />
              </Link>
              <a
                href="#features"
                className="text-center text-xs text-text-muted hover:text-text transition-colors py-1"
              >
                Tüm özellikleri incele →
              </a>
            </motion.div>
          </div>

          {/* ── Right column ─────────────────────────────────────────────── */}
          <div className="lg:col-span-8">

            {/* Lifecycle rail */}
            <motion.div
              className="mb-8 overflow-x-auto pb-3"
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={VP}
              transition={{ duration: 0.5, delay: 0.1, ease: ES }}
              role="tablist"
              aria-label="Lifecycle aşamaları"
            >
              <div className="flex items-start gap-0 min-w-max">
                {LIFECYCLE_STAGES.map((s, i) => (
                  <div key={s.id} className="flex items-start">
                    <div className="flex flex-col items-center gap-2">
                      <button
                        role="tab"
                        aria-selected={i === activeIdx}
                        aria-label={`Aşama ${i + 1}: ${s.label}`}
                        onClick={() => handleStep(i)}
                        className={`w-9 h-9 rounded-full border-2 flex items-center justify-center text-xs font-bold transition-all duration-250 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 ${
                          i === activeIdx
                            ? "border-accent bg-accent text-white shadow-glow-sm scale-110"
                            : i < activeIdx
                              ? "border-success bg-success-subtle text-success-text"
                              : "border-border bg-surface-2 text-text-muted hover:border-accent/40 hover:bg-accent-subtle/50 hover:text-accent"
                        }`}
                      >
                        {i < activeIdx ? <CheckCircle className="w-4 h-4" /> : <span>{i + 1}</span>}
                      </button>
                      <span className={`text-[10px] font-medium whitespace-nowrap transition-colors duration-200 ${
                        i === activeIdx ? "text-accent" : i < activeIdx ? "text-success-text" : "text-text-muted"
                      }`}>
                        {s.label}
                      </span>
                    </div>
                    {i < LIFECYCLE_STAGES.length - 1 && (
                      <div className={`mt-[18px] h-0.5 w-10 flex-shrink-0 transition-all duration-500 ${
                        i < activeIdx ? "bg-success/60" : "bg-border"
                      }`} />
                    )}
                  </div>
                ))}
              </div>
            </motion.div>

            {/* Main card + floating mini cards */}
            <motion.div
              className="relative pt-8 pb-10 lg:pt-10 lg:pb-12"
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={VP}
              transition={{ duration: 0.6, delay: 0.22, ease: ES }}
            >

              {/* Mini card — top right */}
              <motion.div
                className="hidden lg:block absolute top-0 right-0 z-10 w-56"
                animate={shouldReduceMotion ? {} : { y: [0, -5, 0] }}
                transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
              >
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeIdx + "-top"}
                    initial={{ opacity: 0, scale: 0.92, y: 6 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.92, y: -6 }}
                    transition={{ duration: 0.22 }}
                    className="bg-surface border border-border rounded-xl shadow-modal p-3"
                  >
                    <div className="flex items-center gap-2.5">
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${topEv.bgCls}`}>
                        <topEv.icon className={`w-3.5 h-3.5 ${topEv.iconCls}`} />
                      </div>
                      <div className="min-w-0">
                        <div className="text-[11px] font-semibold text-text leading-tight">{topEv.text}</div>
                        <div className="text-[9px] text-text-muted mt-0.5">{topEv.sub}</div>
                      </div>
                    </div>
                  </motion.div>
                </AnimatePresence>
              </motion.div>

              {/* Mini card — bottom left */}
              <motion.div
                className="hidden lg:block absolute bottom-4 -left-4 z-10 w-44"
                animate={shouldReduceMotion ? {} : { y: [0, -7, 0] }}
                transition={{ duration: 5.5, repeat: Infinity, ease: "easeInOut", delay: 1.4 }}
              >
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeIdx + "-bot"}
                    initial={{ opacity: 0, scale: 0.92, y: 6 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.92, y: -6 }}
                    transition={{ duration: 0.22, delay: 0.06 }}
                    className="bg-surface border border-border rounded-xl shadow-modal p-3"
                  >
                    <div className="text-[9px] text-text-muted uppercase tracking-wider mb-1.5">Flobrief</div>
                    <div className="flex justify-between items-center">
                      <span className="text-[10px] text-text-secondary">{botEv.label}</span>
                      <span className="text-[10px] font-semibold text-text">{botEv.value}</span>
                    </div>
                  </motion.div>
                </AnimatePresence>
              </motion.div>

              {/* Main brief card */}
              <div className="rounded-2xl border border-border bg-surface shadow-card overflow-hidden">
                {/* Card header — always visible */}
                <div className="p-6 border-b border-border">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3.5 min-w-0">
                      <div
                        className="w-11 h-11 rounded-xl flex items-center justify-center text-base font-black text-white flex-shrink-0"
                        style={{ background: "var(--gradient-accent)" }}
                      >N</div>
                      <div className="min-w-0">
                        <div className="text-base font-bold text-text leading-tight">Q3 Sosyal Medya Kampanyası</div>
                        <div className="text-xs text-text-muted mt-0.5">Nike TR · #BRF-0124 · Yüksek Öncelik</div>
                      </div>
                    </div>
                    <AnimatePresence mode="wait">
                      <motion.span
                        key={stage.id}
                        className={`text-xs font-semibold px-3 py-1.5 rounded-full flex-shrink-0 ${stage.cls}`}
                        initial={{ opacity: 0, scale: 0.85, y: -4 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.85, y: 4 }}
                        transition={{ duration: 0.18 }}
                      >
                        {stage.label}
                      </motion.span>
                    </AnimatePresence>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-4">
                    {[
                      { icon: Calendar, label: "15 Tem 2026" },
                      { icon: Layers,   label: "IG · TikTok"    },
                      { icon: Users,    label: "Kreatif Ekip"   },
                      { icon: Shield,   label: "Yüksek Öncelik" },
                    ].map(({ icon: Icon, label }) => (
                      <div key={label} className="flex items-center gap-1.5 text-xs text-text-muted">
                        <Icon className="w-3.5 h-3.5 text-text-muted/50" />
                        {label}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Card body — changes per stage */}
                <div className="p-6 min-h-[180px]">
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={activeIdx + "-body"}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.25 }}
                    >
                      <BriefCardBody idx={activeIdx} />
                    </motion.div>
                  </AnimatePresence>
                </div>

                {/* Card footer — progress bar */}
                <div className="px-6 pb-6 pt-2 border-t border-border">
                  <div className="flex justify-between text-[10px] text-text-muted mb-1.5">
                    <span>Süreç İlerlemesi</span>
                    <span>{Math.round(((activeIdx + 1) / LIFECYCLE_STAGES.length) * 100)}% tamamlandı</span>
                  </div>
                  <div className="h-2 rounded-full bg-surface-2 overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-gradient-accent"
                      animate={{ width: `${((activeIdx + 1) / LIFECYCLE_STAGES.length) * 100}%` }}
                      transition={{ duration: 0.55, ease: ES }}
                    />
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Auto-running indicator */}
            {autoRunning && !shouldReduceMotion && (
              <motion.div
                className="flex items-center gap-2 mt-4 text-[10px] text-text-muted"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.5 }}
              >
                <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse flex-shrink-0" />
                <span>Otomatik ilerliyor · Adımlara tıklayarak inceleyebilirsiniz</span>
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── Persona Tabs ────────────────────────────────────────────────────────── */

const PERSONAS = [
  {
    id: "agency",
    label: "Ajans",
    Icon: Building2,
    tagline: "Tüm markalarınızı tek ekrandan yönetin",
    desc: "Brief oluşturun, ekibinize görev atayın, marka portallerini özelleştirin ve raporları tek dashboardda görün.",
    points: ["Sınırsız marka ve brief takibi", "Çok kullanıcılı ekip iş birliği", "White-label marka portalleri", "Detaylı raporlama ve analitik"],
    badgeCls: "status-accent",
    miniStats: [{ label: "Aktif Marka", v: "11" }, { label: "Açık Brief", v: "24" }, { label: "Bu Ay Onay", v: "18" }, { label: "Ekip Üyesi", v: "8" }],
    activity: [{ label: "Q3 Kampanyası onaylandı", dot: "bg-success" }, { label: "Influencer Brief güncellendi", dot: "bg-accent" }, { label: "Yılbaşı Brief oluşturuldu", dot: "bg-info" }],
  },
  {
    id: "brand",
    label: "Marka",
    Icon: Sparkles,
    tagline: "Ajansınızdan gelen işleri kolayca yönetin",
    desc: "Kendi markanıza özel portal üzerinden briefleri inceleyin, onay verin veya revizyon isteyin.",
    points: ["Ajans markalı özel portal", "Tek tıkla onay ve revizyon", "Tüm briefler tek yerden", "Gerçek zamanlı bildirimler"],
    badgeCls: "status-purple",
    miniStats: [{ label: "Bekleyen", v: "3" }, { label: "Onaylanan", v: "14" }, { label: "Revize", v: "2" }, { label: "Tamamlanan", v: "28" }],
    activity: [{ label: "Q3 Kampanyası onaylandı", dot: "bg-success" }, { label: "Revizyon notları eklendi", dot: "bg-danger" }, { label: "Yeni brief alındı", dot: "bg-accent" }],
  },
  {
    id: "team",
    label: "Ekip",
    Icon: Users,
    tagline: "Ekip iş yükünü şeffaf hale getirin",
    desc: "Kim ne yapıyor? Hangi brief bekliyor? Tüm ekip aktivitesini gerçek zamanlı takip edin.",
    points: ["Rol tabanlı erişim kontrolü", "Görev atama ve takip", "Yorum ve not geçmişi", "Aktivite akışı"],
    badgeCls: "status-info",
    miniStats: [{ label: "Aktif Görev", v: "12" }, { label: "Tamamlandı", v: "47" }, { label: "Yorum", v: "89" }, { label: "Aktivite", v: "234" }],
    activity: [{ label: "Murat D. brief teslim etti", dot: "bg-success" }, { label: "Selin K. yorum ekledi", dot: "bg-info" }, { label: "Ahmet Y. görev aldı", dot: "bg-accent" }],
  },
] as const;

function PersonaTabs() {
  const [active, setActive] = useState(0);
  const p = PERSONAS[active];

  return (
    <section className="py-24 bg-background relative">
      <div className="mx-auto max-w-5xl px-6">
        <motion.div className="text-center mb-12" initial="hidden" whileInView="visible" viewport={VP} variants={vStagger}>
          <motion.p variants={vUp} className="text-label-sm text-accent mb-3">Kim İçin?</motion.p>
          <motion.h2 variants={vUp} className="text-heading-xl text-text mb-4">Her role özel tasarlandı</motion.h2>
          <motion.p variants={vUp} className="text-text-secondary max-w-lg mx-auto text-base">
            Ajans yöneticisinden marka yetkilisine, içerik ekibinden proje müdürüne kadar herkes kendi iş akışını bulur.
          </motion.p>
        </motion.div>

        {/* Tab switcher */}
        <motion.div
          className="flex justify-center mb-10"
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VP}
          transition={{ duration: 0.4, ease: ES }}
        >
          <div className="inline-flex rounded-xl border border-border bg-surface p-1 gap-1">
            {PERSONAS.map((tab, i) => (
              <button
                key={tab.id}
                onClick={() => setActive(i)}
                className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  i === active
                    ? "bg-accent text-white shadow-sm"
                    : "text-text-muted hover:text-text hover:bg-hover"
                }`}
              >
                <tab.Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Panel */}
        <AnimatePresence mode="wait">
          <motion.div
            key={active}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.28, ease: ES }}
            className="grid md:grid-cols-2 gap-8 items-center"
          >
            {/* Copy */}
            <div>
              <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-4 ${p.badgeCls}`}>
                <p.Icon className="w-3.5 h-3.5" />
                <span className="text-xs font-semibold">{p.label}</span>
              </div>
              <h3 className="text-2xl font-bold text-text mb-3 tracking-tight leading-snug">{p.tagline}</h3>
              <p className="text-text-secondary text-sm leading-relaxed mb-6">{p.desc}</p>
              <ul className="space-y-2.5">
                {p.points.map(point => (
                  <li key={point} className="flex items-center gap-2.5 text-sm text-text-secondary">
                    <div className="w-4 h-4 rounded-full bg-accent-subtle flex items-center justify-center flex-shrink-0">
                      <CheckCircle className="w-2.5 h-2.5 text-accent" />
                    </div>
                    {point}
                  </li>
                ))}
              </ul>
              <Link
                href="/auth/register"
                className="mt-8 inline-flex items-center gap-2 text-sm font-semibold text-accent hover:text-accent-hover transition-colors group"
              >
                Ücretsiz başlayın
                <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
              </Link>
            </div>

            {/* Mini dashboard */}
            <div className="rounded-2xl border border-border bg-surface shadow-card p-5">
              <div className="flex items-center gap-2.5 mb-4">
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${p.badgeCls}`}>
                  <p.Icon className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-text">{p.label} Dashboardu</div>
                  <div className="text-xs text-text-muted">app.flobrief.com</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 mb-3">
                {p.miniStats.map(s => (
                  <div key={s.label} className="rounded-xl border border-border bg-background p-3">
                    <div className="text-[10px] text-text-muted mb-1">{s.label}</div>
                    <div className="text-xl font-bold text-text">{s.v}</div>
                  </div>
                ))}
              </div>
              <div className="rounded-xl border border-border bg-background overflow-hidden">
                <div className="border-b border-border px-3 py-2">
                  <span className="text-[10px] font-semibold text-text">Son Aktivite</span>
                </div>
                {p.activity.map(item => (
                  <div key={item.label} className="flex items-center gap-2 px-3 py-2 border-b border-border last:border-0">
                    <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${item.dot}`} />
                    <span className="text-[10px] text-text-secondary">{item.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </section>
  );
}

/* ── Main export ─────────────────────────────────────────────────────────── */

export default function HomePage() {
  const [loginOpen, setLoginOpen] = useState(false);
  const shouldReduceMotion = useReducedMotion() ?? false;

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const springX = useSpring(mouseX, { stiffness: 80, damping: 30 });
  const springY = useSpring(mouseY, { stiffness: 80, damping: 30 });
  const rotateX = useTransform(springY, [-400, 400], [3, -3]);
  const rotateY = useTransform(springX, [-400, 400], [-4, 4]);

  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (shouldReduceMotion) return;
      const rect = e.currentTarget.getBoundingClientRect();
      mouseX.set(e.clientX - rect.left - rect.width / 2);
      mouseY.set(e.clientY - rect.top - rect.height / 2);
    },
    [mouseX, mouseY, shouldReduceMotion]
  );

  const onMouseLeave = useCallback(() => {
    mouseX.set(0);
    mouseY.set(0);
  }, [mouseX, mouseY]);

  return (
    <div className="min-h-screen bg-background overflow-x-hidden">

      {/* ── NAV ─────────────────────────────────────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-border glass">
        <div className="mx-auto max-w-7xl px-6">
          <div className="flex h-15 items-center justify-between">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div
                className="rounded-xl flex items-center justify-center flex-shrink-0 transition-all group-hover:scale-105"
                style={{ background: "var(--gradient-accent)", boxShadow: "0 2px 10px rgba(99,102,241,0.30)", width: "30px", height: "30px" }}
              >
                <span className="text-white font-bold text-xs leading-none">F</span>
              </div>
              <span className="text-sm font-semibold text-text tracking-tight">Flobrief</span>
            </Link>

            <div className="hidden items-center gap-1 md:flex">
              {[
                { label: "Ürün",       href: "#features" },
                { label: "İş Akışı",   href: "#workflow" },
                { label: "Sonuçlar",   href: "#stats"    },
                { label: "Fiyatlandırma", href: "/pricing" },
              ].map(item => (
                <a
                  key={item.href}
                  href={item.href}
                  className="px-4 py-2 text-sm text-text-secondary transition-colors hover:text-text rounded-lg hover:bg-hover"
                >
                  {item.label}
                </a>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setLoginOpen(true)}
                className="hidden sm:block px-4 py-2 text-sm text-text-secondary hover:text-text transition-colors rounded-lg hover:bg-hover"
              >
                Giriş Yap
              </button>
              <Link
                href="/auth/register"
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white rounded-xl transition-all hover:opacity-90 hover:scale-[1.02] active:scale-[0.98]"
                style={{ background: "var(--gradient-accent)", boxShadow: "0 2px 12px rgba(99,102,241,0.28)" }}
              >
                Ücretsiz Başla
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* ── HERO ────────────────────────────────────────────────────────── */}
      <section className="relative min-h-screen flex flex-col justify-center pt-16 overflow-hidden">
        <div className="absolute inset-0 hero-grid opacity-60" />
        <div className="pointer-events-none absolute -top-40 left-1/3 w-[700px] h-[700px] rounded-full blur-[130px]" style={{ background: "radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)" }} />
        <div className="pointer-events-none absolute bottom-0 right-1/4 w-[550px] h-[550px] rounded-full blur-[110px]" style={{ background: "radial-gradient(circle, rgba(67,56,202,0.09) 0%, transparent 70%)" }} />
        <div className="pointer-events-none absolute top-1/3 -left-24 w-[400px] h-[400px] rounded-full blur-[100px]" style={{ background: "radial-gradient(circle, rgba(37,99,235,0.07) 0%, transparent 70%)" }} />
        <div className="absolute top-[65px] inset-x-0 h-px bg-gradient-to-r from-transparent via-accent/20 to-transparent" />

        <motion.div
          className="relative mx-auto max-w-4xl px-6 text-center py-20"
          initial="hidden"
          animate="visible"
          variants={vStagger}
        >
          <motion.div
            variants={vUp}
            className="mb-8 inline-flex items-center gap-2.5 rounded-full border border-border bg-surface px-4 py-1.5 shadow-xs"
          >
            <span className="w-2 h-2 rounded-full bg-accent animate-pulse-ring flex-shrink-0" />
            <span className="text-xs font-semibold text-accent tracking-wide">Ajanslar için premium brief yönetimi</span>
            <span className="w-px h-3 bg-border-strong" />
            <span className="text-xs text-text-muted">Beta</span>
          </motion.div>

          <motion.h1 variants={vUp} className="mb-6 text-display text-text">
            WhatsApp&apos;ı bırakın,
            <br className="hidden sm:block" />
            <span className="text-gradient-animated"> profesyonel çalışın.</span>
          </motion.h1>

          <motion.p variants={vUp} className="mx-auto mb-10 max-w-xl text-lg leading-relaxed text-text-secondary">
            Ajans–marka arasındaki e-posta, WhatsApp ve Excel karmaşasını bitirin.
            Briefleri standartlaştırın, onayları izleyin, teslimatları kolaylaştırın.
          </motion.p>

          <motion.div variants={vUp} className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link
              href="/demo"
              className="group flex items-center gap-2.5 rounded-xl px-8 py-3.5 text-sm font-semibold text-white transition-all hover:scale-[1.03] active:scale-[0.98]"
              style={{ background: "var(--gradient-accent)", boxShadow: "0 4px 24px rgba(99,102,241,0.35), 0 1px 4px rgba(0,0,0,0.10)" }}
            >
              Ücretsiz Demo Başlat
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </Link>
            <a
              href="#workflow"
              className="flex items-center gap-2 rounded-xl border border-border bg-surface px-8 py-3.5 text-sm font-medium text-text-secondary shadow-xs transition-all hover:border-border-hover hover:text-text hover:shadow-sm"
            >
              Nasıl Çalışır?
            </a>
          </motion.div>

          <motion.div variants={vUp} className="mt-10 flex items-center justify-center gap-2 text-xs text-text-muted">
            <div className="flex -space-x-2">
              {(["#4F46E5", "#4338CA", "#2563eb", "#059669"] as const).map((color, i) => (
                <div
                  key={i}
                  className="w-6 h-6 rounded-full border-2 border-background flex items-center justify-center text-[9px] font-bold text-white"
                  style={{ background: color }}
                >
                  {["A", "B", "C", "D"][i]}
                </div>
              ))}
            </div>
            <span>Yüzlerce ajans tarafından kullanılıyor</span>
            <span className="flex items-center gap-0.5 text-warning">
              {[...Array(5)].map((_, i) => <Star key={i} className="w-3 h-3 fill-current" />)}
            </span>
          </motion.div>
        </motion.div>

        {/* Dashboard mockup — 2.5D */}
        <motion.div
          className="relative mx-auto w-full max-w-6xl px-6 pb-12"
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.45, ease: ES }}
        >
          <div style={{ perspective: "1200px" }} onMouseMove={onMouseMove} onMouseLeave={onMouseLeave} className="relative">
            <motion.div style={{ rotateX, rotateY }} className="relative">

              {/* Floating approval card */}
              <motion.div
                className="hidden lg:block absolute -top-8 right-8 z-20 w-64"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.0, duration: 0.6, ease: ES }}
              >
                <motion.div
                  animate={shouldReduceMotion ? {} : { y: [0, -5, 0] }}
                  transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                  className="bg-surface border border-border rounded-xl shadow-modal p-4"
                >
                  <div className="flex items-center gap-2 mb-2.5">
                    <div className="w-6 h-6 rounded-full bg-success-subtle flex items-center justify-center flex-shrink-0">
                      <CheckCircle className="w-3.5 h-3.5 text-success" />
                    </div>
                    <span className="text-xs font-semibold text-text">Brief Onaylandı</span>
                  </div>
                  <div className="text-[11px] text-text-muted mb-0.5">Yılbaşı Kampanyası</div>
                  <div className="text-[11px] font-medium text-text mb-3">Zara Home</div>
                  <div className="flex items-center gap-2">
                    <div className="w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold text-white flex-shrink-0" style={{ background: "var(--color-accent)" }}>M</div>
                    <span className="text-[10px] text-text-muted">Murat A. · Az önce</span>
                  </div>
                </motion.div>
              </motion.div>

              {/* Floating notification card */}
              <motion.div
                className="hidden lg:block absolute top-28 -left-4 z-20 w-56"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.2, duration: 0.6, ease: ES }}
              >
                <motion.div
                  animate={shouldReduceMotion ? {} : { y: [0, -7, 0] }}
                  transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 1.5 }}
                  className="bg-surface border border-border rounded-xl shadow-modal p-3.5"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-5 h-5 rounded-full bg-warning-subtle flex items-center justify-center flex-shrink-0">
                      <Bell className="w-3 h-3 text-warning" />
                    </div>
                    <span className="text-[11px] font-semibold text-text">Revizyon İstendi</span>
                  </div>
                  <div className="text-[11px] text-text-secondary mb-2.5">Nike TR · Influencer Brief</div>
                  <div className="flex items-center gap-1 text-[10px] text-accent font-medium">
                    <span>İncele</span>
                    <ArrowRight className="w-2.5 h-2.5" />
                  </div>
                </motion.div>
              </motion.div>

              {/* Dashboard frame */}
              <div
                className="relative overflow-hidden rounded-2xl border border-border bg-surface"
                style={{ boxShadow: "0 0 0 1px var(--color-border), 0 24px 60px rgba(0,0,0,0.10), 0 4px 16px rgba(0,0,0,0.06)" }}
              >
                <div className="absolute inset-x-0 top-0 h-px bg-gradient-accent opacity-30" />
                <div className="flex items-center gap-3 border-b border-border bg-surface-2 px-5 py-3">
                  <div className="flex gap-1.5">
                    <div className="h-3 w-3 rounded-full bg-danger/60" />
                    <div className="h-3 w-3 rounded-full bg-warning/60" />
                    <div className="h-3 w-3 rounded-full bg-success/60" />
                  </div>
                  <div className="flex-1 flex justify-center">
                    <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-1.5">
                      <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
                      <span className="text-xs text-text-muted font-mono">app.flobrief.com/dashboard</span>
                    </div>
                  </div>
                  <div className="w-16" />
                </div>

                <div className="flex h-[380px] overflow-hidden">
                  <div className="hidden w-48 shrink-0 border-r border-border bg-surface-2 p-4 md:flex flex-col">
                    <div className="mb-5 flex items-center gap-2.5">
                      <div className="w-6 h-6 rounded-lg flex items-center justify-center" style={{ background: "var(--gradient-accent)" }}>
                        <span className="text-white text-xs font-bold leading-none">F</span>
                      </div>
                      <span className="text-sm font-semibold text-text">Flobrief</span>
                    </div>
                    <div className="space-y-0.5">
                      {[{ label: "Dashboard", active: true }, { label: "Brief'ler", active: false }, { label: "Takvim", active: false }, { label: "Markalar", active: false }, { label: "Raporlar", active: false }].map(item => (
                        <div key={item.label} className={`flex h-8 items-center gap-2 rounded-lg px-2.5 text-xs font-medium ${item.active ? "bg-accent-subtle text-accent" : "text-text-muted"}`}>
                          <div className={`w-1.5 h-1.5 rounded-full ${item.active ? "bg-accent" : "bg-border-strong"}`} />
                          {item.label}
                        </div>
                      ))}
                    </div>
                    <div className="mt-auto pt-4 border-t border-border">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full flex items-center justify-center" style={{ background: "var(--gradient-accent)" }}>
                          <span className="text-[9px] font-bold text-white">AY</span>
                        </div>
                        <div>
                          <div className="text-[11px] font-medium text-text">Ahmet Y.</div>
                          <div className="text-[10px] text-text-muted">admin</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex-1 overflow-hidden p-5 bg-background">
                    <div className="mb-4 flex items-center justify-between">
                      <div>
                        <div className="text-sm font-semibold text-text tracking-tight">Dashboard</div>
                        <div className="text-xs text-text-muted">Temmuz 2026</div>
                      </div>
                      <div className="flex items-center gap-1.5 rounded-full border border-success-border bg-success-subtle px-3 py-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                        <span className="text-xs text-success-text font-medium">Canlı</span>
                      </div>
                    </div>
                    <div className="mb-4 grid grid-cols-4 gap-3">
                      {[
                        { label: "Aktif Brief", value: "24", delta: "+3", statusClass: "status-accent" },
                        { label: "Onay Bekliyor", value: "7", delta: "−2", statusClass: "status-warning" },
                        { label: "Bu Ay Teslim", value: "18", delta: "+6", statusClass: "status-success" },
                        { label: "Aktif Marka", value: "11", delta: "+1", statusClass: "status-purple" },
                      ].map(m => (
                        <div key={m.label} className="rounded-xl border border-border bg-surface p-3 shadow-xs">
                          <div className="text-[10px] text-text-muted mb-1.5">{m.label}</div>
                          <div className="flex items-end justify-between">
                            <span className="text-xl font-bold text-text">{m.value}</span>
                            <span className={`inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded-full ${m.statusClass}`}>{m.delta}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="rounded-xl border border-border bg-surface overflow-hidden shadow-xs">
                      <div className="border-b border-border px-4 py-2.5">
                        <span className="text-xs font-semibold text-text">Son Brief&apos;ler</span>
                      </div>
                      {mockBriefs.map(brief => (
                        <div key={brief.name} className="flex items-center justify-between px-4 py-2.5 border-b border-border last:border-0 hover:bg-hover transition-colors">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${brief.dot}`} />
                            <div className="min-w-0">
                              <div className="text-xs font-medium text-text truncate">{brief.name}</div>
                              <div className="text-[10px] text-text-muted">{brief.brand}</div>
                            </div>
                          </div>
                          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${brief.statusClass}`}>{brief.status}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
          <div className="absolute bottom-0 left-6 right-6 h-20 bg-gradient-to-t from-background to-transparent pointer-events-none" />
        </motion.div>
      </section>

      {/* ── PROBLEM BANNER ──────────────────────────────────────────────── */}
      <div className="border-y border-border bg-surface-2 py-10">
        <div className="mx-auto max-w-5xl px-6">
          <motion.div
            className="text-center mb-6"
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={VP}
            transition={{ duration: 0.4, ease: ES }}
          >
            <p className="text-xs text-text-muted uppercase tracking-widest font-medium">Eski yöntemlere elveda</p>
          </motion.div>
          <motion.div
            className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4"
            initial="hidden"
            whileInView="visible"
            viewport={VP}
            variants={vStagger}
          >
            {[
              { Icon: MessageSquare, label: "WhatsApp Grupları", desc: "Kayıp mesajlar, belirsiz kararlar" },
              { Icon: Mail,          label: "E-posta Zincirleri", desc: "CC karmaşası, versiyon konfüzyonu" },
              { Icon: FileText,      label: "Excel Takibi",       desc: "Manuel güncelleme, stale data" },
            ].map(({ Icon, label, desc }) => (
              <motion.div
                key={label}
                variants={vUp}
                className="flex items-center gap-3 rounded-xl border border-danger-border bg-danger-subtle px-4 py-3 w-full sm:w-auto"
              >
                <div className="w-8 h-8 rounded-lg bg-background border border-border flex items-center justify-center flex-shrink-0">
                  <Icon className="w-4 h-4 text-text-muted" />
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-text line-through opacity-60">{label}</div>
                  <div className="text-[10px] text-danger-text">{desc}</div>
                </div>
              </motion.div>
            ))}

            <motion.div variants={vUp} className="text-text-muted font-bold text-lg flex-shrink-0">→</motion.div>

            <motion.div
              variants={vUp}
              className="flex items-center gap-3 rounded-xl border border-success-border bg-success-subtle px-4 py-3 w-full sm:w-auto"
            >
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: "var(--gradient-accent)" }}
              >
                <span className="text-white text-xs font-bold">F</span>
              </div>
              <div>
                <div className="text-xs font-semibold text-text">Flobrief</div>
                <div className="text-[10px] text-success-text">Tek platform, tam kontrol</div>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </div>

      {/* ── LOGO MARQUEE ────────────────────────────────────────────────── */}
      <div className="border-b border-border bg-background py-4 overflow-hidden">
        <div className="flex items-center gap-2 text-xs text-text-muted mb-3 px-6">
          <div className="flex-1 h-px bg-gradient-to-r from-transparent via-border-strong to-transparent" />
          <span className="flex-shrink-0 text-label-xs text-text-muted/60">GÜVENDIKLERI PLATFORM</span>
          <div className="flex-1 h-px bg-gradient-to-r from-border-strong via-transparent to-transparent" />
        </div>
        <div className="relative flex">
          <div className="flex gap-12 animate-marquee whitespace-nowrap">
            {logos.map((logo, i) => (
              <span key={i} className="text-sm font-semibold text-text-muted/35 hover:text-text-muted/65 transition-colors tracking-wider">
                {logo}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ── FEATURES BENTO ──────────────────────────────────────────────── */}
      <section id="features" className="py-24 bg-surface">
        <div className="mx-auto max-w-7xl px-6">

          <motion.div className="mb-14 text-center" initial="hidden" whileInView="visible" viewport={VP} variants={vStagger}>
            <motion.p variants={vUp} className="text-label-sm text-accent mb-3">Ürün</motion.p>
            <motion.h2 variants={vUp} className="text-heading-xl text-text mb-4">
              Brief, üretim, revizyon ve onay —<br className="hidden sm:block" /> hepsi aynı yerde.
            </motion.h2>
            <motion.p variants={vUp} className="mx-auto max-w-xl text-base text-text-secondary leading-relaxed">
              Soyut özellikler değil, gerçek iş akışları. Aşağıdaki her kart, canlı Flobrief arayüzünden bir kesit.
            </motion.p>
          </motion.div>

          <motion.div
            className="grid grid-cols-1 md:grid-cols-12 gap-4"
            initial="hidden"
            whileInView="visible"
            viewport={VP}
            variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.07, delayChildren: 0.05 } } }}
          >

            {/* Row 1a: Brief Management — large */}
            <motion.div
              variants={vUp}
              className="md:col-span-7 group relative overflow-hidden rounded-2xl border border-border bg-surface-2 p-6 hover:border-border-hover hover:shadow-card-hover transition-all duration-200 cursor-default"
            >
              <div className="absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-accent" />
              <div className="flex items-center gap-3 mb-1">
                <div className="w-9 h-9 rounded-xl border border-border bg-surface flex items-center justify-center flex-shrink-0">
                  <FileText className="w-4 h-4 text-accent" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-text">Akıllı Brief Şablonları</h3>
                  <p className="text-xs text-text-muted">Brief doldurma süresi %70 azalır</p>
                </div>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed mb-4">
                Sektöre özgü dinamik şablonlar, zorunlu alanlar ve onay öncesi otomatik doğrulama ile her marka için mükemmel brief yapısı oluşturun.
              </p>
              <BriefMiniUI reduced={shouldReduceMotion} />
            </motion.div>

            {/* Row 1b: Approval Flow */}
            <motion.div
              variants={vUp}
              className="md:col-span-5 group relative overflow-hidden rounded-2xl border border-border bg-surface-2 p-6 hover:border-border-hover hover:shadow-card-hover transition-all duration-200 cursor-default"
            >
              <div className="absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-accent" />
              <div className="flex items-center gap-3 mb-1">
                <div className="w-9 h-9 rounded-xl border border-border bg-surface flex items-center justify-center flex-shrink-0">
                  <CheckCircle className="w-4 h-4 text-success" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-text">Onay & Revize Akışı</h3>
                  <p className="text-xs text-text-muted">Revize döngüsü 3× hızlanır</p>
                </div>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed mb-4">
                Marka yöneticileri tek tıkla onay verir, revize notlarını bölüm bazında bırakır. Her versiyon kayıt altında.
              </p>
              <ApprovalMiniUI reduced={shouldReduceMotion} />
            </motion.div>

            {/* Row 2a: Calendar */}
            <motion.div
              variants={vUp}
              className="md:col-span-5 group relative overflow-hidden rounded-2xl border border-border bg-surface-2 p-6 hover:border-border-hover hover:shadow-card-hover transition-all duration-200 cursor-default"
            >
              <div className="absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-accent" />
              <div className="flex items-center gap-3 mb-1">
                <div className="w-9 h-9 rounded-xl border border-border bg-surface flex items-center justify-center flex-shrink-0">
                  <Calendar className="w-4 h-4 text-info" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-text">İçerik Takvimi</h3>
                  <p className="text-xs text-text-muted">Tüm markaların planı tek ekranda</p>
                </div>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed mb-4">
                Markalara göre filtrelenebilir takvim görünümünde içerik planını yönetin. Çakışmaları anında görün.
              </p>
              <CalendarMiniUI reduced={shouldReduceMotion} />
            </motion.div>

            {/* Row 2b: White-Label Portal — large */}
            <motion.div
              variants={vUp}
              className="md:col-span-7 group relative overflow-hidden rounded-2xl border border-border bg-surface-2 p-6 hover:border-border-hover hover:shadow-card-hover transition-all duration-200 cursor-default"
            >
              <div className="absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-accent" />
              <div className="flex items-center gap-3 mb-1">
                <div className="w-9 h-9 rounded-xl border border-border bg-surface flex items-center justify-center flex-shrink-0">
                  <Layers className="w-4 h-4 text-purple" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-text">White-Label Marka Portali</h3>
                  <p className="text-xs text-text-muted">Her müşteri kendi özel portalını görür</p>
                </div>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed mb-4">
                Ajans markanızla özelleştirilmiş marka portalleri. Müşteriniz ajans panelini değil, kendi markalı çalışma ortamını görür.
              </p>
              <div className="flex gap-3 h-28">
                <div className="flex-1 rounded-xl border border-border bg-background p-3">
                  <div className="text-[10px] font-semibold text-accent mb-2">Ajans Görünümü</div>
                  <div className="space-y-1.5">
                    {["Nike TR", "Zara Home", "L'Oréal TR"].map(brand => (
                      <div key={brand} className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" />
                        <span className="text-[10px] text-text-secondary">{brand}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="flex flex-col items-center justify-center">
                  <div className="w-6 h-6 rounded-full border border-border bg-surface-2 flex items-center justify-center text-[10px] text-text-muted flex-shrink-0">↔</div>
                </div>
                <div className="flex-1 rounded-xl border border-accent/20 bg-accent-subtle/20 p-3">
                  <div className="text-[10px] font-semibold text-text mb-2">Marka Portali</div>
                  <div className="rounded-lg border border-border bg-background p-2 mb-1.5">
                    <div className="text-[9px] text-text-muted mb-1">Q3 Sosyal Medya</div>
                    <span className="text-[9px] status-warning px-1.5 py-0.5 rounded-full">Bekliyor</span>
                  </div>
                  <div className="rounded-lg border border-border bg-background p-2">
                    <div className="text-[9px] text-text-muted mb-1">Yılbaşı Kampanya</div>
                    <span className="text-[9px] status-success px-1.5 py-0.5 rounded-full">Onaylandı</span>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Row 3a: Reporting */}
            <motion.div
              variants={vUp}
              className="md:col-span-4 group relative overflow-hidden rounded-2xl border border-border bg-surface-2 p-6 hover:border-border-hover hover:shadow-card-hover transition-all duration-200 cursor-default"
            >
              <div className="absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-accent" />
              <div className="flex items-center gap-3 mb-1">
                <div className="w-9 h-9 rounded-xl border border-border bg-surface flex items-center justify-center flex-shrink-0">
                  <BarChart3 className="w-4 h-4 text-warning" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-text">Raporlama</h3>
                  <p className="text-xs text-text-muted">Onay oranları ve metrikler</p>
                </div>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed mb-4">
                Teslimat performansını ve onay oranlarını tek dashboardda izleyin.
              </p>
              <ReportingMiniUI reduced={shouldReduceMotion} />
            </motion.div>

            {/* Row 3b: Notifications */}
            <motion.div
              variants={vUp}
              className="md:col-span-4 group relative overflow-hidden rounded-2xl border border-border bg-surface-2 p-6 hover:border-border-hover hover:shadow-card-hover transition-all duration-200 cursor-default"
            >
              <div className="absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-accent" />
              <div className="flex items-center gap-3 mb-1">
                <div className="w-9 h-9 rounded-xl border border-border bg-surface flex items-center justify-center flex-shrink-0">
                  <Bell className="w-4 h-4 text-danger" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-text">Akıllı Bildirimler</h3>
                  <p className="text-xs text-text-muted">E-posta %94 azalır</p>
                </div>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed mb-4">
                Onay, revizyon ve teslim anında bildirim. E-posta ve entegrasyon desteğiyle.
              </p>
              <NotifMiniUI reduced={shouldReduceMotion} />
            </motion.div>

            {/* Row 3c: Teams */}
            <motion.div
              variants={vUp}
              className="md:col-span-4 group relative overflow-hidden rounded-2xl border border-border bg-surface-2 p-6 hover:border-border-hover hover:shadow-card-hover transition-all duration-200 cursor-default"
            >
              <div className="absolute inset-x-0 top-0 h-px opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-accent" />
              <div className="flex items-center gap-3 mb-1">
                <div className="w-9 h-9 rounded-xl border border-border bg-surface flex items-center justify-center flex-shrink-0">
                  <Users className="w-4 h-4 text-info" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-text">Ekip İş Birliği</h3>
                  <p className="text-xs text-text-muted">Kim, ne yapıyor, ne zaman?</p>
                </div>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed mb-4">
                Rol tabanlı erişim, görev atama ve ekip iş yükü takibi tek yerden.
              </p>
              <TeamsMiniUI reduced={shouldReduceMotion} />
            </motion.div>

          </motion.div>
        </div>
      </section>

      {/* ── PERSONA TABS ────────────────────────────────────────────────── */}
      <PersonaTabs />

      {/* ── BRIEF LIFECYCLE SCENE ───────────────────────────────────────── */}
      <BriefLifecycleScene />

      {/* ── STATS ───────────────────────────────────────────────────────── */}
      <section id="stats" className="py-24 relative bg-surface">
        <div className="relative mx-auto max-w-5xl px-6">
          <motion.div className="text-center mb-12" initial="hidden" whileInView="visible" viewport={VP} variants={vStagger}>
            <motion.p variants={vUp} className="text-label-sm text-accent mb-3">Kanıtlanmış Sonuçlar</motion.p>
            <motion.h2 variants={vUp} className="text-heading-xl text-text">Rakamlarla Flobrief</motion.h2>
          </motion.div>
          <motion.div
            className="grid grid-cols-2 gap-px md:grid-cols-4 rounded-2xl overflow-hidden border border-border"
            initial="hidden"
            whileInView="visible"
            viewport={VP}
            variants={vStagger}
          >
            {stats.map(({ value, label, icon: Icon }, i) => (
              <motion.div
                key={label}
                variants={vUp}
                className="relative flex flex-col items-center justify-center p-8 bg-surface hover:bg-surface-2 transition-colors group"
              >
                {i > 0 && <div className="absolute left-0 top-1/4 bottom-1/4 w-px bg-border" />}
                <div className="w-10 h-10 rounded-xl bg-accent-subtle flex items-center justify-center mb-4 ring-1 ring-border group-hover:ring-accent/30 transition-all">
                  <Icon className="w-5 h-5 text-accent" />
                </div>
                <div className="text-3xl font-black text-text mb-1 md:text-4xl tracking-tightest gradient-text">{value}</div>
                <div className="text-xs text-text-muted text-center leading-relaxed">{label}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── TRUST SECTION ───────────────────────────────────────────────── */}
      <div className="border-y border-border bg-background py-10">
        <div className="mx-auto max-w-5xl px-6">
          <motion.p
            className="text-center text-[10px] text-text-muted uppercase tracking-widest mb-6"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={VP}
            transition={{ duration: 0.4 }}
          >
            Güvenli ve Uyumlu
          </motion.p>
          <motion.div
            className="flex flex-wrap items-center justify-center gap-8"
            initial="hidden"
            whileInView="visible"
            viewport={VP}
            variants={vStagger}
          >
            {[
              { Icon: Shield,       text: "SOC 2 Uyumlu",        sub: "Güvenlik sertifikası"      },
              { Icon: CheckCircle,  text: "KVKK Uyumlu",         sub: "Kişisel veri koruması"     },
              { Icon: Zap,          text: "99.9% Uptime SLA",    sub: "Garantili erişilebilirlik" },
              { Icon: Users,        text: "Çok Kiracılı Mimari", sub: "Tam veri izolasyonu"       },
              { Icon: Layers,       text: "Rol Tabanlı Erişim",  sub: "RBAC kontrol sistemi"      },
            ].map(({ Icon, text, sub }) => (
              <motion.div key={text} variants={vUp} className="flex items-center gap-2.5 group">
                <div className="w-8 h-8 rounded-lg bg-accent-subtle flex items-center justify-center flex-shrink-0 group-hover:bg-accent/20 transition-colors">
                  <Icon className="w-4 h-4 text-accent" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-text">{text}</div>
                  <div className="text-[10px] text-text-muted">{sub}</div>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>

      {/* ── PRE-FOOTER CTA ──────────────────────────────────────────────── */}
      <section className="py-20 relative overflow-hidden bg-surface">
        <div className="absolute inset-0 hero-grid opacity-15" />
        <div className="pointer-events-none absolute inset-0" style={{ background: "radial-gradient(ellipse 70% 70% at 50% 60%, rgba(99,102,241,0.06) 0%, rgba(67,56,202,0.03) 50%, transparent 70%)" }} />
        <div className="absolute top-0 inset-x-0 h-px bg-border" />

        <div className="relative mx-auto max-w-6xl px-6">
          <motion.div
            className="relative overflow-hidden rounded-3xl border border-border bg-surface shadow-xl"
            style={{ boxShadow: "0 0 0 1px var(--color-border), 0 32px 80px rgba(0,0,0,0.08), 0 4px 20px rgba(99,102,241,0.06)" }}
            initial={{ opacity: 0, y: 28 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={VP}
            transition={{ duration: 0.65, ease: ES }}
          >
            {/* Top accent line */}
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-accent opacity-40" />
            {/* Ambient glow */}
            <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-64 h-64 rounded-full blur-[100px] pointer-events-none" style={{ background: "rgba(99,102,241,0.08)" }} />

            <div className="grid lg:grid-cols-2 gap-0">
              {/* Left: text + CTAs */}
              <div className="relative p-10 md:p-14 flex flex-col justify-center">
                <div className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-border bg-surface-2 px-3 py-1.5 shadow-xs">
                  <Sparkles className="w-3.5 h-3.5 text-accent" />
                  <span className="text-xs font-semibold text-text-secondary">14 gün ücretsiz, kredi kartı yok</span>
                </div>

                <h2 className="mb-4 text-3xl font-black text-text leading-tight tracking-tight md:text-4xl">
                  Brief süreçlerinizi tek{" "}
                  <span className="gradient-text">merkezde</span>{" "}
                  yönetin.
                </h2>

                <p className="mb-8 text-base text-text-secondary leading-relaxed max-w-md">
                  Ajansınız, markalarınız ve ekibiniz aynı akışta çalışsın. Brief&apos;ten yayına, tüm süreç şeffaf ve izlenebilir.
                </p>

                <div className="flex flex-col sm:flex-row gap-3 mb-8">
                  <Link
                    href="/auth/register"
                    className="flex items-center justify-center gap-2.5 rounded-2xl px-7 py-3.5 text-sm font-bold text-white transition-all hover:scale-[1.03] active:scale-[0.98]"
                    style={{ background: "var(--gradient-accent)", boxShadow: "0 4px 20px rgba(99,102,241,0.30)" }}
                  >
                    Ücretsiz Başlayın
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                  <Link
                    href="/pricing"
                    className="flex items-center justify-center gap-2 rounded-2xl border border-border bg-surface px-7 py-3.5 text-sm font-semibold text-text-secondary hover:border-border-hover hover:text-text hover:shadow-sm transition-all"
                  >
                    Fiyatlandırmayı gör
                  </Link>
                </div>

                <div className="flex items-center gap-6 flex-wrap">
                  {["Kredi kartı gerekmez", "İstediğin zaman iptal", "14 gün tam erişim"].map(t => (
                    <div key={t} className="flex items-center gap-1.5 text-xs text-text-muted">
                      <CheckCircle className="w-3.5 h-3.5 text-success flex-shrink-0" />
                      {t}
                    </div>
                  ))}
                </div>
              </div>

              {/* Right: product mini scene */}
              <div className="relative hidden lg:flex items-center justify-center p-10 bg-surface-2/60 border-l border-border overflow-hidden">
                <div className="pointer-events-none absolute inset-0" style={{ background: "radial-gradient(circle at 60% 40%, rgba(99,102,241,0.04) 0%, transparent 60%)" }} />

                {/* Approval card */}
                <motion.div
                  className="absolute top-10 right-8 w-56"
                  animate={shouldReduceMotion ? {} : { y: [0, -6, 0] }}
                  transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
                >
                  <div className="bg-surface border border-border rounded-xl shadow-modal p-4">
                    <div className="flex items-center gap-2.5 mb-2">
                      <div className="w-6 h-6 rounded-full bg-success-subtle flex items-center justify-center flex-shrink-0">
                        <CheckCircle className="w-3.5 h-3.5 text-success" />
                      </div>
                      <span className="text-xs font-semibold text-text">Brief Onaylandı ✓</span>
                    </div>
                    <div className="text-[10px] text-text-muted">Q3 Sosyal Medya · Zara Home</div>
                    <div className="text-[10px] text-text-muted mt-0.5">Murat A. · Az önce</div>
                  </div>
                </motion.div>

                {/* Calendar card */}
                <motion.div
                  className="absolute bottom-10 left-8 w-48"
                  animate={shouldReduceMotion ? {} : { y: [0, -5, 0] }}
                  transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 1.2 }}
                >
                  <div className="bg-surface border border-border rounded-xl shadow-modal p-3.5">
                    <div className="flex items-center gap-2 mb-2">
                      <Calendar className="w-3.5 h-3.5 text-accent" />
                      <span className="text-[11px] font-semibold text-text">15 Tem</span>
                    </div>
                    <span className="text-[10px] status-success px-2 py-0.5 rounded-full">Yayına alındı</span>
                  </div>
                </motion.div>

                {/* Main mini card */}
                <div className="relative w-56 rounded-2xl border border-border bg-surface shadow-card p-5">
                  <div className="absolute inset-x-0 top-0 h-px bg-gradient-accent opacity-30 rounded-t-2xl" />
                  <div className="flex items-center gap-2.5 mb-4">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-black text-white flex-shrink-0" style={{ background: "var(--gradient-accent)" }}>N</div>
                    <div>
                      <div className="text-xs font-bold text-text">Nike TR</div>
                      <div className="text-[9px] text-text-muted">4 aktif brief</div>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    {[
                      { label: "Q3 Kampanya", cls: "status-success"  },
                      { label: "Influencer",  cls: "status-warning"  },
                      { label: "Brand Kit",   cls: "status-accent"   },
                    ].map(item => (
                      <div key={item.label} className="flex items-center justify-between text-[10px]">
                        <span className="text-text-secondary">{item.label}</span>
                        <span className={`px-1.5 py-0.5 rounded-full ${item.cls}`}>•</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Team avatars */}
                <div className="absolute bottom-8 right-10 flex -space-x-2">
                  {(["#4F46E5", "#4338CA", "#2563eb", "#059669"] as const).map((color, i) => (
                    <div
                      key={i}
                      className="w-7 h-7 rounded-full border-2 border-surface-2 flex items-center justify-center text-[9px] font-bold text-white"
                      style={{ background: color }}
                    >
                      {["AY", "SK", "MD", "ZA"][i]}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Existing account link */}
          <motion.div
            className="mt-6 text-center"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={VP}
            transition={{ duration: 0.4, delay: 0.3 }}
          >
            <button
              onClick={() => setLoginOpen(true)}
              className="text-sm text-text-muted hover:text-text transition-colors"
            >
              Zaten hesabınız var mı?{" "}
              <span className="text-accent font-medium">Giriş yapın →</span>
            </button>
          </motion.div>
        </div>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────────────────── */}
      <footer className="border-t border-border bg-background">

        {/* Main footer */}
        <div className="mx-auto max-w-7xl px-6 py-14">
          <div className="grid grid-cols-1 gap-10 sm:grid-cols-2 lg:grid-cols-4">

            {/* Brand */}
            <div className="lg:col-span-2">
              <Link href="/" className="inline-flex items-center gap-2.5 group mb-4">
                <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: "var(--gradient-accent)" }}>
                  <span className="text-white text-sm font-black">F</span>
                </div>
                <span className="text-base font-bold text-text group-hover:text-accent transition-colors tracking-tight">Flobrief</span>
              </Link>
              <p className="text-sm text-text-muted leading-relaxed max-w-xs mb-6">
                Ajanslar ve markalar için brief yönetimi, onay akışları ve içerik takvimi platformu.
                Uçtan uca süreç, tek ekrandan.
              </p>
              <div className="flex gap-3">
                <Link
                  href="/auth/register"
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-white px-4 py-2 rounded-xl transition-all hover:opacity-90"
                  style={{ background: "var(--gradient-accent)" }}
                >
                  Başla
                  <ArrowRight className="w-3 h-3" />
                </Link>
                <Link
                  href="/pricing"
                  className="inline-flex items-center text-xs font-medium text-text-secondary px-4 py-2 rounded-xl border border-border hover:border-border-hover hover:text-text transition-all"
                >
                  Fiyatlandırma
                </Link>
              </div>
            </div>

            {/* Product */}
            <div>
              <h4 className="text-xs font-bold text-text uppercase tracking-wider mb-4">Ürün</h4>
              <ul className="space-y-3">
                {[
                  { label: "Özellikler",       href: "#features" },
                  { label: "İş Akışı",         href: "#workflow" },
                  { label: "Sonuçlar",         href: "#stats"    },
                  { label: "Fiyatlandırma",    href: "/pricing"  },
                ].map(({ label, href }) => (
                  <li key={label}>
                    <a
                      href={href}
                      className="text-sm text-text-muted hover:text-text transition-colors inline-flex items-center gap-1 group"
                    >
                      {label}
                      <ChevronRight className="w-3 h-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            {/* Get started */}
            <div>
              <h4 className="text-xs font-bold text-text uppercase tracking-wider mb-4">Başlangıç</h4>
              <ul className="space-y-3">
                {[
                  { label: "Ücretsiz Kayıt",  href: "/auth/register"      },
                  { label: "Ajans Girişi",    href: "/auth/agency-login"  },
                  { label: "Marka Girişi",    href: "/brand/login"        },
                  { label: "Yönetici Girişi", href: "/platform/login"     },
                ].map(({ label, href }) => (
                  <li key={label}>
                    <Link
                      href={href}
                      className="text-sm text-text-muted hover:text-text transition-colors inline-flex items-center gap-1 group"
                    >
                      {label}
                      <ChevronRight className="w-3 h-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="border-t border-border">
          <div className="mx-auto max-w-7xl px-6 py-5">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
              <p className="text-xs text-text-muted order-2 sm:order-1">
                © {new Date().getFullYear()} Flobrief. Tüm hakları saklıdır.
              </p>
              <div className="flex items-center gap-1.5 order-1 sm:order-2">
                <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                <span className="text-xs text-text-muted">Tüm sistemler çalışıyor</span>
              </div>
            </div>
          </div>
        </div>
      </footer>

      <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} />
    </div>
  );
}
