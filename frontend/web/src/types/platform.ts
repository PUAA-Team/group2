export interface QuotaMap {
  gpu_count: number;
  concurrent_jobs: number;
  storage_gib: number;
  [key: string]: number;
}

export interface AccessPolicy {
  actions: string[];
  quota: QuotaMap;
  role?: string;
}

export interface UserSummary {
  id: string;
  account: string;
  display_name: string;
  is_admin: boolean;
  active: boolean;
  group_id?: string | null;
  revision: number;
}

export interface SessionData {
  user: UserSummary;
  csrf_token: string;
  access: AccessPolicy;
}

export interface SetupState {
  initialized?: boolean;
  enabled?: boolean;
  invitations_enabled?: boolean;
  self_registration_enabled?: boolean;
  platform_name?: string;
}

export interface WorkspaceSummary {
  id: string;
  name: string;
  owner_id: string;
  revision: number;
  created_at?: string;
}

export interface ModalState {
  kind: string;
  item: Record<string, any>;
  workspaceId?: string;
}

export interface UiPreferences {
  navOpen: Record<string, boolean>;
  sidebarCollapsed: boolean;
  sidebarScroll: number;
  workspaceId: string;
  modal: ModalState | null;
  menuOpen: boolean;
}

export interface ApiEnvelope<T = any> {
  data: T;
  pagination?: {
    total: number;
    page: number;
    page_size: number;
  };
  request_id?: string;
  summary?: Record<string, any>;
}
