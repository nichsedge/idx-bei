import fs from 'fs';
import path from 'path';

// === Configuration ===
const INPUT_FILE = "../data/news/idx_news_20250701_to_20250708.json";
const OUTPUT_DIR = "../data/news";
const OUTPUT_FILE = "idx_news_detailed_20250701_to_20250708.json";

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// === Helper Functions ===
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function fetchNewsDetail(newsId, index, total) {
  try {
    console.log(`Fetching detail ${index + 1}/${total} for news ID: ${newsId}`);
    
    const data = await fetch(`https://www.idx.co.id/primary/NewsAnnouncement/GetNewsDetailWithLocale?locale=en-us&newsId=${newsId}`, {
      "headers": {
        "accept": "application/json, text/plain, */*",
        "sec-ch-ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Google Chrome\";v=\"138\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Linux\""
      },
      "referrer": "https://www.idx.co.id/en/news",
      "body": null,
      "method": "GET",
      "mode": "cors",
      "credentials": "omit"
    });

    const res = await data.json();
    return res;

  } catch (error) {
    console.error(`Error fetching detail for ${newsId}:`, error.message);
    return null;
  }
}

// === Main Function ===
async function fetchAllNewsDetails() {
  try {
    // Read the input file
    console.log(`Reading input file: ${INPUT_FILE}`);
    
    if (!fs.existsSync(INPUT_FILE)) {
      throw new Error(`Input file not found: ${INPUT_FILE}`);
    }

    const inputData = JSON.parse(fs.readFileSync(INPUT_FILE, 'utf8'));
    const newsItems = inputData.data || [];

    console.log(`Found ${newsItems.length} news items to process`);

    if (newsItems.length === 0) {
      console.log("No news items to process");
      return;
    }

    const detailedNews = [];
    let successCount = 0;
    let errorCount = 0;

    // Process each news item
    for (let i = 0; i < newsItems.length; i++) {
      const newsItem = newsItems[i];
      const newsId = newsItem.ItemId;

      if (!newsId) {
        console.warn(`No ItemId found for news item at index ${i}`);
        errorCount++;
        continue;
      }

      // Fetch detailed information
      const detail = await fetchNewsDetail(newsId, i, newsItems.length);

      if (detail) {
        // Just push the detail directly
        detailedNews.push(detail);
        successCount++;
      } else {
        errorCount++;
      }

      // Add delay between requests to avoid rate limiting
      if (i < newsItems.length - 1) {
        await delay(1000); // 1 second delay between requests
      }
    }

    // Save just the data with details added
    const outputPath = path.join(OUTPUT_DIR, OUTPUT_FILE);
    const finalData = {
      total: detailedNews.length,
      data: detailedNews
    };

    fs.writeFileSync(outputPath, JSON.stringify(finalData, null, 2));

    console.log(`\n=== Summary ===`);
    console.log(`Total news items processed: ${newsItems.length}`);
    console.log(`Successfully fetched details: ${successCount}`);
    console.log(`Failed to fetch details: ${errorCount}`);
    console.log(`Output saved to: ${outputPath}`);

  } catch (error) {
    console.error("Fatal error:", error.message);
    process.exit(1);
  }
}

// === Retry Failed Function ===
async function retryFailedDetails() {
  try {
    const outputPath = path.join(OUTPUT_DIR, OUTPUT_FILE);
    
    console.log(`Reading previous results from: ${outputPath}`);
    
    if (!fs.existsSync(outputPath)) {
      console.log("No previous results found. Running full fetch instead...");
      return await fetchAllNewsDetails();
    }

    const previousData = JSON.parse(fs.readFileSync(outputPath, 'utf8'));
    const newsItems = previousData.data || [];

    // Find items that are missing (only have original data, no detail fetched)
    const failedItems = [];
    const originalInput = JSON.parse(fs.readFileSync(INPUT_FILE, 'utf8'));
    const originalIds = originalInput.data.map(item => item.ItemId);
    const fetchedIds = newsItems.map(item => item.ItemId || item.Id);
    
    // Find IDs that weren't successfully fetched
    const missingIds = originalIds.filter(id => !fetchedIds.includes(id));
    
    for (const id of missingIds) {
      failedItems.push({ ItemId: id });
    }
    
    console.log(`Found ${failedItems.length} failed items to retry out of ${newsItems.length} total`);

    if (failedItems.length === 0) {
      console.log("No failed items to retry!");
      return;
    }

    let successCount = 0;
    let stillFailedCount = 0;

    // Retry failed items
    for (let i = 0; i < failedItems.length; i++) {
      const newsItem = failedItems[i];
      const newsId = newsItem.ItemId;

      if (!newsId) {
        console.warn(`No ItemId found for failed item at index ${i}`);
        stillFailedCount++;
        continue;
      }

      console.log(`Retrying ${i + 1}/${failedItems.length} - News ID: ${newsId}`);

      // Fetch detailed information
      const detail = await fetchNewsDetail(newsId, i, failedItems.length);

      if (detail) {
        // Just add the detail to the list
        newsItems.push(detail);
        successCount++;
      } else {
        stillFailedCount++;
      }

      // Add delay between requests
      if (i < failedItems.length - 1) {
        await delay(1000);
      }
    }

    // Save updated data - just the clean data structure
    const finalData = {
      total: newsItems.length,
      data: newsItems
    };

    fs.writeFileSync(outputPath, JSON.stringify(finalData, null, 2));

    console.log(`\n=== Retry Summary ===`);
    console.log(`Items attempted to retry: ${failedItems.length}`);
    console.log(`Successfully retried: ${successCount}`);
    console.log(`Still failed: ${stillFailedCount}`);
    console.log(`Total successful details: ${totalSuccessful}`);
    console.log(`Total failed details: ${totalFailed}`);
    console.log(`Updated data saved to: ${outputPath}`);

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