'use client';

import { useCallback, useEffect, useState } from 'react';
import { Alert, Badge } from '@vysel/ui';
import { useAuth } from '@/components/auth/AuthProvider';
import { ApiError } from '@/lib/api';
import type { ProductBudgetFilter, ProductMatches as ProductMatchesData } from '@/lib/reports';

const BUDGET_OPTIONS: { value: ProductBudgetFilter; label: string }[] = [
  { value: 'all', label: 'All budgets' },
  { value: 'low', label: 'Up to ₹500' },
  { value: 'mid', label: 'Up to ₹1,500' },
  { value: 'high', label: 'Any price' },
];

export function ProductMatches({ reportId }: { reportId: string }) {
  const { apiRequest } = useAuth();
  const [data, setData] = useState<ProductMatchesData | null>(null);
  const [budget, setBudget] = useState<ProductBudgetFilter | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (filter?: ProductBudgetFilter) => {
    setLoading(true);
    setError(null);
    try {
      const query = filter ? `?budget=${filter}` : '';
      const result = await apiRequest<ProductMatchesData>(
        `/reports/${encodeURIComponent(reportId)}/products${query}`,
      );
      setData(result);
      setBudget(result.budget_filter);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Could not load product matches.');
    } finally {
      setLoading(false);
    }
  }, [apiRequest, reportId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="style-report__products" aria-labelledby="product-matches-title">
      <header className="style-report__products-head">
        <div>
          <p className="vy-overline">Shop the recommendations</p>
          <h2 className="vy-h4" id="product-matches-title">Product matches</h2>
        </div>
        <label className="style-report__budget">
          <span className="vy-label">Price filter</span>
          <select
            className="vy-input"
            value={budget ?? 'all'}
            onChange={(event) => void load(event.target.value as ProductBudgetFilter)}
            disabled={loading}
          >
            {BUDGET_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
      </header>
      {error && <Alert tone="danger">{error}</Alert>}
      {loading && <p className="vy-caption" role="status">Finding matching products…</p>}
      {data && (
        <>
          <p className="vy-caption">{data.price_disclaimer}</p>
          <div className="style-report__product-groups">
            {data.matches.map((match) => (
              <section className="style-report__product-group" key={match.recommendation_id}>
                <h3 className="vy-label">For: {match.recommendation_label}</h3>
                {match.products.length ? (
                  <div className="style-report__product-cards">
                    {match.products.map((product) => (
                      <article className="style-report__product vy-card" key={product.id}>
                        <div className="style-report__card-top">
                          <h4 className="vy-label">{product.name}</h4>
                          <Badge>{Math.round(product.match_score * 100)}% match</Badge>
                        </div>
                        <p className="vy-caption">{product.brand} · {product.retailer}</p>
                        {product.shade_name && <p className="vy-caption">Shade: {product.shade_name}</p>}
                        {product.color_hex && (
                          <span className="style-report__recommendation-color" style={{ backgroundColor: product.color_hex }} aria-label={`Product shade ${product.color_hex}`} />
                        )}
                        <p className="vy-body">₹{product.price_inr.toLocaleString('en-IN')} · {product.budget} tier</p>
                        <p className="vy-caption">{product.match_reason}</p>
                        <a className="vy-link" href={product.listing_url} target="_blank" rel="noopener noreferrer">
                          Check listing at {product.retailer}<span className="vy-visually-hidden"> (opens in a new tab)</span>
                        </a>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="vy-caption">No exact catalogue match is available at this budget. We have not substituted an unrelated item.</p>
                )}
              </section>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
