# PostPiloter — UI/UX DNA

## Positioning
PostPiloter is a premium B2B SaaS tool used by professional agencies to manage their brand clients.
The UI must reflect this: every screen should feel like it belongs in a sales demo or a VC pitch deck.

## Quality Benchmark
Reference quality (feel, not copy): Linear, Attio, Stripe Dashboard, Vercel, Raycast, Framer.
These tools share: intentional whitespace, strong typography hierarchy, minimal chrome, confident color use.

## Color System
```
Background:   #0A0A0F (near-black, not pure black)
Surface:      #111118
Surface-2:    #1A1A24
Border:       #2A2A3A
Text:         #F0F0F8 (primary)
Text-muted:   #8888A8
Accent:       #6366F1 (indigo — brand primary)
Accent-hover: #4F52E0
Success:      #10B981
Warning:      #F59E0B
Danger:       #EF4444
```

## Typography
- Font: Inter (variable weight)
- Page title: 28-32px, weight 700, tight tracking
- Section heading: 18-20px, weight 600
- Body: 14px, weight 400, line-height 1.6
- Label/caption: 12px, weight 500, letter-spacing 0.02em
- Monospace (IDs, codes): JetBrains Mono or system monospace

## Spacing System
- Base unit: 4px
- Component padding: 16px (sm), 24px (md), 32px (lg)
- Section gaps: 32-48px
- Card padding: 24px
- No cramped layouts — breathing room is premium

## Component Standards

### Cards
- Background: Surface (#111118)
- Border: 1px solid Border (#2A2A3A)
- Border-radius: 12px
- Box-shadow: 0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.04)
- Hover: border brightens to #3A3A4A, subtle lift

### Buttons
- Primary: Accent bg, white text, 8px radius, 40px height
- Secondary: transparent, Border stroke, Text color
- Ghost: no border, muted text, hover shows soft bg
- Destructive: Danger color
- All buttons: 400ms transition, no jarring state changes

### Forms & Inputs
- Background: Surface-2
- Border: Border color, focus → Accent with glow (box-shadow: 0 0 0 3px rgba(99,102,241,0.2))
- Height: 40px (default), 36px (compact)
- Placeholder: Text-muted
- Error: Danger border + error message below
- No plain HTML-looking form fields

### Tables
- Header: Surface-2 background, uppercase 11px labels, muted color
- Row hover: subtle bg shift
- Row height: 48px minimum
- Borders: only horizontal dividers
- Sticky header for long lists

### Navigation Sidebar
- Width: 240px
- Background: Surface
- Items: icon + label, 36px height, 8px radius on hover
- Active: Accent bg (10% opacity), Accent text, left border accent
- Sections separated by subtle labels

### Modals
- Overlay: rgba(0,0,0,0.7) blur(4px)
- Panel: Surface bg, 16px radius, max-width 560px (default)
- Header: title + close button, 24px padding
- Footer: action buttons right-aligned

### Badges / Status Pills
- Draft: gray
- Submitted: blue
- In Review: amber
- Approved: green
- Revision Requested: orange
- Rejected: red
- All: 6px radius, 12px text, weight 500, solid or subtle fill variant

## Required States (Every Screen)
- **Loading**: Skeleton shimmer — same layout as loaded state but with animated gray bars
- **Empty state**: Centered illustration (SVG) + headline + sub-copy + primary CTA button
- **Error state**: Error icon + message + retry action
- **Success feedback**: Toast notification (top-right, auto-dismiss 4s)
- No spinner-only loading states for full pages

## Layout Rules
- Max content width: 1280px, centered
- Sidebar layout for authenticated app
- Full-width layout for approval portal (brand-facing)
- No horizontal scrollbars on any screen
- Responsive breakpoints: 375, 768, 1024, 1280, 1440

## Motion
- Transition: 150-250ms ease-out for micro-interactions
- Page transitions: fade (150ms)
- Modal: scale(0.96)+opacity → scale(1)+opacity, 200ms
- Skeleton shimmer: 1.5s loop
- No decorative animations that delay user interaction

## Dashboard Specific
- Hero metric cards at top (4 across)
- Recent activity feed
- Quick action buttons (prominent)
- Chart section below fold
- Must look compelling in a 1280px browser screenshot for demos

## Approval Portal (Brand-Facing)
- Full white-label capable
- Clean, minimal, professional
- No "logged in as agency" chrome
- Brand logo in header
- Status timeline visible
- Comment/revision UI clean and focused
- Mobile-first for brand reviewers

## Anti-Patterns (Never Do)
- Gray admin panel look (Bootstrap default, MUI default)
- Bright white (#FFFFFF) full-page backgrounds
- Comic Sans, default system serif fonts
- More than 3 font sizes on one screen
- Inconsistent border-radius (pick one and stick to it)
- Clipart or stock photo illustrations
- Too many colors (stay in the palette)
- Cluttered navigation with 20+ items
- Form labels inside inputs (floating labels only if done right)
- Tables without row hover states
