export interface AdminUserSummary {
  id: string;
  email: string;
  display_name: string;
  email_verified: boolean;
  created_at: string;
}

export interface AdminOverview {
  generated_at: string;
  registered_users: number;
  recent_users: AdminUserSummary[];
  analyses: number;
  scans: {
    total: number;
    queued: number;
    running: number;
    succeeded: number;
    failed: number;
    model_versions: Record<string, Record<string, number>>;
  };
  feedback_total: number;
  feedback: Array<{ category: string; helpful: number; not_helpful: number }>;
  flagged_images: Array<{
    scan_id: string;
    image_id: string;
    status: string;
    model_version: string;
    error_code: string | null;
    quality_flags: string[];
    warning_codes: string[];
    created_at: string;
  }>;
  system_failures: Array<{
    id: string;
    source: 'scan' | 'job';
    category: string;
    status: string;
    occurred_at: string;
  }>;
  model_evaluation: {
    status: 'not_available' | 'available';
    accuracy: number | null;
    macro_f1: number | null;
    sample_count: number;
    message: string;
  };
}
