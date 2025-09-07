"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the list of emitters from IDX.
 * @param {string} [emitenType=''] - The type of emitters to retrieve (e.g., 's' for structured warrants).
 * @returns {Promise<string>} - A JSON string of the emitters list.
 * @throws {Error} If the request fails or invalid parameter is provided.
 */
export async function getEmiten(emitenType = '') {
  // Input validation
  if (typeof emitenType !== 'string') {
    throw new Error('emitenType must be a string');
  }

  const url = `https://www.idx.co.id/primary/Helper/GetEmiten?emitenType=${encodeURIComponent(emitenType)}`;
  const referrer = "https://www.idx.co.id/en/market-data/structured-warrant-sw/structured-warrant-information/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching emitters:", error.message);
    throw new Error(`Failed to fetch emitters: ${error.message}`);
  }
}
