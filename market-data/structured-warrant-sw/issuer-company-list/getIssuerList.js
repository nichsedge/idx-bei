"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves the list of issuers from IDX.
 * @param {number} [length=9999] - The number of issuers to retrieve.
 * @param {number} [start=0] - The starting index for pagination.
 * @returns {Promise<string>} - A JSON string of the issuer list.
 * @throws {Error} If the request fails or invalid parameters are provided.
 */
export async function getIssuerList(length = 9999, start = 0) {
  // Input validation
  if (typeof length !== 'number' || typeof start !== 'number') {
    throw new Error('length and start must be numbers');
  }
  if (length < 1 || start < 0) {
    throw new Error('length must be positive and start must be >=0');
  }

  const baseUrl = "https://www.idx.co.id/primary/StructuredWarrant/GetIssuerList";
  const queryParams = new URLSearchParams({ length, start }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/structured-warrant-sw/issuer-company-list/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching issuer list:", error.message);
    throw new Error(`Failed to fetch issuer list: ${error.message}`);
  }
}
