"use strict";

import { fetchData } from "../../../fetchUtil.js";

/**
 * Retrieves the Corporate Bond Index data from IDX.
 * @param {number} [length=10] - The number of records to retrieve.
 * @param {number} [start=1] - The starting index for the records.
 * @returns {Promise<string>} - A JSON string of the Corporate Bond Index data.
 * @throws {Error} If the request fails or invalid parameters are provided.
 */
export async function getCorporateBondIndex(length = 10, start = 1) {
  // Input validation
  if (typeof length !== 'number' || typeof start !== 'number') {
    throw new Error('length and start must be numbers');
  }
  if (length < 1 || start < 1) {
    throw new Error('length and start must be positive numbers');
  }

  const baseUrl = "https://www.idx.co.id/primary/BondSukuk/GetCorporateBondIndex";
  const queryParams = new URLSearchParams({ length, start }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/bonds-sukuk/indobex/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching Corporate Bond Index data:", error.message);
    throw new Error(`Failed to fetch Corporate Bond Index data: ${error.message}`);
  }
}
