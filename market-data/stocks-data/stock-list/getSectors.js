import { fetchData } from "../../../utils/template.js";

/**
 * Retrieves the list of sectors from IDX.
 * @returns {Promise<string>} - A JSON string of the sectors data.
 */
export async function getSectors() {
  const baseUrl = "https://www.idx.co.id/primary/Helper/GetSectors";
  const queryParams = new URLSearchParams({
    language: 'id-id'
  }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/stocks-data/stock-list/";

  try {
    const response = await fetchData(url, referrer);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching sectors:", error.message);
    throw new Error(`Failed to fetch sectors: ${error.message}`);
  }
}
