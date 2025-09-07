"use strict";

import { fetchData } from "../../../../fetchUtil.js";

/**
 * Retrieves structured warrant trading data from IDX.
 * @param {Object} [options] - Options for filtering and pagination.
 * @param {number} [options.length=9999] - The number of records to retrieve.
 * @param {string} [options.issuer=''] - The issuer filter for the structured warrants.
 * @param {string} [options.swType=''] - The structured warrant type filter.
 * @param {number} [options.start=0] - The starting index for pagination.
 * @param {string} [options.dateFrom=''] - The start date for the trading data (YYYY-MM-DD format).
 * @param {string} [options.dateTo=''] - The end date for the trading data (YYYY-MM-DD format).
 * @returns {Promise<string>} - A JSON string of the structured warrant trading data.
 * @throws {Error} If the request fails or invalid parameters are provided.
 */
export async function getSwTrading({
  length = 9999,
  issuer = '',
  swType = '',
  start = 0,
  dateFrom = '',
  dateTo = ''
} = {}) {
  // Input validation
  if (typeof length !== 'number' || typeof start !== 'number') {
    throw new Error('length and start must be numbers');
  }
  if (length < 1 || start < 0) {
    throw new Error('length must be positive and start must be >=0');
  }
  if (typeof issuer !== 'string' || typeof swType !== 'string') {
    throw new Error('issuer and swType must be strings');
  }
  if (dateFrom && !/^\d{4}-\d{2}-\d{2}$/.test(dateFrom)) {
    throw new Error('dateFrom must be in YYYY-MM-DD format if provided');
  }
  if (dateTo && !/^\d{4}-\d{2}-\d{2}$/.test(dateTo)) {
    throw new Error('dateTo must be in YYYY-MM-DD format if provided');
  }

  const baseUrl = "https://www.idx.co.id/secondary/get/StructuredWarrant/Trading";
  const queryParams = new URLSearchParams({
    length,
    issuer,
    SW: swType,
    start,
    datefrom: dateFrom,
    dateto: dateTo
  }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/structured-warrant-sw/structured-warrant-summary/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response["Results"], null, 2);
  } catch (error) {
    console.error("Error fetching structured warrant trading data:", error.message);
    throw new Error(`Failed to fetch structured warrant trading data: ${error.message}`);
  }
}
