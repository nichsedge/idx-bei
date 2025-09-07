"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves government issuer data from IDX.
 * @param {number} [pageSize=1000] - The number of records to retrieve per page.
 * @param {number} [pageNumber=1] - The page number to retrieve.
 * @returns {Promise<string>} - A JSON string of the government issuer data.
 * @throws {Error} If the request fails or invalid parameters are provided.
 */
export async function getGovIssuer(pageSize = 1000, pageNumber = 1) {
  // Input validation
  if (typeof pageSize !== 'number' || typeof pageNumber !== 'number') {
    throw new Error('pageSize and pageNumber must be numbers');
  }
  if (pageSize < 1 || pageNumber < 1) {
    throw new Error('pageSize and pageNumber must be positive numbers');
  }

  const baseUrl = "https://www.idx.co.id/primary/BondSukuk/GetGovIssuer";
  const queryParams = new URLSearchParams({ pageSize, pageNumber }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/bonds-sukuk/corporate-bonds-sukuk/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching government issuer data:", error.message);
    throw new Error(`Failed to fetch government issuer data: ${error.message}`);
  }
}
