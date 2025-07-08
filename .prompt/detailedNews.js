const data = await fetch("https://www.idx.co.id/primary/NewsAnnouncement/GetNewsDetailWithLocale?locale=en-us&newsId=fe2d6bee-7959-f011-b138-0050569d3b40", {
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
console.log(res)