"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves securities stock data from IDX based on specified parameters.
 * @param {string} [code=''] - The stock code to filter by.
 * @param {string} [sector=''] - The sector to filter by.
 * @param {string} [board=''] - The board to filter by.
 * @returns {Promise<string>} - A JSON string of the securities stock data.
 * @throws {Error} If the request fails or invalid parameters are provided.
 */
export async function getSecuritiesStock(code = '', sector = '', board = '') {
  // Input validation
  if (typeof code !== 'string' || typeof sector !== 'string' || typeof board !== 'string') {
    throw new Error('code, sector, and board must be strings');
  }

  const baseUrl = "https://www.idx.co.id/primary/StockData/GetSecuritiesStock";
  const queryParams = new URLSearchParams({
    start: 0,
    length: 9999,
    code,
    sector,
    board,
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
    console.error("Error fetching securities stock data:", error.message);
    throw new Error(`Failed to fetch securities stock data: ${error.message}`);
  }
}
