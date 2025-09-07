"use strict";

import { fetchData } from "../../fetchUtil.js";

/**
 * Retrieves ETF market data from IDX.
 * @returns {Promise<string>} - A JSON string of the ETF market data.
 * @throws {Error} If the request fails.
 */
export async function getEtfMarket() {
  const url = "https://www.idx.co.id/primary/ETF/GetEtfMarket";
  const referrer = "https://www.idx.co.id/en/market-data/exchanged-traded-fund-etf-data/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching ETF market data:", error.message);
    throw new Error(`Failed to fetch ETF market data: ${error.message}`);
  }
}
