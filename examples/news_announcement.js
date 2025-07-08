import fs from 'fs';

// === Configuration ===
const BASE_URL = "https://www.idx.co.id/primary/NewsAnnouncement/GetNewsSearch";
const START_DATE = "20250701";
const END_DATE = "20250708";
const DATA_DIR = "../data/news"; // Save news data separately

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

// Ensure data directory exists
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// === Helper Functions ===
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

function buildUrl(pageNumber) {
  const params = new URLSearchParams({
    locale: "en-us",
    pageNumber,
    pageSize: 12,
    dateFrom: START_DATE,
    dateTo: END_DATE,
    keyword: ""
  });
  return `${BASE_URL}?${params.toString()}`;
}

// === Main Scraper ===
async function fetchAllNewsPages() {
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
      console.log(data)

      if (data?.Items?.length > 0) {
        allNews.push(...data.Items);
        console.log(`Fetched ${data.Items.length} articles from page ${pageNumber}`);
        pageNumber++;
        await delay(1000); // Delay between pages
      } else {
        hasMoreData = false;
        console.log("No more news data.");
      }

    } catch (error) {
      console.error(`Error on page ${pageNumber}:`, error.message);

      if (error.message.includes('429')) {
        console.log("Rate limit hit. Retrying after 30 seconds...");
        await delay(30000);
      } else {
        hasMoreData = false;
      }
    }
  }

  // Save final data
  const outputPath = `${DATA_DIR}/idx_news_${START_DATE}_to_${END_DATE}.json`;
  fs.writeFileSync(outputPath, JSON.stringify({ total: allNews.length, data: allNews }, null, 2));

  console.log(`News scraping complete. Total articles: ${allNews.length}`);
  console.log(`Data saved to: ${outputPath}`);
}

// Run
fetchAllNewsPages().catch(error => {
  console.error("Fatal error:", error);
});
