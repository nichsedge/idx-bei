# IDX Web API Endpoint Empirical Verification Report

This document contains empirical verification results for the IDX Web API endpoints (`https://www.idx.co.id/primary/`), including parameter requirements, response payload structures, schema verification status, and quantitative trading utility.

Tested Date: **August 2026**

---

## 🟢 VERIFIED & WORKING ENDPOINTS (Status: 200 OK)

### 1. Daily Stock Summary (OHLCV & Foreign Flow)
- **Endpoint**: `/TradingSummary/GetStockSummary`
- **Method**: `GET`
- **Required Parameters**:
  - `date`: `YYYYMMDD` (e.g. `20260807`)
  - `start`: `0`
  - `length`: `9999`
- **Status**: 🟢 **200 OK** (~963 records per trading day)
- **Quant Utility**: High Alpha — Daily OHLCV, volume, market frequency, foreign buy/sell flow, bid/offer spreads, non-regular market transactions.
- **Payload Schema**:
```json
{
  "draw": 0,
  "recordsTotal": 963,
  "recordsFiltered": 963,
  "data": [
    {
      "No": 1,
      "IDStockSummary": 4069193,
      "Date": "2026-08-07T00:00:00",
      "StockCode": "AADI",
      "StockName": "Adaro Andalan Indonesia Tbk.",
      "Remarks": "--MO1SD0F70000A121------------",
      "Previous": 8950.0,
      "OpenPrice": 9000.0,
      "FirstTrade": 9000.0,
      "High": 9200.0,
      "Low": 8950.0,
      "Close": 9075.0,
      "Change": 125.0,
      "Volume": 3482700.0,
      "Value": 31599307500.0,
      "Frequency": 2736.0,
      "IndexIndividual": 100.0,
      "Offer": 9075.0,
      "OfferVolume": 250.0,
      "Bid": 9050.0,
      "BidVolume": 310.0,
      "ListedShares": 7785855000.0,
      "TradebleShares": 7785855000.0,
      "WeightForIndex": 7785855000.0,
      "ForeignSell": 845200.0,
      "ForeignBuy": 1240100.0,
      "DelistingDate": null,
      "NonRegularVolume": 0.0,
      "NonRegularValue": 0.0,
      "NonRegularFrequency": 0.0,
      "persen": 1.4,
      "percentage": 1.4
    }
  ]
}
```

---

### 2. Daily Broker Summary (Broker Flow)
- **Endpoint**: `/TradingSummary/GetBrokerSummary`
- **Method**: `GET`
- **Required Parameters**:
  - `date`: `YYYYMMDD` (e.g. `20260807`)
  - `start`: `0`
  - `length`: `9999`
- **Status**: 🟢 **200 OK** (~88 active broker firms per day)
- **Quant Utility**: Institutional Flow Tracking — Net volume and transaction value per broker ID (`IDFirm`).
- **Payload Schema**:
```json
{
  "draw": 0,
  "recordsTotal": 88,
  "recordsFiltered": 88,
  "data": [
    {
      "No": 1,
      "IDBrokerSummary": 960758,
      "Date": "2026-08-07T00:00:00",
      "IDFirm": "AD",
      "FirmName": "Sukadana Prima Sekuritas",
      "Volume": 35415900.0,
      "Value": 4351965300.0,
      "Frequency": 461.0
    }
  ]
}
```

---

### 3. Corporate Actions (Listing Activity & Capital Events)
- **Endpoint**: `/ListingActivity/GetIssuedHistory`
- **Method**: `GET`
- **Required Parameters**:
  - `caType` (String): Filter by corporate action type:
    - `BuybackSaham` (Share Buyback)
    - `PrivatePlacement` (Private Placement)
    - `stockSplit` (Stock Split)
    - `reverseStock` (Reverse Stock Split)
    - `hmetd` (Rights Issue)
    - `tanpaHmetd` (Non-rights Issue)
    - `dividenSaham` (Stock Dividend)
    - `sahamBonus` (Bonus Shares)
    - `ipo` (Initial Public Offering)
    - `waran` (Warrants)
    - `gabungUsaha` (Mergers)
    - `kurangModal` (Capital Reduction)
    - `konversiSaham` (Stock Conversion)
  - `dateFrom`: `YYYY-MM-DD` (optional)
  - `dateTo`: `YYYY-MM-DD` (optional)
  - `start`: `0`
  - `length`: `9999`
- **Status**: 🟢 **200 OK** (Discovered via Browser inspection on Nuxt frontend)
- **Quant Utility**: High Alpha — Corporate actions adjustments, share capital expansions, buyback signals, share count changes (`JumlahSaham`, `JumlahSahamSetelahTindakan`).
- **Payload Schema**:
```json
{
  "draw": 0,
  "recordsTotal": 1,
  "recordsFiltered": 1,
  "data": [
    {
      "id": 5531,
      "KodeEmiten": "SIIP",
      "TanggalPencatatan": "2007-11-30T00:00:00",
      "JenisTindakan": "BuybackSaham",
      "JumlahSaham": 8711000.0,
      "JumlahSahamSetelahTindakan": 1043030063.0
    }
  ]
}
```

---

### 4. Full Company Announcements & PDF Filings
- **Endpoint**: `/NewsAnnouncement/GetAllAnnouncement`
- **Method**: `GET`
- **Required Parameters**:
  - `keywords`: String ticker or topic (e.g. `BBCA`) (optional)
  - `pageNumber`: `1`
  - `pageSize`: `100`
  - `lang`: `id` (Indonesian) or `en` (English)
  - `dateFrom`: `YYYY-MM-DD` (optional)
  - `dateTo`: `YYYY-MM-DD` (optional)
- **Status**: 🟢 **200 OK** (Discovered via Browser inspection on Nuxt frontend)
- **Quant Utility**: Event-Driven & NLP Alpha — Real-time company disclosures with direct download URLs to PDF financial reports and shareholder updates (`Attachments.FullSavePath`).
- **Payload Schema**:
```json
{
  "ItemCount": 230,
  "PageCount": 23,
  "PageNumber": 1,
  "PageSize": 10,
  "Items": [
    {
      "Id": "20260807171121-0002/CSG-IVR/2026_id-id",
      "AnnouncementNo": "0002/CSG-IVR/2026",
      "PublishDate": "2026-08-07T17:11:21",
      "Title": "Laporan Bulanan Registrasi Pemegang Efek",
      "Code": "BBCA                                                                                                ",
      "Jenis": "STOCK",
      "Attachments": [
        {
          "PDFFilename": "5915a9d735_8fb5d1e76b.pdf",
          "FullSavePath": "https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/From_EREP/202608/5915a9d735_8fb5d1e76b.pdf",
          "IsAttachment": 0,
          "OriginalFilename": "20260806_BBCA_Laporan Bulanan Registrasi Pemegang Efek/Perubahan Struktur Pemegang Saham_32118244.pdf"
        }
      ]
    }
  ]
}
```

---

### 5. Daily Index Summary (Market Breadth & Benchmark)
- **Endpoint**: `/TradingSummary/GetIndexSummary`
- **Method**: `GET`
- **Required Parameters**: `date=YYYYMMDD&start=0&length=9999`
- **Status**: 🟢 **200 OK** (~45 sectoral and custom indices)
- **Quant Utility**: Macro / Factor Benchmark — `IndexCode` (IHSG, LQ45, IDX30, etc.), index OHLC, total constituent stock count (`NumberOfStock`), market cap.

---

### 6. Exchange Member / Broker Directory
- **Endpoint**: `/ExchangeMember/GetBrokerSearch`
- **Method**: `GET`
- **Required Parameters**: `option=0&license=&start=0&length=9999`
- **Status**: 🟢 **200 OK** (~90 registered exchange member firms)
- **Quant Utility**: Metadata — Map broker codes (e.g., `ZP`, `YP`, `CC`, `AK`) to full firm names and license types.

---

### 7. Listed Company Directory
- **Endpoint**: `/ListedCompany/GetCompanyProfiles`
- **Method**: `GET`
- **Required Parameters**: `start=0&length=9999`
- **Status**: 🟢 **200 OK** (~962 listed companies)
- **Quant Utility**: Stock Universe Filtering — `KodeEmiten`, `Sektor`, `SubSektor`, `Industri`, `SubIndustri`, `PapanPencatatan` (Main/Development/Acceleration board).

---

### 8. Company Profile Detail & Ownership Network
- **Endpoint**: `/ListedCompany/GetCompanyProfilesDetail`
- **Method**: `GET`
- **Required Parameters**: `KodeEmiten={code}&language=id-id`
- **Status**: 🟢 **200 OK**
- **Quant Utility**: Graph & Governance Alpha — Board of Directors (`Direktur`), Commissioners (`Komisaris`), Shareholders (`PemegangSaham`), Audit Committee (`KomiteAudit`), Subsidiaries (`AnakPerusahaan`).

---

### 9. Financial Data & Ratios
- **Endpoint**: `/DigitalStatistic/GetApiDataPaginated`
- **Method**: `GET`
- **Required Parameters**: `urlName=LINK_FINANCIAL_DATA_RATIO&periodQuarter=4&periodYear=2024&type=yearly&pageSize=100&pageNumber=1`
- **Status**: 🟢 **200 OK** (~947 records per fiscal year)
- **Quant Utility**: Value / Fundamental Factor Signals — `per`, `priceBV`, `deRatio`, `roa`, `roe`, `npm`, `eps`, `bookValue`, `assets`, `liabilities`, `equity`, `sales`.

---

### 10. News Search
- **Endpoint**: `/NewsAnnouncement/GetNewsSearch`
- **Method**: `GET`
- **Required Parameters**: `pageNumber=1&pageSize=100&locale=id-id`
- **Status**: 🟢 **200 OK**
- **Quant Utility**: Market News & Headlines.

---

## 🔴 DEPRECATED / LEGACY PATH MAPPING

The following legacy endpoints were replaced on the modern Nuxt.js frontend:

| Legacy Route | Modern Verified Route | Note |
|---|---|---|
| `/ListedCompany/GetCorporateAction` | `/ListingActivity/GetIssuedHistory` | Replaced on new IDX portal |
| `/NewsAnnouncement/GetAnnouncement` | `/NewsAnnouncement/GetAllAnnouncement` | Replaced on new IDX portal |
| `/DigitalStatistic/GetApiDataPaginated?urlName=LINK_SUMMARY_KEY_STATISTIC` | `/TradingSummary/GetStockSummary` | Derived directly from Stock Summary |
| `/DigitalStatistic/GetApiDataPaginated?urlName=LINK_MARKET_CAPITALIZATION` | `/TradingSummary/GetStockSummary` | Derived via `ListedShares * Close` |
