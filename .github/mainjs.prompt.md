import fs from "fs";

import { 
    getCompanyProfiles, getCompanyProfileDetail, getIssuedHistory, getProfileAnnouncement, getCalendar, getFinancialReport, getNameChangeHistory, getCoreBusinessHistory, getShareholderHistory, getControllingShareholderHistory, getCashDividend, getStockDividend 
} from '../listed-companies/companyProfiles.js';

import { getSecuritiesStock } from '../market-data/stocks-data/stock-list/getSecuritiesStock.js';

import { getIndexIC } from "../market-data/trading-summary/index-summary/getIndexIC.js";

import * as mp from '../members-and-participants/memberProfiles.js'

import { getEmiten } from "../market-data/structured-warrant-sw/structured-warrant-information/getEmiten.js";


// console.log(response.json() );

const data = await getCompanyProfiles();
console.log(data.slice(0, 5));




// // Write JSON to file
// fs.writeFile('data.json', data, (err) => {
//   if (err) {
//     console.error('Error writing to file', err);
//   } else {
//     console.log('Data successfully written to file');
//   }
// });

