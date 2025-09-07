"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the list of ETP tickers from IDX.
 * @returns {Promise<string>} - A JSON string of the ETP tickers list.
 * @throws {Error} If the request fails.
 */
export async function getETPTickerList() {
  const url = "https://www.idx.co.id/primary/BondSukuk/GetETPTickerList";
  const referrer = "https://www.idx.co.id/en/market-data/bonds-sukuk/etp-trading/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching ETP ticker list:", error.message);
    throw new Error(`Failed to fetch ETP ticker list: ${error.message}`);
  }
}
