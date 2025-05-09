import {
  getCompanyProfiles,
  getCompanyProfileDetail,
  configureRateLimit,
  clearApiCache
} from './listed-companies/companyProfiles.js';

import fs from 'fs';

// Configure a more conservative rate limit to avoid being blocked
configureRateLimit(3, 2000); // 3 requests per 2 seconds

async function fetchAndSaveCompanyData() {
  try {
    console.log('Fetching company profiles...');
    const allCompanies = await getCompanyProfiles();
    console.log(`Found ${allCompanies.recordsTotal} companies`);

    const kodeEmitenJson = {};

    // Process all companies
    for (const company of allCompanies.data.slice(0, 5)) {
      try {
        console.log(`Fetching details for ${company.KodeEmiten} (${company.NamaEmiten})...`);

        const details = await getCompanyProfileDetail(company.KodeEmiten);

        kodeEmitenJson[company.KodeEmiten] = details;

        console.log(`Successfully fetched details for ${company.KodeEmiten}`);
        console.log('-----------------------------------');
      } catch (companyError) {
        console.error(`Error processing company ${company.KodeEmiten}:`, companyError.message);
      }
    }

    // Save to JSON file
    fs.writeFileSync('companyDetailsByKodeEmiten.json', JSON.stringify(kodeEmitenJson, null, 2));

    console.log('Data collection completed and saved to companyDetailsByKodeEmiten.json');

    // Optional: Clear the cache when done
    // clearApiCache();

  } catch (error) {
    console.error('Error in data collection process:', error);
  }
}

// Execute the data collection
fetchAndSaveCompanyData();
