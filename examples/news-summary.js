import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

// __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// === Configuration ===
const BASE_URL = "https://www.idx.co.id/primary/NewsAnnouncement/GetNewsSearch";
const START_DATE = "20250701";
const END_DATE = "20250708";
const DATA_DIR = path.join(__dirname, "../data/news"); // Save news data separately
const OUTPUT_FILE_NAME = `idx_news_${START_DATE}_to_${END_DATE}.json`;
const OUTPUT_FILE_PATH = path.join(DATA_DIR, OUTPUT_FILE_NAME);

const HEADERS = {
  "accept": "application/json, text/plain, */*",
  "accept-language": "en-US,en;q=0.9",
  "priority": "u=1, i",
  "sec-ch-ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Google Chrome\";v=\"138\"",
  "sec-ch-ua-mobile": "?0",
  "sec-ch-ua-platform": "\"Linux\"",
  "sec-fetch-dest": "empty",
  "sec-fetch-mode": "cors",
  "sec-fetch-site": "same-origin",
  "referer": `https://www.idx.co.id/en/news/news?ds=${START_DATE}&de=${END_DATE}&qs=&p=1`
};

const PAGE_SIZE = 12;
const DELAY_MS = 1000; // Delay between page fetches
const RATE_LIMIT_RETRY_DELAY_MS = 30000; // Delay if rate limit hit (30 seconds)

// === Helper Functions ===
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function ensureDataDirectory() {
  try {
    await fs.mkdir(DATA_DIR, { recursive: true });
  } catch (error) {
    if (error.code !== 'EEXIST') {
      console.error('Error creating data directory:', error);
      process.exit(1);
    }
  }
}

function buildUrl(pageNumber) {
  const params = new URLSearchParams({
    locale: "en-us",
    pageNumber,
    pageSize: PAGE_SIZE,
    dateFrom: START_DATE,
    dateTo: END_DATE,
    keyword: ""
  });
  return `${BASE_URL}?${params.toString()}`;
}

// === Main Scraper ===
async function fetchAllNewsPages() {
  await ensureDataDirectory();

  let pageNumber = 1;
  let hasMoreData = true;
  const allNews = [];

  console.log("Starting news scraping...");

  while (hasMoreData) {
    try {
      console.log(`Fetching news page ${pageNumber}...`);

      const response = await fetch(buildUrl(pageNumber), {
        method: 'GET',
        headers: HEADERS,
        mode: 'cors',
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }

      const data = await response.json();

      if (data?.Items?.length > 0) {
        allNews.push(...data.Items);
        console.log(`Fetched ${data.Items.length} articles from page ${pageNumber}`);
        pageNumber++;
        await delay(DELAY_MS); // Delay between pages
      } else {
        hasMoreData = false;
        console.log("No more news data.");
      }

    } catch (error) {
      console.error(`Error on page ${pageNumber}:`, error.message);

      if (error.message.includes('429')) {
        console.log(`Rate limit hit. Retrying after ${RATE_LIMIT_RETRY_DELAY_MS / 1000} seconds...`);
        await delay(RATE_LIMIT_RETRY_DELAY_MS);
      } else {
        hasMoreData = false;
      }
    }
  }

  // Save final data
  await fs.writeFile(OUTPUT_FILE_PATH, JSON.stringify({ total: allNews.length, data: allNews }, null, 2));

  console.log(`News scraping complete. Total articles: ${allNews.length}`);
  console.log(`Data saved to: ${OUTPUT_FILE_PATH}`);
}

// Run
fetchAllNewsPages().catch(error => {
  console.error("Fatal error:", error);
});
