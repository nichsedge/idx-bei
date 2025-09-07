"use strict";

import { fetchData } from "../../../fetchUtil.js";

/**
 * Retrieves the PD quotation for a specified instrument from IDX.
 * @param {string} [instrument='FR0097'] - The instrument code to retrieve the PD quotation for.
 * @returns {Promise<string>} - A JSON string of the PD quotation data.
 * @throws {Error} If the request fails or invalid parameter is provided.
 */
export async function getPdQuotation(instrument = 'FR0097') {
  // Input validation
  if (typeof instrument !== 'string') {
    throw new Error('instrument must be a string');
  }

  const baseUrl = "https://www.idx.co.id/primary/BondSukuk/GetPdQuotation";
  const queryParams = new URLSearchParams({
    Instrument: instrument
  }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/bonds-sukuk/pds-quotation/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const response = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching PD quotation:", error.message);
    throw new Error(`Failed to fetch PD quotation: ${error.message}`);
  }
}
