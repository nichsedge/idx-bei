"use strict";

import { fetchData } from "../../fetchUtil.js";

/**
 * Retrieves today's futures data from IDX.
 * @returns {Promise<string>} - A JSON string of today's futures data.
 * @throws {Error} If the request fails.
 */
export async function getFutureToday() {
  const url = "https://www.idx.co.id/primary/DerivativesData/GetFutureToday";
  const referrer = "https://www.idx.co.id/en/market-data/derivatives-data/futures/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching today's futures data:", error.message);
    throw new Error(`Failed to fetch today's futures data: ${error.message}`);
  }
}
