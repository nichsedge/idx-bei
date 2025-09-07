"use strict";

import { fetchData } from "../../../fetchUtil.js";

/**
 * Retrieves Asset-Backed Securities (ABS) data from IDX.
 * @returns {Promise<string>} - A JSON string of the ABS data.
 * @throws {Error} If the request fails.
 */
export async function getAbs() {
  const url = "https://www.idx.co.id/primary/MarketData/GetAbs";
  const referrer = "https://www.idx.co.id/en/market-data/asset-backed-securities-data/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching ABS data:", error.message);
    throw new Error(`Failed to fetch ABS data: ${error.message}`);
  }
}
