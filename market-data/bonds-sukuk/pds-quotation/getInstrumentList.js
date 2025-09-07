"use strict";

import { fetchData } from "../../../fetchUtil.js";

/**
 * Retrieves the list of instruments from IDX.
 * @returns {Promise<string>} - A JSON string of the instrument list data.
 * @throws {Error} If the request fails.
 */
export async function getInstrumentList() {
  const baseUrl = "https://www.idx.co.id/primary/BondSukuk/GetInstrumentList";
  const queryParams = new URLSearchParams({}).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/bonds-sukuk/pds-quotation/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching instrument list:", error.message);
    throw new Error(`Failed to fetch instrument list: ${error.message}`);
  }
}
