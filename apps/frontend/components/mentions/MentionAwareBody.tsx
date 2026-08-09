"use client";

import { useEffect, useRef } from "react";
import { sanitizeHtml } from "@/components/forms/RichTextEditor";
import type { MentionInline } from "@/lib/api-client";

interface MentionAwareBodyProps {
  html: string;
  mentions: MentionInline[];
  className?: string;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Renders sanitized comment/annotation HTML, then upgrades only the
 * @mentions the backend actually confirmed (never arbitrary "@word" text)
 * into styled chips. Operates on already-sanitized live DOM text nodes
 * (never re-injects HTML strings), so it can't reintroduce an XSS vector.
 * Deactivated/removed team members render with a muted "Eski ekip üyesi"
 * tooltip instead of a raw ID.
 */
export function MentionAwareBody({ html, mentions, className }: MentionAwareBodyProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = ref.current;
    if (!container || mentions.length === 0) return;

    const names = Array.from(new Set(mentions.map((m) => m.display_text)))
      .sort((a, b) => b.length - a.length)
      .map(escapeRegExp);
    if (names.length === 0) return;
    const pattern = new RegExp(`@(${names.join("|")})(?![\\w])`, "g");

    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const textNodes: Text[] = [];
    let current: Node | null = walker.nextNode();
    while (current) {
      textNodes.push(current as Text);
      current = walker.nextNode();
    }

    for (const node of textNodes) {
      const text = node.textContent ?? "";
      pattern.lastIndex = 0;
      if (!pattern.test(text)) continue;
      pattern.lastIndex = 0;

      const frag = document.createDocumentFragment();
      let cursor = 0;
      let match: RegExpExecArray | null;
      while ((match = pattern.exec(text))) {
        const before = text.slice(cursor, match.index);
        if (before) frag.appendChild(document.createTextNode(before));

        const name = match[1];
        const mention = mentions.find((m) => m.display_text === name);
        const chip = document.createElement("span");
        chip.textContent = `@${name}`;
        chip.className = mention?.is_active === false
          ? "mention-chip mention-chip--inactive"
          : "mention-chip";
        chip.title = mention?.is_active === false ? "Eski ekip üyesi" : name;
        frag.appendChild(chip);

        cursor = match.index + match[0].length;
      }
      const rest = text.slice(cursor);
      if (rest) frag.appendChild(document.createTextNode(rest));
      node.parentNode?.replaceChild(frag, node);
    }
  }, [html, mentions]);

  return (
    <div
      ref={ref}
      className={className}
      dangerouslySetInnerHTML={{ __html: sanitizeHtml(html) }}
    />
  );
}
