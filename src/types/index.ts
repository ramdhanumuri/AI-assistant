export type AIModeId =
  | 'general'
  | 'research'
  | 'coding'
  | 'creative'
  | 'analysis'
  | 'vision'
  | 'voice';

export type AIState = 'idle' | 'listening' | 'thinking' | 'responding';

export interface AIMode {
  id: AIModeId;
  label: string;
  caption: string;
  description: string;
  aura: string; // rgb triples as "r g b"
  glyph: string; // short symbolic mark
}

/* ── Rich message content blocks ─────────────────────────────────── */

export interface TextBlock {
  kind: 'text';
  body: string;
}

export interface CodeBlock {
  kind: 'code';
  language: string;
  filename?: string;
  body: string;
}

export interface ListBlock {
  kind: 'list';
  ordered?: boolean;
  items: string[];
}

export interface TableBlock {
  kind: 'table';
  caption?: string;
  columns: string[];
  rows: string[][];
}

export interface InsightBlock {
  kind: 'insight';
  title: string;
  metric: string;
  delta?: string;
  detail: string;
}

export interface CardGridBlock {
  kind: 'cards';
  cards: { title: string; meta: string; body: string; tag?: string }[];
}

export interface FileBlock {
  kind: 'file';
  name: string;
  type: string;
  size: string;
  status: 'parsed' | 'indexed' | 'processing';
}

export interface SuggestionBlock {
  kind: 'suggestions';
  label: string;
  items: string[];
}

export interface TimelineBlock {
  kind: 'timeline';
  steps: { label: string; detail?: string; state: 'done' | 'active' | 'pending' }[];
}

export type ContentBlock =
  | TextBlock
  | CodeBlock
  | ListBlock
  | TableBlock
  | InsightBlock
  | CardGridBlock
  | FileBlock
  | SuggestionBlock
  | TimelineBlock;

/* ── Messages ────────────────────────────────────────────────────── */

export interface ToolTrace {
  id: string;
  name: string;
  detail: string;
  state: 'running' | 'done';
  durationMs?: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  createdAt: number;
  mode: AIModeId;
  blocks: ContentBlock[];
  voice?: boolean;
  reasoning?: string;
  traces?: ToolTrace[];
  tokens?: number;
}

export interface Conversation {
  id: string;
  title: string;
  preview: string;
  updatedAt: number;
  mode: AIModeId;
  project?: string;
  pinned?: boolean;
  messageCount: number;
}

export interface Project {
  id: string;
  name: string;
  brief: string;
  progress: number;
  threads: number;
  accent: string;
}

export interface KnowledgeSource {
  id: string;
  name: string;
  kind: 'document' | 'repository' | 'dataset' | 'feed';
  items: number;
  status: 'synced' | 'indexing' | 'paused';
  updated: string;
}

export interface ToolIntegration {
  id: string;
  name: string;
  category: string;
  connected: boolean;
  permission: string;
  calls: number;
}

export interface MemoryRecord {
  id: string;
  statement: string;
  scope: string;
  confidence: number;
  learned: string;
}

export interface UsagePoint {
  label: string;
  value: number;
  secondary: number;
}

export interface CommandAction {
  id: string;
  label: string;
  hint: string;
  group: 'Navigate' | 'Modes' | 'Conversations' | 'Projects' | 'Tools' | 'System';
  icon: string;
  keywords?: string;
  shortcut?: string;
}

export type ViewId =
  | 'home'
  | 'conversation'
  | 'voice'
  | 'dashboard'
  | 'knowledge'
  | 'tools'
  | 'memory'
  | 'projects';