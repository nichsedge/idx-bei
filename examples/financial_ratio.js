import fs from 'fs';

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

// Create data directory if it doesn't exist
const DATA_DIR = '../data';
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
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
      
      // Save individual page data
      // fs.writeFileSync(
      //   `${DATA_DIR}/financial_ratio_page_${pageNumber}.json`, 
      //   JSON.stringify(data, null, 2)
      // );
      
      // Check if we have more data to fetch
      if (data.data && data.data.length > 0) {
        allData.push(...data.data);
        console.log(`Retrieved ${data.data.length} records from page ${pageNumber}`);
        pageNumber++;
        
        // Add delay to respect rate limits (adjust as needed)
        await delay(1000);
      } else {
        hasMoreData = false;
        console.log('No more data available.');
      }
    } catch (error) {
      console.error(`Error on page ${pageNumber}:`, error.message);
      
      if (error.message.includes('429')) {
        console.log('Rate limit hit. Waiting for 30 seconds before retrying...');
        await delay(30000); // Wait 30 seconds if rate limited
      } else {
        hasMoreData = false;
      }
    }
  }
  
  // Save combined data
  fs.writeFileSync(
    `${DATA_DIR}/financial_ratio.json`, 
    JSON.stringify({ totalRecords: allData.length, data: allData }, null, 2)
  );
  
  console.log(`Data collection complete. Total records: ${allData.length}`);
}

// Execute the fetching process
fetchAllPages().catch(error => {
  console.error('Fatal error:', error);
});