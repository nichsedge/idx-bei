import fs from 'fs';

// Helper function to fetch data from the server
async function fetchData(url, referrer) {
  console.log(`fetching ${url}`)
  const response = await fetch(url, {
    headers: {
      "accept": "application/json, text/plain, */*",
      "accept-language": "id-id,en;q=0.9",
      // "priority": "u=1, i",
      // "sec-ch-ua": "\"Not)A;Brand\";v=\"99\", \"Google Chrome\";v=\"127\", \"Chromium\";v=\"127\"",
      // "sec-ch-ua-mobile": "?0",
      // "sec-ch-ua-platform": "\"Linux\"",
      // "sec-fetch-dest": "empty",
      // "sec-fetch-mode": "cors",
      // "sec-fetch-site": "same-origin"
    },
    referrer: referrer,
    referrerPolicy: "strict-origin-when-cross-origin",
    method: "GET",
    mode: "cors",
    credentials: "include"
  });

  if (!response.ok) {
    throw new Error(`HTTP error! Status: ${response.status}`);
  }
  
  return response.json();
}

export {fetchData};