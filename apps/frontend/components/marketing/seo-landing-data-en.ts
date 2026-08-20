import type { LandingPageConfig, LandingSlug } from "./seo-landing-data";

type EnglishIntent = Pick<LandingPageConfig, "badge" | "h1" | "description" | "title" | "metaDescription" | "visual" | "hero" | "tone"> & {
  problemTitle: string;
  problemDescription: string;
  solutionTitle: string;
  solutionDescription: string;
  steps: string[];
  features: LandingPageConfig["features"];
};

const intents: Record<LandingSlug, EnglishIntent> = {
  "ajans-programi": {
    badge: "A connected workspace for creative agencies",
    h1: "Creative Agency Management Software for Briefs, Feedback, and Approvals",
    description: "Coordinate client briefs, production feedback, deliverables, approvals, and content planning without losing context across tools.",
    title: "Creative Agency Management Software | PostPiloter",
    metaDescription: "Manage agency briefs, client feedback, creative deliverables, approvals, and content planning in one shared workspace.",
    visual: "agency", hero: "split", tone: "indigo",
    problemTitle: "Creative operations become hard to follow when every handoff lives in a different channel",
    problemDescription: "Email threads, messages, spreadsheets, and separate file links make it difficult to identify the latest request, revision, or decision.",
    solutionTitle: "Keep the client, brief, work, feedback, and approval history together",
    solutionDescription: "PostPiloter gives agency and brand teams a shared record of what was requested, what changed, and what was approved.",
    steps: ["Client", "Brief", "Production", "Feedback", "Approval", "Delivery"],
    features: [
      { title: "Structured client briefs", description: "Collect consistent requests and give the team a clear starting point.", icon: "brief" },
      { title: "Contextual feedback", description: "Keep comments and changes attached to the relevant work.", icon: "message" },
      { title: "Visible approval status", description: "See what is being reviewed, revised, or approved.", icon: "check" },
      { title: "Client workspace", description: "Give each brand a focused view of its briefs, files, and decisions.", icon: "portal" },
    ],
  },
  "musteri-onay-sistemi": {
    badge: "Clear feedback and recorded decisions",
    h1: "Client Approval Software for Creative Work",
    description: "Share deliverables, collect contextual comments, manage revision requests, and record the client’s final approval in one place.",
    title: "Client Approval Software for Agencies | PostPiloter",
    metaDescription: "Collect client feedback, revision requests, and approvals on creative deliverables with a clear version and decision history.",
    visual: "approval", hero: "centered", tone: "emerald",
    problemTitle: "An approval message is not useful if nobody knows which version it refers to",
    problemDescription: "When the file, feedback, and final decision live in separate places, teams spend time confirming what the client actually approved.",
    solutionTitle: "Give every deliverable one clear review and decision trail",
    solutionDescription: "Clients can review the work, comment, request changes, or approve while the agency keeps the result tied to the correct version.",
    steps: ["Share", "Review", "Comment", "Revise", "Approve"],
    features: [
      { title: "Deliverable comments", description: "Keep feedback connected to the work being reviewed.", icon: "message" },
      { title: "Decision status", description: "Distinguish review, revision, and approval states.", icon: "check" },
      { title: "Version visibility", description: "Make the current and earlier deliverables easy to identify.", icon: "history" },
      { title: "Client access", description: "Let clients review and decide from their own portal.", icon: "portal" },
    ],
  },
  "revizyon-takip": {
    badge: "Keep every change request visible",
    h1: "Creative Proofing and Revision Tracking Software",
    description: "Keep visual feedback, revision requests, replies, and deliverable versions connected from the first review to final approval.",
    title: "Creative Proofing and Revision Tracking | PostPiloter",
    metaDescription: "Track client feedback, visual annotations, revision requests, deliverable versions, and approvals in one creative proofing workflow.",
    visual: "revision", hero: "split", tone: "amber",
    problemTitle: "Scattered feedback makes revision rounds longer and less reliable",
    problemDescription: "Teams lose time resolving conflicting comments, open changes, and uncertainty about which version contains the latest update.",
    solutionTitle: "Keep each request attached to the work and version it belongs to",
    solutionDescription: "Capture feedback in context, share an updated deliverable, and keep open requests visible until the review is complete.",
    steps: ["Share work", "Collect feedback", "Apply changes", "Upload a version", "Get approval"],
    features: [
      { title: "Visual annotations", description: "Point to the exact area that needs attention.", icon: "message" },
      { title: "Deliverable versions", description: "Separate the latest work from earlier review rounds.", icon: "history" },
      { title: "Open feedback", description: "Track unresolved comments and replies.", icon: "check" },
      { title: "Central files", description: "Keep deliverables with their brief and review context.", icon: "file" },
    ],
  },
  "musteri-portali": {
    badge: "A professional client-facing workspace",
    h1: "Client Portal Software for Creative Agencies",
    description: "Give every client one place to submit briefs, review work, share feedback, approve deliverables, and access relevant files.",
    title: "Client Portal Software for Creative Agencies | PostPiloter",
    metaDescription: "Offer agency clients a branded portal for briefs, creative work, comments, revisions, approvals, files, and content planning.",
    visual: "portal", hero: "split", tone: "violet",
    problemTitle: "A professional service also needs a professional client experience",
    problemDescription: "Clients should not need to message the agency whenever they want to find the latest work, pending approval, or shared file.",
    solutionTitle: "Give each brand a clear view of its active creative work",
    solutionDescription: "The portal brings briefs, deliverables, calendar items, comments, revisions, approvals, and shared files into one focused experience.",
    steps: ["Sign in", "Submit a brief", "Follow progress", "Review work", "Comment or approve"],
    features: [
      { title: "Client dashboard", description: "Surface active work and items that need attention.", icon: "portal" },
      { title: "Briefs and files", description: "Collect requests and supporting material together.", icon: "file" },
      { title: "Feedback and approval", description: "Move review decisions into the client workspace.", icon: "check" },
      { title: "Agency branding", description: "Apply the agency’s logo and colors to the portal experience.", icon: "palette" },
    ],
  },
  "online-brief": {
    badge: "Better inputs create clearer work",
    h1: "Online Creative Brief Software for Agencies",
    description: "Collect complete client requests with structured digital brief forms and keep every submission connected to the work that follows.",
    title: "Online Creative Brief Software for Agencies | PostPiloter",
    metaDescription: "Standardize client requests with online creative brief forms, supporting files, required fields, and a connected agency workflow.",
    visual: "brief", hero: "centered", tone: "blue",
    problemTitle: "A message thread is not a complete creative brief",
    problemDescription: "Inconsistent requests leave important questions unanswered and force the team to collect the same details again before work can begin.",
    solutionTitle: "Collect structured client input from the start",
    solutionDescription: "Use digital brief forms to capture the objective, scope, timing, references, and files in a consistent record.",
    steps: ["Choose a form", "Collect details", "Attach files", "Review the request", "Start production"],
    features: [
      { title: "Structured fields", description: "Ask the right questions in a repeatable format.", icon: "brief" },
      { title: "Supporting files", description: "Keep references and attachments with the request.", icon: "file" },
      { title: "Connected workflow", description: "Move an accepted brief into production without losing context.", icon: "history" },
      { title: "Client access", description: "Let clients submit and follow briefs from their portal.", icon: "portal" },
    ],
  },
};

export const SEO_LANDING_PAGES_EN = Object.fromEntries(
  Object.entries(intents).map(([slug, item]) => [slug, {
    slug,
    ...item,
    problem: { eyebrow: "The operational gap", title: item.problemTitle, description: item.problemDescription, points: ["Scattered requests", "Unclear revision history", "Decisions without context"] },
    solution: { eyebrow: "A connected workflow", title: item.solutionTitle, description: item.solutionDescription },
    workflow: { title: "A workflow everyone can follow", description: "Keep every handoff connected to the same source of truth.", steps: item.steps },
    scenario: { title: "When the next client request arrives", description: "The client and agency work from the same brief, deliverable, feedback, and decision history.", agency: "The agency sees the current owner, status, and open feedback.", customer: "The client sees the latest work and the decision it needs to make." },
    proof: ["Structured briefs", "Contextual feedback", "Recorded approvals"],
    related: (Object.keys(intents) as LandingSlug[]).filter((related) => related !== slug).slice(0, 4),
    sectionOrder: ["problem", "workflow", "features", "scenario"],
  }])
) as unknown as Record<LandingSlug, LandingPageConfig>;
