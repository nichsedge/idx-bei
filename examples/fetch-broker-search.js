// saveBrokerSearch.js
import fs from 'fs/promises';
import { getBrokerSearch } from '../members-and-participants/memberProfiles.js';

async function fetchAndSaveBrokerSearch() {
  try {
    const data = await getBrokerSearch();
    
    // Save to JSON file
    await fs.writeFile('../data/brokerSearch.json', JSON.stringify(data, null, 2));
    console.log('Broker search data saved to brokerSearch.json');
  } catch (error) {
    console.error('Error fetching or saving broker search data:', error);
  }
}

fetchAndSaveBrokerSearch();
