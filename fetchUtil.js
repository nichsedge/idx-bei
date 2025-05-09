export const fetchData = async (url, options = {}) => {
    try {
        const response = await fetch(url, {
            headers: {
                "accept": "application/json, text/plain, */*",
                "accept-language": "en-US,en;q=0.9",
                "priority": "u=1, i",
                "sec-ch-ua": "\"Chromium\";v=\"136\", \"Microsoft Edge\";v=\"136\", \"Not.A/Brand\";v=\"99\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\"",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                // "cookie": "auth.strategy=local; __cf_bm=Jfn0aP1F2yAVlfeo0QTrYm_lL3YQCArHK5YgmNKmebk-1746771162-1.0.1.1-KZWd87iFiUdX3.urSecWz1vamCNkWL4kXJLW_YRaZ2_cIPQB3afN4bYci7ZXquqhWK_4flE_oLA3knTvDVAx8feAwa9v1WY8W_phm42xw9k; _cfuvid=0sriSwrHmZBKshDFM6QTHp14NkUva88E_6YGQClyeWQ-1746771162547-0.0.1.1-604800000; _gid=GA1.3.1296679557.1746771165; _ga_VDBWS0BLZR=GS2.1.s1746771164$o1$g1$t1746771194$j0$l0$h0; _ga=GA1.1.957693586.1746771164",
                // "Referer": "https://www.idx.co.id/id/perusahaan-tercatat/profil-perusahaan-tercatat/",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                ...options.headers,
            },
            referrerPolicy: "strict-origin-when-cross-origin",
            mode: "cors",
            credentials: "include",
            ...options,
        });

        if (!response.ok) {
            throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
        }
        const jsonData = await response.json();
        return JSON.stringify(jsonData, null, 2);
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
};
