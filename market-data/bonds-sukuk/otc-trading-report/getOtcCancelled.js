"use strict";

import { fetchData } from "../../../fetchUtil.js";

/**
 * Retrieves the OTC cancelled trading data.
 * @returns {Promise<string>} - A JSON string of the OTC cancelled trading data.
 * @throws {Error} If the request fails.
 */
export async function getOtcCancelled() {
  const baseUrl = "https://www.idx.co.id/secondary/get/otc/cancelled";
  const queryParams = new URLSearchParams({
    length: 9999,
    start: 0
  }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/bonds-sukuk/otc-trading-report/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching OTC cancelled trading data:", error.message);
    throw new Error(`Failed to fetch OTC cancelled trading data: ${error.message}`);
  }
}
