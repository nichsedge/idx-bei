"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves statistical data from IDX.
 * @returns {Promise<string>} - A JSON string of the statistical data.
 * @throws {Error} If the request fails.
 */
export async function getStatistic() {
  const url = "https://www.idx.co.id/primary/Statistic/GetStatistic?year=2024&type=monthly&lang=en";
  const referrer = "https://www.idx.co.id/en/market-data/statistical-reports/statistics/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const res = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(res, null, 2);
  } catch (error) {
    console.error("Error fetching statistical data:", error.message);
    throw new Error(`Failed to fetch statistical data: ${error.message}`);
  }
}
