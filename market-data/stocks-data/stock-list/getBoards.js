"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the list of boards from IDX.
 * @returns {Promise<string>} - A JSON string of the boards data.
 * @throws {Error} If the request fails.
 */
export async function getBoards() {
  const baseUrl = "https://www.idx.co.id/primary/Helper/GetBoards";
  const queryParams = new URLSearchParams({
    language: 'id-id'
  }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/stocks-data/stock-list/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching boards:", error.message);
    throw new Error(`Failed to fetch boards: ${error.message}`);
  }
}
