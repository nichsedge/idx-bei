import { fetchData } from "../../../utils/template.js";

/**
 * Retrieves securities stock data from IDX based on specified parameters.
 * @param {string} [code=''] - The stock code to filter by.
 * @param {string} [sector=''] - The sector to filter by.
 * @param {string} [board=''] - The board to filter by.
 * @returns {Promise<string>} - A JSON string of the securities stock data.
 */
export async function getSecuritiesStock(code = '', sector = '', board = '') {
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
    const response = await fetchData(url, referrer);
    return JSON.stringify(response, null, 2);
  } catch (error) {
    console.error("Error fetching securities stock data:", error.message);
    throw new Error(`Failed to fetch securities stock data: ${error.message}`);
  }
}
