import { localizeApiErrorMessage } from "@/lib/i18n/error";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

const API_ERROR_MESSAGE_KEYS = [
  "message",
  "msg",
  "detail",
  "error",
  "reason",
  "description",
  "title",
] as const;

function extractApiErrorMessage(
  value: unknown,
  depth = 0,
  seen = new Set<object>()
): string {
  if (typeof value === "string") {
    return value.trim();
  }

  if (value === null || value === undefined || depth > 4) {
    return "";
  }

  if (Array.isArray(value)) {
    const messages = value
      .map((item) => {
        if (item && typeof item === "object" && !Array.isArray(item)) {
          const validationItem = item as Record<string, unknown>;
          const message = extractApiErrorMessage(
            validationItem.msg ?? validationItem.message ?? validationItem.detail,
            depth + 1,
            seen
          );
          const location = Array.isArray(validationItem.loc)
            ? validationItem.loc
                .filter((part) => part !== "body" && part !== "query")
                .map(String)
                .join(".")
            : "";

          if (message) {
            return location ? `${location}: ${message}` : message;
          }
        }

        return extractApiErrorMessage(item, depth + 1, seen);
      })
      .filter(Boolean);

    return [...new Set(messages)].join("; ");
  }

  if (typeof value === "object") {
    if (seen.has(value)) {
      return "";
    }
    seen.add(value);

    const record = value as Record<string, unknown>;
    for (const key of API_ERROR_MESSAGE_KEYS) {
      if (key in record) {
        const message = extractApiErrorMessage(record[key], depth + 1, seen);
        if (message) {
          return message;
        }
      }
    }

    if ("errors" in record) {
      return extractApiErrorMessage(record.errors, depth + 1, seen);
    }
  }

  return "";
}

export function formatApiErrorMessage(detail: unknown, status: number): string {
  return extractApiErrorMessage(detail) || `HTTP ${status}`;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: unknown,
    public readonly detail?: unknown
  ) {
    super(localizeApiErrorMessage(formatApiErrorMessage(message, status), status));
    this.name = "ApiError";
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  agencyId?: string | null;
};

async function request<T>(
  path: string,
  options: RequestOptions = {},
  accessToken?: string | null
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  if (options.agencyId) {
    headers["X-Agency-ID"] = options.agencyId;
  }

  const { body, agencyId: _agencyId, ...rest } = options;

  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: { ...headers, ...(rest.headers as Record<string, string> || {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: "include",
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorData?.detail || `HTTP ${response.status}`,
      errorData
    );
  }

  // A 204 (or any empty body) still commonly carries a "content-type:
  // application/json" header from the server's default response class, even
  // though there is no body to parse. Calling response.json() on that throws
  // a raw SyntaxError ("Unexpected end of JSON input") that isn't an ApiError
  // — callers that branch on `instanceof ApiError` then report a generic
  // failure for what was actually a successful request. Guard on status/body
  // presence first so a truly empty response always resolves to null.
  if (response.status === 204) {
    return null as T;
  }

  const contentType = response.headers.get("content-type");
  if (contentType?.includes("application/json")) {
    const text = await response.text();
    return (text ? JSON.parse(text) : null) as T;
  }

  return null as T;
}

export interface RegisterRequest {
  email: string;
  full_name: string;
  password: string;
  phone_number?: string | null;
  whatsapp_opt_in?: boolean;
  locale?: "en" | "tr";
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  mfa_required: boolean;
  mfa_session_token?: string | null;
}

export interface DemoPublicStatus {
  enabled: boolean;
  available: boolean;
  unavailable_reason: string | null;
  duration_hours: number;
  captcha_required: boolean;
  captcha_site_key: string | null;
  active_sandboxes: number;
  capacity: number;
}

export interface DemoStartResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  agency_id: string;
  expires_at: string;
}

export const demoApi = {
  status: () => request<DemoPublicStatus>("/api/v1/demo/status"),
  start: (turnstileToken?: string | null) =>
    request<DemoStartResponse>("/api/v1/demo/sandboxes", {
      method: "POST",
      body: { turnstile_token: turnstileToken ?? null },
    }),
};

export interface ContactSubmissionRequest {
  name: string;
  email: string;
  company?: string | null;
  phone?: string | null;
  subject: string;
  message: string;
  consent: boolean;
  source_path?: string | null;
  website?: string | null;
}

export interface ContactSubmissionRead {
  id: string;
  name: string;
  email: string;
  company: string | null;
  phone: string | null;
  subject: string;
  message: string;
  consent: boolean;
  status: "new" | "in_progress" | "resolved" | "spam";
  source_path: string | null;
  created_at: string;
  updated_at: string;
}

export const contactApi = {
  submit: (data: ContactSubmissionRequest) =>
    request<{ id: string; message: string }>("/api/v1/contact/submissions", {
      method: "POST",
      body: data,
    }),
};

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  job_title: string | null;
  avatar_url: string | null;
  user_type: "agency_user" | "brand_user" | "platform_admin";
  is_active: boolean;
  is_verified: boolean;
  mfa_enabled: boolean;
  phone_number: string | null;
  whatsapp_opt_in: boolean;
  locale: "en" | "tr" | null;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MessageResponse {
  message: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export const authApi = {
  register: (data: RegisterRequest) =>
    request<AuthUser>("/api/v1/auth/register", { method: "POST", body: data }),

  login: (data: LoginRequest) =>
    request<TokenResponse>("/api/v1/auth/login", { method: "POST", body: data }),

  logout: () =>
    request<MessageResponse>("/api/v1/auth/logout", { method: "POST" }),

  refresh: () =>
    request<{ access_token: string; token_type: string; expires_in: number }>(
      "/api/v1/auth/refresh",
      { method: "POST" }
    ),

  me: (accessToken: string) =>
    request<AuthUser>("/api/v1/auth/me", {}, accessToken),

  updateProfile: (
    data: {
      full_name?: string;
      job_title?: string | null;
      phone_number?: string | null;
      whatsapp_opt_in?: boolean;
      locale?: "en" | "tr";
    },
    accessToken: string
  ) =>
    request<AuthUser>("/api/v1/auth/me", { method: "PATCH", body: data }, accessToken),

  changePassword: (data: ChangePasswordRequest, accessToken: string) =>
    request<MessageResponse>(
      "/api/v1/auth/change-password",
      { method: "POST", body: data },
      accessToken
    ),

  verifyEmail: (token: string) =>
    request<MessageResponse>("/api/v1/auth/verify-email", {
      method: "POST",
      body: { token },
    }),

  resendVerification: (email: string) =>
    request<MessageResponse>("/api/v1/auth/verify-email/resend", {
      method: "POST",
      body: { email },
    }),

  forgotPassword: (email: string) =>
    request<MessageResponse>("/api/v1/auth/forgot-password", {
      method: "POST",
      body: { email },
    }),

  resetPassword: (token: string, new_password: string) =>
    request<MessageResponse>("/api/v1/auth/reset-password", {
      method: "POST",
      body: { token, new_password },
    }),

  uploadAvatar: (file: File, accessToken: string): Promise<AuthUser> => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_BASE}/api/v1/auth/me/avatar`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: form,
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new ApiError(r.status, e?.detail || `HTTP ${r.status}`, e); }
      return r.json();
    });
  },

  deleteAvatar: (accessToken: string) =>
    request<AuthUser>("/api/v1/auth/me/avatar", { method: "DELETE" }, accessToken),
};

// ── Active sessions (generic — works for any authenticated user type) ─────────

export interface SessionRead {
  id: string;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  expires_at: string;
}

export const sessionsApi = {
  list: (accessToken: string) =>
    request<SessionRead[]>("/api/v1/auth/sessions", {}, accessToken),

  revoke: (sessionId: string, accessToken: string) =>
    request<void>(`/api/v1/auth/sessions/${sessionId}`, { method: "DELETE" }, accessToken),

  revokeAll: (accessToken: string) =>
    request<MessageResponse>("/api/v1/auth/sessions/revoke-all", { method: "POST" }, accessToken),
};

// ── Workspace / Agency types ─────────────────────────────────────────────────

export interface AgencyRead {
  id: string;
  name: string;
  slug: string;
  status: string;
  owner_user_id: string | null;
  plan_id: string | null;
  logo_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgencyWithRole extends AgencyRead {
  member_role: string;
  member_status: string;
}

export interface AgencyMemberRead {
  id: string;
  agency_id: string;
  user_id: string;
  role: string;
  status: string;
  joined_at: string | null;
  created_at: string;
  user_email: string | null;
  user_full_name: string | null;
}

export interface BrandRead {
  id: string;
  agency_id: string | null;
  name: string;
  slug: string;
  status: string;
  logo_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface BrandMemberRead {
  id: string;
  brand_id: string;
  user_id: string;
  role: string;
  status: string;
  joined_at: string | null;
  created_at: string;
  user_email: string | null;
  user_full_name: string | null;
}

export interface InvitationRead {
  id: string;
  agency_id: string;
  brand_id: string | null;
  invitation_type: string;
  email: string;
  role: string;
  invited_by: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  rejected_at: string | null;
  resent_count: number;
  created_at: string;
  is_pending: boolean;
}

export interface BriefParticipantRead {
  id: string;
  brief_id: string;
  user_id: string;
  user_name: string | null;
  user_email: string | null;
  participant_role: string | null;
  role_label: string | null;
  can_comment: boolean;
  can_upload: boolean;
  can_edit: boolean;
  can_approve: boolean;
  can_request_revision: boolean;
  created_at: string;
}

export interface BriefParticipantCreate {
  user_id: string;
  participant_role: string;
  role_label?: string | null;
  can_comment?: boolean;
  can_upload?: boolean;
  can_edit?: boolean;
  can_approve?: boolean;
  can_request_revision?: boolean;
}

export interface BriefParticipantUpdate {
  participant_role?: string | null;
  role_label?: string | null;
  can_comment?: boolean | null;
  can_upload?: boolean | null;
  can_edit?: boolean | null;
  can_approve?: boolean | null;
  can_request_revision?: boolean | null;
}

export interface InvitationPreview {
  id: string;
  agency_id: string;
  agency_name: string;
  brand_id: string | null;
  brand_name: string | null;
  invitation_type: string;
  email: string;
  role: string;
  expires_at: string;
  is_pending: boolean;
  message?: string | null;
}

export interface WorkspaceAgencyItem {
  id: string;
  name: string;
  slug: string;
  status: string;
  logo_url: string | null;
  member_role: string;
  member_status: string;
}

export interface WorkspaceBrandItem {
  id: string;
  agency_id: string | null;
  name: string;
  slug: string;
  status: string;
  member_role: string;
  member_status: string;
}

export interface WorkspaceList {
  agencies: WorkspaceAgencyItem[];
  brands: WorkspaceBrandItem[];
}

export const workspaceApi = {
  list: (accessToken: string) =>
    request<WorkspaceList>("/api/v1/workspaces", {}, accessToken),
};

export const agencyApi = {
  create: (data: { name: string; slug?: string }, accessToken: string) =>
    request<AgencyRead>("/api/v1/agencies", { method: "POST", body: data }, accessToken),

  listMine: (accessToken: string) =>
    request<AgencyWithRole[]>("/api/v1/agencies/me", {}, accessToken),

  get: (agencyId: string, accessToken: string) =>
    request<AgencyRead>(
      `/api/v1/agencies/${agencyId}`,
      { agencyId },
      accessToken
    ),

  update: (agencyId: string, data: { name?: string; website?: string | null }, accessToken: string) =>
    request<AgencyRead>(
      `/api/v1/agencies/${agencyId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  listMembers: (agencyId: string, accessToken: string) =>
    request<AgencyMemberRead[]>(
      `/api/v1/agencies/${agencyId}/members`,
      { agencyId },
      accessToken
    ),

  updateMemberRole: (
    agencyId: string,
    userId: string,
    role: string,
    accessToken: string
  ) =>
    request<AgencyMemberRead>(
      `/api/v1/agencies/${agencyId}/members/${userId}`,
      { method: "PATCH", body: { role }, agencyId },
      accessToken
    ),

  removeMember: (agencyId: string, userId: string, accessToken: string) =>
    request<void>(
      `/api/v1/agencies/${agencyId}/members/${userId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  listBrands: (agencyId: string, accessToken: string) =>
    request<BrandRead[]>(
      `/api/v1/agencies/${agencyId}/brands`,
      { agencyId },
      accessToken
    ),

  createBrand: (agencyId: string, data: { name: string }, accessToken: string) =>
    request<BrandRead>(
      `/api/v1/agencies/${agencyId}/brands`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  getBrand: (brandId: string, agencyId: string, accessToken: string) =>
    request<BrandRead>(
      `/api/v1/brands/${brandId}`,
      { agencyId },
      accessToken
    ),

  listBrandMembers: (brandId: string, agencyId: string, accessToken: string) =>
    request<BrandMemberRead[]>(
      `/api/v1/brands/${brandId}/members`,
      { agencyId },
      accessToken
    ),

  uploadAgencyLogo: (agencyId: string, file: File, accessToken: string): Promise<AgencyRead> => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_BASE}/api/v1/agencies/${agencyId}/logo`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}`, "X-Agency-ID": agencyId },
      body: form,
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new ApiError(r.status, e?.detail || `HTTP ${r.status}`, e); }
      return r.json();
    });
  },

  deleteAgencyLogo: (agencyId: string, accessToken: string) =>
    request<AgencyRead>(`/api/v1/agencies/${agencyId}/logo`, { method: "DELETE", agencyId }, accessToken),

  uploadBrandLogo: (brandId: string, agencyId: string, file: File, accessToken: string): Promise<BrandRead> => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_BASE}/api/v1/brands/${brandId}/logo`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}`, "X-Agency-ID": agencyId },
      body: form,
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new ApiError(r.status, e?.detail || `HTTP ${r.status}`, e); }
      return r.json();
    });
  },

  deleteBrandLogo: (brandId: string, agencyId: string, accessToken: string) =>
    request<BrandRead>(`/api/v1/brands/${brandId}/logo`, { method: "DELETE", agencyId }, accessToken),
};

export const invitationApi = {
  inviteAgencyMember: (
    agencyId: string,
    data: { email: string; role: string; message?: string },
    accessToken: string
  ) =>
    request<InvitationRead>(
      `/api/v1/invitations/agency/${agencyId}`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  inviteBrandMember: (
    brandId: string,
    agencyId: string,
    data: { email: string; role: string; message?: string },
    accessToken: string
  ) =>
    request<InvitationRead>(
      `/api/v1/invitations/brand/${brandId}`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  getPreview: (token: string) =>
    request<InvitationPreview>(`/api/v1/invitations/preview/${token}`),

  accept: (token: string, accessToken: string) =>
    request<void>(
      `/api/v1/invitations/accept/${token}`,
      { method: "POST" },
      accessToken
    ),

  revokeById: (invitationId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/invitations/${invitationId}/revoke`,
      { method: "POST", agencyId },
      accessToken
    ),

  resendById: (invitationId: string, agencyId: string, accessToken: string) =>
    request<InvitationRead>(
      `/api/v1/invitations/${invitationId}/resend`,
      { method: "POST", agencyId },
      accessToken
    ),

  listAgencyInvitations: (agencyId: string, accessToken: string) =>
    request<InvitationRead[]>(
      `/api/v1/invitations/agency/${agencyId}`,
      { agencyId },
      accessToken
    ),

  getMyPending: (accessToken: string) =>
    request<InvitationRead[]>("/api/v1/invitations/my-pending", {}, accessToken),

  reject: (id: string, accessToken: string) =>
    request<void>(`/api/v1/invitations/${id}/reject`, { method: "POST" }, accessToken),

  acceptById: (id: string, accessToken: string) =>
    request<void>(`/api/v1/invitations/${id}/accept`, { method: "POST" }, accessToken),
};

export const participantApi = {
  list: (briefId: string, agencyId: string, accessToken: string) =>
    request<BriefParticipantRead[]>(
      `/api/v1/briefs/${briefId}/participants`,
      { agencyId },
      accessToken
    ),

  add: (briefId: string, data: BriefParticipantCreate, agencyId: string, accessToken: string) =>
    request<BriefParticipantRead>(
      `/api/v1/briefs/${briefId}/participants`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  update: (
    briefId: string,
    participantId: string,
    data: BriefParticipantUpdate,
    agencyId: string,
    accessToken: string
  ) =>
    request<BriefParticipantRead>(
      `/api/v1/briefs/${briefId}/participants/${participantId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  remove: (briefId: string, participantId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/briefs/${briefId}/participants/${participantId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),
};

// ── Brief Template types ──────────────────────────────────────────────────────

export interface IndustryRead {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export interface FieldRead {
  id: string;
  section_id: string;
  field_key: string;
  label: string;
  help_text: string | null;
  field_type: string;
  is_required: boolean;
  options: Record<string, unknown> | null;
  validation_rules: Record<string, unknown> | null;
  placeholder: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface SectionRead {
  id: string;
  template_id: string;
  title: string;
  description: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface SectionDetail extends SectionRead {
  fields: FieldRead[];
}

export interface TemplateRead {
  id: string;
  agency_id: string | null;
  name: string;
  description: string | null;
  industry: string | null;
  is_system_template: boolean;
  is_active: boolean;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TemplateDetail extends TemplateRead {
  sections: SectionDetail[];
}

export interface TemplateCreate {
  name: string;
  description?: string | null;
  industry?: string | null;
}

export interface TemplateUpdate {
  name?: string;
  description?: string | null;
  industry?: string | null;
}

export interface SectionCreate {
  title: string;
  description?: string | null;
  sort_order?: number;
}

export interface SectionUpdate {
  title?: string;
  description?: string | null;
  sort_order?: number;
}

export interface FieldCreate {
  field_key: string;
  label: string;
  help_text?: string | null;
  field_type: string;
  is_required?: boolean;
  options?: Record<string, unknown> | null;
  validation_rules?: Record<string, unknown> | null;
  placeholder?: string | null;
  sort_order?: number;
}

export interface FieldUpdate {
  label?: string;
  help_text?: string | null;
  field_type?: string;
  is_required?: boolean;
  options?: Record<string, unknown> | null;
  validation_rules?: Record<string, unknown> | null;
  placeholder?: string | null;
  sort_order?: number;
}

export const industryApi = {
  list: () => request<IndustryRead[]>("/api/v1/industries"),
};

export const templateApi = {
  list: (agencyId: string, accessToken: string, industry?: string) =>
    request<TemplateRead[]>(
      `/api/v1/templates${industry ? `?industry=${industry}` : ""}`,
      { agencyId },
      accessToken
    ),

  get: (templateId: string, agencyId: string, accessToken: string) =>
    request<TemplateDetail>(`/api/v1/templates/${templateId}`, { agencyId }, accessToken),

  create: (data: TemplateCreate, agencyId: string, accessToken: string) =>
    request<TemplateRead>(
      "/api/v1/templates",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  update: (templateId: string, data: TemplateUpdate, agencyId: string, accessToken: string) =>
    request<TemplateRead>(
      `/api/v1/templates/${templateId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  archive: (templateId: string, agencyId: string, accessToken: string) =>
    request<TemplateRead>(
      `/api/v1/templates/${templateId}/archive`,
      { method: "POST", agencyId },
      accessToken
    ),

  duplicate: (templateId: string, agencyId: string, accessToken: string) =>
    request<TemplateRead>(
      `/api/v1/templates/${templateId}/duplicate`,
      { method: "POST", agencyId },
      accessToken
    ),

  addSection: (templateId: string, data: SectionCreate, agencyId: string, accessToken: string) =>
    request<SectionRead>(
      `/api/v1/templates/${templateId}/sections`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  updateSection: (
    templateId: string,
    sectionId: string,
    data: SectionUpdate,
    agencyId: string,
    accessToken: string
  ) =>
    request<SectionRead>(
      `/api/v1/templates/${templateId}/sections/${sectionId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  deleteSection: (templateId: string, sectionId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/templates/${templateId}/sections/${sectionId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  reorderSections: (
    templateId: string,
    orderedIds: string[],
    agencyId: string,
    accessToken: string
  ) =>
    request<SectionRead[]>(
      `/api/v1/templates/${templateId}/sections/reorder`,
      { method: "POST", body: { ordered_ids: orderedIds }, agencyId },
      accessToken
    ),

  addField: (
    templateId: string,
    sectionId: string,
    data: FieldCreate,
    agencyId: string,
    accessToken: string
  ) =>
    request<FieldRead>(
      `/api/v1/templates/${templateId}/sections/${sectionId}/fields`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  updateField: (
    templateId: string,
    sectionId: string,
    fieldId: string,
    data: FieldUpdate,
    agencyId: string,
    accessToken: string
  ) =>
    request<FieldRead>(
      `/api/v1/templates/${templateId}/sections/${sectionId}/fields/${fieldId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  deleteField: (
    templateId: string,
    sectionId: string,
    fieldId: string,
    agencyId: string,
    accessToken: string
  ) =>
    request<void>(
      `/api/v1/templates/${templateId}/sections/${sectionId}/fields/${fieldId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  reorderFields: (
    templateId: string,
    sectionId: string,
    orderedIds: string[],
    agencyId: string,
    accessToken: string
  ) =>
    request<FieldRead[]>(
      `/api/v1/templates/${templateId}/sections/${sectionId}/fields/reorder`,
      { method: "POST", body: { ordered_ids: orderedIds }, agencyId },
      accessToken
    ),
};

// ── Brief types ───────────────────────────────────────────────────────────────

export type BriefStatus =
  | "draft"
  | "submitted"
  | "in_review"
  | "accepted"
  | "in_production"
  | "ready_for_review"
  | "revision_requested"
  | "approved"
  | "completed"
  | "scheduled"
  | "archived";

export type BriefPriority = "low" | "normal" | "high" | "urgent";

export interface BriefRead {
  id: string;
  agency_id: string;
  brand_id: string | null;
  template_id: string | null;
  title: string;
  description: string | null;
  description_html: string | null;
  status: BriefStatus;
  priority: BriefPriority;
  start_date: string | null;
  draft_date: string | null;
  feedback_date: string | null;
  deadline: string | null;
  publish_date: string | null;
  platforms: string[] | null;
  content_types: string[] | null;
  source: string | null;
  meta: BriefMeta | null;
  created_by_id: string;
  updated_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface BriefMeta {
  campaign_goal?: string | null;
  target_audience?: string | null;
  platforms?: string[];
  content_type?: string | null;
  cta?: string | null;
  brand_tone?: string | null;
  reference_links?: string[];
  publish_date?: string | null;
  additional_notes?: string | null;
}

export interface BriefFieldValueRead {
  id: string;
  brief_id: string;
  template_field_id: string;
  value: unknown;
  created_at: string;
  updated_at: string;
}

export interface BriefAssigneeRead {
  id: string;
  brief_id: string;
  user_id: string;
  role_label: string | null;
  created_at: string;
}

export interface BriefDetail extends BriefRead {
  field_values: BriefFieldValueRead[];
  assignees: BriefAssigneeRead[];
  linked_calendar_item_id: string | null;
}

export interface BriefListResponse {
  items: BriefRead[];
  total: number;
  offset: number;
  limit: number;
}

export interface BriefCreate {
  template_id?: string | null;
  brand_id?: string | null;
  title: string;
  description?: string | null;
  priority?: BriefPriority;
  deadline?: string | null;
  add_to_calendar?: boolean;
  platforms?: string[];
  content_types?: string[];
  reference_links?: string[];
  assignee_ids?: string[];
}

export interface BriefUpdate {
  title?: string;
  description?: string | null;
  priority?: BriefPriority;
  deadline?: string | null;
  brand_id?: string | null;
}

export interface BriefStatusUpdate {
  status: BriefStatus;
}

export interface BriefFieldValueIn {
  template_field_id: string;
  value: unknown;
}

export interface BriefFieldValuesUpdate {
  values: BriefFieldValueIn[];
}

export interface AssigneeAdd {
  user_id: string;
  role_label?: string | null;
}

export interface BriefListFilters {
  brand_id?: string;
  status?: string;
  priority?: string;
  assignee_id?: string;
  deadline_before?: string;
  search?: string;
  source?: string;
  offset?: number;
  limit?: number;
}

export interface BriefTemplateListItem {
  id: string;
  name: string;
  description: string | null;
  industry: string | null;
  is_system_template: boolean;
}

export interface BrandBriefCreate {
  title: string;
  description?: string | null;
  description_html?: string | null;
  campaign_goal?: string | null;
  target_audience?: string | null;
  platforms?: string[];
  content_type?: string | null;
  content_types?: string[];
  priority?: string;
  start_date?: string | null;
  draft_date?: string | null;
  feedback_date?: string | null;
  deadline?: string | null;
  publish_date?: string | null;
  cta?: string | null;
  key_message?: string | null;
  mandatory_messages?: string | null;
  things_to_avoid?: string | null;
  success_criteria?: string | null;
  technical_requirements?: string | null;
  brand_tone?: string | null;
  reference_links?: string[];
  additional_notes?: string | null;
}

export type BrandBriefUpdate = Partial<BrandBriefCreate>;

export const briefApi = {
  list: (filters: BriefListFilters, agencyId: string, accessToken: string) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== "") params.set(k, String(v));
    });
    const qs = params.toString();
    return request<BriefListResponse>(
      `/api/v1/briefs${qs ? `?${qs}` : ""}`,
      { agencyId },
      accessToken
    );
  },

  get: (briefId: string, agencyId: string, accessToken: string) =>
    request<BriefDetail>(`/api/v1/briefs/${briefId}`, { agencyId }, accessToken),

  create: (data: BriefCreate, agencyId: string, accessToken: string) =>
    request<BriefDetail>("/api/v1/briefs", { method: "POST", body: data, agencyId }, accessToken),

  update: (briefId: string, data: BriefUpdate, agencyId: string, accessToken: string) =>
    request<BriefDetail>(
      `/api/v1/briefs/${briefId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  changeStatus: (briefId: string, data: BriefStatusUpdate, agencyId: string, accessToken: string) =>
    request<BriefDetail>(
      `/api/v1/briefs/${briefId}/status`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  archive: (briefId: string, agencyId: string, accessToken: string) =>
    request<void>(`/api/v1/briefs/${briefId}`, { method: "DELETE", agencyId }, accessToken),

  updateFieldValues: (
    briefId: string,
    data: BriefFieldValuesUpdate,
    agencyId: string,
    accessToken: string
  ) =>
    request<BriefDetail>(
      `/api/v1/briefs/${briefId}/field-values`,
      { method: "PUT", body: data, agencyId },
      accessToken
    ),

  assignUser: (briefId: string, data: AssigneeAdd, agencyId: string, accessToken: string) =>
    request<BriefAssigneeRead>(
      `/api/v1/briefs/${briefId}/assignees`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  unassignUser: (briefId: string, userId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/briefs/${briefId}/assignees/${userId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),
};

// ── Approval types ────────────────────────────────────────────────────────────

export interface ApprovalRead {
  id: string;
  brief_id: string;
  version_id: string | null;
  status: "pending" | "approved" | "revision_requested" | "rejected" | "cancelled" | "expired";
  requested_by_id: string;
  approved_by_email: string | null;
  approved_by_name: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BrandApprovalCard {
  id: string;
  brief_id: string;
  brief_title: string;
  content_types: string[];
  platforms: string[];
  status: "pending" | "approved" | "revision_requested" | "rejected" | "cancelled" | "expired";
  agency_name: string | null;
  requested_by_name: string | null;
  created_at: string;
  due_date: string | null;
  decided_at: string | null;
  comment_count: number;
  assigned_to_me: boolean;
}

export interface BriefVersionSummary {
  id: string;
  brief_id: string;
  version_number: number;
  created_by_id: string | null;
  created_at: string;
}

export interface BriefVersionRead extends BriefVersionSummary {
  snapshot: Record<string, unknown>;
}

export interface ApprovalCommentRead {
  id: string;
  approval_id: string;
  user_id: string | null;
  author_name: string | null;
  author_email: string | null;
  comment: string;
  is_internal: boolean;
  created_at: string;
}

export interface SendToApprovalResponse {
  approval: ApprovalRead;
  approval_token: string;
  approval_url: string;
}

export interface PublicFieldValue {
  field_key: string;
  label: string;
  field_type: string;
  is_required: boolean;
  options: Record<string, unknown> | null;
  placeholder: string | null;
  value: unknown;
}

export interface PublicSection {
  title: string;
  description: string | null;
  fields: PublicFieldValue[];
}

export interface PublicApprovalView {
  approval_id: string;
  status: "pending" | "approved" | "revision_requested" | "cancelled" | "expired";
  brief_title: string;
  brief_description: string | null;
  brief_priority: string;
  brief_deadline: string | null;
  brand_name: string | null;
  template_name: string | null;
  version_number: number;
  sections: PublicSection[];
  comments: ApprovalCommentRead[];
  expires_at: string;
  decided_at: string | null;
}

// ── Private approval API ──────────────────────────────────────────────────────

export const approvalApi = {
  sendToApproval: (briefId: string, agencyId: string, accessToken: string) =>
    request<SendToApprovalResponse>(
      `/api/v1/briefs/${briefId}/send-approval`,
      { method: "POST", agencyId },
      accessToken
    ),

  listApprovals: (briefId: string, agencyId: string, accessToken: string) =>
    request<ApprovalRead[]>(
      `/api/v1/briefs/${briefId}/approvals`,
      { agencyId },
      accessToken
    ),

  revokeApproval: (briefId: string, approvalId: string, agencyId: string, accessToken: string) =>
    request<ApprovalRead>(
      `/api/v1/briefs/${briefId}/approvals/${approvalId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  listVersions: (briefId: string, agencyId: string, accessToken: string) =>
    request<BriefVersionSummary[]>(
      `/api/v1/briefs/${briefId}/versions`,
      { agencyId },
      accessToken
    ),

  getVersion: (briefId: string, versionId: string, agencyId: string, accessToken: string) =>
    request<BriefVersionRead>(
      `/api/v1/briefs/${briefId}/versions/${versionId}`,
      { agencyId },
      accessToken
    ),

  listComments: (
    briefId: string,
    approvalId: string,
    agencyId: string,
    accessToken: string
  ) =>
    request<ApprovalCommentRead[]>(
      `/api/v1/briefs/${briefId}/approvals/${approvalId}/comments`,
      { agencyId },
      accessToken
    ),
};

// ── Mention types ────────────────────────────────────────────────────────────

export interface MentionCandidate {
  member_id: string;
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  role_label: string;
  member_type: "agency" | "brand";
  context_label: string | null;
}

export interface MentionInline {
  mentioned_user_id: string;
  display_text: string;
  is_active: boolean;
}

export type MentionSourceType = "comment" | "annotation" | "annotation_reply";

export const mentionApi = {
  agencyCandidates: (
    sourceType: MentionSourceType,
    query: string | undefined,
    agencyId: string,
    accessToken: string
  ) => {
    const params = new URLSearchParams({ source_type: sourceType });
    if (query) params.set("query", query);
    return request<{ items: MentionCandidate[] }>(
      `/api/v1/mentions/candidates?${params.toString()}`,
      { agencyId },
      accessToken
    );
  },

  brandCandidates: (
    sourceType: MentionSourceType,
    sourceId: string | undefined,
    query: string | undefined,
    accessToken: string
  ) => {
    const params = new URLSearchParams({ source_type: sourceType });
    if (sourceId) params.set("source_id", sourceId);
    if (query) params.set("query", query);
    return request<{ items: MentionCandidate[] }>(
      `/api/v1/brand-portal/mentions/candidates?${params.toString()}`,
      {},
      accessToken
    );
  },
};

// ── Comment / Thread types ────────────────────────────────────────────────────

export type ThreadType = "brief" | "field" | "asset" | "approval";
export type ThreadStatus = "open" | "resolved";
export type CommentVisibility = "internal" | "client_visible";

export interface CommentRead {
  id: string;
  thread_id: string;
  author_user_id: string | null;
  author_name: string | null;
  author_email: string | null;
  author_job_title: string | null;
  body: string;
  visibility: CommentVisibility;
  created_at: string;
  updated_at: string;
  attachments: AssetRead[];
  mentions: MentionInline[];
}

export interface ThreadRead {
  id: string;
  agency_id: string;
  brief_id: string | null;
  approval_id: string | null;
  field_key: string | null;
  asset_id: string | null;
  thread_type: ThreadType;
  status: ThreadStatus;
  created_by_id: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  comments: CommentRead[];
}

export interface ThreadCreate {
  thread_type: ThreadType;
  brief_id?: string | null;
  brand_id?: string | null;
  field_key?: string | null;
  asset_id?: string | null;
  approval_id?: string | null;
  initial_comment: string;
  visibility: CommentVisibility;
  attachment_ids?: string[] | null;
  mentioned_user_ids?: string[];
}

export interface AddCommentRequest {
  body: string;
  visibility: CommentVisibility;
  author_name?: string | null;
  author_email?: string | null;
  attachment_ids?: string[] | null;
  mentioned_user_ids?: string[];
}

export interface UpdateCommentRequest {
  body: string;
  mentioned_user_ids?: string[];
}

export const commentApi = {
  createThread: (
    briefId: string,
    data: ThreadCreate,
    agencyId: string,
    accessToken: string
  ) =>
    request<ThreadRead>(
      `/api/v1/briefs/${briefId}/threads`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  listThreads: (briefId: string, agencyId: string, accessToken: string) =>
    request<ThreadRead[]>(
      `/api/v1/briefs/${briefId}/threads`,
      { agencyId },
      accessToken
    ),

  resolveThread: (threadId: string, agencyId: string, accessToken: string) =>
    request<ThreadRead>(
      `/api/v1/threads/${threadId}/resolve`,
      { method: "POST", agencyId },
      accessToken
    ),

  reopenThread: (threadId: string, agencyId: string, accessToken: string) =>
    request<ThreadRead>(
      `/api/v1/threads/${threadId}/reopen`,
      { method: "POST", agencyId },
      accessToken
    ),

  addComment: (
    threadId: string,
    data: AddCommentRequest,
    agencyId: string,
    accessToken: string
  ) =>
    request<CommentRead>(
      `/api/v1/threads/${threadId}/comments`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  updateComment: (
    threadId: string,
    commentId: string,
    data: UpdateCommentRequest,
    agencyId: string,
    accessToken: string
  ) =>
    request<CommentRead>(
      `/api/v1/threads/${threadId}/comments/${commentId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  deleteComment: (
    threadId: string,
    commentId: string,
    agencyId: string,
    accessToken: string
  ) =>
    request<void>(
      `/api/v1/threads/${threadId}/comments/${commentId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  uploadAttachment: (
    briefId: string,
    file: File,
    agencyId: string,
    accessToken: string
  ) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_BASE}/api/v1/briefs/${briefId}/comment-attachments`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}`, "X-Agency-ID": agencyId },
      body: form,
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new ApiError(r.status, err?.detail || `HTTP ${r.status}`, err);
      }
      return r.json() as Promise<AssetRead>;
    });
  },
};

// ── Asset types ───────────────────────────────────────────────────────────────

export interface AssetRead {
  id: string;
  agency_id: string;
  brand_id: string | null;
  uploaded_by_id: string | null;
  filename: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  storage_provider: string;
  checksum: string | null;
  width_px?: number | null;
  height_px?: number | null;
  created_at: string;
}

export interface AssetVersionRead {
  id: string;
  asset_id: string;
  version_number: number;
  filename: string;
  mime_type: string;
  size_bytes: number;
  checksum: string | null;
  uploaded_by_id: string | null;
  created_at: string;
}

export interface AssetLinkRead {
  id: string;
  asset_id: string;
  brief_id: string | null;
  calendar_item_id: string | null;
  comment_id: string | null;
  created_at: string;
}

export const assetApi = {
  upload: (briefId: string, file: File, agencyId: string, accessToken: string) => {
    const formData = new FormData();
    formData.append("file", file);
    return fetch(`${API_BASE}/api/v1/briefs/${briefId}/assets`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Agency-ID": agencyId,
      },
      body: formData,
      credentials: "include",
    }).then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new ApiError(res.status, err?.detail || `HTTP ${res.status}`, err);
      }
      return res.json() as Promise<AssetRead>;
    });
  },

  listByBrief: (briefId: string, agencyId: string, accessToken: string) =>
    request<AssetRead[]>(
      `/api/v1/briefs/${briefId}/assets`,
      { agencyId },
      accessToken
    ),

  get: (assetId: string, agencyId: string, accessToken: string) =>
    request<AssetRead>(`/api/v1/assets/${assetId}`, { agencyId }, accessToken),

  delete: (assetId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/assets/${assetId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  createVersion: (assetId: string, file: File, agencyId: string, accessToken: string) => {
    const formData = new FormData();
    formData.append("file", file);
    return fetch(`${API_BASE}/api/v1/assets/${assetId}/versions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Agency-ID": agencyId,
      },
      body: formData,
      credentials: "include",
    }).then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new ApiError(res.status, err?.detail || `HTTP ${res.status}`, err);
      }
      return res.json() as Promise<AssetVersionRead>;
    });
  },

  linkToBrief: (assetId: string, briefId: string, agencyId: string, accessToken: string) =>
    request<AssetLinkRead>(
      `/api/v1/briefs/${briefId}/assets/${assetId}/link`,
      { method: "POST", agencyId },
      accessToken
    ),

  unlink: (assetId: string, linkId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/assets/${assetId}/links/${linkId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  downloadUrl: (assetId: string) =>
    `${API_BASE}/api/v1/assets/${assetId}/download`,
};

// ── Public approval API (no auth) ─────────────────────────────────────────────

// ── Calendar types ────────────────────────────────────────────────────────────

export type CalendarItemType =
  | "post" | "story" | "reels" | "video" | "campaign" | "blog" | "email" | "ad_creative"
  | "meeting" | "custom";

export type CalendarPlatform =
  | "instagram" | "facebook" | "tiktok" | "linkedin" | "x"
  | "youtube" | "website" | "email" | "other";

export type CalendarMilestoneType =
  | "brief_start" | "first_draft" | "brand_feedback" | "approval_deadline"
  | "final_delivery" | "publish_date";

export const CALENDAR_MILESTONE_LABELS: Record<CalendarMilestoneType, string> = {
  brief_start: "Brief Başlangıcı",
  first_draft: "İlk Taslak",
  brand_feedback: "Marka Geri Bildirimi",
  approval_deadline: "Onay Son Tarihi",
  final_delivery: "Nihai Teslim",
  publish_date: "Yayın Tarihi",
};

export type CalendarItemStatus =
  | "planned" | "in_design" | "waiting_approval" | "approved"
  | "scheduled" | "published" | "cancelled";

export interface CalendarItemRead {
  id: string;
  agency_id: string;
  brand_id: string | null;
  brief_id: string | null;
  title: string;
  description: string | null;
  item_type: CalendarItemType;
  platform: CalendarPlatform;
  status: CalendarItemStatus;
  priority: string;
  milestone_type: CalendarMilestoneType | null;
  publish_at: string | null;
  due_at: string | null;
  color_label: string | null;
  created_by_id: string | null;
  updated_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface BrandCalendarEntry {
  id: string;
  kind: "calendar_item" | "brief_milestone";
  event_type: string;
  title: string;
  entry_date: string;
  entry_time: string | null;
  priority: string;
  status: string;
  brief_id: string | null;
  brief_title: string | null;
  calendar_item_id: string | null;
  assignee_ids: string[];
  assignee_names: string[];
}

export type AgencyCalendarSourceType =
  | "manual" | "brief_start" | "first_draft" | "brand_feedback"
  | "approval_deadline" | "publish_date" | "deliverable_submitted" | "revision_requested";

export interface AgencyCalendarEntry {
  id: string;
  source_type: AgencyCalendarSourceType | string;
  calendar_item_id: string | null;
  agency_id: string;
  brand_id: string | null;
  brand_name: string | null;
  brand_logo_url: string | null;
  title: string;
  description: string | null;
  item_type: string;
  platform: string | null;
  status: string;
  priority: string;
  milestone_type: CalendarMilestoneType | null;
  publish_at: string | null;
  due_at: string | null;
  all_day: boolean;
  brief_id: string | null;
  brief_title: string | null;
  deliverable_id: string | null;
  assignee_ids: string[];
  assignee_names: string[];
  is_overdue: boolean;
  editable: boolean;
  action_url: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CalendarItemAssetRead {
  id: string;
  calendar_item_id: string;
  asset_id: string;
  created_at: string;
}

export interface CalendarItemAssigneeRead {
  id: string;
  calendar_item_id: string;
  user_id: string;
  created_at: string;
}

export interface CalendarItemStatusHistoryRead {
  id: string;
  calendar_item_id: string;
  old_status: string | null;
  new_status: string;
  changed_by_id: string | null;
  created_at: string;
}

export interface CalendarItemDetail extends CalendarItemRead {
  assets: CalendarItemAssetRead[];
  assignees: CalendarItemAssigneeRead[];
  status_history: CalendarItemStatusHistoryRead[];
}

export interface CalendarItemCreate {
  title: string;
  description?: string | null;
  brand_id?: string | null;
  brief_id?: string | null;
  item_type?: CalendarItemType;
  platform?: CalendarPlatform;
  status?: CalendarItemStatus;
  priority?: string;
  milestone_type?: CalendarMilestoneType | null;
  publish_at?: string | null;
  due_at?: string | null;
  color_label?: string | null;
}

export interface CalendarItemUpdate {
  title?: string;
  description?: string | null;
  brand_id?: string | null;
  brief_id?: string | null;
  item_type?: CalendarItemType;
  platform?: CalendarPlatform;
  priority?: string;
  milestone_type?: CalendarMilestoneType | null;
  publish_at?: string | null;
  due_at?: string | null;
  color_label?: string | null;
}

export interface StatusChangeRequest {
  new_status: CalendarItemStatus;
}

export const calendarApi = {
  create: (data: CalendarItemCreate, agencyId: string, accessToken: string) =>
    request<CalendarItemRead>(
      "/api/v1/calendar/items",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  list: (
    agencyId: string,
    accessToken: string,
    params?: { brand_id?: string; platform?: string; status?: string; limit?: number; offset?: number }
  ) => {
    const qs = params ? new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null).map(([k, v]) => [k, String(v)])
    ).toString() : "";
    return request<CalendarItemRead[]>(
      `/api/v1/calendar/items${qs ? `?${qs}` : ""}`,
      { agencyId },
      accessToken
    );
  },

  get: (itemId: string, agencyId: string, accessToken: string) =>
    request<CalendarItemDetail>(
      `/api/v1/calendar/items/${itemId}`,
      { agencyId },
      accessToken
    ),

  update: (itemId: string, data: CalendarItemUpdate, agencyId: string, accessToken: string) =>
    request<CalendarItemRead>(
      `/api/v1/calendar/items/${itemId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  delete: (itemId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/calendar/items/${itemId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  changeStatus: (itemId: string, data: StatusChangeRequest, agencyId: string, accessToken: string) =>
    request<CalendarItemRead>(
      `/api/v1/calendar/items/${itemId}/status`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  monthView: (
    year: number,
    month: number,
    agencyId: string,
    accessToken: string,
    params?: { brand_id?: string; platform?: string; status?: string }
  ) => {
    const qs = new URLSearchParams({ year: String(year), month: String(month), ...(params ?? {}) }).toString();
    return request<CalendarItemRead[]>(`/api/v1/calendar/month?${qs}`, { agencyId }, accessToken);
  },

  weekView: (
    year: number,
    week: number,
    agencyId: string,
    accessToken: string,
    params?: { brand_id?: string; platform?: string; status?: string }
  ) => {
    const qs = new URLSearchParams({ year: String(year), week: String(week), ...(params ?? {}) }).toString();
    return request<CalendarItemRead[]>(`/api/v1/calendar/week?${qs}`, { agencyId }, accessToken);
  },

  attachAsset: (itemId: string, assetId: string, agencyId: string, accessToken: string) =>
    request<CalendarItemAssetRead>(
      `/api/v1/calendar/items/${itemId}/assets/${assetId}`,
      { method: "POST", agencyId },
      accessToken
    ),

  detachAsset: (itemId: string, assetId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/calendar/items/${itemId}/assets/${assetId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  assignUser: (itemId: string, userId: string, agencyId: string, accessToken: string) =>
    request<CalendarItemAssigneeRead>(
      `/api/v1/calendar/items/${itemId}/assignees/${userId}`,
      { method: "POST", agencyId },
      accessToken
    ),

  unassignUser: (itemId: string, userId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/calendar/items/${itemId}/assignees/${userId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  linkBrief: (itemId: string, briefId: string, agencyId: string, accessToken: string) =>
    request<CalendarItemRead>(
      `/api/v1/calendar/items/${itemId}/brief/${briefId}`,
      { method: "POST", agencyId },
      accessToken
    ),

  unlinkBrief: (itemId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/calendar/items/${itemId}/brief`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  agenda: (
    agencyId: string,
    accessToken: string,
    params?: {
      from?: string;
      to?: string;
      brand_id?: string;
      status?: string;
      event_type?: string;
      assignee_id?: string;
      priority?: string;
    }
  ) => {
    const qs = params
      ? new URLSearchParams(
          Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
        ).toString()
      : "";
    return request<AgencyCalendarEntry[]>(
      `/api/v1/calendar/agenda${qs ? `?${qs}` : ""}`,
      { agencyId },
      accessToken
    );
  },
};

// ── Notification & Activity types ────────────────────────────────────────────

export type NotificationEventType =
  | "brief.created"
  | "brief.updated"
  | "brief.submitted_for_approval"
  | "brief.revision_requested"
  | "brief.approved"
  | "calendar.item_created"
  | "calendar.item_due"
  | "calendar.item_published"
  | "user.invited"
  | "subscription.payment_failed"
  | "subscription.changed";

export type NotificationChannel = "email" | "whatsapp" | "in_app";
export type NotificationDeliveryStatus =
  | "pending"
  | "processing"
  | "sent"
  | "failed"
  | "skipped"
  | "passive"
  | "not_configured";

export interface NotificationRead {
  id: string;
  user_id: string;
  agency_id: string | null;
  brand_id: string | null;
  event_id: string | null;
  title: string;
  body: string;
  event_type: NotificationEventType;
  is_read: boolean;
  read_at: string | null;
  archived_at: string | null;
  created_at: string;
  /** Backend-computed, relative in-app route — never a user-controlled or external URL. */
  action_url: string | null;
}

export interface NotificationListResponse {
  items: NotificationRead[];
  total: number;
  unread_count: number;
  limit: number;
  offset: number;
}

export interface NotificationRealtimeTicket {
  ticket: string;
  expires_in_seconds: number;
  websocket_path: string;
}

export interface NotificationPreferenceRead {
  id: string;
  user_id: string;
  email_enabled: boolean;
  whatsapp_enabled: boolean;
  in_app_enabled: boolean;
  created_at: string;
  updated_at: string;
  // provider/user context (always present from API)
  whatsapp_provider_active: boolean;
  has_phone_number: boolean;
  whatsapp_opt_in: boolean;
}

export interface NotificationPreferenceUpdate {
  email_enabled?: boolean;
  whatsapp_enabled?: boolean;
  in_app_enabled?: boolean;
}

export interface ActivityLogRead {
  id: string;
  agency_id: string | null;
  brand_id: string | null;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  meta: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface ActivityLogListResponse {
  items: ActivityLogRead[];
  total: number;
  limit: number;
  offset: number;
}

// ── Notification API ──────────────────────────────────────────────────────────

export const notificationApi = {
  list: (
    agencyId: string,
    accessToken: string,
    params?: { is_read?: boolean; include_archived?: boolean; limit?: number; offset?: number }
  ) => {
    const qs = new URLSearchParams();
    if (params?.is_read !== undefined) qs.set("unread_only", String(params.is_read));
    if (params?.include_archived !== undefined) qs.set("include_archived", String(params.include_archived));
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<NotificationListResponse>(
      `/api/v1/notifications${query}`,
      { agencyId },
      accessToken
    );
  },

  markRead: (notificationId: string, agencyId: string, accessToken: string) =>
    request<NotificationRead>(
      `/api/v1/notifications/${notificationId}/read`,
      { method: "POST", agencyId },
      accessToken
    ),

  markAllRead: (agencyId: string, accessToken: string) =>
    request<{ marked_read: number }>(
      `/api/v1/notifications/read-all`,
      { method: "POST", agencyId },
      accessToken
    ),

  createRealtimeTicket: (agencyId: string, accessToken: string) =>
    request<NotificationRealtimeTicket>(
      "/api/v1/notifications/realtime-ticket",
      { method: "POST", agencyId },
      accessToken
    ),

  archive: (notificationId: string, agencyId: string, accessToken: string) =>
    request<NotificationRead>(
      `/api/v1/notifications/${notificationId}/archive`,
      { method: "POST", agencyId },
      accessToken
    ),

  getPreferences: (accessToken: string) =>
    request<NotificationPreferenceRead>(
      `/api/v1/notifications/preferences`,
      {},
      accessToken
    ),

  updatePreferences: (payload: NotificationPreferenceUpdate, accessToken: string) =>
    request<NotificationPreferenceRead>(
      `/api/v1/notifications/preferences`,
      { method: "PATCH", body: payload },
      accessToken
    ) as Promise<NotificationPreferenceRead>,
};

// ── Activity API ──────────────────────────────────────────────────────────────

export const activityApi = {
  list: (
    agencyId: string,
    accessToken: string,
    params?: {
      entity_type?: string;
      actor_user_id?: string;
      limit?: number;
      offset?: number;
    }
  ) => {
    const qs = new URLSearchParams();
    if (params?.entity_type) qs.set("entity_type", params.entity_type);
    if (params?.actor_user_id) qs.set("actor_user_id", params.actor_user_id);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<ActivityLogListResponse>(
      `/api/v1/activity${query}`,
      { agencyId },
      accessToken
    );
  },
};

// ── Report types ──────────────────────────────────────────────────────────────

export type ReportType = "monthly_brand" | "agency_overview" | "campaign_summary";
export type ReportStatus = "draft" | "generated" | "shared" | "archived";

export interface ReportRead {
  id: string;
  agency_id: string;
  brand_id: string | null;
  created_by_id: string | null;
  report_type: ReportType;
  period_start: string;
  period_end: string;
  status: ReportStatus;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ReportSnapshotRead {
  id: string;
  report_id: string;
  metrics: Record<string, unknown>;
  narrative: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ReportShareTokenRead {
  id: string;
  report_id: string;
  expires_at: string;
  revoked_at: string | null;
  allow_pdf_download: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReportShareTokenCreated extends ReportShareTokenRead {
  token: string;
}

export interface ReportWithSnapshot extends ReportRead {
  snapshot: ReportSnapshotRead | null;
  active_share_tokens: ReportShareTokenRead[];
}

export interface PublicReportView {
  report_type: ReportType;
  period_start: string;
  period_end: string;
  title: string;
  metrics: Record<string, unknown>;
  narrative: Record<string, unknown> | null;
  generated_at: string;
  allow_pdf_download: boolean;
}

export interface ReportListResponse {
  items: ReportRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReportCreate {
  report_type: ReportType;
  period_start: string;
  period_end: string;
  title: string;
  brand_id?: string | null;
}

export interface ReportShareTokenCreate {
  expires_in_days?: number;
  allow_pdf_download?: boolean;
}

export const reportApi = {
  create: (data: ReportCreate, agencyId: string, accessToken: string) =>
    request<ReportWithSnapshot>(
      "/api/v1/reports",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  list: (
    agencyId: string,
    accessToken: string,
    params?: { brand_id?: string; report_type?: string; limit?: number; offset?: number }
  ) => {
    const qs = new URLSearchParams();
    if (params?.brand_id) qs.set("brand_id", params.brand_id);
    if (params?.report_type) qs.set("report_type", params.report_type);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<ReportListResponse>(
      `/api/v1/reports${query}`,
      { agencyId },
      accessToken
    );
  },

  get: (reportId: string, agencyId: string, accessToken: string) =>
    request<ReportWithSnapshot>(`/api/v1/reports/${reportId}`, { agencyId }, accessToken),

  regenerate: (reportId: string, agencyId: string, accessToken: string) =>
    request<ReportWithSnapshot>(
      `/api/v1/reports/${reportId}/regenerate`,
      { method: "POST", agencyId },
      accessToken
    ),

  archive: (reportId: string, agencyId: string, accessToken: string) =>
    request<ReportWithSnapshot>(
      `/api/v1/reports/${reportId}/archive`,
      { method: "POST", agencyId },
      accessToken
    ),

  createShareToken: (
    reportId: string,
    data: ReportShareTokenCreate,
    agencyId: string,
    accessToken: string
  ) =>
    request<ReportShareTokenCreated>(
      `/api/v1/reports/${reportId}/share`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  revokeShareToken: (
    reportId: string,
    tokenId: string,
    agencyId: string,
    accessToken: string
  ) =>
    request<ReportShareTokenRead>(
      `/api/v1/reports/${reportId}/share/${tokenId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  pdfUrl: (reportId: string) => `${API_BASE}/api/v1/reports/${reportId}/pdf`,
};

export const publicReportApi = {
  getByToken: (token: string) =>
    request<PublicReportView>(`/api/v1/public/reports/${token}`),

  pdfUrl: (token: string) => `${API_BASE}/api/v1/public/reports/${token}/pdf`,
};

// ── Public approval API (no auth) ─────────────────────────────────────────────

export const publicApprovalApi = {
  getByToken: (token: string) =>
    request<PublicApprovalView>(`/api/v1/public/approvals/${token}`),

  approve: (token: string, payload: { approver_name?: string; approver_email?: string }) =>
    request<{ message: string }>(`/api/v1/public/approvals/${token}/approve`, {
      method: "POST",
      body: payload,
    }),

  requestRevision: (
    token: string,
    payload: { comment: string; approver_name?: string; approver_email?: string }
  ) =>
    request<{ message: string }>(`/api/v1/public/approvals/${token}/revision`, {
      method: "POST",
      body: payload,
    }),

  addComment: (
    token: string,
    payload: { comment: string; author_name?: string; author_email?: string }
  ) =>
    request<ApprovalCommentRead>(`/api/v1/public/approvals/${token}/comment`, {
      method: "POST",
      body: payload,
    }),
};

// ── Branding types ────────────────────────────────────────────────────────────

export type BrandingAssetType = "logo" | "email_logo" | "favicon" | "social_preview";
export type CustomDomainStatus = "pending" | "verified" | "failed" | "disabled";

export interface AgencyBrandingRead {
  id: string;
  agency_id: string;
  brand_name_override: string | null;
  primary_color: string | null;
  secondary_color: string | null;
  accent_color: string | null;
  logo_url: string | null;
  email_logo_url: string | null;
  favicon_url: string | null;
  custom_footer_text: string | null;
  is_white_label_enabled: boolean;
  white_label_entitlement: boolean;
  seo_title: string | null;
  seo_description: string | null;
  og_image_url: string | null;
  google_analytics_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface BrandingSettingsUpdate {
  brand_name_override?: string | null;
  primary_color?: string | null;
  secondary_color?: string | null;
  accent_color?: string | null;
  custom_footer_text?: string | null;
  is_white_label_enabled?: boolean;
  seo_title?: string | null;
  seo_description?: string | null;
  og_image_url?: string | null;
  google_analytics_id?: string | null;
}

export interface CustomDomainRead {
  id: string;
  agency_id: string;
  domain: string;
  status: CustomDomainStatus;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomDomainCreated extends CustomDomainRead {
  verification_token: string;
}

export interface PublicBrandingView {
  agency_name: string;
  brand_name: string | null;
  primary_color: string | null;
  secondary_color: string | null;
  accent_color: string | null;
  logo_url: string | null;
  favicon_url: string | null;
  custom_footer_text: string | null;
  is_branded: boolean;
}

export const brandingApi = {
  get: (agencyId: string, accessToken: string) =>
    request<AgencyBrandingRead>("/api/v1/branding", { agencyId }, accessToken),

  update: (data: BrandingSettingsUpdate, agencyId: string, accessToken: string) =>
    request<AgencyBrandingRead>(
      "/api/v1/branding",
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  uploadAsset: (
    file: File,
    assetType: BrandingAssetType,
    agencyId: string,
    accessToken: string
  ): Promise<AgencyBrandingRead> => {
    const formData = new FormData();
    formData.append("file", file);
    return fetch(
      `${API_BASE}/api/v1/branding/assets?asset_type=${encodeURIComponent(assetType)}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "X-Agency-ID": agencyId,
        },
        body: formData,
        credentials: "include",
      }
    ).then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new ApiError(res.status, err?.detail || `HTTP ${res.status}`, err);
      }
      return res.json() as Promise<AgencyBrandingRead>;
    });
  },

  reset: (agencyId: string, accessToken: string) =>
    request<AgencyBrandingRead>(
      "/api/v1/branding/reset",
      { method: "POST", agencyId },
      accessToken
    ),

  getDomain: (agencyId: string, accessToken: string) =>
    request<CustomDomainRead>("/api/v1/branding/domain", { agencyId }, accessToken),

  createDomain: (domain: string, agencyId: string, accessToken: string) =>
    request<CustomDomainCreated>(
      "/api/v1/branding/domain",
      { method: "POST", body: { domain }, agencyId },
      accessToken
    ),
};

export const publicBrandingApi = {
  getByApprovalToken: (token: string) =>
    request<PublicBrandingView>(`/api/v1/public/branding/by-approval-token/${token}`),

  getByReportToken: (token: string) =>
    request<PublicBrandingView>(`/api/v1/public/branding/by-report-token/${token}`),

  assetUrl: (assetId: string) =>
    `${API_BASE}/api/v1/public/branding/assets/${assetId}`,
};

// ── Platform admin types ──────────────────────────────────────────────────────

export interface PlatformAgencyMembershipRead {
  agency_id: string;
  agency_name: string;
  role: string;
  status: string;
  joined_at: string | null;
}

export interface PlatformBrandMembershipRead {
  brand_id: string;
  brand_name: string;
  agency_id: string | null;
  role: string;
  status: string;
  joined_at: string | null;
}

export interface PlatformUserDetail {
  id: string;
  email: string;
  full_name: string;
  user_type: string;
  is_active: boolean;
  is_verified: boolean;
  mfa_enabled: boolean;
  last_login_at: string | null;
  created_at: string;
  phone_number: string | null;
  whatsapp_opt_in: boolean;
  agency_memberships: PlatformAgencyMembershipRead[];
  brand_memberships: PlatformBrandMembershipRead[];
  brief_created_count: number;
  brief_assigned_count: number;
  notification_email_enabled: boolean | null;
  notification_whatsapp_enabled: boolean | null;
  notification_in_app_enabled: boolean | null;
}

export interface PlatformBrandRead {
  id: string;
  name: string;
  slug: string;
  status: string;
  agency_id: string | null;
  agency_name: string | null;
  member_count: number;
  brief_count: number;
  created_at: string;
  updated_at: string;
}

export interface PlatformBrandMemberRead {
  id: string;
  user_id: string;
  user_email: string;
  user_full_name: string;
  role: string;
  status: string;
  joined_at: string | null;
  created_at: string;
}

export interface PlatformSeoPageRead {
  id: string;
  page_key: string;
  title: string | null;
  description: string | null;
  canonical_url: string | null;
  og_title: string | null;
  og_description: string | null;
  og_image_url: string | null;
  twitter_title: string | null;
  twitter_description: string | null;
  indexable: boolean;
  follow_links: boolean;
  updated_at: string;
}

export interface PlatformSeoPageUpdate {
  title?: string | null;
  description?: string | null;
  canonical_url?: string | null;
  og_title?: string | null;
  og_description?: string | null;
  og_image_url?: string | null;
  twitter_title?: string | null;
  twitter_description?: string | null;
  indexable?: boolean;
  follow_links?: boolean;
}

export interface PlatformGrowthSettingsRead {
  google_analytics_id: string | null;
  google_tag_manager_id: string | null;
  search_console_verification: string | null;
  meta_pixel_id: string | null;
  linkedin_partner_id: string | null;
  robots_txt: string | null;
  sitemap_last_generated_at: string | null;
  public_app_url: string | null;
}

export interface PlatformSeoAuditIssue {
  severity: "critical" | "high" | "medium" | "low";
  page_key: string | null;
  area: string;
  problem: string;
  reason: string;
  suggestion: string;
}

export interface PlatformSeoPageInventoryItem {
  page_key: string;
  path: string | null;
  label: string;
  status: "published" | "not_built";
  title: string | null;
  description: string | null;
  canonical_url: string | null;
  indexable: boolean;
  has_og_image: boolean;
  issue_count: number;
  severity: "critical" | "warning" | "healthy";
}

export interface PlatformSeoHealthSummary {
  health_score: number;
  critical_count: number;
  warning_count: number;
  indexable_page_count: number;
  missing_title_count: number;
  missing_description_count: number;
  sitemap_configured: boolean;
  robots_configured: boolean;
  last_audit_at: string;
}

export interface PlatformPageSpeedResult {
  url: string;
  strategy: string;
  performance_score: number | null;
  accessibility_score: number | null;
  best_practices_score: number | null;
  seo_score: number | null;
  lcp: string | null;
  cls: string | null;
  fcp: string | null;
  tbt: string | null;
}

export interface PlatformIntegrationStatus {
  provider: string;
  configured: boolean;
  detail: Record<string, string>;
}

export interface PlatformGrowthMetrics {
  total_agencies: number;
  active_agencies: number;
  total_brands: number;
  active_brands: number;
  total_users: number;
  new_agencies_this_month: number;
  new_users_this_month: number;
  agencies_with_first_brand: number;
  agencies_with_first_brief: number;
}

export interface PlatformTokenResponse {
  access_token: string;
  expires_in: number;
  mfa_required: boolean;
  mfa_session_token?: string | null;
}

export interface PlatformAgencyRead {
  id: string;
  name: string;
  slug: string;
  status: string;
  owner_user_id: string | null;
  plan_id: string | null;
  member_count: number;
  brand_count: number;
  created_at: string;
  updated_at: string;
}

export interface PlatformAgencyDetail extends PlatformAgencyRead {
  subscription_status: string | null;
  plan_name: string | null;
  plan_code: string | null;
  monthly_price_cents: number | null;
}

export interface PlatformUserRead {
  id: string;
  email: string;
  full_name: string;
  user_type: string;
  is_active: boolean;
  is_verified: boolean;
  mfa_enabled: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface PlatformSubscriptionRead {
  id: string;
  agency_id: string | null;
  agency_name: string | null;
  brand_id: string | null;
  plan_id: string;
  plan_name: string;
  plan_code: string;
  status: string;
  monthly_price_cents: number;
  current_period_start: string | null;
  current_period_end: string | null;
  created_at: string;
}

export interface PlatformDashboardStats {
  total_agencies: number;
  active_agencies: number;
  suspended_agencies: number;
  total_users: number;
  active_users_30d: number;
  total_subscriptions: number;
  mrr_cents: number;
}

export interface PlatformDemoSettings {
  enabled: boolean;
  duration_hours: number;
  max_active_sandboxes: number;
  max_creations_per_ip_per_day: number;
  captcha_required: boolean;
  captcha_configured: boolean;
  active_sandboxes: number;
  total_created: number;
  expired_or_terminated: number;
}

export interface PlatformDemoSandbox {
  id: string;
  agency_id: string;
  owner_user_id: string;
  agency_name: string;
  status: "active" | "expired" | "terminated";
  expires_at: string;
  terminated_at: string | null;
  termination_reason: string | null;
  created_at: string;
}

export interface PlatformAnalytics {
  agencies_by_status: Record<string, number>;
  users_by_type: Record<string, number>;
  plan_distribution: Record<string, number>;
}

export interface PlatformAuditLogRead {
  id: string;
  admin_user_id: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  meta: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface ImpersonationResponse {
  access_token: string;
  expires_in: number;
  impersonated_user_id: string;
  impersonated_email: string;
  impersonated_user_type: string;
}

export interface OwnerDashboardStats {
  active_brands: number;
  active_members: number;
  open_briefs: number;
  approved_briefs_total: number;
  calendar_items_this_month: number;
}

export interface OwnerMemberRead {
  member_id: string;
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  status: string;
  last_login_at: string | null;
  joined_at: string | null;
  created_at: string;
}

export interface OwnerSubscriptionRead {
  plan_code: string;
  plan_name: string;
  plan_description: string | null;
  status: string;
  max_brands: number | null;
  max_users: number | null;
  monthly_price_cents: number;
  current_period_end: string | null;
  active_brands: number;
  active_members: number;
}

// ── Platform admin API ────────────────────────────────────────────────────────

export interface PlatformBrandingDefaults {
  portal_name: string | null;
  login_title: string | null;
  login_description: string | null;
  primary_color: string | null;
  accent_color: string | null;
  background_color: string | null;
  surface_color: string | null;
  text_color: string | null;
  link_color: string | null;
  logo_url: string | null;
  logo_dark_url: string | null;
  favicon_url: string | null;
  email_from_name: string | null;
  support_email: string | null;
  footer_text: string | null;
  terms_url: string | null;
  privacy_url: string | null;
  social_links: Record<string, string> | null;
  updated_at: string;
}

export interface PlatformBrandingDefaultsUpdate {
  portal_name?: string | null;
  login_title?: string | null;
  login_description?: string | null;
  primary_color?: string | null;
  accent_color?: string | null;
  background_color?: string | null;
  surface_color?: string | null;
  text_color?: string | null;
  link_color?: string | null;
  email_from_name?: string | null;
  support_email?: string | null;
  footer_text?: string | null;
  terms_url?: string | null;
  privacy_url?: string | null;
  social_links?: Record<string, string> | null;
}

export const platformBrandingApi = {
  get: (accessToken: string) =>
    request<PlatformBrandingDefaults>("/api/v1/platform/branding", {}, accessToken),

  update: (data: PlatformBrandingDefaultsUpdate, accessToken: string) =>
    request<PlatformBrandingDefaults>(
      "/api/v1/platform/branding", { method: "PATCH", body: data }, accessToken
    ),

  reset: (accessToken: string) =>
    request<PlatformBrandingDefaults>(
      "/api/v1/platform/branding/reset", { method: "POST" }, accessToken
    ),

  uploadAsset: (file: File, assetType: "logo" | "logo_dark" | "favicon", accessToken: string) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(
      `${API_BASE}/api/v1/platform/branding/assets?asset_type=${encodeURIComponent(assetType)}`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
        body: form,
        credentials: "include",
      }
    ).then(async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new ApiError(r.status, err?.detail || `HTTP ${r.status}`, err);
      }
      return r.json() as Promise<PlatformBrandingDefaults>;
    });
  },
};

export const platformAuthApi = {
  login: (email: string, password: string) =>
    request<PlatformTokenResponse>("/api/v1/platform/auth/login", {
      method: "POST",
      body: { email, password },
    }),

  changePassword: (data: ChangePasswordRequest, accessToken: string) =>
    request<MessageResponse>(
      "/api/v1/platform/auth/change-password",
      { method: "POST", body: data },
      accessToken
    ),

  mfaVerify: (mfa_session_token: string, code: string) =>
    request<PlatformTokenResponse>("/api/v1/platform/auth/mfa-verify", {
      method: "POST",
      body: { mfa_session_token, code },
    }),

  mfaRecovery: (mfa_session_token: string, recovery_code: string) =>
    request<PlatformTokenResponse>("/api/v1/platform/auth/mfa-recovery", {
      method: "POST",
      body: { mfa_session_token, recovery_code },
    }),

  logout: () =>
    request<MessageResponse>("/api/v1/platform/auth/logout", { method: "POST" }),
};

export const platformApi = {
  health: (accessToken: string) =>
    request<{ status: string; scope: string }>(
      "/api/v1/platform/health",
      {},
      accessToken
    ),

  getDemoSettings: (accessToken: string) =>
    request<PlatformDemoSettings>("/api/v1/platform/demo/settings", {}, accessToken),

  updateDemoSettings: (
    changes: Partial<
      Pick<
        PlatformDemoSettings,
        | "enabled"
        | "duration_hours"
        | "max_active_sandboxes"
        | "max_creations_per_ip_per_day"
        | "captcha_required"
      >
    >,
    accessToken: string
  ) =>
    request<PlatformDemoSettings>(
      "/api/v1/platform/demo/settings",
      { method: "PATCH", body: changes },
      accessToken
    ),

  listDemoSandboxes: (accessToken: string, statusFilter?: string) =>
    request<PlatformDemoSandbox[]>(
      `/api/v1/platform/demo/sandboxes${statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : ""}`,
      {},
      accessToken
    ),

  terminateDemoSandbox: (sandboxId: string, accessToken: string) =>
    request<void>(
      `/api/v1/platform/demo/sandboxes/${sandboxId}/terminate`,
      { method: "POST" },
      accessToken
    ),

  cleanupDemoSandboxes: (accessToken: string) =>
    request<{ cleaned: number }>(
      "/api/v1/platform/demo/cleanup",
      { method: "POST" },
      accessToken
    ),

  dashboard: (accessToken: string) =>
    request<PlatformDashboardStats>("/api/v1/platform/dashboard", {}, accessToken),

  analytics: (accessToken: string) =>
    request<PlatformAnalytics>("/api/v1/platform/analytics", {}, accessToken),

  listAgencies: (accessToken: string, params?: { status_filter?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status_filter) qs.set("status_filter", params.status_filter);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs}` : "";
    return request<PlatformAgencyRead[]>(`/api/v1/platform/agencies${query}`, {}, accessToken);
  },

  getAgency: (agencyId: string, accessToken: string) =>
    request<PlatformAgencyDetail>(`/api/v1/platform/agencies/${agencyId}`, {}, accessToken),

  suspendAgency: (agencyId: string, reason: string, accessToken: string) =>
    request<void>(`/api/v1/platform/agencies/${agencyId}/suspend`, {
      method: "POST",
      body: { reason },
    }, accessToken),

  reactivateAgency: (agencyId: string, accessToken: string) =>
    request<void>(`/api/v1/platform/agencies/${agencyId}/reactivate`, { method: "POST" }, accessToken),

  listUsers: (accessToken: string, params?: { user_type?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.user_type) qs.set("user_type", params.user_type);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs}` : "";
    return request<PlatformUserRead[]>(`/api/v1/platform/users${query}`, {}, accessToken);
  },

  deactivateUser: (userId: string, accessToken: string) =>
    request<void>(`/api/v1/platform/users/${userId}/deactivate`, { method: "POST" }, accessToken),

  reactivateUser: (userId: string, accessToken: string) =>
    request<void>(`/api/v1/platform/users/${userId}/reactivate`, { method: "POST" }, accessToken),

  listSubscriptions: (accessToken: string, params?: { limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs}` : "";
    return request<PlatformSubscriptionRead[]>(
      `/api/v1/platform/subscriptions${query}`, {}, accessToken
    );
  },

  listPlans: (accessToken: string) =>
    request<PlanRead[]>("/api/v1/platform/plans", {}, accessToken),

  updatePlan: (planId: string, changes: Partial<PlanRead>, accessToken: string) =>
    request<PlanRead>(`/api/v1/platform/plans/${planId}`, {
      method: "PATCH",
      body: changes,
    }, accessToken),

  listAuditLogs: (accessToken: string, params?: { limit?: number; offset?: number; action_filter?: string }) => {
    const qs = new URLSearchParams();
    if (params?.action_filter) qs.set("action_filter", params.action_filter);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs}` : "";
    return request<PlatformAuditLogRead[]>(`/api/v1/platform/audit-logs${query}`, {}, accessToken);
  },

  startImpersonation: (userId: string, reason: string, accessToken: string) =>
    request<ImpersonationResponse>(`/api/v1/platform/impersonate/${userId}`, {
      method: "POST",
      body: { reason },
    }, accessToken),

  endImpersonation: (accessToken: string) =>
    request<void>("/api/v1/platform/impersonate/end", { method: "POST" }, accessToken),

  refresh: () =>
    request<{ access_token: string; expires_in: number }>(
      "/api/v1/platform/auth/refresh",
      { method: "POST" }
    ),

  // User detail & management
  getUserDetail: (userId: string, accessToken: string) =>
    request<PlatformUserDetail>(`/api/v1/platform/users/${userId}`, {}, accessToken),

  updateUser: (userId: string, data: { full_name?: string; phone_number?: string | null; is_active?: boolean }, accessToken: string) =>
    request<PlatformUserRead>(`/api/v1/platform/users/${userId}`, { method: "PATCH", body: data }, accessToken),

  terminateSessions: (userId: string, accessToken: string) =>
    request<void>(`/api/v1/platform/users/${userId}/terminate-sessions`, { method: "POST" }, accessToken),

  getUserActivity: (userId: string, accessToken: string) =>
    request<Record<string, unknown>[]>(`/api/v1/platform/users/${userId}/activity`, {}, accessToken),

  listUsersWithSearch: (accessToken: string, params?: { user_type?: string; search?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.user_type) qs.set("user_type", params.user_type);
    if (params?.search) qs.set("search", params.search);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs}` : "";
    return request<PlatformUserRead[]>(`/api/v1/platform/users${query}`, {}, accessToken);
  },

  // Agency update & members
  updateAgency: (agencyId: string, data: { name?: string; status?: string }, accessToken: string) =>
    request<PlatformAgencyRead>(`/api/v1/platform/agencies/${agencyId}`, { method: "PATCH", body: data }, accessToken),

  getAgencyMembers: (agencyId: string, accessToken: string) =>
    request<{ id: string; user_id: string; user_email: string; user_full_name: string; role: string; status: string; joined_at: string | null; created_at: string }[]>(
      `/api/v1/platform/agencies/${agencyId}/members`, {}, accessToken
    ),

  getAgencyBrands: (agencyId: string, accessToken: string) =>
    request<PlatformBrandRead[]>(`/api/v1/platform/brands?agency_id=${agencyId}&limit=100`, {}, accessToken),

  updateAgencyMember: (
    agencyId: string,
    memberId: string,
    data: { role?: string; status?: string },
    accessToken: string
  ) =>
    request<{
      id: string;
      user_id: string;
      user_email: string;
      user_full_name: string;
      role: string;
      status: string;
      joined_at: string | null;
      created_at: string;
    }>(`/api/v1/platform/agencies/${agencyId}/members/${memberId}`, { method: "PATCH", body: data }, accessToken),

  updateAgencyPlan: (agencyId: string, planId: string, reason: string | undefined, accessToken: string) =>
    request<PlatformAgencyDetail>(
      `/api/v1/platform/agencies/${agencyId}/plan`,
      { method: "PATCH", body: { plan_id: planId, reason } },
      accessToken
    ),

  getAgencyBrandingAdmin: (agencyId: string, accessToken: string) =>
    request<{ branding: AgencyBrandingRead; domain: CustomDomainRead | null }>(
      `/api/v1/platform/agencies/${agencyId}/branding`, {}, accessToken
    ),

  getAgencyAuditFeed: (agencyId: string, accessToken: string) =>
    request<
      { source: "platform_admin" | "tenant"; id: string; action: string; entity_type?: string; meta: Record<string, unknown> | null; created_at: string }[]
    >(`/api/v1/platform/agencies/${agencyId}/audit`, {}, accessToken),

  // Brand management
  listBrands: (accessToken: string, params?: { search?: string; status_filter?: string; agency_id?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.status_filter) qs.set("status_filter", params.status_filter);
    if (params?.agency_id) qs.set("agency_id", params.agency_id);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs}` : "";
    return request<PlatformBrandRead[]>(`/api/v1/platform/brands${query}`, {}, accessToken);
  },

  getBrand: (brandId: string, accessToken: string) =>
    request<PlatformBrandRead>(`/api/v1/platform/brands/${brandId}`, {}, accessToken),

  updateBrandPlatform: (brandId: string, data: { name?: string; status?: string }, accessToken: string) =>
    request<PlatformBrandRead>(`/api/v1/platform/brands/${brandId}`, { method: "PATCH", body: data }, accessToken),

  getBrandMembers: (brandId: string, accessToken: string) =>
    request<PlatformBrandMemberRead[]>(`/api/v1/platform/brands/${brandId}/members`, {}, accessToken),

  getBrandBriefs: (brandId: string, accessToken: string) =>
    request<Record<string, unknown>[]>(`/api/v1/platform/brands/${brandId}/briefs`, {}, accessToken),

  // SEO management
  listSeoPages: (accessToken: string) =>
    request<PlatformSeoPageRead[]>("/api/v1/platform/seo/pages", {}, accessToken),

  updateSeoPage: (pageKey: string, data: PlatformSeoPageUpdate, accessToken: string) =>
    request<PlatformSeoPageRead>(`/api/v1/platform/seo/pages/${pageKey}`, { method: "PATCH", body: data }, accessToken),

  getTracking: (accessToken: string) =>
    request<PlatformGrowthSettingsRead>("/api/v1/platform/seo/tracking", {}, accessToken),

  updateTracking: (data: Partial<PlatformGrowthSettingsRead>, accessToken: string) =>
    request<PlatformGrowthSettingsRead>("/api/v1/platform/seo/tracking", { method: "PATCH", body: data }, accessToken),

  getRobots: (accessToken: string) =>
    request<{ robots_txt: string | null }>("/api/v1/platform/seo/robots", {}, accessToken),

  updateRobots: (robots_txt: string, accessToken: string) =>
    request<{ robots_txt: string | null }>("/api/v1/platform/seo/robots", { method: "PATCH", body: { robots_txt } }, accessToken),

  getSeoAudit: (accessToken: string) =>
    request<PlatformSeoAuditIssue[]>("/api/v1/platform/seo/audit", {}, accessToken),

  getSeoPageInventory: (accessToken: string) =>
    request<PlatformSeoPageInventoryItem[]>(
      "/api/v1/platform/seo/pages/inventory", {}, accessToken
    ),

  getSeoHealth: (accessToken: string) =>
    request<PlatformSeoHealthSummary>("/api/v1/platform/seo/health", {}, accessToken),

  getPageSpeedResult: (url: string, strategy: "mobile" | "desktop", accessToken: string) =>
    request<PlatformPageSpeedResult>(
      `/api/v1/platform/seo/pagespeed?url=${encodeURIComponent(url)}&strategy=${strategy}`,
      {}, accessToken
    ),

  getIntegrationStatus: (
    provider: "pagespeed" | "search-console" | "ga4", accessToken: string
  ) =>
    request<PlatformIntegrationStatus>(
      `/api/v1/platform/seo/integrations/${provider}`, {}, accessToken
    ),

  regenerateSitemap: (accessToken: string) =>
    request<{ message: string; generated_at: string }>("/api/v1/platform/seo/sitemap/regenerate", { method: "POST" }, accessToken),

  getGrowthMetrics: (accessToken: string) =>
    request<PlatformGrowthMetrics>("/api/v1/platform/growth/metrics", {}, accessToken),
};

// ── Agency KPI types ──────────────────────────────────────────────────────────

export interface AgencyKPIStats {
  pending_briefs: number;
  accepted_briefs: number;
  in_production_briefs: number;
  pending_deliverables: number;
  revision_requested_deliverables: number;
  overdue_briefs: number;
  completed_this_month: number;
  approved_this_month: number;
  open_tasks: number;
  overdue_tasks: number;
  total_deliverables_submitted: number;
  total_deliverables_approved: number;
}

export interface WorkloadMember {
  user_id: string;
  full_name: string | null;
  open_tasks: number;
  overdue_tasks: number;
}

export interface AgencyWorkloadStats {
  members: WorkloadMember[];
}

export interface BrandKPIStats {
  total_briefs: number;
  pending_review: number;
  revision_requested: number;
  approved: number;
  in_production: number;
  overdue_briefs: number;
  pending_deliverables: number;
  approved_deliverables: number;
}

// ── Owner dashboard API ───────────────────────────────────────────────────────

export const ownerApi = {
  dashboard: (agencyId: string, accessToken: string) =>
    request<OwnerDashboardStats>("/api/v1/owner/dashboard", { agencyId }, accessToken),

  members: (agencyId: string, accessToken: string) =>
    request<OwnerMemberRead[]>("/api/v1/owner/members", { agencyId }, accessToken),

  deactivateMember: (memberId: string, agencyId: string, accessToken: string) =>
    request<void>(`/api/v1/owner/members/${memberId}/deactivate`, { method: "POST", agencyId }, accessToken),

  subscription: (agencyId: string, accessToken: string) =>
    request<OwnerSubscriptionRead>("/api/v1/owner/subscription", { agencyId }, accessToken),
};

// ── Brief Center types ────────────────────────────────────────────────────────

export interface BriefCenterKPI {
  total_active_briefs: number;
  overdue_briefs: number;
  revision_requested: number;
  pending_approvals: number;
  new_brand_requests: number;
  due_today: number;
}

export interface AttentionItem {
  id: string;
  title: string;
  brand_id: string | null;
  brand_name: string | null;
  status: string;
  priority: string;
  deadline: string | null;
  days_overdue: number | null;
  source: string | null;
  attention_reason: "overdue" | "revision_requested" | "urgent" | "new_request";
}

export interface BrandCardItem {
  id: string;
  name: string;
  logo_url: string | null;
  status: string;
  active_brief_count: number;
  overdue_count: number;
  revision_requested_count: number;
  pending_approval_count: number;
  this_week_calendar_count: number;
  last_activity_at: string | null;
  has_brand_dna: boolean;
  brand_dna_status: string | null;
}

export interface BriefCenterData {
  kpis: BriefCenterKPI;
  attention_items: AttentionItem[];
  brand_cards: BrandCardItem[];
}

export interface BrandWorkspaceKPI {
  active_briefs: number;
  overdue_briefs: number;
  revision_requested: number;
  pending_approvals: number;
  this_week_calendar: number;
}

export interface BrandBriefSummary {
  id: string;
  title: string;
  status: string;
  priority: string;
  deadline: string | null;
  source: string | null;
  updated_at: string;
}

export interface BrandDeliverableSummary {
  id: string;
  brief_id: string;
  title: string;
  deliverable_type: string;
  status: string;
  version_number: number;
  revision_count: number;
  updated_at: string;
}

export interface BrandCalendarItemSummary {
  id: string;
  title: string;
  item_type: string;
  platform: string;
  status: string;
  publish_at: string | null;
  due_at: string | null;
  brief_id: string | null;
}

export interface BrandWorkspaceDNA {
  has_profile: boolean;
  status: string | null;
  primary_colors: string[] | null;
  typography: unknown[] | null;
  tone_of_voice: Record<string, unknown> | null;
  summary: string | null;
}

export interface BrandWorkspaceData {
  brand_id: string;
  brand_name: string;
  brand_logo_url: string | null;
  brand_status: string;
  kpis: BrandWorkspaceKPI;
  recent_briefs: BrandBriefSummary[];
  recent_deliverables: BrandDeliverableSummary[];
  upcoming_calendar: BrandCalendarItemSummary[];
  brand_dna: BrandWorkspaceDNA;
}

// ── Agency dashboard KPI API ──────────────────────────────────────────────────

export const dashboardApi = {
  agencyKpis: (agencyId: string, accessToken: string) =>
    request<AgencyKPIStats>("/api/v1/dashboard/agency-kpis", { agencyId }, accessToken),

  workload: (agencyId: string, accessToken: string) =>
    request<AgencyWorkloadStats>("/api/v1/dashboard/workload", { agencyId }, accessToken),

  briefCenter: (agencyId: string, accessToken: string) =>
    request<BriefCenterData>("/api/v1/dashboard/brief-center", { agencyId }, accessToken),

  brandWorkspace: (brandId: string, agencyId: string, accessToken: string) =>
    request<BrandWorkspaceData>(
      `/api/v1/dashboard/brands/${brandId}/workspace`,
      { agencyId },
      accessToken
    ),
};

// ── MFA API (user-facing) ─────────────────────────────────────────────────────

export interface MfaSetupResponse {
  secret: string;
  otpauth_url: string;
}

export interface MfaConfirmResponse {
  recovery_codes: string[];
  message: string;
}

export const mfaApi = {
  setup: (accessToken: string) =>
    request<MfaSetupResponse>("/api/v1/auth/mfa/setup", { method: "POST" }, accessToken),

  confirm: (code: string, accessToken: string) =>
    request<MfaConfirmResponse>("/api/v1/auth/mfa/setup/confirm", {
      method: "POST",
      body: { code },
    }, accessToken),

  disable: (code: string, accessToken: string) =>
    request<void>("/api/v1/auth/mfa/disable", { method: "POST", body: { code } }, accessToken),

  regenerateCodes: (code: string, accessToken: string) =>
    request<MfaConfirmResponse>("/api/v1/auth/mfa/recovery-codes/regenerate", {
      method: "POST",
      body: { code },
    }, accessToken),
};

// ── Billing types ─────────────────────────────────────────────────────────────

export interface PlanRead {
  id: string;
  code: string;
  name: string;
  description: string | null;
  monthly_price_cents: number;
  yearly_price_cents: number | null;
  currency: string;
  max_brands: number | null;
  max_users: number | null;
  max_brief_templates: number | null;
  max_storage_gb: number | null;
  white_label_enabled: boolean;
  advanced_reporting_enabled: boolean;
  pdf_export_enabled: boolean;
  public_report_link_enabled: boolean;
  whatsapp_infrastructure_enabled: boolean;
  is_active: boolean;
}

export interface SubscriptionRead {
  id: string;
  agency_id: string;
  plan_id: string;
  plan: PlanRead;
  status: string;
  billing_provider: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

export interface CheckoutRequest {
  plan_id: string;
  yearly?: boolean;
}

export interface CheckoutResponse {
  payment_page_url: string;
  token: string;
  plan_code: string;
  amount_cents: number;
  currency: string;
  provider: string;
  sandbox?: boolean;
}

export interface InvoiceRead {
  id: string;
  subscription_id: string;
  provider_invoice_id: string | null;
  amount_cents: number;
  currency: string;
  status: string;
  period_start: string | null;
  period_end: string | null;
  hosted_invoice_url: string | null;
  created_at: string;
}

export interface UsageSummary {
  plan_code: string | null;
  plan_name: string | null;
  brands: { used: number; limit: number | null };
  users: { used: number; limit: number | null };
  brief_templates: { used: number; limit: number | null };
  storage_gb: { used: number; limit: number | null };
  features: {
    white_label_enabled: boolean;
    advanced_reporting_enabled: boolean;
    pdf_export_enabled: boolean;
    public_report_link_enabled: boolean;
    whatsapp_infrastructure_enabled: boolean;
  };
}

export interface EntitlementCheckResponse {
  feature: string;
  allowed: boolean;
  reason: string | null;
}

export const planApi = {
  list: () => request<PlanRead[]>("/api/v1/plans"),
};

export const billingApi = {
  getSubscription: (accessToken: string, agencyId: string) =>
    request<SubscriptionRead>("/api/v1/billing/subscription", { agencyId }, accessToken),

  createCheckout: (body: CheckoutRequest, accessToken: string, agencyId: string) =>
    request<CheckoutResponse>("/api/v1/billing/checkout", {
      method: "POST",
      body,
      agencyId,
    }, accessToken),

  cancelSubscription: (accessToken: string, agencyId: string) =>
    request<void>("/api/v1/billing/cancel", { method: "POST", agencyId }, accessToken),

  changePlan: (planId: string, accessToken: string, agencyId: string) =>
    request<void>("/api/v1/billing/change-plan", {
      method: "POST",
      body: { plan_id: planId },
      agencyId,
    }, accessToken),

  listInvoices: (accessToken: string, agencyId: string) =>
    request<InvoiceRead[]>("/api/v1/billing/invoices", { agencyId }, accessToken),

  getEntitlements: (accessToken: string, agencyId: string) =>
    request<UsageSummary>("/api/v1/billing/entitlements", { agencyId }, accessToken),

  checkFeature: (feature: string, accessToken: string, agencyId: string) =>
    request<EntitlementCheckResponse>("/api/v1/billing/entitlements/check", {
      method: "POST",
      body: { feature },
      agencyId,
    }, accessToken),
};

// ── Brand Portal API (brand_user only, no X-Agency-ID) ───────────────────────

export interface BrandPortalMeResponse {
  user_id: string;
  email: string;
  full_name: string;
  user_type: string;
  brand_id: string;
  brand_name: string;
  brand_slug: string;
  brand_status: string;
  membership_role: string;
}

export interface BrandPortalDashboard {
  total_briefs: number;
  pending_approval: number;
  revision_requested: number;
  approved: number;
  recent_briefs: BriefRead[];
}

export interface BrandProfileRead {
  id: string;
  name: string;
  slug: string;
  status: string;
  agency_id: string | null;
}

export interface UserProfileRead {
  id: string;
  email: string;
  full_name: string;
  user_type: string;
  job_title?: string | null;
  phone_number?: string | null;
  whatsapp_opt_in?: boolean;
}

export interface BriefWithAssets {
  brief: BriefRead;
  assets: AssetRead[];
}

export interface BrandPortalFilesResponse {
  briefs: BriefWithAssets[];
  total_assets: number;
}

export interface BrandCommentRead {
  id: string;
  body: string;
  comment_type: "general" | "revision_note" | "approval_note";
  author_name: string | null;
  author_user_id: string | null;
  is_brand_user: boolean;
  created_at: string;
}

export interface BrandTeamMemberRead {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  status: string;
  joined_at: string | null;
}

export interface BrandTeamResponse {
  members: BrandTeamMemberRead[];
  pending_invitations: InvitationRead[];
}

export interface BrandTeamUsage {
  plan_code: string | null;
  plan_name: string | null;
  users: {
    used: number;
    active: number;
    pending_invites: number;
    limit: number | null;
    available: number | null;
  };
  pending_invites: {
    used: number;
    limit: number | null;
  };
}

export interface BrandTimelineEntry {
  id: string;
  event: string;
  label: string;
  timestamp: string;
  actor: string | null;
  note: string | null;
  color: "muted" | "amber" | "emerald" | "orange" | "blue";
}

// ── Brand Portal: invoices (Phase 5) ────────────────────────────────────────
// Mirrors apps/backend/app/schemas/brand_finance.py `BrandInvoiceRead`
// field-for-field — a deliberately separate, minimal type from
// `ClientInvoiceRead` (see that type's comment, defined further below in
// this file next to `financeApi` — `ClientInvoiceStatusValue`/
// `ClientInvoiceDocumentTypeValue` are reused here by forward reference,
// TS type aliases don't require declaration order). It carries zero
// cost/margin fields and zero agency-internal bookkeeping fields
// (`commercial_terms_id`, `created_by_id`, `approved_by_id`) by
// construction.

export interface BrandInvoiceRead {
  id: string;
  invoice_number: string;
  document_type: ClientInvoiceDocumentTypeValue;
  issue_date: string;
  due_date: string;
  service_period_start: string | null;
  service_period_end: string | null;
  currency: string;
  subtotal_cents: number;
  discount_cents: number;
  tax_cents: number;
  total_cents: number;
  amount_paid_cents: number;
  status: ClientInvoiceStatusValue;
  notes: string | null;
  billing_contact_name: string | null;
  billing_contact_email: string | null;
  tax_office: string | null;
  tax_number: string | null;
  sent_at: string | null;
  paid_at: string | null;
}

// Mirrors `BrandInvoiceLineRead` — no invoice_id/source_type/source_id, no
// cost/billing-rate snapshot fields, by construction on the backend.
export interface BrandInvoiceLineRead {
  id: string;
  description: string;
  quantity: number;
  unit: string;
  unit_price_cents: number;
  tax_rate_bps: number;
  discount_cents: number;
  subtotal_cents: number;
  tax_cents: number;
  total_cents: number;
  service_period_start: string | null;
  service_period_end: string | null;
}

export interface BrandInvoiceWithLines extends BrandInvoiceRead {
  lines: BrandInvoiceLineRead[];
}

export const brandPortalApi = {
  me: (accessToken: string) =>
    request<BrandPortalMeResponse>("/api/v1/brand-portal/me", {}, accessToken),

  dashboard: (accessToken: string) =>
    request<BrandPortalDashboard>("/api/v1/brand-portal/dashboard", {}, accessToken),

  kpis: (accessToken: string) =>
    request<BrandKPIStats>("/api/v1/brand-portal/dashboard/kpis", {}, accessToken),

  listBriefs: (accessToken: string, params?: { status?: string; search?: string; offset?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.search) qs.set("search", params.search);
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    const query = qs.toString() ? `?${qs}` : "";
    return request<BriefListResponse>(`/api/v1/brand-portal/briefs${query}`, {}, accessToken);
  },

  getBrief: (briefId: string, accessToken: string) =>
    request<BriefRead>(`/api/v1/brand-portal/briefs/${briefId}`, {}, accessToken),

  listApprovals: (
    accessToken: string,
    params?: { status?: string; assigned_to_me?: boolean }
  ) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.assigned_to_me) qs.set("assigned_to_me", "true");
    const query = qs.toString() ? `?${qs}` : "";
    return request<BrandApprovalCard[]>(`/api/v1/brand-portal/approvals${query}`, {}, accessToken);
  },

  getApprovalDetail: (approvalId: string, accessToken: string) =>
    request<BrandApprovalCard>(`/api/v1/brand-portal/approvals/${approvalId}`, {}, accessToken),

  addApprovalComment: (approvalId: string, body: string, commentType: string, accessToken: string) =>
    request<BrandCommentRead>(
      `/api/v1/brand-portal/approvals/${approvalId}/comment`,
      { method: "POST", body: { body, comment_type: commentType } },
      accessToken,
    ),

  rejectBrief: (briefId: string, reason: string, accessToken: string) =>
    request<BriefRead>(
      `/api/v1/brand-portal/briefs/${briefId}/reject`,
      { method: "POST", body: { reason } },
      accessToken,
    ),

  listNotifications: (
    accessToken: string,
    params?: { unread_only?: boolean; include_archived?: boolean; limit?: number; offset?: number }
  ) => {
    const qs = new URLSearchParams();
    if (params?.unread_only !== undefined) qs.set("unread_only", String(params.unread_only));
    if (params?.include_archived !== undefined) qs.set("include_archived", String(params.include_archived));
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs}` : "";
    return request<NotificationListResponse>(`/api/v1/brand-portal/notifications${query}`, {}, accessToken);
  },

  markNotificationRead: (notificationId: string, accessToken: string) =>
    request<NotificationRead>(
      `/api/v1/brand-portal/notifications/${notificationId}/read`,
      { method: "POST" },
      accessToken,
    ),

  markAllNotificationsRead: (accessToken: string) =>
    request<{ marked_read: number }>(
      `/api/v1/brand-portal/notifications/read-all`,
      { method: "POST" },
      accessToken,
    ),

  createNotificationRealtimeTicket: (accessToken: string) =>
    request<NotificationRealtimeTicket>(
      "/api/v1/brand-portal/notifications/realtime-ticket",
      { method: "POST" },
      accessToken,
    ),

  archiveNotification: (notificationId: string, accessToken: string) =>
    request<NotificationRead>(
      `/api/v1/brand-portal/notifications/${notificationId}/archive`,
      { method: "POST" },
      accessToken,
    ),

  getTeam: (accessToken: string) =>
    request<BrandTeamResponse>("/api/v1/brand-portal/team", {}, accessToken),

  getTeamUsage: (accessToken: string) =>
    request<BrandTeamUsage>("/api/v1/brand-portal/team/usage", {}, accessToken),

  inviteTeamMember: (data: { email: string; role: string; message?: string | null }, accessToken: string) =>
    request<InvitationRead>(
      "/api/v1/brand-portal/team/invite",
      { method: "POST", body: data },
      accessToken,
    ),

  cancelTeamInvitation: (invitationId: string, accessToken: string) =>
    request<{ message: string }>(
      `/api/v1/brand-portal/team/invitations/${invitationId}/cancel`,
      { method: "POST" },
      accessToken,
    ),

  resendTeamInvitation: (invitationId: string, accessToken: string) =>
    request<InvitationRead>(
      `/api/v1/brand-portal/team/invitations/${invitationId}/resend`,
      { method: "POST" },
      accessToken,
    ),

  deleteAsset: (assetId: string, accessToken: string) =>
    request<void>(`/api/v1/brand-portal/assets/${assetId}`, { method: "DELETE" }, accessToken),

  listCalendar: (
    accessToken: string,
    params?: {
      from?: string;
      to?: string;
      status?: string;
      event_type?: string;
      brief_id?: string;
      assignee_id?: string;
      priority?: string;
    },
  ) => {
    const qs = new URLSearchParams();
    if (params?.from) qs.set("from", params.from);
    if (params?.to) qs.set("to", params.to);
    if (params?.status) qs.set("status", params.status);
    if (params?.event_type) qs.set("event_type", params.event_type);
    if (params?.brief_id) qs.set("brief_id", params.brief_id);
    if (params?.assignee_id) qs.set("assignee_id", params.assignee_id);
    if (params?.priority) qs.set("priority", params.priority);
    const query = qs.toString() ? `?${qs}` : "";
    return request<BrandCalendarEntry[]>(`/api/v1/brand-portal/calendar${query}`, {}, accessToken);
  },

  listFiles: (accessToken: string) =>
    request<BrandPortalFilesResponse>("/api/v1/brand-portal/files", {}, accessToken),

  listReports: (accessToken: string) =>
    request<ReportRead[]>("/api/v1/brand-portal/reports", {}, accessToken),

  getProfile: (accessToken: string) =>
    request<UserProfileRead>("/api/v1/brand-portal/profile", {}, accessToken),

  updateProfile: (
    data: { full_name?: string; job_title?: string | null; phone_number?: string | null; whatsapp_opt_in?: boolean },
    accessToken: string
  ) =>
    request<UserProfileRead>("/api/v1/brand-portal/profile", { method: "PATCH", body: data }, accessToken),

  getBrand: (accessToken: string) =>
    request<BrandProfileRead>("/api/v1/brand-portal/brand", {}, accessToken),

  updateBrand: (data: { name?: string }, accessToken: string) =>
    request<BrandProfileRead>("/api/v1/brand-portal/brand", { method: "PATCH", body: data }, accessToken),

  listBriefComments: (briefId: string, accessToken: string) =>
    request<BrandCommentRead[]>(`/api/v1/brand-portal/briefs/${briefId}/comments`, {}, accessToken),

  addBriefComment: (briefId: string, body: string, commentType: string, accessToken: string) =>
    request<BrandCommentRead>(
      `/api/v1/brand-portal/briefs/${briefId}/comments`,
      { method: "POST", body: { body, comment_type: commentType } },
      accessToken,
    ),

  approveBrief: (briefId: string, note: string | null, accessToken: string) =>
    request<BriefRead>(
      `/api/v1/brand-portal/briefs/${briefId}/approve`,
      { method: "POST", body: { note } },
      accessToken,
    ),

  requestRevision: (briefId: string, reason: string, accessToken: string) =>
    request<BriefRead>(
      `/api/v1/brand-portal/briefs/${briefId}/request-revision`,
      { method: "POST", body: { reason } },
      accessToken,
    ),

  getBriefTimeline: (briefId: string, accessToken: string) =>
    request<BrandTimelineEntry[]>(`/api/v1/brand-portal/briefs/${briefId}/timeline`, {}, accessToken),

  createBrief: (data: BrandBriefCreate, accessToken: string) =>
    request<BriefRead>("/api/v1/brand-portal/briefs", { method: "POST", body: data }, accessToken),

  updateBrief: (briefId: string, data: BrandBriefUpdate, accessToken: string) =>
    request<BriefRead>(`/api/v1/brand-portal/briefs/${briefId}`, { method: "PATCH", body: data }, accessToken),

  submitBrief: (briefId: string, accessToken: string) =>
    request<BriefRead>(`/api/v1/brand-portal/briefs/${briefId}/submit`, { method: "POST" }, accessToken),

  listTemplates: (accessToken: string) =>
    request<BriefTemplateListItem[]>("/api/v1/brand-portal/templates", {}, accessToken),

  listBriefAssets: (briefId: string, accessToken: string) =>
    request<AssetRead[]>(`/api/v1/brand-portal/briefs/${briefId}/assets`, {}, accessToken),

  uploadBriefAsset: (briefId: string, file: File, accessToken: string) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_BASE}/api/v1/brand-portal/briefs/${briefId}/assets`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: form,
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new ApiError(r.status, err?.detail || `HTTP ${r.status}`, err);
      }
      return r.json() as Promise<AssetRead>;
    });
  },

  listDeliverables: (briefId: string, accessToken: string) =>
    request<BrandDeliverableRead[]>(`/api/v1/brand-portal/briefs/${briefId}/deliverables`, {}, accessToken),

  approveDeliverable: (briefId: string, deliverableId: string, note: string | null, accessToken: string) =>
    request<BrandDeliverableRead>(
      `/api/v1/brand-portal/briefs/${briefId}/deliverables/${deliverableId}/approve`,
      { method: "POST", body: { note } },
      accessToken,
    ),

  requestDeliverableRevision: (briefId: string, deliverableId: string, reason: string, accessToken: string) =>
    request<BrandDeliverableRead>(
      `/api/v1/brand-portal/briefs/${briefId}/deliverables/${deliverableId}/request-revision`,
      { method: "POST", body: { reason } },
      accessToken,
    ),

  // ── Invoices (Phase 5) ────────────────────────────────────────────────────

  listInvoices: (accessToken: string, params?: { limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<BrandInvoiceRead[]>(`/api/v1/brand-portal/invoices${query}`, {}, accessToken);
  },

  getInvoice: (invoiceId: string, accessToken: string) =>
    request<BrandInvoiceWithLines>(`/api/v1/brand-portal/invoices/${invoiceId}`, {}, accessToken),

  /** Blob-fetch pattern mirrors `financeApi.downloadInvoicePdf` — no
   * `X-Agency-ID` header here since brand-portal auth is a separate
   * context keyed only on the bearer token (matches every other
   * `brandPortalApi` call). */
  downloadInvoicePdf: async (invoiceId: string, accessToken: string): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/api/v1/brand-portal/invoices/${invoiceId}/pdf`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      credentials: "include",
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new ApiError(response.status, err?.detail || `HTTP ${response.status}`, err);
    }
    return response.blob();
  },
};

// ── Deliverable types ─────────────────────────────────────────────────────────

export type DeliverableType = "image" | "video" | "text" | "document" | "link" | "other";
export type DeliverableStatus =
  | "draft"
  | "submitted"
  | "revision_requested"
  | "approved"
  | "rejected"
  | "archived";

export interface DeliverableRead {
  id: string;
  agency_id: string;
  brand_id: string | null;
  brief_id: string;
  title: string;
  description: string | null;
  description_html: string | null;
  deliverable_type: DeliverableType;
  status: DeliverableStatus;
  version_number: number;
  revision_count: number;
  revision_note: string | null;
  approve_note: string | null;
  is_latest_version: boolean;
  created_by_id: string | null;
  submitted_by_id: string | null;
  submitted_at: string | null;
  approved_by_id: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
  assets: AssetRead[];
}

export interface AnnotationReplyRead {
  id: string;
  annotation_id: string;
  author_user_id: string | null;
  author_name: string | null;
  body: string;
  body_html: string | null;
  visibility: string;
  created_at: string;
  updated_at: string;
  mentions: MentionInline[];
}

export interface AnnotationRead {
  id: string;
  agency_id: string;
  brand_id: string | null;
  brief_id: string;
  deliverable_id: string;
  asset_id: string | null;
  version_number: number;
  x_percent: number | null;
  y_percent: number | null;
  label_number: number;
  status: "open" | "resolved";
  annotation_type: "general" | "revision" | "approval_note";
  visibility: "internal" | "client_visible";
  body: string | null;
  body_html: string | null;
  created_by_id: string | null;
  created_by_name?: string | null;
  resolved_by_id: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  replies: AnnotationReplyRead[];
  mentions: MentionInline[];
}

export interface AnnotationCreate {
  asset_id?: string | null;
  version_number?: number;
  x_percent?: number | null;
  y_percent?: number | null;
  annotation_type?: "general" | "revision" | "approval_note";
  visibility?: "internal" | "client_visible";
  body: string;
  body_html?: string | null;
  mentioned_user_ids?: string[];
}

export interface AnnotationReplyCreate {
  body: string;
  body_html?: string | null;
  visibility?: "internal" | "client_visible";
  mentioned_user_ids?: string[];
}

export const annotationApi = {
  list: (briefId: string, deliverableId: string, accessToken: string, agencyId: string, versionNumber?: number) =>
    request<AnnotationRead[]>(
      `/api/v1/briefs/${briefId}/deliverables/${deliverableId}/annotations${versionNumber != null ? `?version_number=${versionNumber}` : ""}`,
      { agencyId },
      accessToken
    ),

  create: (briefId: string, deliverableId: string, data: AnnotationCreate, accessToken: string, agencyId: string) =>
    request<AnnotationRead>(`/api/v1/briefs/${briefId}/deliverables/${deliverableId}/annotations`, {
      method: "POST",
      body: data,
      agencyId,
    }, accessToken),

  resolve: (deliverableId: string, annotationId: string, accessToken: string, agencyId: string) =>
    request<AnnotationRead>(`/api/v1/annotations/${annotationId}/resolve?deliverable_id=${deliverableId}`, {
      method: "POST",
      agencyId,
    }, accessToken),

  reply: (deliverableId: string, annotationId: string, data: AnnotationReplyCreate, accessToken: string, agencyId: string) =>
    request<AnnotationReplyRead>(`/api/v1/annotations/${annotationId}/replies?deliverable_id=${deliverableId}`, {
      method: "POST",
      body: data,
      agencyId,
    }, accessToken),
};

export const brandAnnotationApi = {
  list: (deliverableId: string, accessToken: string, versionNumber?: number) =>
    request<AnnotationRead[]>(
      `/api/v1/brand-portal/deliverables/${deliverableId}/annotations${versionNumber != null ? `?version_number=${versionNumber}` : ""}`,
      {},
      accessToken
    ),

  create: (deliverableId: string, data: Omit<AnnotationCreate, "visibility">, accessToken: string) =>
    request<AnnotationRead>(`/api/v1/brand-portal/deliverables/${deliverableId}/annotations`, {
      method: "POST",
      body: data,
    }, accessToken),

  reply: (deliverableId: string, annotationId: string, data: { body: string; body_html?: string | null; mentioned_user_ids?: string[] }, accessToken: string) =>
    request<AnnotationReplyRead>(`/api/v1/brand-portal/annotations/${annotationId}/replies?deliverable_id=${deliverableId}`, {
      method: "POST",
      body: data,
    }, accessToken),

  reopen: (deliverableId: string, annotationId: string, accessToken: string) =>
    request<AnnotationRead>(`/api/v1/brand-portal/annotations/${annotationId}/reopen?deliverable_id=${deliverableId}`, {
      method: "POST",
    }, accessToken),
};

export interface BrandDeliverableRead {
  id: string;
  brief_id: string;
  title: string;
  description: string | null;
  description_html: string | null;
  deliverable_type: DeliverableType;
  status: DeliverableStatus;
  version_number: number;
  revision_count: number;
  revision_note: string | null;
  approve_note: string | null;
  is_latest_version: boolean;
  submitted_at: string | null;
  approved_at: string | null;
  created_at: string;
  assets: AssetRead[];
  open_annotation_count: number;
}

export interface DeliverableCreate {
  title: string;
  description?: string | null;
  description_html?: string | null;
  deliverable_type?: DeliverableType;
}

export interface DeliverableUpdate {
  title?: string | null;
  description?: string | null;
  description_html?: string | null;
  deliverable_type?: DeliverableType | null;
}

export const deliverableApi = {
  list: (briefId: string, accessToken: string, agencyId: string) =>
    request<DeliverableRead[]>(`/api/v1/briefs/${briefId}/deliverables`, { agencyId }, accessToken),

  get: (briefId: string, deliverableId: string, accessToken: string, agencyId: string) =>
    request<DeliverableRead>(`/api/v1/briefs/${briefId}/deliverables/${deliverableId}`, { agencyId }, accessToken),

  create: (briefId: string, data: DeliverableCreate, accessToken: string, agencyId: string) =>
    request<DeliverableRead>(`/api/v1/briefs/${briefId}/deliverables`, {
      method: "POST",
      body: data,
      agencyId,
    }, accessToken),

  update: (briefId: string, deliverableId: string, data: DeliverableUpdate, accessToken: string, agencyId: string) =>
    request<DeliverableRead>(`/api/v1/briefs/${briefId}/deliverables/${deliverableId}`, {
      method: "PATCH",
      body: data,
      agencyId,
    }, accessToken),

  delete: (briefId: string, deliverableId: string, accessToken: string, agencyId: string) =>
    request<void>(`/api/v1/briefs/${briefId}/deliverables/${deliverableId}`, {
      method: "DELETE",
      agencyId,
    }, accessToken),

  submit: (briefId: string, deliverableId: string, accessToken: string, agencyId: string) =>
    request<DeliverableRead>(`/api/v1/briefs/${briefId}/deliverables/${deliverableId}/submit`, {
      method: "POST",
      agencyId,
    }, accessToken),

  uploadAsset: (briefId: string, deliverableId: string, file: File, accessToken: string, agencyId: string) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_BASE}/api/v1/briefs/${briefId}/deliverables/${deliverableId}/assets`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}`, "X-Agency-ID": agencyId },
      body: form,
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new ApiError(r.status, err?.detail || `HTTP ${r.status}`, err);
      }
      return r.json() as Promise<AssetRead>;
    });
  },
};

// ── Social Media Preview Center types ────────────────────────────────────────

export type PreviewPlatform = "instagram" | "facebook" | "tiktok" | "linkedin" | "x";

export type PreviewFormat =
  | "feed_single"
  | "feed_carousel"
  | "story"
  | "reel"
  | "reel_cover"
  | "grid"
  | "document_carousel"
  | "text_post";

export interface PreviewWarning {
  code: string;
  message: string;
  severity: "info" | "warning";
}

export interface PreviewConfigRead {
  id: string;
  agency_id: string;
  brand_id: string | null;
  brief_id: string;
  deliverable_id: string;
  platform: PreviewPlatform;
  preview_format: PreviewFormat;
  caption: string | null;
  title: string | null;
  cta_label: string | null;
  hashtags: string[] | null;
  display_name_override: string | null;
  profile_photo_asset_id: string | null;
  cover_asset_id: string | null;
  revision_number: number;
  created_by_id: string | null;
  updated_by_id: string | null;
  created_at: string;
  updated_at: string;
  warnings: PreviewWarning[];
}

export interface PreviewConfigUpsert {
  platform: PreviewPlatform;
  preview_format: PreviewFormat;
  caption?: string | null;
  title?: string | null;
  cta_label?: string | null;
  hashtags?: string[] | null;
  display_name_override?: string | null;
  profile_photo_asset_id?: string | null;
  cover_asset_id?: string | null;
}

export interface PreviewSlotRead {
  id: string;
  deliverable_id: string;
  asset_id: string;
  position: number;
  is_cover: boolean;
  created_at: string;
  updated_at: string;
}

export interface PreviewSlotItem {
  asset_id: string;
  position: number;
  is_cover?: boolean;
}

export interface PreviewSlotsReorderPayload {
  slots: PreviewSlotItem[];
}

export const deliverablePreviewApi = {
  getConfig: (briefId: string, deliverableId: string, accessToken: string, agencyId: string) =>
    request<PreviewConfigRead>(
      `/api/v1/briefs/${briefId}/deliverables/${deliverableId}/preview-config`,
      { agencyId },
      accessToken,
    ),

  upsertConfig: (
    briefId: string,
    deliverableId: string,
    data: PreviewConfigUpsert,
    accessToken: string,
    agencyId: string,
  ) =>
    request<PreviewConfigRead>(
      `/api/v1/briefs/${briefId}/deliverables/${deliverableId}/preview-config`,
      { method: "PUT", body: data, agencyId },
      accessToken,
    ),

  listSlots: (briefId: string, deliverableId: string, accessToken: string, agencyId: string) =>
    request<PreviewSlotRead[]>(
      `/api/v1/briefs/${briefId}/deliverables/${deliverableId}/preview-slots`,
      { agencyId },
      accessToken,
    ),

  reorderSlots: (
    briefId: string,
    deliverableId: string,
    data: PreviewSlotsReorderPayload,
    accessToken: string,
    agencyId: string,
  ) =>
    request<PreviewSlotRead[]>(
      `/api/v1/briefs/${briefId}/deliverables/${deliverableId}/preview-slots`,
      { method: "PUT", body: data, agencyId },
      accessToken,
    ),
};

export const brandPreviewApi = {
  getConfig: (briefId: string, deliverableId: string, accessToken: string) =>
    request<PreviewConfigRead>(
      `/api/v1/brand-portal/briefs/${briefId}/deliverables/${deliverableId}/preview-config`,
      {},
      accessToken,
    ),

  listSlots: (briefId: string, deliverableId: string, accessToken: string) =>
    request<PreviewSlotRead[]>(
      `/api/v1/brand-portal/briefs/${briefId}/deliverables/${deliverableId}/preview-slots`,
      {},
      accessToken,
    ),
};

// ── Twilio / WhatsApp provider types ─────────────────────────────────────────

export type WhatsAppProviderType =
  | "disabled"
  | "twilio_sandbox"
  | "twilio_production"
  | "future_provider";

export type WhatsAppConnectionStatus =
  | "disabled"
  | "not_configured"
  | "sandbox"
  | "connected"
  | "degraded"
  | "error";

export interface TwilioProviderStatusRead {
  provider: string;
  provider_type: WhatsAppProviderType;
  is_enabled: boolean;
  is_configured: boolean;
  connection_status: WhatsAppConnectionStatus;
  account_sid_masked: string | null;
  whatsapp_from_masked: string | null;
  auth_token_set: boolean;
  webhook_verify_token_set: boolean;
  messaging_service_sid_set: boolean;
  configured_at: string | null;
  configured_by_user_id: string | null;
  last_connection_check_at: string | null;
  last_connection_error: string | null;
  missing_fields: string[];
}

export interface ConnectionVerifyResult {
  connection_status: WhatsAppConnectionStatus;
  detail: string | null;
  checked_at: string;
}

export interface WhatsAppTenantTestSendResponse {
  delivery_id: string | null;
  masked_recipient: string | null;
  status: string;
  provider: string;
  template_key: string;
  provider_message_id: string | null;
  safe_error: string | null;
}

export interface TwilioProviderUpdate {
  provider_type?: WhatsAppProviderType;
  is_enabled?: boolean;
  account_sid?: string | null;
  auth_token?: string | null;
  whatsapp_from?: string | null;
  messaging_service_sid?: string | null;
  webhook_verify_token?: string | null;
}

export interface WhatsAppTestSendRequest {
  to_phone: string;
  message?: string | null;
}

export interface WhatsAppTestSendResult {
  status: string;
  provider: string;
  provider_message_id: string | null;
  error_message: string | null;
  to_phone_masked: string;
}

// ── Resend / Email provider types ─────────────────────────────────────────────

export interface ResendProviderStatusRead {
  provider: string;
  configuration_source: "database" | "environment" | "none";
  is_enabled: boolean;
  is_configured: boolean;
  api_key_set: boolean;
  email_api_key_masked: string | null;
  from_name: string | null;
  from_email: string | null;
  reply_to: string | null;
  configured_at: string | null;
  configured_by_user_id: string | null;
  missing_fields: string[];
}

export interface ResendProviderUpdate {
  is_enabled?: boolean;
  api_key?: string | null;
  from_name?: string | null;
  from_email?: string | null;
  reply_to?: string | null;
}

export interface EmailTestSendRequest {
  to_email: string;
  subject?: string | null;
  message?: string | null;
}

export interface EmailTestSendResult {
  status: string;
  provider: string;
  provider_message_id: string | null;
  error_message: string | null;
  to_email_masked: string;
}

export const resendProviderApi = {
  getStatus: (accessToken: string) =>
    request<ResendProviderStatusRead>(
      "/api/v1/platform/notification-providers/email",
      {},
      accessToken
    ),

  update: (data: ResendProviderUpdate, accessToken: string) =>
    request<ResendProviderStatusRead>(
      "/api/v1/platform/notification-providers/email",
      { method: "PATCH", body: data },
      accessToken
    ),

  testSend: (data: EmailTestSendRequest, accessToken: string) =>
    request<EmailTestSendResult>(
      "/api/v1/platform/notification-providers/email/test",
      { method: "POST", body: data },
      accessToken
    ),

  clearApiKey: (accessToken: string) =>
    request<ResendProviderStatusRead>(
      "/api/v1/platform/notification-providers/email/clear-secret",
      { method: "POST", body: { field: "api_key" } },
      accessToken
    ),
};

export const twilioProviderApi = {
  getStatus: (accessToken: string) =>
    request<TwilioProviderStatusRead>(
      "/api/v1/platform/notification-providers/whatsapp",
      {},
      accessToken
    ),

  update: (data: TwilioProviderUpdate, accessToken: string) =>
    request<TwilioProviderStatusRead>(
      "/api/v1/platform/notification-providers/whatsapp",
      { method: "PATCH", body: data },
      accessToken
    ),

  testSend: (data: WhatsAppTestSendRequest, accessToken: string) =>
    request<WhatsAppTestSendResult>(
      "/api/v1/platform/notification-providers/whatsapp/test",
      { method: "POST", body: data },
      accessToken
    ),

  clearSecret: (
    field:
      | "auth_token"
      | "account_sid"
      | "whatsapp_from"
      | "messaging_service_sid"
      | "webhook_verify_token",
    accessToken: string
  ) =>
    request<TwilioProviderStatusRead>(
      "/api/v1/platform/notification-providers/whatsapp/clear-secret",
      { method: "POST", body: { field } },
      accessToken
    ),

  verifyConnection: (accessToken: string) =>
    request<ConnectionVerifyResult>(
      "/api/v1/platform/notification-providers/whatsapp/verify-connection",
      { method: "POST" },
      accessToken
    ),
};

// Tenant-scoped (Owner/Admin) controlled WhatsApp test-send — takes no
// recipient argument; the backend always resolves the target itself.
export const whatsappTestSendApi = {
  testSend: (agencyId: string, accessToken: string) =>
    request<WhatsAppTenantTestSendResponse>(
      "/api/v1/notifications/whatsapp/test",
      { method: "POST", agencyId },
      accessToken
    ),
};

// ── WhatsApp preferences & management center (Part 6B-2) ─────────────────────

export type WhatsAppEventGroup =
  | "brief_and_work"
  | "comments_and_collaboration"
  | "delivery_and_approval"
  | "finance";

export interface WhatsAppEventPreferenceRead {
  event_type: string;
  event_label: string;
  group: WhatsAppEventGroup;
  group_label: string;
  whatsapp_enabled: boolean;
  template_ready: boolean;
  is_customized: boolean;
  updated_at: string | null;
}

export interface PhoneStatusRead {
  has_phone_number: boolean;
  phone_masked: string | null;
  phone_verified: boolean;
}

export interface WhatsAppConsentRead {
  whatsapp_opt_in: boolean;
  whatsapp_opt_in_at: string | null;
  whatsapp_opt_out_at: string | null;
  whatsapp_consent_source: string | null;
  whatsapp_consent_version: string | null;
}

export interface WhatsAppUserStatusRead {
  whatsapp_provider_active: boolean;
  phone: PhoneStatusRead;
  consent: WhatsAppConsentRead;
  master_enabled: boolean;
  is_demo_tenant: boolean;
  events: WhatsAppEventPreferenceRead[];
  last_delivery_status: string | null;
  last_delivery_at: string | null;
  last_safe_error: string | null;
}

export interface WhatsAppAgencySummaryRead {
  connection_status: WhatsAppConnectionStatus;
  sender_masked: string | null;
  environment: string;
  opted_in_users: number;
  whatsapp_enabled_users: number;
  templates_ready: number;
  templates_not_ready: number;
  deliveries_24h: Record<string, number>;
  deliveries_7d: Record<string, number>;
  last_safe_error: string | null;
  demo_tenant: boolean;
  retry_queue: number;
  retry_exhausted: number;
  delivery_success_rate_7d: number | null;
  read_rate_7d: number | null;
  top_failure_category_7d: string | null;
}

export interface WhatsAppTemplateMatrixRowRead {
  event_type: string;
  event_label: string;
  template_key: string;
  locale: string;
  status: string;
  enabled: boolean;
  has_content_sid: boolean;
  approved_at: string | null;
  recipient_policy: string;
}

export interface WhatsAppTemplatePreviewRead {
  event_type: string;
  event_label: string;
  template_key: string;
  locale: string;
  status: string;
  sample_message: string;
  variable_names: string[];
  recipient_roles: string;
  sensitive_data_note: string;
}

export interface WhatsAppDeliveryHistoryItemRead {
  id: string;
  created_at: string;
  event_type: string;
  template_key: string | null;
  recipient_phone_masked: string | null;
  recipient_display_name: string | null;
  provider: string;
  status: string;
  attempt_count: number;
  safe_error: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  read_at: string | null;
}

export interface WhatsAppDeliveryHistoryPage {
  items: WhatsAppDeliveryHistoryItemRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface WhatsAppDeliveryHistoryFilters {
  event_type?: string;
  status?: string;
  template_key?: string;
  user_id?: string;
  limit?: number;
  offset?: number;
}

// Self-service, any authenticated agency/brand user — self-scoped only.
export const whatsappPreferencesApi = {
  getStatus: (agencyId: string | null, accessToken: string) =>
    request<WhatsAppUserStatusRead>(
      "/api/v1/notifications/whatsapp/status",
      agencyId ? { agencyId } : {},
      accessToken
    ),

  updateConsent: (optIn: boolean, agencyId: string | null, accessToken: string) =>
    request<WhatsAppUserStatusRead>(
      "/api/v1/notifications/whatsapp/consent",
      { method: "POST", body: { opt_in: optIn }, ...(agencyId ? { agencyId } : {}) },
      accessToken
    ),

  updateEventPreference: (
    eventType: string,
    whatsappEnabled: boolean,
    agencyId: string | null,
    accessToken: string
  ) =>
    request<WhatsAppEventPreferenceRead>(
      `/api/v1/notifications/whatsapp/event-preferences/${encodeURIComponent(eventType)}`,
      {
        method: "PATCH",
        body: { whatsapp_enabled: whatsappEnabled },
        ...(agencyId ? { agencyId } : {}),
      },
      accessToken
    ),

  testSendBrand: (accessToken: string) =>
    request<WhatsAppTenantTestSendResponse>(
      "/api/v1/brand-portal/notifications/whatsapp/test",
      { method: "POST" },
      accessToken
    ),
};

// Owner/Admin management center — agency-scoped, requires agency:manage_notifications.
export const whatsappAdminApi = {
  getSummary: (agencyId: string, accessToken: string) =>
    request<WhatsAppAgencySummaryRead>(
      "/api/v1/notifications/whatsapp/summary",
      { agencyId },
      accessToken
    ),

  getTemplateMatrix: (agencyId: string, accessToken: string) =>
    request<WhatsAppTemplateMatrixRowRead[]>(
      "/api/v1/notifications/whatsapp/template-matrix",
      { agencyId },
      accessToken
    ),

  getTemplatePreview: (eventType: string, agencyId: string, accessToken: string) =>
    request<WhatsAppTemplatePreviewRead>(
      `/api/v1/notifications/whatsapp/template-preview/${encodeURIComponent(eventType)}`,
      { agencyId },
      accessToken
    ),

  listDeliveries: (
    agencyId: string,
    accessToken: string,
    filters?: WhatsAppDeliveryHistoryFilters
  ) => {
    const qs = new URLSearchParams();
    if (filters?.event_type) qs.set("event_type", filters.event_type);
    if (filters?.status) qs.set("status", filters.status);
    if (filters?.template_key) qs.set("template_key", filters.template_key);
    if (filters?.user_id) qs.set("user_id", filters.user_id);
    if (filters?.limit !== undefined) qs.set("limit", String(filters.limit));
    if (filters?.offset !== undefined) qs.set("offset", String(filters.offset));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<WhatsAppDeliveryHistoryPage>(
      `/api/v1/notifications/whatsapp/deliveries${query}`,
      { agencyId },
      accessToken
    );
  },
};

// ── Brand Identity / Marka DNA ────────────────────────────────────────────────

export interface ColorEntry {
  name: string | null;
  hex: string | null;
  rgb: string | null;
  cmyk?: string | null;
  usage: string | null;
  source?: string | null;
  confidence?: string | null;
}

export interface FontEntry {
  role: string | null;
  family: string | null;
  weight: string | null;
  usage: string | null;
}

export interface BrandIdentityDocumentRead {
  id: string;
  brand_id: string;
  agency_id: string | null;
  uploaded_by_id: string | null;
  file_name: string;
  file_size: number;
  content_type: string;
  status: "uploaded" | "processing" | "analyzed" | "needs_review" | "approved" | "failed";
  analysis_error: string | null;
  page_count: number | null;
  extraction_method: string | null;
  extraction_debug_json: {
    page_count?: number;
    text_length?: number;
    extraction_method?: string;
    hex_count_in_text?: number;
    rgb_count_in_text?: number;
    font_metadata_count?: number;
    visual_colors_extracted?: number;
    is_image_based?: boolean;
    notes?: string[];
  } | null;
  created_at: string;
  updated_at: string;
}

export interface BrandIdentityProfileRead {
  id: string;
  brand_id: string;
  agency_id: string | null;
  source_document_id: string | null;
  status: "draft" | "ai_generated" | "reviewed" | "approved";
  summary: string | null;
  primary_colors: ColorEntry[] | null;
  secondary_colors: ColorEntry[] | null;
  typography: FontEntry[] | null;
  logo_rules: string[] | null;
  visual_style: { tags?: string[]; description?: string } | null;
  tone_of_voice: { summary?: string | null; tags?: string[]; preferred_words?: string[]; avoid_words?: string[]; use_words?: string[]; description?: string } | null;
  social_media_notes: string[] | null;
  do_rules: string[] | null;
  dont_rules: string[] | null;
  key_takeaways: string[] | null;
  confidence_score: number | null;
  is_active: boolean;
  reviewed_by_id: string | null;
  approved_by_id: string | null;
  reviewed_at: string | null;
  approved_at: string | null;
  approved_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface BrandIdentityOverview {
  profile: BrandIdentityProfileRead | null;
  documents: BrandIdentityDocumentRead[];
}

export interface BrandIdentityProfileUpdate {
  summary?: string | null;
  primary_colors?: ColorEntry[] | null;
  secondary_colors?: ColorEntry[] | null;
  typography?: FontEntry[] | null;
  logo_rules?: string[] | null;
  visual_style?: Record<string, unknown> | null;
  tone_of_voice?: Record<string, unknown> | null;
  social_media_notes?: string[] | null;
  do_rules?: string[] | null;
  dont_rules?: string[] | null;
  key_takeaways?: string[] | null;
  change_note?: string | null;
}

export interface BrandIdentityRevisionRead {
  id: string;
  profile_id: string;
  changed_by_id: string | null;
  changed_by_name: string | null;
  before_json: Record<string, unknown> | null;
  after_json: Record<string, unknown> | null;
  change_note: string | null;
  created_at: string;
}

export interface BrandDNASummary {
  profile_id: string | null;
  status: string | null;
  summary: string | null;
  primary_colors: ColorEntry[] | null;
  typography: FontEntry[] | null;
  tone_of_voice: Record<string, unknown> | null;
  key_takeaways: string[] | null;
  dont_rules: string[] | null;
  approved_by_name: string | null;
  approved_at: string | null;
}

export const brandIdentityApi = {
  getOverview: (brandId: string, agencyId: string, accessToken: string) =>
    request<BrandIdentityOverview>(
      `/api/v1/brands/${brandId}/identity`,
      { agencyId },
      accessToken
    ),

  uploadDocument: (brandId: string, agencyId: string, file: File, accessToken: string) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_BASE}/api/v1/brands/${brandId}/identity/documents`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Agency-ID": agencyId,
      },
      body: form,
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new ApiError(r.status, err?.detail || `HTTP ${r.status}`, err);
      }
      return r.json() as Promise<BrandIdentityDocumentRead>;
    });
  },

  listDocuments: (brandId: string, agencyId: string, accessToken: string) =>
    request<BrandIdentityDocumentRead[]>(
      `/api/v1/brands/${brandId}/identity/documents`,
      { agencyId },
      accessToken
    ),

  analyzeDocument: (brandId: string, documentId: string, agencyId: string, accessToken: string) =>
    request<BrandIdentityDocumentRead>(
      `/api/v1/brands/${brandId}/identity/documents/${documentId}/analyze`,
      { method: "POST", agencyId },
      accessToken
    ),

  updateProfile: (brandId: string, agencyId: string, data: BrandIdentityProfileUpdate, accessToken: string) =>
    request<BrandIdentityProfileRead>(
      `/api/v1/brands/${brandId}/identity/profile`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  approveProfile: (brandId: string, agencyId: string, accessToken: string) =>
    request<BrandIdentityProfileRead>(
      `/api/v1/brands/${brandId}/identity/profile/approve`,
      { method: "POST", agencyId },
      accessToken
    ),

  listRevisions: (brandId: string, agencyId: string, accessToken: string) =>
    request<BrandIdentityRevisionRead[]>(
      `/api/v1/brands/${brandId}/identity/revisions`,
      { agencyId },
      accessToken
    ),

  getDNASummary: (brandId: string, agencyId: string, accessToken: string) =>
    request<BrandDNASummary>(
      `/api/v1/brands/${brandId}/identity/dna-summary`,
      { agencyId },
      accessToken
    ),
};

export const brandPortalIdentityApi = {
  getOverview: (accessToken: string) =>
    request<BrandIdentityOverview>("/api/v1/brand-portal/identity", {}, accessToken),

  listDocuments: (accessToken: string) =>
    request<BrandIdentityDocumentRead[]>("/api/v1/brand-portal/identity/documents", {}, accessToken),

  uploadDocument: (file: File, accessToken: string) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_BASE}/api/v1/brand-portal/identity/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: form,
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new ApiError(r.status, err?.detail || `HTTP ${r.status}`, err);
      }
      return r.json() as Promise<BrandIdentityDocumentRead>;
    });
  },

  updateProfile: (data: BrandIdentityProfileUpdate, accessToken: string) =>
    request<BrandIdentityProfileRead>(
      "/api/v1/brand-portal/identity/profile",
      { method: "PATCH", body: data },
      accessToken
    ),

  getDNASummary: (accessToken: string) =>
    request<BrandDNASummary>("/api/v1/brand-portal/identity/dna-summary", {}, accessToken),
};

// ── Time tracking types ───────────────────────────────────────────────────────

export type TimeEntryCategory =
  | "design"
  | "copywriting"
  | "social_media"
  | "client_meeting"
  | "internal_meeting"
  | "revision"
  | "research"
  | "reporting"
  | "project_management"
  | "other";

export interface TimeEntryRead {
  id: string;
  agency_id: string;
  brand_id: string | null;
  brief_id: string | null;
  deliverable_id: string | null;
  task_id: string | null;
  user_id: string;
  category: TimeEntryCategory;
  description: string | null;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  billable: boolean;
  source: "timer" | "manual";
  locked: boolean;
  locked_by_id: string | null;
  locked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ActiveTimerRead {
  id: string;
  brief_id: string | null;
  brand_id: string | null;
  deliverable_id: string | null;
  task_id: string | null;
  category: TimeEntryCategory;
  description: string | null;
  billable: boolean;
  started_at: string;
}

export interface TimeEntryCreateResult {
  entry: TimeEntryRead;
  overlap_warning: boolean;
}

export interface TimeEntryStartPayload {
  brief_id?: string | null;
  brand_id?: string | null;
  deliverable_id?: string | null;
  task_id?: string | null;
  category: TimeEntryCategory;
  description?: string | null;
  billable?: boolean;
}

export interface TimeEntryStopPayload {
  category?: TimeEntryCategory;
  description?: string | null;
  billable?: boolean;
}

export interface TimeEntryManualCreatePayload {
  brief_id?: string | null;
  brand_id?: string | null;
  deliverable_id?: string | null;
  task_id?: string | null;
  category: TimeEntryCategory;
  description?: string | null;
  started_at: string;
  ended_at: string;
  billable?: boolean;
  confirm_future?: boolean;
}

export interface TimeEntryUpdatePayload {
  category?: TimeEntryCategory;
  description?: string | null;
  billable?: boolean;
}

export interface CategoryBreakdown {
  category: TimeEntryCategory;
  hours: number;
  entry_count: number;
}

export interface BriefTimeSummary {
  brief_id: string;
  estimated_hours: number | null;
  estimated_hours_by_category: Record<string, number> | null;
  actual_hours: number;
  remaining_hours: number | null;
  variance_hours: number | null;
  is_over_estimate: boolean;
  entry_count: number;
  category_breakdown: CategoryBreakdown[];
}

export interface BrandTimeSummary {
  brand_id: string;
  total_hours: number;
  billable_hours: number;
  non_billable_hours: number;
  brief_count: number;
  entry_count: number;
  category_breakdown: CategoryBreakdown[];
}

export interface UserTimeSummary {
  user_id: string;
  user_name: string;
  total_hours: number;
  billable_hours: number;
  entry_count: number;
}

export interface WeeklyTimesheetResponse {
  user_id: string;
  start_date: string;
  end_date: string;
  entries: TimeEntryRead[];
  total_hours: number;
  billable_hours: number;
  by_day: Record<string, number>;
}

export interface TeamTimeReportResponse {
  start_date: string;
  end_date: string;
  users: UserTimeSummary[];
  total_hours: number;
  billable_hours: number;
}

export interface MissingTimesheetEntry {
  user_id: string;
  user_name: string;
  missing_date: string;
}

export interface MissingTimesheetResponse {
  start_date: string;
  end_date: string;
  missing: MissingTimesheetEntry[];
}

// ── Time entry API ─────────────────────────────────────────────────────────────

export const timeEntryApi = {
  start: (data: TimeEntryStartPayload, agencyId: string, accessToken: string) =>
    request<TimeEntryRead>(
      "/api/v1/time-entries/start",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  getActive: (agencyId: string, accessToken: string) =>
    request<ActiveTimerRead | null>("/api/v1/time-entries/active", { agencyId }, accessToken),

  stop: (entryId: string, data: TimeEntryStopPayload, agencyId: string, accessToken: string) =>
    request<TimeEntryCreateResult>(
      `/api/v1/time-entries/${entryId}/stop`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  createManual: (data: TimeEntryManualCreatePayload, agencyId: string, accessToken: string) =>
    request<TimeEntryCreateResult>(
      "/api/v1/time-entries",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  get: (entryId: string, agencyId: string, accessToken: string) =>
    request<TimeEntryRead>(`/api/v1/time-entries/${entryId}`, { agencyId }, accessToken),

  update: (
    entryId: string,
    data: TimeEntryUpdatePayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<TimeEntryRead>(
      `/api/v1/time-entries/${entryId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  remove: (entryId: string, agencyId: string, accessToken: string) =>
    request<void>(`/api/v1/time-entries/${entryId}`, { method: "DELETE", agencyId }, accessToken),

  lock: (entryId: string, agencyId: string, accessToken: string) =>
    request<TimeEntryRead>(
      `/api/v1/time-entries/${entryId}/lock`,
      { method: "POST", agencyId },
      accessToken
    ),

  getBriefSummary: (briefId: string, agencyId: string, accessToken: string) =>
    request<BriefTimeSummary>(
      `/api/v1/briefs/${briefId}/time-summary`,
      { agencyId },
      accessToken
    ),
};

// ── Time report API ────────────────────────────────────────────────────────────

export const timeReportApi = {
  getWeekly: (
    agencyId: string,
    accessToken: string,
    params?: { user_id?: string; start_date?: string; end_date?: string }
  ) => {
    const qs = new URLSearchParams();
    if (params?.user_id) qs.set("user_id", params.user_id);
    if (params?.start_date) qs.set("start_date", params.start_date);
    if (params?.end_date) qs.set("end_date", params.end_date);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<WeeklyTimesheetResponse>(
      `/api/v1/time-reports/weekly${query}`,
      { agencyId },
      accessToken
    );
  },

  getTeam: (
    agencyId: string,
    accessToken: string,
    params?: { start_date?: string; end_date?: string }
  ) => {
    const qs = new URLSearchParams();
    if (params?.start_date) qs.set("start_date", params.start_date);
    if (params?.end_date) qs.set("end_date", params.end_date);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<TeamTimeReportResponse>(
      `/api/v1/time-reports/team${query}`,
      { agencyId },
      accessToken
    );
  },

  getByBrand: (
    brandId: string,
    agencyId: string,
    accessToken: string,
    params?: { start_date?: string; end_date?: string }
  ) => {
    const qs = new URLSearchParams({ brand_id: brandId });
    if (params?.start_date) qs.set("start_date", params.start_date);
    if (params?.end_date) qs.set("end_date", params.end_date);
    return request<BrandTimeSummary>(
      `/api/v1/time-reports/by-brand?${qs.toString()}`,
      { agencyId },
      accessToken
    );
  },

  getByBrief: (briefId: string, agencyId: string, accessToken: string) =>
    request<BriefTimeSummary>(
      `/api/v1/time-reports/by-brief?brief_id=${briefId}`,
      { agencyId },
      accessToken
    ),

  /** Single-brief estimate/actual/remaining/variance — same computation as
   * getByBrief but reachable to any workspace member with brief access
   * (not gated behind TIME_ENTRY_VIEW_TEAM), used for the brief-detail
   * header badge. */
  getBriefSummary: (briefId: string, agencyId: string, accessToken: string) =>
    request<BriefTimeSummary>(
      `/api/v1/briefs/${briefId}/time-summary`,
      { agencyId },
      accessToken
    ),

  getMissing: (
    agencyId: string,
    accessToken: string,
    params?: { start_date?: string; end_date?: string }
  ) => {
    const qs = new URLSearchParams();
    if (params?.start_date) qs.set("start_date", params.start_date);
    if (params?.end_date) qs.set("end_date", params.end_date);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<MissingTimesheetResponse>(
      `/api/v1/time-reports/missing${query}`,
      { agencyId },
      accessToken
    );
  },

  exportCsvUrl: (
    agencyId: string,
    params?: { start_date?: string; end_date?: string }
  ) => {
    const qs = new URLSearchParams();
    if (params?.start_date) qs.set("start_date", params.start_date);
    if (params?.end_date) qs.set("end_date", params.end_date);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return `${API_BASE}/api/v1/time-reports/export.csv${query}`;
  },

  exportCsv: async (
    agencyId: string,
    accessToken: string,
    params?: { start_date?: string; end_date?: string }
  ): Promise<Blob> => {
    const qs = new URLSearchParams();
    if (params?.start_date) qs.set("start_date", params.start_date);
    if (params?.end_date) qs.set("end_date", params.end_date);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    const response = await fetch(`${API_BASE}/api/v1/time-reports/export.csv${query}`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Agency-ID": agencyId,
      },
      credentials: "include",
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new ApiError(response.status, err?.detail || `HTTP ${response.status}`, err);
    }
    return response.blob();
  },
};

// ── Capacity/resource-planning types ────────────────────────────────────────

export type CapacityExceptionTypeValue = "reduced" | "increased" | "closure";
export type TimeOffTypeValue = "vacation" | "sick" | "holiday" | "unpaid" | "other";
export type TimeOffStatusValue = "requested" | "approved" | "rejected";
export type WorkAllocationSourceValue = "manual" | "auto_task" | "auto_brief";

export interface WorkScheduleDayRead {
  id: string;
  weekday: number;
  is_working_day: boolean;
  capacity_minutes: number;
}

export interface WorkScheduleDayPayload {
  weekday: number;
  is_working_day: boolean;
  capacity_minutes: number;
}

export interface WorkScheduleRead {
  id: string;
  agency_id: string;
  user_id: string;
  timezone: string;
  effective_from: string | null;
  days: WorkScheduleDayRead[];
  created_at: string;
  updated_at: string;
}

export interface WorkScheduleUpsertPayload {
  user_id: string;
  timezone: string;
  effective_from?: string | null;
  days: WorkScheduleDayPayload[];
}

export interface CapacityExceptionRead {
  id: string;
  agency_id: string;
  user_id: string;
  date: string;
  capacity_minutes: number;
  reason: string | null;
  exception_type: CapacityExceptionTypeValue;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CapacityExceptionCreatePayload {
  user_id: string;
  date: string;
  capacity_minutes: number;
  reason?: string | null;
  exception_type: CapacityExceptionTypeValue;
}

export interface TimeOffRead {
  id: string;
  agency_id: string;
  user_id: string;
  start_at: string;
  end_at: string;
  all_day: boolean;
  type: TimeOffTypeValue;
  status: TimeOffStatusValue;
  notes: string | null;
  approved_by_id: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimeOffCreatePayload {
  user_id: string;
  start_at: string;
  end_at: string;
  all_day?: boolean;
  type?: TimeOffTypeValue;
  notes?: string | null;
}

export interface TimeOffRejectPayload {
  notes?: string | null;
}

export interface TimeOffSaveResult {
  time_off: TimeOffRead;
  allocation_warning: boolean;
}

export interface WorkAllocationRead {
  id: string;
  agency_id: string;
  brand_id: string | null;
  brief_id: string | null;
  task_id: string | null;
  deliverable_id: string | null;
  user_id: string;
  category: TimeEntryCategory | null;
  start_date: string;
  end_date: string;
  allocated_minutes: number;
  allocation_source: WorkAllocationSourceValue;
  locked: boolean;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkAllocationCreatePayload {
  user_id: string;
  brand_id?: string | null;
  brief_id?: string | null;
  task_id?: string | null;
  deliverable_id?: string | null;
  category?: TimeEntryCategory | null;
  start_date: string;
  end_date: string;
  allocated_minutes: number;
  allocation_source?: WorkAllocationSourceValue;
  locked?: boolean;
}

export interface WorkAllocationUpdatePayload {
  category?: TimeEntryCategory | null;
  start_date?: string;
  end_date?: string;
  allocated_minutes?: number;
  locked?: boolean;
}

export interface WorkAllocationSaveResult {
  allocation: WorkAllocationRead;
  over_capacity_warning: boolean;
}

export interface UserCapacityReport {
  user_id: string;
  start_date: string;
  end_date: string;
  net_capacity_minutes: number;
  planned_minutes: number;
  actual_minutes: number;
  open_timer_minutes: number;
  planned_utilization_pct: number;
  actual_utilization_pct: number;
  planned_status: string;
  actual_status: string;
  capacity_status_reason: string;
}

export interface TeamCapacityMember extends UserCapacityReport {
  user_name: string;
}

export interface TeamCapacityReport {
  start_date: string;
  end_date: string;
  members: TeamCapacityMember[];
}

export interface BrandCapacityUserShare {
  user_id: string;
  user_name: string;
  planned_minutes: number;
}

export interface BrandCapacityReport {
  brand_id: string;
  start_date: string;
  end_date: string;
  planned_minutes: number;
  unassigned_minutes: number;
  actual_minutes: number;
  by_user: BrandCapacityUserShare[];
}

export interface UnassignedWorkItem {
  brief_id: string;
  brief_title: string;
  task_id: string | null;
  task_title: string | null;
  minutes: number;
  has_estimate: boolean;
}

export interface UnassignedWorkReport {
  start_date: string;
  end_date: string;
  items: UnassignedWorkItem[];
  total_minutes: number;
}

interface CapacityDateRangeParams {
  start_date?: string;
  end_date?: string;
}

function buildDateRangeQuery(params?: CapacityDateRangeParams): string {
  const qs = new URLSearchParams();
  if (params?.start_date) qs.set("start_date", params.start_date);
  if (params?.end_date) qs.set("end_date", params.end_date);
  const query = qs.toString();
  return query ? `?${query}` : "";
}

// ── Capacity API ────────────────────────────────────────────────────────────

export const capacityApi = {
  getSchedule: (userId: string, agencyId: string, accessToken: string) =>
    request<WorkScheduleRead>(`/api/v1/capacity/schedules/${userId}`, { agencyId }, accessToken),

  upsertSchedule: (
    userId: string,
    data: WorkScheduleUpsertPayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<WorkScheduleRead>(
      `/api/v1/capacity/schedules/${userId}`,
      { method: "PUT", body: data, agencyId },
      accessToken
    ),

  listExceptions: (
    userId: string,
    agencyId: string,
    accessToken: string,
    params?: { start?: string; end?: string }
  ) => {
    const qs = new URLSearchParams({ user_id: userId });
    if (params?.start) qs.set("start", params.start);
    if (params?.end) qs.set("end", params.end);
    return request<CapacityExceptionRead[]>(
      `/api/v1/capacity/exceptions?${qs.toString()}`,
      { agencyId },
      accessToken
    );
  },

  createException: (data: CapacityExceptionCreatePayload, agencyId: string, accessToken: string) =>
    request<CapacityExceptionRead>(
      "/api/v1/capacity/exceptions",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  deleteException: (exceptionId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/capacity/exceptions/${exceptionId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  listTimeOff: (
    userId: string,
    agencyId: string,
    accessToken: string,
    params?: { start?: string; end?: string }
  ) => {
    const qs = new URLSearchParams({ user_id: userId });
    if (params?.start) qs.set("start", params.start);
    if (params?.end) qs.set("end", params.end);
    return request<TimeOffRead[]>(
      `/api/v1/capacity/time-off?${qs.toString()}`,
      { agencyId },
      accessToken
    );
  },

  requestTimeOff: (data: TimeOffCreatePayload, agencyId: string, accessToken: string) =>
    request<TimeOffSaveResult>(
      "/api/v1/capacity/time-off",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  approveTimeOff: (timeOffId: string, agencyId: string, accessToken: string) =>
    request<TimeOffSaveResult>(
      `/api/v1/capacity/time-off/${timeOffId}/approve`,
      { method: "PATCH", agencyId },
      accessToken
    ),

  rejectTimeOff: (
    timeOffId: string,
    data: TimeOffRejectPayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<TimeOffRead>(
      `/api/v1/capacity/time-off/${timeOffId}/reject`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  listAllocations: (
    userId: string,
    agencyId: string,
    accessToken: string,
    params?: { start?: string; end?: string }
  ) => {
    const qs = new URLSearchParams({ user_id: userId });
    if (params?.start) qs.set("start", params.start);
    if (params?.end) qs.set("end", params.end);
    return request<WorkAllocationRead[]>(
      `/api/v1/capacity/allocations?${qs.toString()}`,
      { agencyId },
      accessToken
    );
  },

  createAllocation: (data: WorkAllocationCreatePayload, agencyId: string, accessToken: string) =>
    request<WorkAllocationSaveResult>(
      "/api/v1/capacity/allocations",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  updateAllocation: (
    allocationId: string,
    data: WorkAllocationUpdatePayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<WorkAllocationSaveResult>(
      `/api/v1/capacity/allocations/${allocationId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  deleteAllocation: (allocationId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/capacity/allocations/${allocationId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  getTeamReport: (agencyId: string, accessToken: string, params?: CapacityDateRangeParams) =>
    request<TeamCapacityReport>(
      `/api/v1/capacity/report/team${buildDateRangeQuery(params)}`,
      { agencyId },
      accessToken
    ),

  getUserReport: (
    userId: string,
    agencyId: string,
    accessToken: string,
    params?: CapacityDateRangeParams
  ) =>
    request<UserCapacityReport>(
      `/api/v1/capacity/report/user/${userId}${buildDateRangeQuery(params)}`,
      { agencyId },
      accessToken
    ),

  getBrandReport: (
    brandId: string,
    agencyId: string,
    accessToken: string,
    params?: CapacityDateRangeParams
  ) =>
    request<BrandCapacityReport>(
      `/api/v1/capacity/report/brand/${brandId}${buildDateRangeQuery(params)}`,
      { agencyId },
      accessToken
    ),

  getUnassignedReport: (agencyId: string, accessToken: string, params?: CapacityDateRangeParams) =>
    request<UnassignedWorkReport>(
      `/api/v1/capacity/report/unassigned${buildDateRangeQuery(params)}`,
      { agencyId },
      accessToken
    ),
};

// ── Finance: commercial terms + cost rates ─────────────────────────────────
// Types mirror apps/backend/app/schemas/commercial_terms.py and
// apps/backend/app/schemas/member_cost_rate.py field-for-field. Money is
// always integer cents + a paired ISO-4217 `currency` string (plan §2) —
// the UI layer (lib/finance.ts) is responsible for whole-unit conversion,
// never this file.

export type CommercialTermsBillingModelValue =
  | "hourly"
  | "fixed_fee"
  | "retainer"
  | "per_item"
  | "hybrid";

export interface CommercialTermsRead {
  id: string;
  agency_id: string;
  brand_id: string;
  billing_model: CommercialTermsBillingModelValue;
  currency: string;
  hourly_rate_cents: number | null;
  fixed_fee_cents: number | null;
  retainer_amount_cents: number | null;
  retainer_included_minutes: number | null;
  overage_rate_cents: number | null;
  per_item_rate_cents: number | null;
  payment_terms_days: number;
  tax_rate_bps: number;
  discount_rate_bps: number | null;
  billing_contact_name: string | null;
  billing_contact_email: string | null;
  billing_address: Record<string, unknown> | null;
  tax_office: string | null;
  tax_number: string | null;
  valid_from: string;
  valid_until: string | null;
  active: boolean;
  created_by_id: string | null;
  updated_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CommercialTermsCreatePayload {
  brand_id: string;
  billing_model: CommercialTermsBillingModelValue;
  currency: string;
  hourly_rate_cents?: number | null;
  fixed_fee_cents?: number | null;
  retainer_amount_cents?: number | null;
  retainer_included_minutes?: number | null;
  overage_rate_cents?: number | null;
  per_item_rate_cents?: number | null;
  payment_terms_days?: number;
  tax_rate_bps?: number;
  discount_rate_bps?: number | null;
  billing_contact_name?: string | null;
  billing_contact_email?: string | null;
  billing_address?: Record<string, unknown> | null;
  tax_office?: string | null;
  tax_number?: string | null;
  valid_from: string;
  valid_until?: string | null;
}

export interface CommercialTermsUpdatePayload {
  billing_model?: CommercialTermsBillingModelValue;
  currency?: string;
  hourly_rate_cents?: number | null;
  fixed_fee_cents?: number | null;
  retainer_amount_cents?: number | null;
  retainer_included_minutes?: number | null;
  overage_rate_cents?: number | null;
  per_item_rate_cents?: number | null;
  payment_terms_days?: number;
  tax_rate_bps?: number;
  discount_rate_bps?: number | null;
  billing_contact_name?: string | null;
  billing_contact_email?: string | null;
  billing_address?: Record<string, unknown> | null;
  tax_office?: string | null;
  tax_number?: string | null;
  valid_until?: string | null;
}

export interface MemberCostRateRead {
  id: string;
  agency_id: string;
  user_id: string | null;
  role: string | null;
  currency: string;
  hourly_cost_cents: number;
  valid_from: string;
  valid_until: string | null;
  active: boolean;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
}

/** Exactly one of `user_id`/`role` must be set (never both, never neither)
 * — mirrors the `MemberCostRateCreate` model-validator server-side. */
export interface MemberCostRateCreatePayload {
  user_id?: string | null;
  role?: string | null;
  currency: string;
  hourly_cost_cents: number;
  valid_from: string;
  valid_until?: string | null;
}

export interface MemberCostRateUpdatePayload {
  currency?: string;
  hourly_cost_cents?: number;
  valid_until?: string | null;
}

// ── Finance: billable time + client invoicing + retainers (Phase 4) ────────
// Types mirror apps/backend/app/schemas/client_invoice.py field-for-field.
// `ClientInvoiceLineRead`/`ClientInvoiceRead` deliberately omit
// `billing_rate_snapshot_cents`/`cost_rate_snapshot_cents` — the backend
// response shape never serializes them (internal-margin data never leaves
// the service layer), so there is nothing to type here either.

export type ClientInvoiceStatusValue =
  | "draft"
  | "pending_approval"
  | "approved"
  | "sending"
  | "sent"
  | "partially_paid"
  | "paid"
  | "overdue"
  | "cancelled"
  | "failed";

export type ClientInvoiceDocumentTypeValue = "draft_invoice" | "proforma";

export type ClientInvoiceLineSourceTypeValue =
  | "time_entry"
  | "fixed_fee"
  | "retainer"
  | "per_item"
  | "deliverable"
  | "manual";

export interface BillableTimeEntryRead {
  id: string;
  user_id: string;
  brief_id: string | null;
  category: TimeEntryCategory;
  description: string | null;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  locked: boolean;
}

/** Explicit field allowlist for a non-time-entry line — mirrors
 * `ManualInvoiceLineInput` server-side exactly (mass-assignment guard). */
export interface ManualInvoiceLineInputPayload {
  source_type?: ClientInvoiceLineSourceTypeValue;
  source_id?: string | null;
  description: string;
  quantity: number;
  unit: string;
  unit_price_cents: number;
  tax_rate_bps?: number;
  discount_cents?: number;
}

export interface ClientInvoiceDraftCreatePayload {
  brand_id: string;
  time_entry_ids?: string[];
  include_fixed_fee?: boolean;
  manual_lines?: ManualInvoiceLineInputPayload[];
  document_type?: ClientInvoiceDocumentTypeValue;
  issue_date?: string | null;
  due_date?: string | null;
  service_period_start?: string | null;
  service_period_end?: string | null;
  notes?: string | null;
}

/** Only draft-stage, non-money-integrity fields are patchable — line/total
 * changes always go through the lines endpoints (matches backend comment). */
export interface ClientInvoiceUpdatePayload {
  notes?: string | null;
  due_date?: string | null;
  document_type?: ClientInvoiceDocumentTypeValue | null;
  billing_contact_name?: string | null;
  billing_contact_email?: string | null;
}

export interface ClientInvoiceLineRead {
  id: string;
  invoice_id: string;
  source_type: ClientInvoiceLineSourceTypeValue;
  source_id: string | null;
  description: string;
  quantity: number;
  unit: string;
  unit_price_cents: number;
  tax_rate_bps: number;
  discount_cents: number;
  subtotal_cents: number;
  tax_cents: number;
  total_cents: number;
  service_period_start: string | null;
  service_period_end: string | null;
}

export interface ClientInvoiceRead {
  id: string;
  agency_id: string;
  brand_id: string;
  commercial_terms_id: string | null;
  invoice_number: string;
  external_invoice_id: string | null;
  document_type: ClientInvoiceDocumentTypeValue;
  issue_date: string;
  due_date: string;
  service_period_start: string | null;
  service_period_end: string | null;
  currency: string;
  subtotal_cents: number;
  discount_cents: number;
  tax_cents: number;
  total_cents: number;
  amount_paid_cents: number;
  status: ClientInvoiceStatusValue;
  notes: string | null;
  billing_contact_name: string | null;
  billing_contact_email: string | null;
  billing_address: Record<string, unknown> | null;
  tax_office: string | null;
  tax_number: string | null;
  sent_at: string | null;
  paid_at: string | null;
  cancelled_at: string | null;
  created_by_id: string | null;
  approved_by_id: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClientInvoiceWithLines extends ClientInvoiceRead {
  lines: ClientInvoiceLineRead[];
}

export interface RetainerSummary {
  period_start: string;
  period_end: string;
  included_minutes: number;
  rolled_over_minutes: number;
  used_minutes: number;
  remaining_minutes: number;
  overage_minutes: number;
  overage_cost_cents: number;
  currency: string;
}

// ── Finance: accounting connectors + payments (Phase 5) ────────────────────
// Types mirror apps/backend/app/schemas/accounting_connector.py and
// apps/backend/app/schemas/payment.py field-for-field. `AccountingConnectorRead`
// deliberately has no credential field — the backend never serializes
// `encrypted_credentials` (or any decrypted value) on any response, so
// there is nothing to type here either (plan §3/§12).

export type AccountingProviderValue =
  | "manual"
  | "quickbooks"
  | "xero"
  | "logo"
  | "parasut"
  | "mikro";

export type ConnectorStatusValue = "not_configured" | "connected" | "error";

export interface AccountingConnectorRead {
  id: string;
  agency_id: string;
  provider: AccountingProviderValue;
  status: ConnectorStatusValue;
  config: Record<string, unknown> | null;
  last_tested_at: string | null;
  last_sync_at: string | null;
  last_error: string | null;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
}

/** `credentials` is write-only — sent here, never returned by any read
 * schema. Only `provider: "manual"` is ever actually dispatched
 * server-side; every other value is a valid enum member (accepted by
 * schema validation, future UI/schema readiness per plan §10) but any real
 * operation on it raises `NotImplementedError` -> HTTP 501 at the
 * connector registry boundary — the frontend must never let a user select
 * one and believe it will work. */
export interface AccountingConnectorCreatePayload {
  provider: AccountingProviderValue;
  credentials?: Record<string, string> | null;
  config?: Record<string, unknown> | null;
}

export interface AccountingConnectorUpdatePayload {
  credentials?: Record<string, string> | null;
  config?: Record<string, unknown> | null;
}

export interface ConnectorSyncLogRead {
  id: string;
  connector_id: string;
  operation: string;
  related_invoice_id: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface ConnectorTestConnectionResult {
  connected: boolean;
  tested_at: string;
}

export interface ConnectorSyncInvoiceResult {
  external_invoice_id: string;
  status: string;
  sync_log: ConnectorSyncLogRead;
}

export type PaymentMethodValue = "bank_transfer" | "credit_card" | "cash" | "other";
export type PaymentSourceValue = "manual" | "connector";

export interface PaymentRead {
  id: string;
  agency_id: string;
  brand_id: string;
  invoice_id: string | null;
  amount_cents: number;
  currency: string;
  payment_method: PaymentMethodValue;
  paid_at: string;
  external_payment_id: string | null;
  source: PaymentSourceValue;
  notes: string | null;
  recorded_by_id: string | null;
  created_at: string;
}

/** `allow_overpayment` must be explicitly `true` to permit a payment past
 * the invoice's remaining balance — mirrors the backend's default-reject
 * behavior (plan §7 `PaymentService`); the frontend never sets this
 * implicitly. */
export interface PaymentCreatePayload {
  brand_id: string;
  invoice_id?: string | null;
  amount_cents: number;
  currency?: string;
  payment_method: PaymentMethodValue;
  paid_at: string;
  external_payment_id?: string | null;
  notes?: string | null;
  allow_overpayment?: boolean;
}

// ── Finance: profitability (Phase 6) ────────────────────────────────────────
// Types mirror the dataclasses returned by
// apps/backend/app/services/profitability_service.py (serialized via
// dataclasses.asdict() -> FastAPI's jsonable_encoder: `date` becomes an
// ISO "YYYY-MM-DD" string, `uuid.UUID` becomes a string). Every cost/margin
// field is nullable and gated by `cost_data_visible`/`margin_missing_reason`
// (brand/brief scope) or `cost_data_visible`/`cost_rate_missing` (agency
// scope) — the UI (lib/finance.ts's `costMissingInfo`) must render an
// explicit label whenever these signal missing/hidden data, never a bare 0
// or blank number (plan §7/§13, this phase's design requirement).

/** Mirrors `_COST_RATE_MISSING_REASON`/`_BILLING_RATE_MISSING_REASON` in
 * profitability_service.py exactly. */
export type MarginMissingReasonValue = "cost_rate_eksik" | "fiyatlandirma_eksik";

/** Mirrors the `RiskFlag.type` string constants in profitability_service.py.
 * Left as a loose string union (not a closed type) since the dataclass
 * field itself is plain `str` server-side — an unrecognized future value
 * must still render (falls back to the raw string), never crash. */
export type ProfitabilityRiskTypeValue =
  | "dusuk_kar_marji"
  | "negatif_kar_marji"
  | "retainer_asimi"
  | "yuksek_faturalanmamis_is"
  | "gecikmis_fatura"
  | string;

export interface ProfitabilityRiskFlag {
  type: ProfitabilityRiskTypeValue;
  message: string;
  brand_id: string | null;
  brief_id: string | null;
}

export interface AgencyCurrencyOverview {
  currency: string;
  invoiced_revenue_cents: number;
  unbilled_wip_cents: number;
  internal_cost_cents: number | null;
  gross_profit_cents: number | null;
  average_margin_pct: number | null;
  overdue_receivables_cents: number;
  cost_data_visible: boolean;
  cost_rate_missing: boolean;
}

export interface AgencyProfitabilityOverview {
  period_start: string | null;
  period_end: string | null;
  currencies: AgencyCurrencyOverview[];
  risk_flags: ProfitabilityRiskFlag[];
}

/** Distinct from `RetainerSummary` (Phase 4/5's `/finance/retainers/{id}`
 * response) — this is `ProfitabilityService`'s own `RetainerUtilization`
 * dataclass, which has no `rolled_over_minutes` field. Kept as a separate
 * type rather than reusing `RetainerSummary` so a field that doesn't exist
 * on this response can never be referenced by mistake. */
export interface ProfitabilityRetainerUtilization {
  period_start: string;
  period_end: string;
  included_minutes: number;
  used_minutes: number;
  remaining_minutes: number;
  overage_minutes: number;
  overage_cost_cents: number;
  currency: string;
}

export interface BrandCurrencyFinancials {
  currency: string;
  invoiced_revenue_cents: number;
  unbilled_wip_cents: number | null;
  unbilled_wip_hours: number;
  billing_rate_missing_for_wip: boolean;
  internal_cost_cents: number | null;
  gross_profit_cents: number | null;
  gross_margin_pct: number | null;
  cost_data_visible: boolean;
  margin_missing_reason: MarginMissingReasonValue | null;
}

export interface BrandProfitability {
  brand_id: string;
  brand_name: string;
  period_start: string | null;
  period_end: string | null;
  currencies: BrandCurrencyFinancials[];
  retainer: ProfitabilityRetainerUtilization | null;
  risk_flags: ProfitabilityRiskFlag[];
}

export interface BriefRealizedCurrency {
  currency: string;
  invoiced_hours: number;
  revenue_cents: number;
  cost_cents: number | null;
  gross_profit_cents: number | null;
  gross_margin_pct: number | null;
  cost_data_visible: boolean;
  margin_missing_reason: MarginMissingReasonValue | null;
}

export interface BriefEstimated {
  currency: string | null;
  estimated_hours: number | null;
  revenue_cents: number | null;
  cost_cents: number | null;
  gross_profit_cents: number | null;
  gross_margin_pct: number | null;
  billing_rate_missing: boolean;
  cost_data_visible: boolean;
  margin_missing_reason: MarginMissingReasonValue | null;
}

export interface BriefProfitability {
  brief_id: string;
  brief_title: string;
  brand_id: string | null;
  realized: BriefRealizedCurrency[];
  estimated: BriefEstimated | null;
  note: string;
}

export const financeApi = {
  listCommercialTerms: (brandId: string, agencyId: string, accessToken: string) =>
    request<CommercialTermsRead[]>(
      `/api/v1/finance/commercial-terms?brand_id=${brandId}`,
      { agencyId },
      accessToken
    ),

  createCommercialTerms: (
    data: CommercialTermsCreatePayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<CommercialTermsRead>(
      "/api/v1/finance/commercial-terms",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  updateCommercialTerms: (
    termsId: string,
    data: CommercialTermsUpdatePayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<CommercialTermsRead>(
      `/api/v1/finance/commercial-terms/${termsId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  /** Exactly one of `userId`/`role` must be provided — matches the
   * backend's `GET /finance/cost-rates?user_id=|role=` XOR requirement.
   * Owner-only: callers must gate invocation itself (not just rendering)
   * behind an Owner check, since even a 403 response is an information
   * leak about the endpoint's existence to a non-Owner UI session. */
  listCostRates: (
    target: { userId: string } | { role: string },
    agencyId: string,
    accessToken: string
  ) => {
    const qs =
      "userId" in target
        ? `user_id=${target.userId}`
        : `role=${target.role}`;
    return request<MemberCostRateRead[]>(
      `/api/v1/finance/cost-rates?${qs}`,
      { agencyId },
      accessToken
    );
  },

  createCostRate: (data: MemberCostRateCreatePayload, agencyId: string, accessToken: string) =>
    request<MemberCostRateRead>(
      "/api/v1/finance/cost-rates",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  updateCostRate: (
    rateId: string,
    data: MemberCostRateUpdatePayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<MemberCostRateRead>(
      `/api/v1/finance/cost-rates/${rateId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  // ── Billable time / client invoicing / retainers (Phase 4) ───────────────

  listBillableTime: (
    brandId: string,
    agencyId: string,
    accessToken: string,
    params?: { start?: string; end?: string }
  ) => {
    const qs = new URLSearchParams();
    qs.set("brand_id", brandId);
    if (params?.start) qs.set("start", params.start);
    if (params?.end) qs.set("end", params.end);
    return request<BillableTimeEntryRead[]>(
      `/api/v1/finance/billable-time?${qs.toString()}`,
      { agencyId },
      accessToken
    );
  },

  createInvoiceDraft: (
    data: ClientInvoiceDraftCreatePayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<ClientInvoiceWithLines>(
      "/api/v1/finance/invoices/draft",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  listInvoices: (
    agencyId: string,
    accessToken: string,
    params?: { brand_id?: string; status?: string; limit?: number; offset?: number }
  ) => {
    const qs = new URLSearchParams();
    if (params?.brand_id) qs.set("brand_id", params.brand_id);
    if (params?.status) qs.set("status", params.status);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<ClientInvoiceRead[]>(
      `/api/v1/finance/invoices${query}`,
      { agencyId },
      accessToken
    );
  },

  getInvoice: (invoiceId: string, agencyId: string, accessToken: string) =>
    request<ClientInvoiceWithLines>(
      `/api/v1/finance/invoices/${invoiceId}`,
      { agencyId },
      accessToken
    ),

  updateInvoice: (
    invoiceId: string,
    data: ClientInvoiceUpdatePayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<ClientInvoiceWithLines>(
      `/api/v1/finance/invoices/${invoiceId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  addInvoiceLine: (
    invoiceId: string,
    data: ManualInvoiceLineInputPayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<ClientInvoiceWithLines>(
      `/api/v1/finance/invoices/${invoiceId}/lines`,
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  removeInvoiceLine: (
    invoiceId: string,
    lineId: string,
    agencyId: string,
    accessToken: string
  ) =>
    request<ClientInvoiceWithLines>(
      `/api/v1/finance/invoices/${invoiceId}/lines/${lineId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  approveInvoice: (invoiceId: string, agencyId: string, accessToken: string) =>
    request<ClientInvoiceWithLines>(
      `/api/v1/finance/invoices/${invoiceId}/approve`,
      { method: "POST", agencyId },
      accessToken
    ),

  sendInvoice: (invoiceId: string, agencyId: string, accessToken: string) =>
    request<ClientInvoiceWithLines>(
      `/api/v1/finance/invoices/${invoiceId}/send`,
      { method: "POST", agencyId },
      accessToken
    ),

  voidInvoice: (invoiceId: string, agencyId: string, accessToken: string) =>
    request<ClientInvoiceWithLines>(
      `/api/v1/finance/invoices/${invoiceId}/void`,
      { method: "POST", agencyId },
      accessToken
    ),

  /** Blob-fetch pattern mirrors `timeReportApi.exportCsv` — auth header +
   * X-Agency-ID attached manually since these are not plain JSON GETs. */
  downloadInvoicePdf: async (
    invoiceId: string,
    agencyId: string,
    accessToken: string
  ): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/api/v1/finance/invoices/${invoiceId}/pdf`, {
      headers: { Authorization: `Bearer ${accessToken}`, "X-Agency-ID": agencyId },
      credentials: "include",
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new ApiError(response.status, err?.detail || `HTTP ${response.status}`, err);
    }
    return response.blob();
  },

  downloadInvoiceCsv: async (
    invoiceId: string,
    agencyId: string,
    accessToken: string
  ): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/api/v1/finance/invoices/${invoiceId}/csv`, {
      headers: { Authorization: `Bearer ${accessToken}`, "X-Agency-ID": agencyId },
      credentials: "include",
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new ApiError(response.status, err?.detail || `HTTP ${response.status}`, err);
    }
    return response.blob();
  },

  getRetainerSummary: (
    brandId: string,
    agencyId: string,
    accessToken: string,
    asOf?: string
  ) => {
    const qs = asOf ? `?as_of=${asOf}` : "";
    return request<RetainerSummary>(
      `/api/v1/finance/retainers/${brandId}${qs}`,
      { agencyId },
      accessToken
    );
  },

  // ── Accounting connectors (Phase 5) ─────────────────────────────────────

  listConnectors: (agencyId: string, accessToken: string) =>
    request<AccountingConnectorRead[]>("/api/v1/finance/connectors", { agencyId }, accessToken),

  createConnector: (
    data: AccountingConnectorCreatePayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<AccountingConnectorRead>(
      "/api/v1/finance/connectors",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  updateConnector: (
    connectorId: string,
    data: AccountingConnectorUpdatePayload,
    agencyId: string,
    accessToken: string
  ) =>
    request<AccountingConnectorRead>(
      `/api/v1/finance/connectors/${connectorId}`,
      { method: "PATCH", body: data, agencyId },
      accessToken
    ),

  deleteConnector: (connectorId: string, agencyId: string, accessToken: string) =>
    request<void>(
      `/api/v1/finance/connectors/${connectorId}`,
      { method: "DELETE", agencyId },
      accessToken
    ),

  testConnectorConnection: (connectorId: string, agencyId: string, accessToken: string) =>
    request<ConnectorTestConnectionResult>(
      `/api/v1/finance/connectors/${connectorId}/test-connection`,
      { method: "POST", agencyId },
      accessToken
    ),

  syncConnectorInvoice: (
    connectorId: string,
    invoiceId: string,
    agencyId: string,
    accessToken: string
  ) =>
    request<ConnectorSyncInvoiceResult>(
      `/api/v1/finance/connectors/${connectorId}/sync-invoice/${invoiceId}`,
      { method: "POST", agencyId },
      accessToken
    ),

  // ── Payments (Phase 5) ───────────────────────────────────────────────────

  listPayments: (
    agencyId: string,
    accessToken: string,
    params?: { brand_id?: string; invoice_id?: string; limit?: number; offset?: number }
  ) => {
    const qs = new URLSearchParams();
    if (params?.brand_id) qs.set("brand_id", params.brand_id);
    if (params?.invoice_id) qs.set("invoice_id", params.invoice_id);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaymentRead[]>(`/api/v1/finance/payments${query}`, { agencyId }, accessToken);
  },

  recordPayment: (data: PaymentCreatePayload, agencyId: string, accessToken: string) =>
    request<PaymentRead>(
      "/api/v1/finance/payments",
      { method: "POST", body: data, agencyId },
      accessToken
    ),

  // ── Profitability (Phase 6) ─────────────────────────────────────────────
  // `include_cost_data` is never a caller-supplied param — the backend
  // derives it server-side from whether the caller holds `COST_RATE_VIEW`
  // (plan §7/§8), so there is nothing for the frontend to pass here.

  getProfitabilityOverview: (
    agencyId: string,
    accessToken: string,
    params?: { start?: string; end?: string }
  ) => {
    const qs = new URLSearchParams();
    if (params?.start) qs.set("start", params.start);
    if (params?.end) qs.set("end", params.end);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<AgencyProfitabilityOverview>(
      `/api/v1/finance/profitability/overview${query}`,
      { agencyId },
      accessToken
    );
  },

  getBrandProfitability: (
    brandId: string,
    agencyId: string,
    accessToken: string,
    params?: { start?: string; end?: string; as_of?: string }
  ) => {
    const qs = new URLSearchParams();
    if (params?.start) qs.set("start", params.start);
    if (params?.end) qs.set("end", params.end);
    if (params?.as_of) qs.set("as_of", params.as_of);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<BrandProfitability>(
      `/api/v1/finance/profitability/brand/${brandId}${query}`,
      { agencyId },
      accessToken
    );
  },

  getBriefProfitability: (
    briefId: string,
    agencyId: string,
    accessToken: string,
    params?: { as_of?: string }
  ) => {
    const qs = params?.as_of ? `?as_of=${params.as_of}` : "";
    return request<BriefProfitability>(
      `/api/v1/finance/profitability/brief/${briefId}${qs}`,
      { agencyId },
      accessToken
    );
  },
};

// ── Onboarding types ─────────────────────────────────────────────────────────

export type OnboardingType = "agency_owner_admin" | "agency_member" | "brand_user";

export interface OnboardingStepRead {
  key: string;
  completed: boolean;
  kind: "action" | "view";
  skipped: boolean;
  first_seen_at: string | null;
  last_seen_at: string | null;
}

export interface OnboardingProgressRead {
  id: string;
  onboarding_type: OnboardingType;
  current_step: string | null;
  started_at: string;
  completed_at: string | null;
  dismissed_at: string | null;
  version: number;
  percent_complete: number;
  steps: OnboardingStepRead[];
}

export const onboardingApi = {
  getProgress: (agencyId: string, accessToken: string) =>
    request<OnboardingProgressRead>("/api/v1/onboarding/progress", { agencyId }, accessToken),

  dismiss: (agencyId: string, accessToken: string) =>
    request<OnboardingProgressRead>(
      "/api/v1/onboarding/progress/dismiss",
      { method: "POST", agencyId },
      accessToken
    ),

  resume: (agencyId: string, accessToken: string) =>
    request<OnboardingProgressRead>(
      "/api/v1/onboarding/progress/resume",
      { method: "POST", agencyId },
      accessToken
    ),

  markStepSeen: (stepKey: string, agencyId: string, accessToken: string) =>
    request<OnboardingProgressRead>(
      `/api/v1/onboarding/progress/step/${stepKey}/seen`,
      { method: "POST", agencyId },
      accessToken
    ),

  skipStep: (stepKey: string, agencyId: string, accessToken: string) =>
    request<OnboardingProgressRead>(
      `/api/v1/onboarding/progress/step/${stepKey}/skip`,
      { method: "POST", agencyId },
      accessToken
    ),
};

export const brandOnboardingApi = {
  getProgress: (accessToken: string) =>
    request<OnboardingProgressRead>("/api/v1/brand-portal/onboarding/progress", {}, accessToken),

  dismiss: (accessToken: string) =>
    request<OnboardingProgressRead>(
      "/api/v1/brand-portal/onboarding/progress/dismiss",
      { method: "POST" },
      accessToken
    ),

  resume: (accessToken: string) =>
    request<OnboardingProgressRead>(
      "/api/v1/brand-portal/onboarding/progress/resume",
      { method: "POST" },
      accessToken
    ),

  markStepSeen: (stepKey: string, accessToken: string) =>
    request<OnboardingProgressRead>(
      `/api/v1/brand-portal/onboarding/progress/step/${stepKey}/seen`,
      { method: "POST" },
      accessToken
    ),

  skipStep: (stepKey: string, accessToken: string) =>
    request<OnboardingProgressRead>(
      `/api/v1/brand-portal/onboarding/progress/step/${stepKey}/skip`,
      { method: "POST" },
      accessToken
    ),
};
