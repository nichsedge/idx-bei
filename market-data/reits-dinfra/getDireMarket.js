"use strict";

import { fetchData } from "../../fetchUtil.js";

/**
 * Retrieves the DIRE market data from IDX.
 * @param {Object} [options] - Options for pagination.
 * @param {number} [options.start=0] - The starting index for pagination.
 * @param {number} [options.length=9999] - The number of records to retrieve.
 * @returns {Promise<string>} - A JSON string of the DIRE market data.
 * @throws {Error} If the request fails or invalid parameters are provided.
 */
export async function getDireMarket({
  start = 0,
  length = 9999
} = {}) {
  // Input validation
  if (typeof start !== 'number' || typeof length !== 'number') {
    throw new Error('start and length must be numbers');
  }
  if (start < 0 || length < 1) {
    throw new Error('start must be >=0 and length must be positive');
  }

  const baseUrl = "https://www.idx.co.id/primary/EDD/GetDireMarket";
  const queryParams = new URLSearchParams({ start, length }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/reits-dinfra/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching DIRE market data:", error.message);
    throw new Error(`Failed to fetch DIRE market data: ${error.message}`);
  }
}
