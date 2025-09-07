"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves bond book data from IDX.
 * @returns {Promise<string>} - A JSON string of the bond book data.
 * @throws {Error} If the request fails.
 */
export async function getBook() {
  const url = "https://www.idx.co.id/primary/Book/GetBook?type=BondBook&lang=en";
  const referrer = "https://www.idx.co.id/en/market-data/statistical-reports/bond-book/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const res = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(res, null, 2);
  } catch (error) {
    console.error("Error fetching bond book data:", error.message);
    throw new Error(`Failed to fetch bond book data: ${error.message}`);
  }
}
