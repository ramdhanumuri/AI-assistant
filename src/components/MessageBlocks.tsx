import { motion } from 'framer-motion';
import { Check, Copy, FileText, Loader2, Sparkles, TrendingUp } from 'lucide-react';
import { useState } from 'react';
import type { ContentBlock } from '@/types';
import { cx, rgba } from '@/lib/utils';

interface BlockRendererProps {
  block: ContentBlock;
  aura: string;
  onSuggestion?: (text: string) => void;
  index: number;
}

export function BlockRenderer({ block, aura, onSuggestion, index }: BlockRendererProps) {
  const delay = index * 0.05;

  switch (block.kind) {
    case 'text':
      return <TextBlockView body={block.body} delay={delay} />;
    case 'code':
      return <CodeBlockView block={block} aura={aura} delay={delay} />;
    case 'list':
      return <ListBlockView block={block} aura={aura} delay={delay} />;
    case 'table':
      return <TableBlockView block={block} aura={aura} delay={delay} />;
    case 'insight':
      return <InsightBlockView block={block} aura={aura} delay={delay} />;
    case 'cards':
      return <CardsBlockView block={block} aura={aura} delay={delay} />;
    case 'file':
      return <FileBlockView block={block} aura={aura} delay={delay} />;
    case 'timeline':
      return <TimelineBlockView block={block} aura={aura} delay={delay} />;
    case 'suggestions':
      return (
        <SuggestionsBlockView
          block={block}
          aura={aura}
          delay={delay}
          onSuggestion={onSuggestion}
        />
      );
  }
}

const reveal = (delay: number) => ({
  initial: { opacity: 0, y: 10, filter: 'blur(6px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
  transition: { duration: 0.65, delay, ease: [0.16, 1, 0.3, 1] as const },
});

/* ── Text ───────────────────────────────────────────────────────── */

function TextBlockView({ body, delay }: { body: string; delay: number }) {
  const paragraphs = body.split('\n\n');
  return (
    <motion.div {...reveal(delay)} className="space-y-4">
      {paragraphs.map((p, i) => (
        <p
          key={i}
          className="max-w-[68ch] text-[14.5px] font-[350] leading-[1.78] tracking-[0.005em] text-platinum-soft/92"
        >
          {p}
        </p>
      ))}
    </motion.div>
  );
}

/* ── Code ───────────────────────────────────────────────────────── */

function CodeBlockView({
  block,
  aura,
  delay,
}: {
  block: Extract<ContentBlock, { kind: 'code' }>;
  aura: string;
  delay: number;
}) {
  const [copied, setCopied] = useState(false);
  const lines = block.body.split('\n');

  return (
    <motion.div
      {...reveal(delay)}
      className="overflow-hidden rounded-xl border border-white/[0.07] bg-[#05060c]/80"
    >
      <div className="flex items-center justify-between border-b border-white/[0.055] bg-white/[0.017] px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="flex gap-1.5">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="h-1.5 w-1.5 rounded-full bg-white/12"
                style={i === 0 ? { background: rgba(aura, 0.5) } : undefined}
              />
            ))}
          </span>
          <span className="font-mono text-[10.5px] text-platinum-dim">
            {block.filename ?? 'snippet'}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60">
            {block.language}
          </span>
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard?.writeText(block.body);
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1600);
            }}
            className="flex items-center gap-1.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim transition-colors hover:text-platinum"
            aria-label="Copy code"
          >
            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <pre className="min-w-full py-3">
          <code className="block font-mono text-[12px] leading-[1.75]">
            {lines.map((line, i) => (
              <div key={i} className="group/line flex hover:bg-white/[0.02]">
                <span className="w-11 shrink-0 select-none pr-4 text-right text-platinum-dim/35">
                  {i + 1}
                </span>
                <span className="flex-1 whitespace-pre pr-4 text-platinum-soft/88">
                  <Tokenize line={line} aura={aura} />
                </span>
              </div>
            ))}
          </code>
        </pre>
      </div>
    </motion.div>
  );
}

const KEYWORDS =
  /\b(import|from|export|const|let|function|return|if|else|for|while|await|async|type|interface|new|class|extends|implements|try|catch|switch|case|default|break|continue|as|of|in|typeof|instanceof|void|null|undefined|true|false)\b/;
const TYPES =
  /\b(string|number|boolean|Message|Action|Partial|Record|Array|Promise|React|JSX|Element|Props|Context|AbortController|Project|SyntaxKind)\b/;

function Tokenize({ line, aura }: { line: string; aura: string }) {
  const trimmed = line.trimStart();
  if (trimmed.startsWith('//') || trimmed.startsWith('*') || trimmed.startsWith('/*')) {
    return <span className="italic text-platinum-dim/55">{line}</span>;
  }

  const parts = line.split(/(\/\/.*$)/);
  const code = parts[0];
  const comment = parts[1];

  const tokens = code.split(/(\s+|[{}()[\];,.=<>+\-*/!?:&|`'"@])/g);

  return (
    <>
      {tokens.map((tok, i) => {
        if (!tok) return null;
        if (/^\s+$/.test(tok)) return <span key={i}>{tok}</span>;
        if (/^['"`]/.test(tok)) {
          return (
            <span key={i} style={{ color: rgba('216 195 154', 0.88) }}>
              {tok}
            </span>
          );
        }
        if (/^\d+(\.\d+)?$/.test(tok)) {
          return (
            <span key={i} style={{ color: rgba('170 210 200', 0.9) }}>
              {tok}
            </span>
          );
        }
        if (KEYWORDS.test(tok)) {
          return (
            <span key={i} style={{ color: rgba(aura, 0.95) }}>
              {tok}
            </span>
          );
        }
        if (TYPES.test(tok)) {
          return (
            <span key={i} style={{ color: rgba('150 190 255', 0.85) }}>
              {tok}
            </span>
          );
        }
        if (/^[{}()[\];,.=<>+\-*/!?:&|@]$/.test(tok)) {
          return (
            <span key={i} className="text-platinum-dim/70">
              {tok}
            </span>
          );
        }
        return (
          <span key={i} className="text-platinum-soft/90">
            {tok}
          </span>
        );
      })}
      {comment && <span className="italic text-platinum-dim/50">{comment}</span>}
    </>
  );
}

/* ── List ───────────────────────────────────────────────────────── */

function ListBlockView({
  block,
  aura,
  delay,
}: {
  block: Extract<ContentBlock, { kind: 'list' }>;
  aura: string;
  delay: number;
}) {
  return (
    <motion.ul {...reveal(delay)} className="space-y-3">
      {block.items.map((item, i) => (
        <li key={i} className="flex items-start gap-3.5">
          {block.ordered ? (
            <span
              className="mt-[3px] flex h-5 w-5 shrink-0 items-center justify-center rounded-full border font-mono text-[9px]"
              style={{
                borderColor: rgba(aura, 0.3),
                color: rgba(aura, 0.9),
                background: rgba(aura, 0.07),
              }}
            >
              {i + 1}
            </span>
          ) : (
            <span
              className="mt-[9px] h-[5px] w-[5px] shrink-0 rotate-45"
              style={{ background: rgba(aura, 0.75) }}
            />
          )}
          <span className="max-w-[64ch] text-[13.5px] leading-relaxed text-platinum-soft/85">
            {item}
          </span>
        </li>
      ))}
    </motion.ul>
  );
}

/* ── Table ──────────────────────────────────────────────────────── */

function TableBlockView({
  block,
  aura,
  delay,
}: {
  block: Extract<ContentBlock, { kind: 'table' }>;
  aura: string;
  delay: number;
}) {
  return (
    <motion.figure {...reveal(delay)} className="space-y-3">
      {block.caption && (
        <figcaption className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
          {block.caption}
        </figcaption>
      )}
      <div className="overflow-hidden rounded-xl border border-white/[0.065] bg-white/[0.012]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] border-collapse text-left">
            <thead>
              <tr className="border-b border-white/[0.07] bg-white/[0.02]">
                {block.columns.map((c) => (
                  <th
                    key={c}
                    scope="col"
                    className="px-4 py-3 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim"
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, ri) => (
                <tr
                  key={ri}
                  className="border-b border-white/[0.04] transition-colors last:border-0 hover:bg-white/[0.025]"
                >
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className={cx(
                        'px-4 py-3 text-[13px] tabular-nums',
                        ci === 0
                          ? 'font-[380] text-platinum/90'
                          : 'text-platinum-soft/78',
                      )}
                    >
                      {ci === 1 ? (
                        <span
                          className="inline-flex items-center gap-2"
                          style={{ color: ri === 2 ? rgba(aura, 0.95) : undefined }}
                        >
                          {ri === 2 && (
                            <span
                              className="h-1 w-1 rounded-full"
                              style={{ background: rgba(aura, 1) }}
                            />
                          )}
                          {cell}
                        </span>
                      ) : (
                        cell
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.figure>
  );
}

/* ── Insight ────────────────────────────────────────────────────── */

function InsightBlockView({
  block,
  aura,
  delay,
}: {
  block: Extract<ContentBlock, { kind: 'insight' }>;
  aura: string;
  delay: number;
}) {
  return (
    <motion.div
      {...reveal(delay)}
      className="relative overflow-hidden rounded-xl border p-5"
      style={{
        borderColor: rgba(aura, 0.22),
        background: `linear-gradient(120deg, ${rgba(aura, 0.09)}, rgba(255,255,255,0.012) 62%)`,
      }}
    >
      <span
        aria-hidden
        className="absolute left-0 top-0 h-full w-[2px]"
        style={{
          background: `linear-gradient(180deg, transparent, ${rgba(aura, 0.85)}, transparent)`,
        }}
      />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
            {block.title}
          </div>
          <div
            className="mt-2 text-[2rem] font-extralight leading-none tracking-tight"
            style={{ color: rgba(aura, 0.98) }}
          >
            {block.metric}
          </div>
        </div>
        {block.delta && (
          <span
            className="flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-3xs uppercase tracking-widest2"
            style={{
              borderColor: 'rgba(216,195,154,0.3)',
              color: rgba('216 195 154', 0.95),
              background: rgba('216 195 154', 0.07),
            }}
          >
            <TrendingUp className="h-3 w-3" />
            {block.delta}
          </span>
        )}
      </div>
      <p className="mt-4 max-w-[62ch] text-[13px] leading-relaxed text-platinum-soft/72">
        {block.detail}
      </p>
    </motion.div>
  );
}

/* ── Cards ──────────────────────────────────────────────────────── */

function CardsBlockView({
  block,
  aura,
  delay,
}: {
  block: Extract<ContentBlock, { kind: 'cards' }>;
  aura: string;
  delay: number;
}) {
  return (
    <motion.div {...reveal(delay)} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {block.cards.map((card, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: delay + i * 0.08, ease: [0.16, 1, 0.3, 1] }}
          className="group relative overflow-hidden rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 transition-all duration-500 ease-cinematic hover:-translate-y-0.5 hover:border-white/[0.15] hover:bg-white/[0.035]"
        >
          <span
            aria-hidden
            className="pointer-events-none absolute inset-x-4 top-0 h-px opacity-0 transition-opacity duration-500 group-hover:opacity-100"
            style={{
              background: `linear-gradient(90deg, transparent, ${rgba(aura, 0.6)}, transparent)`,
            }}
          />
          <div className="flex items-start justify-between gap-3">
            <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/70">
              {card.meta}
            </span>
            {card.tag && (
              <span
                className="rounded px-2 py-0.5 font-mono text-[9px] uppercase tracking-widest2"
                style={{
                  background: rgba(aura, 0.1),
                  color: rgba(aura, 0.9),
                  border: `1px solid ${rgba(aura, 0.24)}`,
                }}
              >
                {card.tag}
              </span>
            )}
          </div>
          <h4 className="mt-3 text-[13.5px] font-normal leading-snug text-platinum/92">
            {card.title}
          </h4>
          <p className="mt-2 text-[12.5px] leading-relaxed text-platinum-soft/68">
            {card.body}
          </p>
        </motion.div>
      ))}
    </motion.div>
  );
}

/* ── File ──────────────────────────────────────────────────────── */

function FileBlockView({
  block,
  aura,
  delay,
}: {
  block: Extract<ContentBlock, { kind: 'file' }>;
  aura: string;
  delay: number;
}) {
  const statusCopy = {
    parsed: 'Parsed',
    indexed: 'Indexed',
    processing: 'Processing',
  }[block.status];

  return (
    <motion.div
      {...reveal(delay)}
      className="flex items-center gap-4 rounded-xl border border-white/[0.07] bg-white/[0.02] p-4"
    >
      <span
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border"
        style={{
          borderColor: rgba(aura, 0.22),
          background: rgba(aura, 0.07),
        }}
      >
        <FileText className="h-4 w-4" style={{ color: rgba(aura, 0.9) }} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13.5px] text-platinum/92">{block.name}</div>
        <div className="mt-1 flex items-center gap-2.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
          <span>{block.type}</span>
          <span className="opacity-40">·</span>
          <span>{block.size}</span>
          <span className="opacity-40">·</span>
          <span style={{ color: rgba(aura, 0.85) }}>{statusCopy}</span>
        </div>
      </div>
      {/* Integrity bars — reads as a verified artefact */}
      <div className="hidden items-end gap-[2px] sm:flex">
        {Array.from({ length: 14 }, (_, i) => (
          <span
            key={i}
            className="w-[2px] rounded-full"
            style={{
              height: 4 + ((i * 7) % 13),
              background: rgba(aura, 0.18 + ((i % 5) / 5) * 0.55),
            }}
          />
        ))}
      </div>
    </motion.div>
  );
}

/* ── Timeline ───────────────────────────────────────────────────── */

function TimelineBlockView({
  block,
  aura,
  delay,
}: {
  block: Extract<ContentBlock, { kind: 'timeline' }>;
  aura: string;
  delay: number;
}) {
  const tone = {
    done: rgba(aura, 0.9),
    active: rgba('216 195 154', 0.95),
    pending: 'rgba(255,255,255,0.16)',
  };

  return (
    <motion.ol {...reveal(delay)} className="relative list-none space-y-4 pl-6">
      <span
        aria-hidden
        className="absolute left-[5px] top-2 bottom-2 w-px bg-gradient-to-b from-white/12 via-white/08 to-transparent"
      />
      {block.steps.map((step, i) => (
        <li key={i} className="relative">
          <span
            className="absolute -left-6 top-[5px] flex h-[11px] w-[11px] items-center justify-center rounded-full border"
            style={{ borderColor: tone[step.state], background: 'rgba(5,6,10,0.95)' }}
          >
            {step.state === 'active' ? (
              <motion.span
                className="h-[5px] w-[5px] rounded-full"
                style={{ background: tone.active }}
                animate={{ scale: [1, 1.5, 1], opacity: [1, 0.6, 1] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
              />
            ) : (
              <span
                className="h-[5px] w-[5px] rounded-full"
                style={{ background: tone[step.state] }}
              />
            )}
          </span>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span
              className={cx(
                'text-[13.5px]',
                step.state === 'pending' ? 'text-platinum-dim/70' : 'text-platinum/90',
              )}
            >
              {step.label}
            </span>
            {step.detail && (
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/65">
                {step.detail}
              </span>
            )}
          </div>
        </li>
      ))}
    </motion.ol>
  );
}

/* ─ Suggestions ────────────────────────────────────────────────── */

function SuggestionsBlockView({
  block,
  aura,
  delay,
  onSuggestion,
}: {
  block: Extract<ContentBlock, { kind: 'suggestions' }>;
  aura: string;
  delay: number;
  onSuggestion?: (text: string) => void;
}) {
  return (
    <motion.div {...reveal(delay)} className="space-y-3 pt-1">
      <div className="flex items-center gap-2.5">
        <Sparkles className="h-3 w-3 text-champagne/75" />
        <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
          {block.label}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {block.items.map((item, i) => (
          <motion.button
            key={item}
            type="button"
            onClick={() => onSuggestion?.(item)}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: delay + i * 0.06 }}
            whileHover={{ y: -1 }}
            className="group relative overflow-hidden rounded-full border border-white/[0.08] bg-white/[0.025] px-4 py-2 text-[12.5px] text-platinum-soft/85 transition-colors duration-400 hover:border-white/[0.18] hover:text-platinum"
          >
            <span
              aria-hidden
              className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-400 group-hover:opacity-100"
              style={{
                background: `linear-gradient(90deg, ${rgba(aura, 0.12)}, transparent)`,
              }}
            />
            <span
              className="relative flex items-center gap-2"
              style={{ color: undefined }}
            >
              <span
                className="h-1 w-1 rounded-full transition-colors"
                style={{ background: rgba(aura, 0.5) }}
              />
              {item}
            </span>
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
}

/* ── Thinking indicator (used for pending assistant turns) ──────── */

export function ThinkingIndicator({ aura, label }: { aura: string; label: string }) {
  return (
    <div className="flex items-center gap-3.5">
      <span className="relative flex h-8 w-8 items-center justify-center">
        <motion.span
          className="absolute inset-0 rounded-full border"
          style={{ borderColor: rgba(aura, 0.18) }}
        />
        <motion.span
          className="absolute inset-0 rounded-full border-t"
          style={{ borderColor: rgba(aura, 0.85) }}
          animate={{ rotate: 360 }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'linear' }}
        />
        <Loader2 className="h-3.5 w-3.5" style={{ color: rgba(aura, 0.85) }} />
      </span>
      <div>
        <div className="font-mono text-[10px] uppercase tracking-widest2 text-platinum-dim">
          {label}
        </div>
        <div className="mt-1.5 flex gap-1">
          {[0, 1, 2, 3, 4].map((i) => (
            <motion.span
              key={i}
              className="h-[3px] w-[3px] rounded-full"
              style={{ background: rgba(aura, 0.85) }}
              animate={{ opacity: [0.2, 1, 0.2], scale: [0.8, 1.25, 0.8] }}
              transition={{
                duration: 1.4,
                repeat: Infinity,
                delay: i * 0.16,
                ease: 'easeInOut',
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}