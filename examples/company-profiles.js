import {
  getCompanyProfiles,
  getCompanyProfileDetail,
  configureRateLimit,
  clearApiCache
} from '../listed-companies/companyProfiles.js';

import fs from 'fs';

// Configure a more conservative rate limit
configureRateLimit(3, 2000); // 3 requests per 2 seconds

async function fetchAndSaveCompanyData() {
  try {
    const allCompanies = JSON.parse(fs.readFileSync('../data/allCompanies.json', 'utf-8'));

    // console.log('Fetching company profiles...');
    // const allCompanies = await getCompanyProfiles();
    // fs.writeFileSync('../data/allCompanies.json', JSON.stringify(allCompanies, null, 2));
    // console.log(`Found ${allCompanies.recordsTotal} companies`);

    // Load existing data if it exists
    let kodeEmitenJson = {};
    const filePath = '../data/companyDetailsByKodeEmiten.json';

    if (fs.existsSync(filePath)) {
      const fileContent = fs.readFileSync(filePath, 'utf-8');
      kodeEmitenJson = JSON.parse(fileContent || '{}');
      console.log(`Loaded ${Object.keys(kodeEmitenJson).length} existing company records`);
    }

    let processedCount = 0;

    for (const company of allCompanies.data) {
      if (kodeEmitenJson[company.KodeEmiten]) {
        console.log(`Skipping already processed ${company.KodeEmiten}`);
        continue;
      }

      try {
        console.log(`Fetching details for ${company.KodeEmiten} (${company.NamaEmiten})...`);

        const details = await getCompanyProfileDetail(company.KodeEmiten);
        kodeEmitenJson[company.KodeEmiten] = details;

        // Save incrementally to avoid data loss on crash
        fs.writeFileSync(filePath, JSON.stringify(kodeEmitenJson, null, 2));
        console.log(`Saved details for ${company.KodeEmiten}`);
        processedCount++;
      } catch (companyError) {
        console.error(`Error processing ${company.KodeEmiten}:`, companyError.message);
        
        const now = new Date();
        console.log(`Sleeping for 5 minutes at ${now.toLocaleString()}`);
      
        await sleep(5 * 60 * 1000); // 15 minutes in milliseconds
      
        const afterSleep = new Date();
        console.log(`Woke up at ${afterSleep.toLocaleString()}`);
      }

      console.log('-----------------------------------');
    }

    console.log(`Data collection completed. ${processedCount} new companies processed.`);

    // Optional: Clear the cache when done
    // clearApiCache();

  } catch (error) {
    console.error('Error in data collection process:', error);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}


// Execute the data collection
fetchAndSaveCompanyData();
