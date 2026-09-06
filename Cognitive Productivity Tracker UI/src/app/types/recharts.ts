/**
 * TypeScript definitions for Recharts custom tooltips and chart payloads.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

export interface RechartsTooltipPayloadItem {
  name?: string;
  value?: number;
  color?: string;
  dataKey?: string;
  payload?: Record<string, unknown>;
}

export interface RechartsTooltipProps {
  active?: boolean;
  payload?: RechartsTooltipPayloadItem[];
  label?: string;
}
