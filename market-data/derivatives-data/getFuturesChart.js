"use strict";

import { fetchData } from "../../fetchUtil.js";

/**
 * Retrieves futures chart data from IDX.
 * @param {Object} [options] - Options for the futures chart data.
 * @param {string} [options.period='1Y'] - The period for the chart data (e.g., '1Y' for one year).
 * @param {string} [options.contractCode='BM10Z2'] - The contract code for the futures chart.
 * @returns {Promise<string>} - A JSON string of the futures chart data.
 * @throws {Error} If the request fails or invalid parameters are provided.
 */
export async function getFuturesChart({
  period = '1Y',
  contractCode = 'BM10Z2'
} = {}) {
  // Input validation
  if (typeof period !== 'string' || typeof contractCode !== 'string') {
    throw new Error('period and contractCode must be strings');
  }

  const baseUrl = "https://www.idx.co.id/primary/DerivativesData/GetFuturesChart";
  const queryParams = new URLSearchParams({ period, contractCode }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/derivatives-data/futures/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching futures chart data:", error.message);
    throw new Error(`Failed to fetch futures chart data: ${error.message}`);
  }
}
