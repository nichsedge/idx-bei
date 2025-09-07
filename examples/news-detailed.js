import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

// __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// === Configuration ===
const INPUT_FILE_NAME = "idx_news_20250701_to_20250708.json";
const OUTPUT_FILE_NAME = "idx_news_detailed_20250701_to_20250708.json";
const DATA_DIR = path.join(__dirname, '../data/news');
const INPUT_FILE_PATH = path.join(DATA_DIR, INPUT_FILE_NAME);
const OUTPUT_FILE_PATH = path.join(DATA_DIR, OUTPUT_FILE_NAME);

const NEWS_DETAIL_API_BASE_URL = "https://www.idx.co.id/primary/NewsAnnouncement/GetNewsDetailWithLocale";
const REQUEST_HEADERS = {
  "accept": "application/json, text/plain, */*",
  "sec-ch-ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Google Chrome\";v=\"138\"",
  "sec-ch-ua-mobile": "?0",
  "sec-ch-ua-platform": "\"Linux\""
};
const REQUEST_REFERRER = "https://www.idx.co.id/en/news";
const DELAY_MS = 1000; // 1 second delay between requests

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

async function readJsonFile(filePath) {
  try {
    const fileContent = await fs.readFile(filePath, 'utf8');
    return JSON.parse(fileContent);
  } catch (error) {
    if (error.code === 'ENOENT') {
      return null; // File not found
    }
    throw error;
  }
}

async function writeJsonFile(filePath, data) {
  await fs.writeFile(filePath, JSON.stringify(data, null, 2));
}

async function fetchNewsDetail(newsId, index, total) {
  try {
    console.log(`Fetching detail ${index + 1}/${total} for news ID: ${newsId}`);
    
    const url = `${NEWS_DETAIL_API_BASE_URL}?locale=en-us&newsId=${newsId}`;
    const response = await fetch(url, {
      headers: REQUEST_HEADERS,
      referrer: REQUEST_REFERRER,
      method: "GET",
      mode: "cors",
      credentials: "omit"
    });

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    
    return await response.json();

  } catch (error) {
    console.error(`Error fetching detail for ${newsId}:`, error.message);
    return null;
  }
}

// === Main Function ===
async function fetchAllNewsDetails() {
  await ensureDataDirectory();

  try {
    console.log(`Reading input file: ${INPUT_FILE_PATH}`);
    const inputData = await readJsonFile(INPUT_FILE_PATH);
    
    if (!inputData) {
      throw new Error(`Input file not found: ${INPUT_FILE_PATH}`);
    }

    const newsItems = inputData.data || [];
    console.log(`Found ${newsItems.length} news items to process`);

    if (newsItems.length === 0) {
      console.log("No news items to process");
      return;
    }

    const detailedNews = [];
    let successCount = 0;
    let errorCount = 0;

    for (let i = 0; i < newsItems.length; i++) {
      const newsItem = newsItems[i];
      const newsId = newsItem.ItemId;

      if (!newsId) {
        console.warn(`No ItemId found for news item at index ${i}`);
        errorCount++;
        continue;
      }

      const detail = await fetchNewsDetail(newsId, i, newsItems.length);

      if (detail) {
        detailedNews.push(detail);
        successCount++;
      } else {
        errorCount++;
      }

      if (i < newsItems.length - 1) {
        await delay(DELAY_MS);
      }
    }

    const finalData = {
      total: detailedNews.length,
      data: detailedNews
    };

    await writeJsonFile(OUTPUT_FILE_PATH, finalData);

    console.log(`\n=== Summary ===`);
    console.log(`Total news items processed: ${newsItems.length}`);
    console.log(`Successfully fetched details: ${successCount}`);
    console.log(`Failed to fetch details: ${errorCount}`);
    console.log(`Output saved to: ${OUTPUT_FILE_PATH}`);

  } catch (error) {
    console.error("Fatal error:", error.message);
    process.exit(1);
  }
}

// === Retry Failed Function ===
async function retryFailedDetails() {
  await ensureDataDirectory();

  try {
    console.log(`Reading previous results from: ${OUTPUT_FILE_PATH}`);
    let previousData = await readJsonFile(OUTPUT_FILE_PATH);
    
    if (!previousData) {
      console.log("No previous results found. Running full fetch instead...");
      return await fetchAllNewsDetails();
    }

    let newsItems = previousData.data || [];

    const originalInput = await readJsonFile(INPUT_FILE_PATH);
    if (!originalInput) {
      throw new Error(`Original input file not found: ${INPUT_FILE_PATH}`);
    }

    const originalIds = new Set(originalInput.data.map(item => item.ItemId));
    const fetchedIds = new Set(newsItems.map(item => item.ItemId || item.Id));
    
    const missingIds = Array.from(originalIds).filter(id => !fetchedIds.has(id));
    
    console.log(`Found ${missingIds.length} failed items to retry out of ${originalIds.size} total original items.`);

    if (missingIds.length === 0) {
      console.log("No failed items to retry!");
      return;
    }

    let successCount = 0;
    let stillFailedCount = 0;

    for (let i = 0; i < missingIds.length; i++) {
      const newsId = missingIds[i];

      console.log(`Retrying ${i + 1}/${missingIds.length} - News ID: ${newsId}`);

      const detail = await fetchNewsDetail(newsId, i, missingIds.length);

      if (detail) {
        newsItems.push(detail);
        successCount++;
      } else {
        stillFailedCount++;
      }

      if (i < missingIds.length - 1) {
        await delay(DELAY_MS);
      }
    }

    const finalData = {
      total: newsItems.length,
      data: newsItems
    };

    await writeJsonFile(OUTPUT_FILE_PATH, finalData);

    console.log(`\n=== Retry Summary ===`);
    console.log(`Items attempted to retry: ${missingIds.length}`);
    console.log(`Successfully retried: ${successCount}`);
    console.log(`Still failed: ${stillFailedCount}`);
    console.log(`Updated data saved to: ${OUTPUT_FILE_PATH}`);

  } catch (error) {
    console.error("Fatal error during retry:", error.message);
    process.exit(1);
  }
}

// Run - check command line argument
const args = process.argv.slice(2);
if (args.includes('--retry')) {
  console.log("Starting retry for failed items...");
  retryFailedDetails().catch(error => {
    console.error("Fatal error:", error);
    process.exit(1);
  });
} else {
  console.log("Starting IDX news detail fetcher...");
  fetchAllNewsDetails().catch(error => {
    console.error("Fatal error:", error);
    process.exit(1);
  });
}
