"use strict";

import fs from "fs";
import { fetchData } from "../../../../fetchUtil.js";

const pageSize = 100;

/**
 * Builds the fetch URL for bond data.
 * @param {number} indexFrom - The starting index for pagination.
 * @param {number} bondType - The type of bond (1 for corporate, 2 for government).
 * @param {number} instrumentId - The instrument ID (0 for all, 1 for obligation, 2 for sukuk).
 * @returns {string} - The URL for fetching bond data.
 * @throws {Error} If invalid parameters are provided.
 */
function buildFetchUrl(indexFrom, bondType, instrumentId) {
  if (typeof indexFrom !== 'number' || typeof bondType !== 'number' || typeof instrumentId !== 'number') {
    throw new Error('indexFrom, bondType, and instrumentId must be numbers');
  }
  if (indexFrom < 1 || bondType < 1 || instrumentId < 0) {
    throw new Error('Invalid parameter values: indexFrom and bondType must be >=1, instrumentId >=0');
  }
  return `https://www.idx.co.id/secondary/get/BondSukuk/bond?pageSize=${pageSize}&indexFrom=${indexFrom}&bondType=${bondType}&instrumentId=${instrumentId}`;
}

const referrer = "https://www.idx.co.id/en/market-data/bonds-sukuk/corporate-bonds-sukuk/";

/**
 * Fetches bond data with pagination.
 * @param {number} [indexFrom=1] - The starting index for pagination.
 * @param {number} [bondType=2] - The type of bond (1 for corporate, 2 for government).
 * @param {number} [instrumentId=0] - The instrument ID (0 for all, 1 for obligation, 2 for sukuk).
 * @returns {Promise<string>} - A JSON string of all fetched bond data.
 * @throws {Error} If the request fails or invalid parameters are provided.
 */
export async function getBondSukuk(indexFrom = 1, bondType = 2, instrumentId = 0) {
  // Input validation
  if (typeof indexFrom !== 'number' || typeof bondType !== 'number' || typeof instrumentId !== 'number') {
    throw new Error('indexFrom, bondType, and instrumentId must be numbers');
  }
  if (indexFrom < 1 || bondType < 1 || instrumentId < 0) {
    throw new Error('Invalid parameter values: indexFrom and bondType must be >=1, instrumentId >=0');
  }

  const allResults = [];

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    
    const initialUrl = buildFetchUrl(indexFrom, bondType, instrumentId);
    const initialData = await fetchData(initialUrl, { headers: { referrer } }, cacheOptions, retryOptions);

    const totalResultCount = initialData.ResultCount;
    const totalPages = Math.ceil(totalResultCount / pageSize);

    let currentIndex = indexFrom;
    while (currentIndex <= totalPages) {
      console.log(`Fetching page ${currentIndex} of ${totalPages}`);

      const url = buildFetchUrl(currentIndex, bondType, instrumentId);
      const data = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);

      console.log(`Fetched ${data.Results.length} results from page ${currentIndex}`);
      allResults.push(...data.Results);

      currentIndex += 1; // Move to the next page
    }

    return JSON.stringify(allResults, null, 2);

  } catch (error) {
    console.error('Error fetching bond data:', error.message);
    throw new Error(`Failed to fetch bond data: ${error.message}`);
  }
}
