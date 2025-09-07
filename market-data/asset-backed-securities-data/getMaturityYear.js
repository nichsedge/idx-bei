"use strict";

import { fetchData } from "../../../fetchUtil.js";

/**
 * Retrieves maturity year data from IDX.
 * @returns {Promise<string>} - A JSON string of the maturity year data.
 * @throws {Error} If the request fails.
 */
export async function getMaturityYear() {
  const url = "https://www.idx.co.id/primary/Helper/GetMaturityYear";
  const referrer = "https://www.idx.co.id/en/market-data/asset-backed-securities-data/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching maturity year data:", error.message);
    throw new Error(`Failed to fetch maturity year data: ${error.message}`);
  }
}
