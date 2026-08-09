"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { cn } from "@/lib/utils";
import type { MentionCandidate } from "@/lib/api-client";
import { useMentionTrigger, detectTrigger } from "@/components/mentions/useMentionTrigger";
import { MentionSuggestionPopover } from "@/components/mentions/MentionSuggestionPopover";

// Client-side HTML allowlist sanitizer (mirrors backend)
const ALLOWED_TAGS = new Set([
  "P", "BR", "STRONG", "B", "EM", "I", "U", "S",
  "H1", "H2", "H3", "H4",
  "UL", "OL", "LI",
  "A", "BLOCKQUOTE", "PRE", "CODE",
  "SPAN", "DIV",
]);

// Allowlist, not blocklist: browsers strip ASCII control characters (tabs,
// newlines, etc.) from anywhere in a URL before parsing its scheme, so a
// naive `startsWith("javascript")` check can be bypassed with e.g.
// "java\tscript:alert(1)". Stripping control chars first and requiring the
// scheme (if any) to be on an allowlist closes that regardless of obfuscation.
const ALLOWED_URI_SCHEMES = new Set(["http", "https", "mailto", "tel"]);

function isSafeHref(value: string): boolean {
  // eslint-disable-next-line no-control-regex
  const cleaned = value.replace(/[\x00-\x1f\x7f]/g, "").trim();
  const match = /^([a-zA-Z][a-zA-Z0-9+.-]*):/.exec(cleaned);
  if (!match) return true; // no scheme — relative/fragment URL, safe
  return ALLOWED_URI_SCHEMES.has(match[1].toLowerCase());
}

function sanitizeNode(node: Node): Node | null {
  if (node.nodeType === Node.TEXT_NODE) return node.cloneNode();
  if (node.nodeType !== Node.ELEMENT_NODE) return null;
  const el = node as Element;
  if (!ALLOWED_TAGS.has(el.tagName)) {
    const frag = document.createDocumentFragment();
    el.childNodes.forEach((c) => {
      const s = sanitizeNode(c);
      if (s) frag.appendChild(s);
    });
    return frag;
  }
  const clone = document.createElement(el.tagName.toLowerCase());
  if (el.tagName === "A") {
    const href = el.getAttribute("href") || "";
    if (href && isSafeHref(href)) {
      clone.setAttribute("href", href);
    }
    clone.setAttribute("rel", "noopener noreferrer");
    clone.setAttribute("target", "_blank");
  }
  el.childNodes.forEach((c) => {
    const s = sanitizeNode(c);
    if (s) clone.appendChild(s);
  });
  return clone;
}

export function sanitizeHtml(html: string): string {
  if (typeof document === "undefined") return html;
  const div = document.createElement("div");
  div.innerHTML = html;
  const out = document.createElement("div");
  div.childNodes.forEach((c) => {
    const s = sanitizeNode(c);
    if (s) out.appendChild(s);
  });
  return out.innerHTML;
}

// ── Toolbar button ────────────────────────────────────────────────────────────

interface ToolbarButtonProps {
  title: string;
  onClick: () => void;
  children: React.ReactNode;
}

function ToolbarButton({ title, onClick, children }: ToolbarButtonProps) {
  return (
    <button
      type="button"
      title={title}
      onMouseDown={(e) => {
        e.preventDefault();
        onClick();
      }}
      className="w-7 h-7 rounded flex items-center justify-center text-sm text-text-muted hover:text-text hover:bg-hover transition-colors select-none"
    >
      {children}
    </button>
  );
}

// ── Link modal ────────────────────────────────────────────────────────────────

interface LinkModalProps {
  onConfirm: (url: string) => void;
  onClose: () => void;
}

function LinkModal({ onConfirm, onClose }: LinkModalProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => { inputRef.current?.focus(); }, []);
  return (
    <div className="absolute z-50 top-full mt-1 left-0 bg-surface border border-border rounded-lg shadow-lg p-3 w-72">
      <p className="text-xs font-medium text-text mb-2">Bağlantı URL&apos;si</p>
      <input
        ref={inputRef}
        type="url"
        placeholder="https://..."
        className="w-full text-xs bg-background border border-border rounded px-2.5 py-1.5 text-text placeholder:text-text-muted outline-none focus:border-accent"
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); onConfirm((e.target as HTMLInputElement).value); }
          if (e.key === "Escape") onClose();
        }}
      />
      <div className="flex gap-2 mt-2">
        <button
          type="button"
          onClick={() => onConfirm(inputRef.current?.value || "")}
          className="flex-1 text-xs bg-accent text-white rounded px-2 py-1 hover:bg-accent/90"
        >
          Ekle
        </button>
        <button
          type="button"
          onClick={onClose}
          className="flex-1 text-xs border border-border text-text-muted rounded px-2 py-1 hover:text-text"
        >
          İptal
        </button>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface RichTextEditorProps {
  value?: string;
  onChange?: (html: string) => void;
  placeholder?: string;
  error?: string | null;
  readOnly?: boolean;
  minHeight?: number;
  className?: string;
  /** Enables the @mention popover; omit to keep the editor mention-free. */
  mentionCandidatesFetcher?: (query: string) => Promise<MentionCandidate[]>;
  /** Fired every time a mention is inserted via the popover (Enter/Tab/click). */
  onMentionInsert?: (candidate: MentionCandidate) => void;
}

function getCaretContext(
  editor: HTMLElement
): { textBeforeCaret: string; range: Range } | null {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return null;
  const range = sel.getRangeAt(0);
  if (!range.collapsed || !editor.contains(range.startContainer)) return null;
  const node = range.startContainer;
  if (node.nodeType !== Node.TEXT_NODE) return null;
  const text = node.textContent || "";
  return { textBeforeCaret: text.slice(0, range.startOffset), range };
}

function insertMentionChip(range: Range, matchLength: number, candidate: MentionCandidate): boolean {
  const textNode = range.startContainer as Text;
  const caretOffset = range.startOffset;
  const startOffset = caretOffset - (matchLength + 1); // +1 for the "@"
  if (startOffset < 0) return false;

  const delRange = document.createRange();
  delRange.setStart(textNode, startOffset);
  delRange.setEnd(textNode, caretOffset);
  delRange.deleteContents();

  const chip = document.createElement("span");
  chip.className = "mention-chip";
  chip.setAttribute("contenteditable", "false");
  chip.setAttribute("data-mention-user-id", candidate.user_id);
  chip.textContent = `@${candidate.display_name}`;
  const spaceNode = document.createTextNode(" ");

  const frag = document.createDocumentFragment();
  frag.appendChild(chip);
  frag.appendChild(spaceNode);
  delRange.insertNode(frag);

  const newRange = document.createRange();
  newRange.setStartAfter(spaceNode);
  newRange.collapse(true);
  const sel = window.getSelection();
  sel?.removeAllRanges();
  sel?.addRange(newRange);
  return true;
}

export default function RichTextEditor({
  value = "",
  onChange,
  placeholder = "İçerik yazın…",
  error,
  readOnly = false,
  minHeight = 160,
  className,
  mentionCandidatesFetcher,
  onMentionInsert,
}: RichTextEditorProps) {
  const editorRef = useRef<HTMLDivElement>(null);
  const lastValueRef = useRef<string>("");
  const savedRangeRef = useRef<Range | null>(null);
  const [showLink, setShowLink] = useState(false);
  const mention = useMentionTrigger(mentionCandidatesFetcher);

  // Sync external value → editor DOM on mount (skip if editor is focused)
  useEffect(() => {
    if (!editorRef.current) return;
    if (value !== lastValueRef.current) {
      lastValueRef.current = value;
      if (document.activeElement !== editorRef.current) {
        editorRef.current.innerHTML = sanitizeHtml(value);
      }
    }
  }, [value]);

  const emit = useCallback(() => {
    if (!editorRef.current || !onChange) return;
    const html = sanitizeHtml(editorRef.current.innerHTML);
    lastValueRef.current = html;
    onChange(html);
  }, [onChange]);

  const exec = useCallback((cmd: string, val?: string) => {
    editorRef.current?.focus();
    document.execCommand(cmd, false, val);
    emit();
  }, [emit]);

  const saveRange = () => {
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0) savedRangeRef.current = sel.getRangeAt(0).cloneRange();
  };

  const restoreRange = () => {
    const r = savedRangeRef.current;
    if (!r) return;
    const sel = window.getSelection();
    if (sel) { sel.removeAllRanges(); sel.addRange(r); }
  };

  function insertLink(url: string) {
    restoreRange();
    editorRef.current?.focus();
    if (url) exec("createLink", url);
    setShowLink(false);
    emit();
  }

  const detectMentionTrigger = useCallback(() => {
    if (!editorRef.current || !mentionCandidatesFetcher) return;
    const ctx = getCaretContext(editorRef.current);
    const query = ctx ? detectTrigger(ctx.textBeforeCaret) : null;
    if (ctx && query !== null) {
      const rect = ctx.range.getBoundingClientRect();
      mention.open(query, { top: rect.bottom || rect.top, left: rect.left });
    } else {
      mention.close();
    }
  }, [mentionCandidatesFetcher, mention]);

  const handleMentionSelect = useCallback(
    (candidate: MentionCandidate) => {
      if (editorRef.current) {
        const ctx = getCaretContext(editorRef.current);
        if (ctx) {
          const query = detectTrigger(ctx.textBeforeCaret) ?? "";
          insertMentionChip(ctx.range, query.length, candidate);
        }
      }
      mention.close();
      onMentionInsert?.(candidate);
      emit();
    },
    [mention, onMentionInsert, emit]
  );

  const handleEditorKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (!mention.state.active) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        mention.moveHighlight(1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        mention.moveHighlight(-1);
      } else if (e.key === "Enter" || e.key === "Tab") {
        if (mention.state.candidates.length > 0) {
          e.preventDefault();
          handleMentionSelect(mention.state.candidates[mention.state.highlightedIndex]);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        mention.close();
      }
    },
    [mention, handleMentionSelect]
  );

  if (readOnly) {
    return (
      <div
        className={cn("prose-custom text-sm text-text leading-relaxed", className)}
        dangerouslySetInnerHTML={{ __html: sanitizeHtml(value) }}
      />
    );
  }

  return (
    <div className={cn("relative", className)}>
      {/* Toolbar */}
      <div className="flex items-center gap-0.5 px-2 py-1.5 border border-border rounded-t-lg bg-surface/50 flex-wrap">
        <ToolbarButton title="Kalın (Ctrl+B)" onClick={() => exec("bold")}>
          <strong className="text-xs leading-none">B</strong>
        </ToolbarButton>
        <ToolbarButton title="İtalik (Ctrl+I)" onClick={() => exec("italic")}>
          <em className="text-xs not-italic font-serif leading-none">I</em>
        </ToolbarButton>
        <ToolbarButton title="Altı çizili (Ctrl+U)" onClick={() => exec("underline")}>
          <span className="text-xs underline leading-none">U</span>
        </ToolbarButton>

        <div className="w-px h-4 bg-border mx-0.5" />

        <ToolbarButton title="Başlık 2" onClick={() => exec("formatBlock", "h2")}>
          <span className="text-[10px] font-bold leading-none">H2</span>
        </ToolbarButton>
        <ToolbarButton title="Başlık 3" onClick={() => exec("formatBlock", "h3")}>
          <span className="text-[10px] font-bold leading-none">H3</span>
        </ToolbarButton>
        <ToolbarButton title="Paragraf" onClick={() => exec("formatBlock", "p")}>
          <span className="text-[10px] leading-none">¶</span>
        </ToolbarButton>

        <div className="w-px h-4 bg-border mx-0.5" />

        <ToolbarButton title="Madde listesi" onClick={() => exec("insertUnorderedList")}>
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </ToolbarButton>
        <ToolbarButton title="Numaralı liste" onClick={() => exec("insertOrderedList")}>
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 6h13M7 12h13M7 18h13M3 6h.01M3 12h.01M3 18h.01" />
          </svg>
        </ToolbarButton>

        <div className="w-px h-4 bg-border mx-0.5" />

        <div className="relative">
          <ToolbarButton
            title="Bağlantı ekle"
            onClick={() => {
              saveRange();
              setShowLink(true);
            }}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </ToolbarButton>
          {showLink && (
            <LinkModal onConfirm={insertLink} onClose={() => setShowLink(false)} />
          )}
        </div>

        <div className="w-px h-4 bg-border mx-0.5" />

        <ToolbarButton title="Geri al" onClick={() => exec("undo")}>
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
          </svg>
        </ToolbarButton>
        <ToolbarButton title="Yinele" onClick={() => exec("redo")}>
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10H11a8 8 0 00-8 8v2m18-10l-6 6m6-6l-6-6" />
          </svg>
        </ToolbarButton>
      </div>

      {/* Editor */}
      <div
        ref={editorRef}
        contentEditable
        suppressContentEditableWarning
        spellCheck
        data-placeholder={placeholder}
        style={{ minHeight }}
        onInput={() => {
          emit();
          detectMentionTrigger();
        }}
        onKeyDown={handleEditorKeyDown}
        onBlur={() => {
          emit();
          mention.close();
        }}
        className={cn(
          "px-3 py-2.5 border border-t-0 border-border rounded-b-lg",
          "text-sm text-text leading-relaxed outline-none",
          "bg-background focus:border-accent transition-colors overflow-auto",
          "[&:empty]:before:content-[attr(data-placeholder)] [&:empty]:before:text-text-muted [&:empty]:before:pointer-events-none",
          error && "border-danger"
        )}
      />

      {error && (
        <p className="mt-1 text-xs text-danger">{error}</p>
      )}

      {mentionCandidatesFetcher && (
        <MentionSuggestionPopover
          state={mention.state}
          onSelect={handleMentionSelect}
          onHighlight={mention.setHighlight}
        />
      )}
    </div>
  );
}
