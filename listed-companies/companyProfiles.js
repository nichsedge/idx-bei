// companyProfiles.js
import { fetchData, clearCache, setRateLimit } from '../fetchUtil.js';

// Base URL for API endpoints
const BASE_URL = 'https://www.idx.co.id/primary';

// Default API options
const DEFAULT_OPTIONS = {
  // Common options for all API calls
};

// Default cache options - can be overridden per call
const DEFAULT_CACHE_OPTIONS = {
  useCache: true,
  ttl: 15 * 60 * 1000  // 15 minutes cache TTL
};

// Default retry options
const DEFAULT_RETRY_OPTIONS = {
  maxRetries: 3,
  baseDelay: 1000
};

/**
 * Set custom rate limits for API calls
 * @param {number} maxRequests - Maximum requests per window
 * @param {number} timeWindowMs - Time window in milliseconds
 */
export const configureRateLimit = (maxRequests = 5, timeWindowMs = 1000) => {
  setRateLimit({
    maxRequests,
    timeWindow: timeWindowMs
  });
};

/**
 * Clear the API response cache
 */
export const clearApiCache = () => {
  clearCache();
};

/**
 * Get all company profiles
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Company profiles data
 */
export const getCompanyProfiles = (options = {}, cacheOptions = {}) => {
  const url = `${BASE_URL}/ListedCompany/GetCompanyProfiles?start=0&length=9999`;
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions, ttl: 24 * 60 * 60 * 1000 }, // 24 hours cache for this endpoint
    DEFAULT_RETRY_OPTIONS
  );
};

/**
 * Get detail for a specific company
 * @param {string} kodeEmiten - Company code
 * @param {string} [language='id-id'] - Response language
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Company profile detail
 */
export const getCompanyProfileDetail = (
  kodeEmiten, 
  language = 'id-id',
  options = {},
  cacheOptions = {}
) => {
  if (!kodeEmiten) {
    throw new Error('Company code (kodeEmiten) is required');
  }
  
  const url = `${BASE_URL}/ListedCompany/GetCompanyProfilesDetail?KodeEmiten=${encodeURIComponent(kodeEmiten)}&language=${encodeURIComponent(language)}`;
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );
};

/**
 * Get company issued history
 * @param {string} kodeEmiten - Company code
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Issued history data
 */
export const getIssuedHistory = (
  kodeEmiten,
  options = {},
  cacheOptions = {}
) => {
  if (!kodeEmiten) {
    throw new Error('Company code (kodeEmiten) is required');
  }
  
  const url = `${BASE_URL}/ListingActivity/GetIssuedHistory?kodeEmiten=${encodeURIComponent(kodeEmiten)}&start=0&length=9999`;
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );
};

/**
 * Get company profile announcements
 * @param {string} kodeEmiten - Company code
 * @param {string} dateFrom - Start date (YYYY-MM-DD)
 * @param {string} dateTo - End date (YYYY-MM-DD)
 * @param {Object} pagination - Pagination parameters
 * @param {number} [pagination.indexFrom=0] - Start index
 * @param {number} [pagination.pageSize=10] - Page size
 * @param {string} [lang='en'] - Language
 * @param {string} [keyword=''] - Search keyword
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Announcement data
 */
export const getProfileAnnouncement = (
  kodeEmiten,
  dateFrom,
  dateTo,
  pagination = { indexFrom: 0, pageSize: 10 },
  lang = 'en',
  keyword = '',
  options = {},
  cacheOptions = {}
) => {
  if (!kodeEmiten) {
    throw new Error('Company code (kodeEmiten) is required');
  }
  
  if (!dateFrom || !dateTo) {
    throw new Error('Date range (dateFrom and dateTo) is required');
  }
  
  const url = `${BASE_URL}/ListedCompany/GetProfileAnnouncement?KodeEmiten=${encodeURIComponent(kodeEmiten)}` +
    `&indexFrom=${pagination.indexFrom}&pageSize=${pagination.pageSize}` +
    `&dateFrom=${encodeURIComponent(dateFrom)}&dateTo=${encodeURIComponent(dateTo)}` +
    `&lang=${encodeURIComponent(lang)}&keyword=${encodeURIComponent(keyword)}`;
    
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );
};

/**
 * Get calendar data
 * @param {string} range - Date range code
 * @param {string} date - Calendar date
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Calendar data
 */
export const getCalendar = (
  range,
  date,
  options = {},
  cacheOptions = {}
) => {
  if (!range || !date) {
    throw new Error('Range and date parameters are required');
  }
  
  const url = `${BASE_URL}/Home/GetCalendar?range=${encodeURIComponent(range)}&date=${encodeURIComponent(date)}`;
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );
};

/**
 * Get company financial report
 * @param {string} kodeEmiten - Company code
 * @param {string|number} year - Report year
 * @param {Object} params - Additional parameters
 * @param {string} [params.periode='audit'] - Report period
 * @param {number} [params.indexFrom=0] - Start index
 * @param {number} [params.pageSize=1000] - Page size
 * @param {string} [params.reportType='rdf'] - Report type
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Financial report data
 */
export const getFinancialReport = (
  kodeEmiten,
  year,
  params = { periode: 'audit', indexFrom: 0, pageSize: 1000, reportType: 'rdf' },
  options = {},
  cacheOptions = {}
) => {
  if (!kodeEmiten || !year) {
    throw new Error('Company code (kodeEmiten) and year are required');
  }
  
  const url = `${BASE_URL}/ListedCompany/GetFinancialReport` +
    `?periode=${encodeURIComponent(params.periode)}` +
    `&year=${encodeURIComponent(year)}` +
    `&indexFrom=${params.indexFrom}` +
    `&pageSize=${params.pageSize}` +
    `&reportType=${encodeURIComponent(params.reportType)}` +
    `&kodeEmiten=${encodeURIComponent(kodeEmiten)}`;
    
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );
};

/**
 * Get company name change history
 * @param {string} kodeEmiten - Company code
 * @param {string|number} year - Year
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Name change history data
 */
export const getNameChangeHistory = (
  kodeEmiten,
  year,
  options = {},
  cacheOptions = {}
) => {
  if (!kodeEmiten || !year) {
    throw new Error('Company code (kodeEmiten) and year are required');
  }
  
  const url = `${BASE_URL}/ListedCompany/GetPerubahanNamaHistory?KodeEmiten=${encodeURIComponent(kodeEmiten)}&Year=${encodeURIComponent(year)}`;
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions, ttl: 7 * 24 * 60 * 60 * 1000 }, // 7 days cache for historical data
    DEFAULT_RETRY_OPTIONS
  );
};

/**
 * Get company core business history
 * @param {string} kodeEmiten - Company code
 * @param {string|number} year - Year
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Core business history data
 */
export const getCoreBusinessHistory = (
  kodeEmiten,
  year,
  options = {},
  cacheOptions = {}
) => {
  if (!kodeEmiten || !year) {
    throw new Error('Company code (kodeEmiten) and year are required');
  }
  
  const url = `${BASE_URL}/ListedCompany/GetCoreBusinessHistory?KodeEmiten=${encodeURIComponent(kodeEmiten)}&Year=${encodeURIComponent(year)}`;
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions, ttl: 7 * 24 * 60 * 60 * 1000 }, // 7 days cache for historical data
    DEFAULT_RETRY_OPTIONS
  );
};

/**
 * Get shareholder history
 * @param {string} kodeEmiten - Company code
 * @param {string|number} year - Year
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Shareholder history data
 */
export const getShareholderHistory = (
  kodeEmiten,
  year,
  options = {},
  cacheOptions = {}
) => {
  if (!kodeEmiten || !year) {
    throw new Error('Company code (kodeEmiten) and year are required');
  }
  
  const url = `${BASE_URL}/ListedCompany/GetPemegangSahamHistory?KodeEmiten=${encodeURIComponent(kodeEmiten)}&Year=${encodeURIComponent(year)}`;
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );
};

/**
 * Get controlling shareholder history
 * @param {string} kodeEmiten - Company code
 * @param {string|number} year - Year
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Controlling shareholder history data
 */
export const getControllingShareholderHistory = (
  kodeEmiten,
  year,
  options = {},
  cacheOptions = {}
) => {
  if (!kodeEmiten || !year) {
    throw new Error('Company code (kodeEmiten) and year are required');
  }
  
  const url = `${BASE_URL}/ListedCompany/GetPemegangSahamPengendaliHistory?KodeEmiten=${encodeURIComponent(kodeEmiten)}&Year=${encodeURIComponent(year)}`;
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );
};

/**
 * Get cash dividend data
 * @param {string} kodeEmiten - Company code
 * @param {string|number} year - Year
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Cash dividend data
 */
export const getCashDividend = (
  kodeEmiten,
  year,
  options = {},
  cacheOptions = {}
) => {
  if (!kodeEmiten || !year) {
    throw new Error('Company code (kodeEmiten) and year are required');
  }
  
  const url = `${BASE_URL}/ListedCompany/GetDividenTunai?KodeEmiten=${encodeURIComponent(kodeEmiten)}&Year=${encodeURIComponent(year)}`;
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );
};

/**
 * Get stock dividend data
 * @param {string} kodeEmiten - Company code
 * @param {string|number} year - Year
 * @param {Object} options - Custom fetch options
 * @param {Object} cacheOptions - Custom cache options
 * @returns {Promise<Object>} - Stock dividend data
 */
export const getStockDividend = (
  kodeEmiten,
  year,
  options = {},
  cacheOptions = {}
) => {
  if (!kodeEmiten || !year) {
    throw new Error('Company code (kodeEmiten) and year are required');
  }
  
  const url = `${BASE_URL}/ListedCompany/GetDividenSaham?KodeEmiten=${encodeURIComponent(kodeEmiten)}&Year=${encodeURIComponent(year)}`;
  return fetchData(
    url, 
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );
};