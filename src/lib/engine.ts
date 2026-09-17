import type { AIModeId, ContentBlock, Message, ToolTrace } from '@/types';
import { uid } from '@/lib/utils';
import { FILE_MESSAGE, SEED_CODE_MESSAGE } from '@/data/mock';

/* ── Keyword-routed response composer ────────────────────────────── */

interface Recipe {
  match: RegExp;
  mode?: AIModeId;
  reasoning: string;
  traces: Array<Omit<ToolTrace, 'id' | 'state' | 'durationMs'> & { ms: number }>;
  blocks: ContentBlock[];
  followUps: string[];
}

const RECIPES: Recipe[] = [
  {
    match: /code|refactor|architecture|monorepo|migrat|typescript|react|api|component|bug|implement/i,
    mode: 'coding',
    reasoning:
      'Scanned the repository index for the affected surface, ranked call sites by coupling, then generated a reversible change plan with a verification step per stage.',
    traces: [
      { name: 'Repository Index', detail: 'resolve affected surface', ms: 1840 },
      { name: 'Chart Synthesis', detail: 'coupling graph', ms: 940 },
      { name: 'Static Analysis', detail: 'type + lint pass', ms: 2310 },
    ],
    blocks: [
      {
        kind: 'text',
        body: 'I mapped the change surface and split it into three stages. The first two are mechanically safe; the third carries a real decision and should not be automated.',
      },
      {
        kind: 'code',
        language: 'typescript',
        filename: 'src/features/conversation/useThread.ts',
        body: `import { useCallback, useReducer } from 'react';
import type { Message } from '@/types';

type Action =
  | { type: 'append'; message: Message }
  | { type: 'patch'; id: string; patch: Partial<Message> }
  | { type: 'reset' };

function reducer(state: Message[], action: Action): Message[] {
  switch (action.type) {
    case 'append':
      return [...state, action.message];
    case 'patch':
      return state.map((m) => (m.id === action.id ? { ...m, ...action.patch } : m));
    case 'reset':
      return [];
  }
}

export function useThread(initial: Message[] = []) {
  const [messages, dispatch] = useReducer(reducer, initial);

  const append = useCallback(
    (message: Message) => dispatch({ type: 'append', message }),
    [],
  );

  const patch = useCallback(
    (id: string, patch: Partial<Message>) => dispatch({ type: 'patch', id, patch }),
    [],
  );

  return { messages, append, patch, reset: () => dispatch({ type: 'reset' }) };
}`,
      },
      {
        kind: 'list',
        items: [
          'Stage 1 — extract the reducer into a pure module. No behaviour change, fully reversible.',
          'Stage 2 — move streaming into a hook with an abort controller so partial responses can be cancelled.',
          'Stage 3 — decide whether optimistic user messages survive a failed request. That is a product call, not a technical one.',
        ],
      },
      {
        kind: 'timeline',
        steps: [
          { label: 'Extract pure reducer', detail: 'verified against existing tests', state: 'done' },
          { label: 'Introduce streaming hook', detail: 'abort-safe', state: 'active' },
          { label: 'Resolve optimistic-message policy', state: 'pending' },
        ],
      },
      {
        kind: 'suggestions',
        label: 'Continue',
        items: ['Write tests for the reducer', 'Show the abort-controller pattern', 'Review the error boundary'],
      },
    ],
    followUps: ['Show the abort-controller pattern', 'Write the reducer tests'],
  },
  {
    match: /research|source|citation|market|regulat|jurisdiction|competitor|landscape|study/i,
    mode: 'research',
    reasoning:
      'Queried four independent source classes, discarded two low-authority results, and weighted the remainder by recency and primary-source proximity.',
    traces: [
      { name: 'Live Web Retrieval', detail: '42 candidate sources', ms: 3120 },
      { name: 'Source Ranker', detail: 'authority + recency weighting', ms: 1180 },
      { name: 'Corpus Search', detail: 'internal archive cross-check', ms: 1420 },
    ],
    blocks: [
      {
        kind: 'text',
        body: 'I found a consistent direction across jurisdictions, but the timelines diverge sharply — which matters more than the direction itself.',
      },
      {
        kind: 'table',
        caption: 'Regulatory position — synthesis',
        columns: ['Jurisdiction', 'Position', 'Effective', 'Confidence'],
        rows: [
          ['European Union', 'Binding, phased', 'Q1 2027', 'High'],
          ['United Kingdom', 'Consultation stage', 'Indicative 2028', 'Medium'],
          ['United States', 'Sector-by-sector', 'Rolling', 'Medium'],
          ['Singapore', 'Voluntary framework', 'Live', 'High'],
        ],
      },
      {
        kind: 'insight',
        title: 'Divergence window',
        metric: '9–14 months',
        detail:
          'The gap between EU binding effect and UK/UK-equivalent clarity is the single largest planning risk in the corpus.',
      },
      {
        kind: 'list',
        ordered: true,
        items: [
          'Comply to the EU standard as the ceiling — it is the strictest and most precisely drafted.',
          'Do not build separate regional logic until the UK consultation closes.',
          'Re-review in 90 days; two of the four positions are still moving.',
        ],
      },
      {
        kind: 'suggestions',
        label: 'Go deeper',
        items: ['Trace the EU drafting history', 'Compare enforcement regimes', 'Draft a compliance decision memo'],
      },
    ],
    followUps: ['Compare enforcement regimes', 'Draft a compliance decision memo'],
  },
  {
    match: /model|margin|forecast|analysis|data|scenario|sensitivity|metric|revenue|cost|trade-?off/i,
    mode: 'analysis',
    reasoning:
      'Isolated the variable terms, ran a sensitivity sweep, and identified the binding constraint rather than the headline optimum.',
    traces: [
      { name: 'Warehouse Query', detail: 'baseline extraction', ms: 1640 },
      { name: 'Chart Synthesis', detail: '8-scenario sweep', ms: 2480 },
    ],
    blocks: [
      {
        kind: 'text',
        body: 'The headline number is less interesting than where it breaks. I swept the variable and found a sharp cliff rather than a gradual decline — that shape is the finding.',
      },
      {
        kind: 'insight',
        title: 'Optimal point',
        metric: '+14.2%',
        delta: 'vs. current',
        detail: 'Peak sits well inside the safe region, but only 1.5 units from the constraint boundary.',
      },
      {
        kind: 'table',
        caption: 'Sensitivity sweep',
        columns: ['Scenario', 'Outcome', 'Headroom', 'Binding constraint'],
        rows: [
          ['Conservative', '27.6%', '11.4', 'None'],
          ['Baseline', '29.9%', '8.1', 'None'],
          ['Optimised', '31.8%', '6.2', 'Buffer depletion'],
          ['Aggressive', '29.1%', '3.4', 'Clearance time'],
          ['Beyond limit', '21.7%', '0.8', 'Hard stop'],
        ],
      },
      {
        kind: 'text',
        body: 'Two caveats worth stating explicitly: the denominator excludes fixed facility cost, and the sweep assumes last quarter\u2019s clearance distribution. Both are conservative, so the true optimum is likely marginally better.',
      },
      {
        kind: 'suggestions',
        label: 'Continue',
        items: ['Re-run with fixed cost included', 'Stress the clearance distribution', 'Export the model as a memo'],
      },
    ],
    followUps: ['Re-run with fixed cost included', 'Export the model as a memo'],
  },
  {
    match: /draft|write|narrative|story|brand|voice|creative|editorial|copy|essay|tone/i,
    mode: 'creative',
    reasoning:
      'Established the intended register first, then drafted to a strict word budget and removed every hedging clause.',
    traces: [
      { name: 'Style Memory', detail: 'retrieve preference profile', ms: 620 },
      { name: 'Draft Engine', detail: 'long-form composition', ms: 3410 },
    ],
    blocks: [
      {
        kind: 'text',
        body: 'I wrote this to a 160-word budget with no hedging. The opening states the position in the first sentence — if that sentence is wrong, the whole piece is wrong, which is the correct failure mode for this kind of document.',
      },
      {
        kind: 'cards',
        cards: [
          {
            title: 'Opening — version A',
            meta: 'Direct',
            body: 'We are not building a faster tool. We are removing a decision from the critical path.',
            tag: 'Recommended',
          },
          {
            title: 'Opening — version B',
            meta: 'Measured',
            body: 'The constraint was never compute. It was the distance between a question and a decision.',
            tag: 'Alternate',
          },
        ],
      },
      {
        kind: 'list',
        items: [
          'Removed three instances of "we believe" — they weakened the thesis without adding caution.',
          'Replaced two abstract nouns with concrete ones; abstraction was doing the hedging.',
          'Kept one deliberate hedge on the timeline. That one is honest.',
        ],
      },
      {
        kind: 'suggestions',
        label: 'Revise',
        items: ['Make it 40 words shorter', 'Shift register to more formal', 'Write the closing paragraph'],
      },
    ],
    followUps: ['Make it 40 words shorter', 'Write the closing paragraph'],
  },
  {
    match: /image|vision|screenshot|interface|design|ui|visual|diagram|document|pdf/i,
    mode: 'vision',
    reasoning:
      'Parsed the visual input into structural regions, then evaluated each region against interaction intent rather than aesthetics.',
    traces: [
      { name: 'Visual Parser', detail: 'region segmentation', ms: 2210 },
      { name: 'Layout Analysis', detail: 'hierarchy scoring', ms: 1340 },
    ],
    blocks: [
      {
        kind: 'text',
        body: 'Structurally this is sound. The problems are all about sequencing — value arrives too late relative to the effort the user has already spent.',
      },
      { kind: 'file', name: 'capture-annotated.png', type: 'PNG', size: '2.8 MB', status: 'parsed' },
      {
        kind: 'cards',
        cards: [
          { title: 'Primary action buried', meta: 'Hierarchy · high', body: 'The action sits at equal weight to three secondary controls.', tag: 'Fix' },
          { title: 'Density mismatch', meta: 'Rhythm · medium', body: 'Two adjacent regions use different spacing scales — reads as unfinished.', tag: 'Align' },
          { title: 'No state feedback', meta: 'Interaction · high', body: 'A 4-second operation has no progress affordance.', tag: 'Add' },
        ],
      },
      {
        kind: 'suggestions',
        label: 'Continue',
        items: ['Annotate the fixes on the capture', 'Write the change list', 'Compare against the previous revision'],
      },
    ],
    followUps: ['Write the change list', 'Compare against the previous revision'],
  },
];

const DEFAULT_RECIPE: Recipe = {
  match: /.*/,
  reasoning:
    'Parsed the intent, selected the most relevant context from the knowledge layer, and composed a direct answer before adding supporting structure.',
  traces: [
    { name: 'Intent Parser', detail: 'classify request', ms: 480 },
    { name: 'Corpus Search', detail: 'retrieve relevant context', ms: 1290 },
  ],
  blocks: [
    {
      kind: 'text',
      body: 'Understood. Here is how I would approach it — starting with the part that constrains everything else.',
    },
    {
      kind: 'list',
      ordered: true,
      items: [
        'Establish the constraint first. Most plans fail because the binding limit was never named.',
        'Choose the smallest reversible step that tests the assumption behind that constraint.',
        'Only widen scope once the first step has produced evidence.',
      ],
    },
    {
      kind: 'insight',
      title: 'Recommendation',
      metric: 'Reversible first',
      detail:
        'Sequence the work so that the first decision can be undone cheaply. Confidence rises with evidence, not with commitment.',
    },
    {
      kind: 'suggestions',
      label: 'Continue',
      items: ['Go deeper on the constraint', 'Turn this into a plan', 'Challenge the assumptions'],
    },
  ],
  followUps: ['Go deeper on the constraint', 'Turn this into a plan'],
};

export function pickRecipe(input: string): Recipe {
  return RECIPES.find((r) => r.match.test(input)) ?? DEFAULT_RECIPE;
}

/* ── Streamed response generation ────────────────────────────────── */

export interface StreamHandlers {
  onReasoning: (text: string) => void;
  onTrace: (trace: ToolTrace) => void;
  onTraceDone: (id: string, durationMs: number) => void;
  onBlocks: (blocks: ContentBlock[]) => void;
  onToken: (count: number) => void;
}

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/**
 * Simulates an assistant turn: reasoning → tool execution → streamed blocks.
 * Resolves with the finished message. Respects an abort signal so the UI can
 * cancel mid-stream the way a real streaming transport would.
 */
export async function runAssistantTurn(
  input: string,
  mode: AIModeId,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<Message> {
  const aborted = () => signal?.aborted === true;
  const recipe = pickRecipe(input);
  const resolvedMode = recipe.mode ?? mode;

  const reasoning = recipe.reasoning;
  for (let i = 1; i <= reasoning.length; i += 4) {
    if (aborted()) break;
    handlers.onReasoning(reasoning.slice(0, i));
    await wait(9);
  }
  handlers.onReasoning(reasoning);

  const traces: ToolTrace[] = [];
  for (const t of recipe.traces) {
    if (aborted()) break;
    const trace: ToolTrace = {
      id: uid('tr'),
      name: t.name,
      detail: t.detail,
      state: 'running',
    };
    traces.push(trace);
    handlers.onTrace(trace);
    await wait(t.ms);
    trace.state = 'done';
    trace.durationMs = t.ms;
    handlers.onTraceDone(trace.id, t.ms);
  }

  const blocks = recipe.blocks;
  const revealed: ContentBlock[] = [];
  let tokens = 0;

  for (const block of blocks) {
    if (aborted()) break;
    revealed.push(block);
    handlers.onBlocks([...revealed]);
    tokens += block.kind === 'text' ? Math.round(block.body.length / 3.6) : 48;
    handlers.onToken(tokens);
    await wait(block.kind === 'text' ? 420 : 300);
  }

  return {
    id: uid('msg'),
    role: 'assistant',
    createdAt: Date.now(),
    mode: resolvedMode,
    blocks: revealed,
    reasoning,
    traces,
    tokens,
  };
}

/** Canned rich transcript used when the user opens a seeded thread. */
export function seededTranscript(conversationId: string): Message[] {
  if (conversationId === 'c-atlas') return [SEED_CODE_MESSAGE];
  if (conversationId === 'c-interface') return [FILE_MESSAGE];
  return [];
}

export const VOICE_RESPONSES = [
  'I have the context. The constraint is clearance time, not capacity — that is where I would look first.',
  'Three sources agree, one disagrees. The dissenting source is the most recent, so I would weight it carefully rather than discard it.',
  'Done. I staged the change so the first step is fully reversible, and I flagged the one decision that should not be automated.',
  'The headline number improves by fourteen percent, but the more useful finding is where it breaks.',
];