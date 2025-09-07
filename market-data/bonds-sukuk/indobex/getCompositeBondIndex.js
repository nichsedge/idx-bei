"use strict";

import { fetchData } from "../../../fetchUtil.js";

/**
 * Retrieves the Composite Bond Index data from IDX.
 * @returns {Promise<string>} - A JSON string of the Composite Bond Index data.
 * @throws {Error} If the request fails.
 */
export async function getCompositeBondIndex() {
  const url = "https://www.idx.co.id/primary/BondSukuk/GetCompositeBondIndex";
  const referrer = "https://www.idx.co.id/en/market-data/bonds-sukuk/indobex/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching Composite Bond Index data:", error.message);
    throw new Error(`Failed to fetch Composite Bond Index data: ${error.message}`);
  }
}
