import { fetchData } from "../../../utils/template.js";

/**
 * Retrieves the list of boards from IDX.
 * @returns {Promise<string>} - A JSON string of the boards data.
 */
export async function getBoards() {
  const baseUrl = "https://www.idx.co.id/primary/Helper/GetBoards";
  const queryParams = new URLSearchParams({
    language: 'id-id'
  }).toString();
  const url = `${baseUrl}?${queryParams}`;
  const referrer = "https://www.idx.co.id/en/market-data/stocks-data/stock-list/";

  try {
    const response = await fetchData(url, referrer);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching boards:", error.message);
    throw new Error(`Failed to fetch boards: ${error.message}`);
  }
}
