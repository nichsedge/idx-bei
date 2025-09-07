"use strict";

import { fetchData } from "../../fetchUtil.js";

/**
 * Retrieves the top SLB lender value data from IDX.
 * @returns {Promise<string>} - A JSON string of the top SLB lender value data.
 * @throws {Error} If the request fails.
 */
export async function getSlbTopLenderVal() {
  const url = "https://www.idx.co.id/primary/Slb/TopLenderVal";
  const referrer = "https://www.idx.co.id/en/market-data/securities-borrowing-and-lending/";

  try {
    const cacheOptions = { useCache: true, ttl: 5 * 60 * 1000 }; // 5 minutes
    const retryOptions = { maxRetries: 3, baseDelay: 1000 };
    const res = await fetchData(url, { headers: { referrer } }, cacheOptions, retryOptions);
    return JSON.stringify(res, null, 2);
  } catch (error) {
    console.error("Error fetching SLB top lender value data:", error.message);
    throw new Error(`Failed to fetch SLB top lender value data: ${error.message}`);
  }
}
