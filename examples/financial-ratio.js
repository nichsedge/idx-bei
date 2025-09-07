import fs from 'fs/promises'; // Use promise-based fs
import path from 'path'; // Import path module for robust path handling
import { fileURLToPath } from 'url'; // For __dirname equivalent in ES modules

// __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configuration
const BASE_URL = "https://www.idx.co.id/primary/DigitalStatistic/GetApiDataPaginated";
const QUERY_PARAMS = {
  urlName: "LINK_FINANCIAL_DATA_RATIO",
  periodQuarter: 4,
  periodYear: 2024,
  type: "yearly",
  // periodMonth: 4,
  // periodType: "monthly",
  isPrint: false,
  cumulative: false,
  pageSize: 100,
  orderBy: "",
  search: ""
};

const HEADERS = {
  "accept": "application/json, text/plain, */*",
  "accept-language": "en-US,en;q=0.9",
  "priority": "u=1, i",
  "sec-ch-ua": "\"Chromium\";v=\"136\", \"Microsoft Edge\";v=\"136\", \"Not.A/Brand\";v=\"99\"",
  "sec-ch-ua-mobile": "?0",
  "sec-ch-ua-platform": "\"Windows\"",
  "sec-fetch-dest": "empty",
  "sec-fetch-mode": "cors",
  "sec-fetch-site": "same-origin",
  "referer": "https://www.idx.co.id/id/data-pasar/laporan-statistik/digital-statistic/monthly/financial-report-and-ratio-of-listed-companies/financial-data-and-ratio"
};

const DATA_DIR = path.join(__dirname, '../data');
const DELAY_MS = 1000; // Delay between page fetches
const RATE_LIMIT_RETRY_DELAY_MS = 30000; // Delay if rate limit hit (30 seconds)

// Create data directory if it doesn't exist
async function ensureDataDirectory() {
  try {
    await fs.mkdir(DATA_DIR, { recursive: true });
  } catch (error) {
    if (error.code !== 'EEXIST') { // Ignore directory already exists error
      console.error('Error creating data directory:', error);
      process.exit(1); // Exit if directory cannot be created
    }
  }
}

// Combine URL with query parameters
function buildUrl(pageNumber) {
  const params = new URLSearchParams({
    ...QUERY_PARAMS,
    pageNumber
  });
  return `${BASE_URL}?${params.toString()}`;
}

// Delay function to handle rate limits
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

// Main function to fetch all pages
async function fetchAllPages() {
  await ensureDataDirectory(); // Ensure data directory exists before fetching

  let pageNumber = 1;
  let hasMoreData = true;
  const allData = [];
  
  console.log('Starting data collection...');
  
  while (hasMoreData) {
    try {
      console.log(`Fetching page ${pageNumber}...`);
      const url = buildUrl(pageNumber);
      
      const response = await fetch(url, { 
        method: 'GET', 
        headers: HEADERS 
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Check if we have more data to fetch
      if (data.data && data.data.length > 0) {
        allData.push(...data.data);
        console.log(`Retrieved ${data.data.length} records from page ${pageNumber}`);
        pageNumber++;
        
        // Add delay to respect rate limits
        await delay(DELAY_MS);
      } else {
        hasMoreData = false;
        console.log('No more data available.');
      }
    } catch (error) {
      console.error(`Error on page ${pageNumber}:`, error.message);
      
      if (error.message.includes('429')) {
        console.log(`Rate limit hit. Waiting for ${RATE_LIMIT_RETRY_DELAY_MS / 1000} seconds before retrying...`);
        await delay(RATE_LIMIT_RETRY_DELAY_MS);
      } else {
        hasMoreData = false;
      }
    }
  }
  
  // Save combined data
  await fs.writeFile(
    path.join(DATA_DIR, 'financial_ratio.json'), 
    JSON.stringify({ totalRecords: allData.length, data: allData }, null, 2)
  );
  
  console.log(`Data collection complete. Total records: ${allData.length}`);
}

// Execute the fetching process
fetchAllPages().catch(error => {
  console.error('Fatal error:', error);
});
