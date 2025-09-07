"use strict";

import { fetchData } from "../../fetchUtil.js";

/**
 * Retrieves data on the most active brokers from IDX.
 * @returns {Promise<string>} - A JSON string of the most active brokers data.
 * @throws {Error} If the request fails.
 */
export async function getMostActiveBroker() {
  const url = "https://www.idx.co.id/primary/DerivativesData/GetMostActiveBroker";
  const referrer = "https://www.idx.co.id/en/market-data/derivatives-data/futures/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching most active brokers data:", error.message);
    throw new Error(`Failed to fetch most active brokers data: ${error.message}`);
  }
}
