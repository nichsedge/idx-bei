"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves fact sheet index data from IDX.
 * @returns {Promise<string>} - A JSON string of the fact sheet index data.
 * @throws {Error} If the request fails.
 */
export async function getFactSheetIndex() {
  const url = "https://www.idx.co.id/primary/StockData/GetFactSheetIndex?year=2024&lang=en";
  const referrer = "https://www.idx.co.id/en/market-data/statistical-reports/fact-sheet-index/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const res = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(res, null, 2);
  } catch (error) {
    console.error("Error fetching fact sheet index data:", error.message);
    throw new Error(`Failed to fetch fact sheet index data: ${error.message}`);
  }
}
