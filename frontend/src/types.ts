export type JobStatus = "pending" | "running" | "succeeded" | "partial_success" | "failed";

export interface JobStep {
  step_key: string;
  status: string;
  attempt_count: number;
  started_at: string | null;
  finished_at: string | null;
  metrics: Record<string, unknown>;
  item_progress: {
    total: number;
    completed: number;
    succeeded: number;
    failed: number;
    percent: number;
  } | null;
  error: { code: string | null; message: string | null } | null;
}

export interface Job {
  job_id: string;
  youtube_video_id: string;
  status: JobStatus;
  progress: { percent: number; current_step: string | null };
  steps: JobStep[];
  summary: Record<string, number>;
  links: { report_api: string | null; report_page: string | null };
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface CreatedJob {
  job_id: string;
  youtube_video_id: string;
  status: JobStatus;
  status_url: string;
  created_at: string;
}

export interface AnalysisSummary {
  total: number;
  succeeded: number;
  failed: number;
  missing: number;
  hate_speech_count: number;
  category_distribution: Record<string, number>;
}

export interface Report {
  report_id: string;
  analysis_run_id: string;
  status: string;
  title: string;
  created_at: string;
  youtube_video_id: string;
  video: {
    title: string | null;
    channel_title: string | null;
    published_at: string | null;
    view_count: number | null;
    comment_count: number | null;
    thumbnail_url: string | null;
  };
  collection_summary: {
    comments_collected: number;
    replies_collected: number;
    transcript_available: boolean;
  };
  comment_analysis_summary: AnalysisSummary;
  script_analysis_summary: AnalysisSummary;
  network_summary: Record<string, unknown>;
  representative_comments: Array<{
    youtube_comment_id: string;
    text: string;
    like_count: number;
    categories: string[];
    reasoning: string | null;
  }>;
  failure_summary: Array<{
    step_key: string;
    status: string;
    error_code: string | null;
    message: string | null;
  }>;
  links: Record<string, string>;
}

export interface CommentNetworkNode {
  node_key: string;
  node_type: string;
  label: string | null;
  comment_count: number;
  hate_speech_count: number;
  hate_speech_ratio: number;
  metrics: Record<string, unknown>;
}

export interface CommentNetworkEdge {
  source_node_key: string;
  target_node_key: string;
  edge_type: string;
  weight: number;
  is_hate_speech: boolean | null;
}

export interface CommentNetwork {
  network_id: string;
  status: string;
  graph_type: string;
  directed: boolean;
  summary: Record<string, unknown>;
  nodes: CommentNetworkNode[];
  edges: CommentNetworkEdge[];
}

export interface ReportComment {
  comment_snapshot_id: string;
  youtube_comment_id: string;
  is_reply: boolean;
  parent_youtube_comment_id: string | null;
  author_display_name: string | null;
  author_channel_id: string | null;
  text_original: string | null;
  like_count: number | null;
  published_at: string | null;
  analysis: {
    status: string;
    is_hate_speech: boolean | null;
    categories: string[];
    reasoning: string | null;
  };
}

export interface ReportCommentPage {
  items: ReportComment[];
  total: number;
  next_cursor: number | null;
  has_more: boolean;
}

export interface ReportScriptSegment {
  segment_id: string;
  segment_index: number;
  start_seconds: number;
  end_seconds: number;
  text: string;
  analysis: {
    status: string;
    is_hate_speech: boolean | null;
    categories: string[] | null;
    target_group: string | null;
    hate_type: string | null;
    reasoning: string | null;
  };
}

export interface ReportScriptSegmentPage {
  items: ReportScriptSegment[];
  total: number;
  next_cursor: number | null;
  has_more: boolean;
}

export interface ExportStatus {
  export_id: string;
  report_id: string;
  format: "html" | "xlsx";
  status: string;
  download_url: string | null;
}

export interface AuthSession {
  user_id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  api_keys_registered: { anthropic: boolean; upstage: boolean };
}

export interface ApiKeySummary {
  provider: "anthropic" | "upstage";
  key_fingerprint: string;
  is_valid: boolean;
  last_validated_at: string | null;
}

export interface PublicReportSummary {
  report_id: string;
  youtube_video_id: string | null;
  status: string;
  created_at: string;
  title: string;
  channel_title: string | null;
  thumbnail_url: string | null;
  comments_collected: number;
  transcript_available: boolean;
  hate_speech_ratio: number;
  top_categories: string[];
}

export interface Page<T> {
  items: T[];
  total: number;
  next_cursor: number | null;
  has_more: boolean;
}
