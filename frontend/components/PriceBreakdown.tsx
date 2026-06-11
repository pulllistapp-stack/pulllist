import {
  buildSearchTerms,
  ebaySoldUrl,
  SearchContext,
  tcgplayerSearchUrl,
} from "@/lib/externalSearch";

type TcgVariant = {
  low?: number | null;
  mid?: number | null;
  high?: number | null;
  market?: number | null;
  directLow?: number | null;
};

type TcgPrices = Record<string, TcgVariant> | null | undefined;

type Props = {
  tcgplayerPrices: TcgPrices;
  tcgplayerUrl?: string | null;
  searchCtx?: SearchContext;
};

const VARIANT_LABELS: Record<string, string> = {
  normal: "Normal",
  holofoil: "Holofoil",
  reverseHolofoil: "Reverse Holo",
  "1stEditionHolofoil": "1st Ed. Holo",
  "1stEditionNormal": "1st Ed. Normal",
  unlimitedHolofoil: "Unlimited Holo",
  unlimited: "Unlimited",
};

function EmptyPrice({
  searchCtx,
  message,
}: {
  searchCtx?: SearchContext;
  message: string;
}) {
  const haveContext = searchCtx && searchCtx.cardName;
  const tcgUrl = haveContext ? tcgplayerSearchUrl(searchCtx!) : null;
  const ebayUrl = haveContext ? ebaySoldUrl(searchCtx!) : null;
  const queryPreview = haveContext ? buildSearchTerms(searchCtx!) : null;

  return (
    <div className="rounded-card bg-bg-surface border border-border p-5">
      <div className="text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2">
        Market price
      </div>
      <div className="text-sm text-text-secondary mb-3">{message}</div>
      {queryPreview && (
        <div className="text-xs font-mono text-text-tertiary mb-3 truncate" title={queryPreview}>
          → {queryPreview}
        </div>
      )}
      {haveContext && (
        <div className="flex flex-col gap-2">
          <a
            href={tcgUrl!}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-accent-blue hover:underline inline-flex items-center gap-1"
          >
            Search on TCGplayer →
          </a>
          <a
            href={ebayUrl!}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-accent-blue hover:underline inline-flex items-center gap-1"
          >
            Check eBay sold listings →
          </a>
        </div>
      )}
    </div>
  );
}

export function PriceBreakdown({
  tcgplayerPrices,
  tcgplayerUrl,
  searchCtx,
}: Props) {
  if (!tcgplayerPrices) {
    return (
      <EmptyPrice
        searchCtx={searchCtx}
        message="Pricing data hasn't synced yet for this set — usually new releases catch up within a few weeks. Check live market manually:"
      />
    );
  }

  const variants = Object.entries(tcgplayerPrices).filter(
    ([, v]) => v && (v.market != null || v.mid != null),
  );

  if (variants.length === 0) {
    return (
      <EmptyPrice
        searchCtx={searchCtx}
        message="No price data points for this card yet."
      />
    );
  }

  return (
    <div className="rounded-card bg-bg-surface border border-border p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-mono uppercase tracking-wider text-text-tertiary">
          TCGplayer market
        </div>
        {tcgplayerUrl && (
          <a
            href={tcgplayerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-accent-blue hover:underline"
          >
            View listings →
          </a>
        )}
      </div>

      <div className="space-y-3">
        {variants.map(([key, v]) => {
          const market = v.market ?? v.mid;
          const label = VARIANT_LABELS[key] ?? key;
          return (
            <div key={key}>
              <div className="flex items-baseline justify-between gap-2 mb-1">
                <span className="text-sm font-medium">{label}</span>
                <span className="text-2xl font-bold font-mono text-accent-green">
                  ${(market ?? 0).toFixed(2)}
                </span>
              </div>
              <div className="flex gap-4 text-xs font-mono text-text-tertiary">
                {v.low != null && <span>low ${v.low.toFixed(2)}</span>}
                {v.mid != null && <span>mid ${v.mid.toFixed(2)}</span>}
                {v.high != null && <span>high ${v.high.toFixed(2)}</span>}
              </div>
            </div>
          );
        })}
      </div>

      {searchCtx && searchCtx.cardName && (
        <div className="mt-4 pt-3 border-t border-border flex gap-4">
          <a
            href={ebaySoldUrl(searchCtx)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-accent-blue hover:underline"
          >
            eBay sold listings →
          </a>
        </div>
      )}
    </div>
  );
}
