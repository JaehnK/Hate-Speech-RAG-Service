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

export interface ExportStatus {
  export_id: string;
  report_id: string;
  format: "html" | "xlsx";
  status: string;
  download_url: string | null;
}

export interface StoredJob {
  jobId: string;
  videoId: string;
  createdAt: string;
}
