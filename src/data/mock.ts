import type {
  AIMode,
  AIModeId,
  CommandAction,
  Conversation,
  KnowledgeSource,
  MemoryRecord,
  Message,
  Project,
  ToolIntegration,
  UsagePoint,
} from '@/types';

export const AI_MODES: AIMode[] = [
  {
    id: 'general',
    label: 'General',
    caption: 'Balanced reasoning',
    description:
      'Everyday intelligence for questions, drafting, planning and synthesis.',
    aura: '110 168 255',
    glyph: '◍',
  },
  {
    id: 'research',
    label: 'Research',
    caption: 'Sources & synthesis',
    description:
      'Deep multi-source investigation with citations, timelines and confidence scoring.',
    aura: '150 190 255',
    glyph: '◎',
  },
  {
    id: 'coding',
    label: 'Coding',
    caption: 'Architecture & refactor',
    description:
      'Repository-aware engineering: design, implement, review and harden systems.',
    aura: '130 200 230',
    glyph: '⌘',
  },
  {
    id: 'creative',
    label: 'Creative',
    caption: 'Narrative & direction',
    description:
      'Editorial writing, brand voice, concept development and art direction.',
    aura: '216 195 154',
    glyph: '✦',
  },
  {
    id: 'analysis',
    label: 'Analysis',
    caption: 'Data & decisions',
    description:
      'Structured evaluation, modelling, trade-off matrices and decision memos.',
    aura: '170 210 200',
    glyph: '◈',
  },
  {
    id: 'vision',
    label: 'Vision',
    caption: 'Visual understanding',
    description:
      'Interpret documents, interfaces, diagrams and photographic context.',
    aura: '190 170 255',
    glyph: '◉',
  },
  {
    id: 'voice',
    label: 'Voice',
    caption: 'Live conversation',
    description:
      'Continuous spoken dialogue with interruption handling and live transcription.',
    aura: '140 220 210',
    glyph: '◌',
  },
];

export const MODE_BY_ID: Record<AIModeId, AIMode> = AI_MODES.reduce(
  (acc, m) => ({ ...acc, [m.id]: m }),
  {} as Record<AIModeId, AIMode>,
);

/* ── Conversations ───────────────────────────────────────────────── */

const now = Date.now();
const min = 60_000;
const hr = 60 * min;
const day = 24 * hr;

export const CONVERSATIONS: Conversation[] = [
  {
    id: 'c-orbital',
    title: 'Orbital logistics margin model',
    preview:
      'Reframed the launch cadence assumption — recoverable margin improves by 14.2% under the revised window.',
    updatedAt: now - 24 * min,
    mode: 'analysis',
    project: 'Helios Program',
    pinned: true,
    messageCount: 42,
  },
  {
    id: 'c-atlas',
    title: 'Atlas design system migration',
    preview:
      'Generated the codemod plan for 340 legacy components with a staged rollout sequence.',
    updatedAt: now - 2 * hr,
    mode: 'coding',
    project: 'Atlas Platform',
    pinned: true,
    messageCount: 88,
  },
  {
    id: 'c-series-b',
    title: 'Series B narrative — investor long form',
    preview:
      'Tightened the opening to 84 words and removed three hedging clauses from the thesis.',
    updatedAt: now - 5 * hr,
    mode: 'creative',
    project: 'Capital Raise',
    messageCount: 31,
  },
  {
    id: 'c-supply',
    title: 'Supply chain exposure across APAC',
    preview:
      'Mapped 6 tier-2 dependencies against the new tariff schedule; two need dual-sourcing.',
    updatedAt: now - day,
    mode: 'research',
    project: 'Operations',
    messageCount: 57,
  },
  {
    id: 'c-board',
    title: 'Board pre-read — FY26 strategy',
    preview: 'Restructured into three decisions, each with a recommendation and a cost.',
    updatedAt: now - day - 3 * hr,
    mode: 'general',
    messageCount: 24,
  },
  {
    id: 'c-interface',
    title: 'Interface audit — onboarding funnel',
    preview: 'Identified 4 friction points in the activation path with annotated captures.',
    updatedAt: now - 2 * day,
    mode: 'vision',
    messageCount: 19,
  },
  {
    id: 'c-voice-notes',
    title: 'Voice notes — product review',
    preview: 'Spoken review transcribed and organised into 9 actionable items.',
    updatedAt: now - 3 * day,
    mode: 'voice',
    messageCount: 12,
  },
  {
    id: 'c-lattice',
    title: 'Lattice inference cost curve',
    preview: 'Quantised deployment path cuts per-request cost by 61% at parity quality.',
    updatedAt: now - 4 * day,
    mode: 'coding',
    project: 'Atlas Platform',
    messageCount: 63,
  },
];

/* ── Projects, knowledge, tools, memory ──────────────────────────── */

export const PROJECTS: Project[] = [
  {
    id: 'p-helios',
    name: 'Helios Program',
    brief: 'Autonomous orbital logistics planning and margin optimisation.',
    progress: 0.72,
    threads: 18,
    accent: '216 195 154',
  },
  {
    id: 'p-atlas',
    name: 'Atlas Platform',
    brief: 'Core product re-architecture and design system consolidation.',
    progress: 0.46,
    threads: 31,
    accent: '110 168 255',
  },
  {
    id: 'p-capital',
    name: 'Capital Raise',
    brief: 'Series B materials, diligence room and investor narrative.',
    progress: 0.88,
    threads: 12,
    accent: '150 190 255',
  },
  {
    id: 'p-ops',
    name: 'Operations',
    brief: 'Supply resilience, vendor risk and regional compliance mapping.',
    progress: 0.35,
    threads: 9,
    accent: '170 210 200',
  },
];

export const KNOWLEDGE_SOURCES: KnowledgeSource[] = [
  {
    id: 'k-corp',
    name: 'Corporate Archive 2019–2026',
    kind: 'document',
    items: 12480,
    status: 'synced',
    updated: '4 min ago',
  },
  {
    id: 'k-atlas',
    name: 'atlas-platform (monorepo)',
    kind: 'repository',
    items: 3842,
    status: 'indexing',
    updated: 'now',
  },
  {
    id: 'k-market',
    name: 'Market Intelligence Feed',
    kind: 'feed',
    items: 912,
    status: 'synced',
    updated: '22 min ago',
  },
  {
    id: 'k-telemetry',
    name: 'Product Telemetry Warehouse',
    kind: 'dataset',
    items: 210650,
    status: 'synced',
    updated: '1 hr ago',
  },
  {
    id: 'k-legal',
    name: 'Contracts & Regulatory Corpus',
    kind: 'document',
    items: 2264,
    status: 'paused',
    updated: '3 days ago',
  },
];

export const TOOLS: ToolIntegration[] = [
  {
    id: 't-web',
    name: 'Live Web Retrieval',
    category: 'Research',
    connected: true,
    permission: 'Read',
    calls: 1840,
  },
  {
    id: 't-repo',
    name: 'Repository Index',
    category: 'Engineering',
    connected: true,
    permission: 'Read / Write',
    calls: 642,
  },
  {
    id: 't-sql',
    name: 'Warehouse Query',
    category: 'Data',
    connected: true,
    permission: 'Read',
    calls: 318,
  },
  {
    id: 't-chart',
    name: 'Chart Synthesis',
    category: 'Visualisation',
    connected: true,
    permission: 'Compute',
    calls: 205,
  },
  {
    id: 't-calendar',
    name: 'Calendar Bridge',
    category: 'Productivity',
    connected: false,
    permission: 'Read / Write',
    calls: 0,
  },
  {
    id: 't-mail',
    name: 'Correspondence Draft',
    category: 'Productivity',
    connected: true,
    permission: 'Draft only',
    calls: 96,
  },
  {
    id: 't-vision',
    name: 'Visual Parser',
    category: 'Vision',
    connected: true,
    permission: 'Compute',
    calls: 411,
  },
];

export const MEMORY: MemoryRecord[] = [
  {
    id: 'm-1',
    statement:
      'Prefers decisions framed as a recommendation with an explicit cost and a reversal path.',
    scope: 'Communication',
    confidence: 0.96,
    learned: '6 weeks ago',
  },
  {
    id: 'm-2',
    statement:
      'Operating across the Helios and Atlas workstreams; Helios takes priority before Thursday board cycles.',
    scope: 'Context',
    confidence: 0.91,
    learned: '3 weeks ago',
  },
  {
    id: 'm-3',
    statement:
      'Writes in British spelling for external documents, American for internal engineering notes.',
    scope: 'Style',
    confidence: 0.88,
    learned: '2 months ago',
  },
  {
    id: 'm-4',
    statement:
      'Distrusts aggregated metrics without a stated denominator; always show the base.',
    scope: 'Analysis',
    confidence: 0.94,
    learned: '5 weeks ago',
  },
  {
    id: 'm-5',
    statement:
      'Holds a standing review Thursday 09:00 UTC — long-form output should land the evening before.',
    scope: 'Schedule',
    confidence: 0.83,
    learned: '2 weeks ago',
  },
];

export const USAGE_SERIES: UsagePoint[] = [
  { label: 'Mon', value: 128, secondary: 42 },
  { label: 'Tue', value: 186, secondary: 61 },
  { label: 'Wed', value: 242, secondary: 88 },
  { label: 'Thu', value: 205, secondary: 74 },
  { label: 'Fri', value: 268, secondary: 103 },
  { label: 'Sat', value: 96, secondary: 31 },
  { label: 'Sun', value: 74, secondary: 22 },
];

export const ACTIVITY_FEED = [
  {
    id: 'a-1',
    at: '2 min ago',
    label: 'Indexed 412 files from atlas-platform',
    mode: 'coding' as AIModeId,
  },
  {
    id: 'a-2',
    at: '18 min ago',
    label: 'Completed margin sensitivity sweep (8 scenarios)',
    mode: 'analysis' as AIModeId,
  },
  {
    id: 'a-3',
    at: '46 min ago',
    label: 'Retrieved 23 sources on APAC tariff amendments',
    mode: 'research' as AIModeId,
  },
  {
    id: 'a-4',
    at: '2 hr ago',
    label: 'Drafted investor long-form — v4',
    mode: 'creative' as AIModeId,
  },
  {
    id: 'a-5',
    at: '4 hr ago',
    label: 'Parsed 6 interface captures from onboarding audit',
    mode: 'vision' as AIModeId,
  },
];

/* ── Seeded conversation transcript ──────────────────────────────── */

export const SEED_MESSAGES: Message[] = [
  {
    id: 'm-seed-u1',
    role: 'user',
    createdAt: now - 12 * min,
    mode: 'analysis',
    blocks: [
      {
        kind: 'text',
        body: 'Model the margin impact if we move the Helios launch cadence from 9 to 7 days. Show me where it breaks first.',
      },
    ],
  },
  {
    id: 'm-seed-a1',
    role: 'assistant',
    createdAt: now - 11 * min,
    mode: 'analysis',
    tokens: 847,
    reasoning:
      'Retrieved three cost baselines, isolated the fixed-facility term, then swept cadence 9→7 days in 0.5-day increments against the revised tariff schedule.',
    traces: [
      { id: 'tr-1', name: 'Warehouse Query', detail: 'helios_cost_baseline', state: 'done', durationMs: 1840 },
      { id: 'tr-2', name: 'Chart Synthesis', detail: 'cadence sensitivity sweep', state: 'done', durationMs: 2620 },
      { id: 'tr-3', name: 'Live Web Retrieval', detail: 'tariff schedule Q3 revision', state: 'done', durationMs: 1130 },
    ],
    blocks: [
      {
        kind: 'text',
        body: 'I ran the sweep across 8 cadence scenarios against the Q3 tariff revision. Recoverable margin rises to a peak at 7.5 days, then collapses — the binding constraint is not launch capacity, it is the tier-2 component buffer.',
      },
      {
        kind: 'insight',
        title: 'Optimal cadence',
        metric: '7.5 days',
        delta: '+14.2% margin',
        detail:
          'Peak recoverable margin of 31.8%. Beyond 7.5 days the buffer depletes faster than replenishment clears customs.',
      },
      {
        kind: 'table',
        caption: 'Cadence sensitivity — recoverable margin',
        columns: ['Cadence', 'Margin', 'Buffer days', 'Constraint'],
        rows: [
          ['9.0 d', '27.6%', '11.4', 'None'],
          ['8.0 d', '29.9%', '8.1', 'None'],
          ['7.5 d', '31.8%', '6.2', 'Component buffer'],
          ['7.0 d', '29.1%', '3.4', 'Customs clearance'],
          ['6.0 d', '21.7%', '0.8', 'Hard stop'],
        ],
      },
      {
        kind: 'text',
        body: 'It breaks first at tier-2 replenishment. Two suppliers — both APAC — carry a 5.5-day effective lead time once customs variability is included. Below a 7.5-day cadence you are consuming buffer faster than it clears.',
      },
      {
        kind: 'list',
        items: [
          'Dual-source the two APAC tier-2 components — removes the 7.5-day floor entirely.',
          'Pre-clear customs for a rolling 3-launch window — recovers ~1.2 buffer days.',
          'Hold cadence at 7.5 days until either mitigation lands.',
        ],
      },
      {
        kind: 'suggestions',
        label: 'Continue',
        items: [
          'Cost the dual-sourcing option',
          'Model a 6-day cadence with pre-clearance',
          'Draft the supplier negotiation brief',
        ],
      },
    ],
  },
];

export const SEED_CODE_MESSAGE: Message = {
  id: 'm-seed-a-code',
  role: 'assistant',
  createdAt: now - 2 * hr,
  mode: 'coding',
  tokens: 1204,
  reasoning:
    'Scanned the monorepo for legacy Card usages, classified by prop surface, then generated a staged codemod with a reversible rollout.',
  traces: [
    { id: 'tr-4', name: 'Repository Index', detail: 'scan 340 component usages', state: 'done', durationMs: 4210 },
    { id: 'tr-5', name: 'Chart Synthesis', detail: 'dependency graph render', state: 'done', durationMs: 990 },
  ],
  blocks: [
    {
      kind: 'text',
      body: 'The migration is mechanically safe for 291 of 340 usages. The remaining 49 depend on legacy layout props that have no direct equivalent — those need a decision, not a codemod.',
    },
    {
      kind: 'code',
      language: 'typescript',
      filename: 'codemods/migrate-card.ts',
      body: `import { Project, SyntaxKind } from 'ts-morph';

/**
 * Migrates legacy <Card> usage to the Atlas surface primitive.
 * Skips any element that still reads a layout prop — those are
 * reported for human review rather than rewritten.
 */
const LEGACY_LAYOUT_PROPS = ['gutter', 'span', 'collapseBelow'];

export async function migrate(glob = 'src/**/*.tsx') {
  const project = new Project({ tsConfigFilePath: 'tsconfig.json' });
  project.addSourceFilesAtPaths(glob);

  const report: string[] = [];

  for (const file of project.getSourceFiles()) {
    for (const jsx of file.getDescendantsOfKind(SyntaxKind.JsxElement)) {
      if (jsx.getOpeningElement().getTagNameNode().getText() !== 'Card') continue;

      const attributes = jsx.getOpeningElement().getAttributes();
      const blocked = attributes.some((attr) =>
        LEGACY_LAYOUT_PROPS.includes(attr.getText().split('=')[0].trim()),
      );

      if (blocked) {
        report.push(\`\${file.getFilePath()}:\${jsx.getStartLineNumber()}\`);
        continue;
      }

      jsx.getOpeningElement().setName('Surface');
      jsx.getClosingElement().setName('Surface');
      jsx.getOpeningElement().addAttribute({
        name: 'elevation',
        initializer: '"raised"',
      });
    }
  }

  await project.save();
  return { migrated: 291, needsReview: report };
}`,
    },
    {
      kind: 'timeline',
      steps: [
        { label: 'Freeze legacy Card surface', detail: '291 of 340 usages covered', state: 'done' },
        { label: 'Run codemod on a feature branch', detail: 'isolated to one workstream', state: 'done' },
        { label: 'Resolve 49 layout-dependent usages', detail: 'requires design decision', state: 'active' },
        { label: 'Delete legacy surface', state: 'pending' },
      ],
    },
    {
      kind: 'suggestions',
      label: 'Next',
      items: [
        'Group the 49 usages by prop pattern',
        'Open the migration tracking issue',
        'Estimate the design-decision cost',
      ],
    },
  ],
};

export const FILE_MESSAGE: Message = {
  id: 'm-seed-a-file',
  role: 'assistant',
  createdAt: now - 5 * hr,
  mode: 'vision',
  tokens: 402,
  blocks: [
    {
      kind: 'text',
      body: 'Parsed the onboarding flow capture. Four friction points stand out — all of them before first value is delivered.',
    },
    { kind: 'file', name: 'onboarding-audit-v3.pdf', type: 'PDF', size: '4.2 MB', status: 'indexed' },
    {
      kind: 'cards',
      cards: [
        {
          title: 'Step 3 — workspace naming',
          meta: 'Friction · high',
          body: 'Unlabeled field with no example. 38% of sessions stall here for over 20 seconds.',
          tag: 'Fix',
        },
        {
          title: 'Step 5 — permission prompt',
          meta: 'Friction · medium',
          body: 'Native browser prompt interrupts a single-screen flow. Defer until after first value.',
          tag: 'Defer',
        },
        {
          title: 'Step 6 — empty dashboard',
          meta: 'Friction · high',
          body: 'No guidance after activation. Users cannot tell what to do next.',
          tag: 'Redesign',
        },
      ],
    },
  ],
};

/* ── Command palette index ───────────────────────────────────────── */

export const COMMANDS: CommandAction[] = [
  { id: 'nav-home', label: 'Go to Intelligence Home', hint: 'Overview', group: 'Navigate', icon: 'Home', keywords: 'landing orb' },
  { id: 'nav-chat', label: 'Open Conversation', hint: 'Chat workspace', group: 'Navigate', icon: 'MessagesSquare', keywords: 'chat thread' },
  { id: 'nav-voice', label: 'Enter Voice Mode', hint: 'Live dialogue', group: 'Navigate', icon: 'AudioWaveform', keywords: 'mic speak' },
  { id: 'nav-dash', label: 'Intelligence Dashboard', hint: 'Metrics & activity', group: 'Navigate', icon: 'Activity', keywords: 'analytics charts' },
  { id: 'nav-knowledge', label: 'Knowledge Sources', hint: 'Indexed corpus', group: 'Navigate', icon: 'Library', keywords: 'documents' },
  { id: 'nav-tools', label: 'Tools & Integrations', hint: 'Connected systems', group: 'Navigate', icon: 'Plug', keywords: 'integrations' },
  { id: 'nav-memory', label: 'Memory Layer', hint: 'Learned preferences', group: 'Navigate', icon: 'Brain', keywords: 'recall' },
  { id: 'nav-projects', label: 'Projects', hint: 'Active workstreams', group: 'Navigate', icon: 'FolderKanban', keywords: 'workspaces' },
  { id: 'act-new', label: 'New Conversation', hint: 'Clear the thread', group: 'System', icon: 'Plus', shortcut: '⌘N' },
  { id: 'act-voice', label: 'Toggle Voice Capture', hint: 'Hands-free input', group: 'System', icon: 'Mic', shortcut: '⌘M' },
  { id: 'act-sidebar', label: 'Toggle Sidebar', hint: 'Collapse navigation', group: 'System', icon: 'PanelLeft', shortcut: '⌘B' },
  ...AI_MODES.map<CommandAction>((m) => ({
    id: `mode-${m.id}`,
    label: `Switch to ${m.label} mode`,
    hint: m.caption,
    group: 'Modes',
    icon: 'Sparkles',
    keywords: m.description,
  })),
  ...CONVERSATIONS.slice(0, 6).map<CommandAction>((c) => ({
    id: `conv-${c.id}`,
    label: c.title,
    hint: c.preview.slice(0, 64) + '…',
    group: 'Conversations',
    icon: 'MessageSquare',
    keywords: c.mode + ' ' + (c.project ?? ''),
  })),
  ...PROJECTS.map<CommandAction>((p) => ({
    id: `proj-${p.id}`,
    label: p.name,
    hint: p.brief,
    group: 'Projects',
    icon: 'FolderKanban',
    keywords: 'project',
  })),
  ...TOOLS.slice(0, 5).map<CommandAction>((t) => ({
    id: `tool-${t.id}`,
    label: t.name,
    hint: `${t.category} · ${t.connected ? 'Connected' : 'Not connected'}`,
    group: 'Tools',
    icon: 'Plug',
    keywords: t.category,
  })),
];

export const PROMPT_SUGGESTIONS = [
  {
    id: 's-1',
    label: 'Model a decision',
    prompt:
      'Model the trade-off between two vendor options and recommend one with an explicit reversal path.',
  },
  {
    id: 's-2',
    label: 'Review a codebase',
    prompt:
      'Review the architecture of a monorepo and identify the three highest-risk coupling points.',
  },
  {
    id: 's-3',
    label: 'Synthesise research',
    prompt:
      'Synthesise the current regulatory position across three jurisdictions into a decision memo.',
  },
  {
    id: 's-4',
    label: 'Draft long form',
    prompt:
      'Draft a 900-word investor narrative with a restrained, confident editorial voice.',
  },
];